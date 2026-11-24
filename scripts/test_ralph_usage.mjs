import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const self = fileURLToPath(import.meta.url);
const args = ['--mode', 'rpc', '--no-session'];
const secret = 'Test content must never enter usage records 🌿';
const message = (totalTokens, responseId) => ({ role: 'assistant', responseId, usage: { totalTokens }, content: secret });
const first = message(7, 'Test-response-id');
const wire = Buffer.from([
  { type: 'message_end', message: first },
  { type: 'message_end', message: first }, // Duplicate response id.
  { type: 'agent_end', messages: [first], willRetry: true },
  { type: 'message_update', message: message(500) },
  { type: 'message_end', message: message('500') },
  { type: 'message_end', message: message(-1) },
  { type: 'message_end', message: { role: 'assistant' } },
  { type: 'message_end', message: { ...message(500), content: secret.repeat(30000) } },
  { type: 'message_end', message: message(5) },
  { type: 'agent_end', messages: [first, message(5)] },
].map(x => JSON.stringify(x)).join('\r\n') + '\nnot JSON\n{"type":"message_end"');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const usageFile = () => path.join(process.env.PPP_RALPH_GUARDS, 'usage.json');

if (process.argv.includes('--mode')) {
  const split = wire.indexOf(Buffer.from('🌿')) + 1;
  process.stdout.write(wire.subarray(0, split));
  await delay(25);
  process.stdout.write(wire.subarray(split));
} else if (process.argv.includes('--wire-host')) {
  async function runChild(taskDir, loopToken) {
    const child = spawn(process.execPath, [self, ...args], {
      cwd: process.cwd(), detached: true, stdio: ['ignore', 'pipe', 'inherit'],
      env: { ...process.env, RALPH_RUNNER_LOOP_TOKEN: loopToken, RALPH_RUNNER_CWD: process.cwd(), RALPH_RUNNER_TASK_DIR: taskDir },
    });
    const closed = once(child, 'close');
    assert.equal(child.stdout.readableFlowing, null, 'observer does not start reading');
    assert.equal(child.stdout.listenerCount('data'), 0, 'observer adds no flowing listener');
    child.stdout.pause();
    const chunks = [];
    child.stdout.on('data', chunk => chunks.push(chunk));
    await delay(100); // Large frame cannot push through a paused pipe.
    assert.deepEqual(chunks, []);
    child.stdout.resume();
    assert.deepEqual(await closed, [0, null]);
    assert.deepEqual(Buffer.concat(chunks), wire, 'all bytes and frame boundaries survive backpressure');
  }
  const taskDir = process.env.PPP_RALPH_USAGE_TASK_DIR;
  await runChild(process.cwd(), 'Test-wrong-task');
  assert.equal(fs.existsSync(usageFile()), false);
  await runChild(taskDir, 'Test-loop');
  await runChild(taskDir, 'Test-other-loop');
  await runChild(taskDir, 'Test-loop');
  assert.equal(read(usageFile()).tokens, 24);
  process.kill(process.pid, 'SIGKILL'); // Already published high-water survives without host cleanup.
} else if (process.argv.includes('--native-host')) {
  const packageJson = process.env.PI_PACKAGE_JSON;
  const source = process.env.RALPH_RUNNER_SOURCE || path.join(os.homedir(), '.pi/agent/npm/node_modules/@lnilluv/pi-ralph-loop/src/runner.ts');
  const { createJiti } = createRequire(packageJson)('jiti');
  const packageDir = path.dirname(packageJson);
  const pi = path.join(packageDir, read(packageJson).exports['.'].import);
  const { runRalphLoop } = await createJiti(import.meta.url, { alias: { '@earendil-works/pi-coding-agent': pi } }).import(source);
  const taskDir = process.env.PPP_RALPH_USAGE_TASK_DIR;
  const ralphPath = path.join(taskDir, 'RALPH.md');
  fs.writeFileSync(ralphPath, '---\nmax_iterations: 2\ntimeout: 15\n---\nTest synthetic provider.\n');
  const cli = path.join(packageDir, read(packageJson).bin.pi);
  const provider = path.join(process.cwd(), 'Test-provider.ts');
  fs.writeFileSync(provider, `import { createAssistantMessageEventStream } from '@earendil-works/pi-ai';
export default function(pi) {
  pi.registerProvider('Test-meter', {
    baseUrl: 'http://127.0.0.1:1', api: 'Test-memory', apiKey: 'Test-not-a-credential',
    models: [{type:'chat',id:'Test-model',name:'Test model',reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:100000,maxTokens:1024}],
    streamSimple(model) {
      const stream = createAssistantMessageEventStream();
      const message = { role:'assistant', content:[{type:'text',text:${JSON.stringify(secret)}}], api:model.api, provider:model.provider, model:model.id,
        usage:{input:7,output:3,cacheRead:2,cacheWrite:0,totalTokens:12,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},stopReason:'stop',timestamp:Date.now() };
      queueMicrotask(() => { stream.push({type:'start',partial:message}); stream.push({type:'done',reason:'stop',message}); stream.end(); });
      return stream;
    },
  });
}
`);
  const result = await runRalphLoop({ ralphPath, cwd: process.cwd(), maxIterations: 2, timeout: 15, guardrails: [],
    provider: 'Test-meter', modelId: 'Test-model', spawnCommand: process.execPath,
    spawnArgs: [cli, ...args, '--no-extensions', '--no-skills', '--no-prompt-templates', '-e', provider] });
  assert.ok(['max-iterations', 'no-progress-exhaustion'].includes(result.status), JSON.stringify(result.iterations));
  assert.deepEqual(result.iterations.map(iteration => iteration.status), ['complete', 'complete']);
  const status = read(path.join(taskDir, '.ralph-runner/status.json'));
  assert.equal(read(usageFile()).loop_token, status.loopToken);
  assert.equal(read(usageFile()).tokens, 24, 'real Pi message_end across two native Ralph iterations');
} else {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'ppp-ralph-usage-')));
  const guard = new URL('./ralph-parent-guard.mjs', import.meta.url).href;
  const modes = process.env.PI_PACKAGE_JSON ? ['wire', 'native'] : ['wire'];
  try {
    for (const mode of modes) {
      const cwd = path.join(root, mode);
      const task = path.join(cwd, 'Test task');
      const directory = path.join(cwd, '.ralph-runner/ppp-guards');
      fs.mkdirSync(task, { recursive: true });
      fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
      const host = spawn(process.execPath, [self, `--${mode}-host`], { cwd, stdio: 'inherit', env: {
        HOME: os.homedir(), PATH: process.env.PATH, PI_PACKAGE_JSON: process.env.PI_PACKAGE_JSON,
        RALPH_RUNNER_SOURCE: process.env.RALPH_RUNNER_SOURCE, PI_CODING_AGENT_DIR: path.join(cwd, 'Test-agent'), PI_OFFLINE: '1',
        NODE_OPTIONS: `--import=${guard}`, PPP_RALPH_GUARD_IMPORT: `--import=${guard}`, PPP_RALPH_GUARDS: directory,
        PPP_RALPH_USAGE_DISPATCH: 'Test-dispatch', PPP_RALPH_USAGE_TASK_DIR: task,
      } });
      assert.deepEqual(await once(host, 'close'), mode === 'wire' ? [null, 'SIGKILL'] : [0, null]);
      const file = path.join(directory, 'usage.json');
      const record = read(file);
      assert.deepEqual(record, { dispatch: 'Test-dispatch', host: host.pid, loop_token: mode === 'wire' ? 'Test-loop' : record.loop_token, tokens: 24 });
      assert.equal(fs.statSync(file).mode & 0o777, 0o600);
      assert.equal(fs.readdirSync(directory).some(name => name.endsWith('.tmp')), false);
      console.log(`Ralph usage ${mode}: PASS (zero model calls)`);
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}
