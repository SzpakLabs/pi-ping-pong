import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

// Characterize unmodified native runner with a synthetic wire peer, never Pi/models.
const packageJson = process.env.PI_PACKAGE_JSON || path.join(os.homedir(), '.pi/agent/install/releases/1.3.0/node_modules/@earendil-works/pi-coding-agent/package.json');
const source = process.env.RALPH_RPC_SOURCE || path.join(os.homedir(), '.pi/agent/npm/node_modules/@lnilluv/pi-ralph-loop/src/runner-rpc.ts');
assert.equal(JSON.parse(fs.readFileSync(path.join(path.dirname(source), '../package.json'))).version, '2.1.0');
const { createJiti } = createRequire(packageJson)('jiti');
const { runRpcIteration } = await createJiti(import.meta.url).import(source);
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ppp-runtime-boundaries-'));
const peer = path.join(root, 'Test-peer.py');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, label) {
  const deadline = Date.now() + 5000;
  while (!check()) {
    assert.ok(Date.now() < deadline, label);
    await delay(10);
  }
}
function heartbeat(dir) {
  try { return Number(fs.readFileSync(path.join(dir, 'Test-heartbeat'), 'utf8')); }
  catch { return 0; }
}
fs.writeFileSync(peer, `import json,os,subprocess,sys,time
from pathlib import Path
mode,escape=sys.argv[1],sys.argv[2]=='escape'
child_code="""import time,os
from pathlib import Path
n=0
while not Path('Test-release').exists():
 n+=1
 p=Path('Test-heartbeat.pending');p.write_text(str(n));p.replace('Test-heartbeat')
 time.sleep(.01)
Path('Test-child-stopped').touch()
"""
child=subprocess.Popen([sys.executable,'-B','-c',child_code],start_new_session=escape,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
Path('Test-processes.json').write_text(json.dumps(dict(parent=os.getppid(),peer=os.getpid(),peer_group=os.getpgrp(),child=child.pid,child_group=os.getpgid(child.pid),escape=escape)))
while not Path('Test-heartbeat').exists(): time.sleep(.005)
def emit(x): print(json.dumps(x),flush=True)
for line in sys.stdin:
 command=json.loads(line)
 emit(dict(type='response',command=command['type'],success=True,id=command.get('id')))
 if command['type']=='prompt':
  emit(dict(type='Test-ready'))
  if mode=='normal': emit(dict(type='agent_end',messages=[dict(role='assistant',content=[dict(type='text',text='Test synthetic wire result')],usage=dict(input=10,output=2,totalTokens=12))]))
  else:
   while not Path('Test-release').exists(): time.sleep(.01)
if mode!='normal':
 while not Path('Test-release').exists(): time.sleep(.01)
Path('Test-peer-stopped').touch()
`);
let cases = 0;
try {
  for (const mode of ['normal', 'cancel', 'timeout']) {
    for (const escape of [false, true]) {
      const dir = path.join(root, `Test-${mode}-${escape}`);
      fs.mkdirSync(dir);
      const controller = new AbortController();
      const result = await runRpcIteration({
        prompt: 'Test wire only', cwd: dir, timeoutMs: 700,
        spawnCommand: process.env.PYTHON || 'python3', spawnArgs: ['-B', peer, mode, escape ? 'escape' : 'group'],
        provider: 'Test-provider', modelId: 'Test-model', thinkingLevel: 'low',
        signal: controller.signal,
        onEvent: event => { if (mode === 'cancel' && event.type === 'Test-ready') controller.abort(); },
      });
      const info = JSON.parse(fs.readFileSync(path.join(dir, 'Test-processes.json')));
      assert.equal(info.peer_group, info.peer, 'native runner actually detaches peer');
      assert.equal(info.child_group === info.peer_group, !escape);
      assert.equal(Boolean(result.cancelled), mode === 'cancel');
      assert.equal(Boolean(result.timedOut), mode === 'timeout');
      assert.equal(result.success, mode === 'normal');
      if (mode === 'normal') assert.equal(result.agentEndMessages[0].usage.totalTokens, 12);
      await delay(80);
      const before = heartbeat(dir);
      await delay(100);
      assert.equal(heartbeat(dir) > before, escape, 'only escaped descendant survives native cleanup');
      fs.writeFileSync(path.join(dir, 'Test-release'), 'Test cooperative cleanup');
      if (escape) await until(() => fs.existsSync(path.join(dir, 'Test-child-stopped')), 'escaped child stopped');
      console.log(`native runner ${mode}: ${escape ? 'escaped child SURVIVES (outside guarantee)' : 'same-group child stopped'}`);
      cases++;
    }
  }

  // The runner owner itself disappears; detached peers cannot rely on its timeout.
  for (const escape of [false, true]) {
    const dir = path.join(root, `Test-owner-crash-${escape}`);
    fs.mkdirSync(dir);
    const code = `import {createRequire} from 'node:module';
      const {createJiti}=createRequire(${JSON.stringify(packageJson)})('jiti');
      const {runRpcIteration}=await createJiti(import.meta.url).import(${JSON.stringify(source)});
      await runRpcIteration({prompt:'Test no model',cwd:${JSON.stringify(dir)},timeoutMs:30000,
        spawnCommand:${JSON.stringify(process.env.PYTHON || 'python3')},spawnArgs:['-B',${JSON.stringify(peer)},'hold',${JSON.stringify(escape ? 'escape' : 'group')}]});`;
    const owner = spawn(process.execPath, ['--input-type=module', '-e', code], { stdio: ['ignore', 'ignore', 'pipe'] });
    let diagnostic = '';
    owner.stderr.on('data', x => { diagnostic += x; });
    try {
      await until(() => heartbeat(dir) > 0, 'owned native runner ready: ' + diagnostic);
      const closed = new Promise(resolve => owner.once('close', resolve));
      assert.equal(owner.kill('SIGKILL'), true); // Fresh directly owned process handle only.
      await closed;
      const before = heartbeat(dir);
      await delay(100);
      assert.ok(heartbeat(dir) > before, 'descendant outlives runner owner crash');
      fs.writeFileSync(path.join(dir, 'Test-release'), 'Test cooperative cleanup');
      await until(() => fs.existsSync(path.join(dir, 'Test-peer-stopped')) && fs.existsSync(path.join(dir, 'Test-child-stopped')), 'orphan fixture stopped');
      console.log(`native runner owner crash: peer + ${escape ? 'escaped' : 'same-group'} descendant SURVIVE`);
      cases++;
    } finally {
      fs.writeFileSync(path.join(dir, 'Test-release'), 'Test cleanup');
      if (owner.exitCode === null && owner.signalCode === null) owner.kill('SIGKILL');
    }
  }
  const ai = path.resolve(path.dirname(packageJson), '../pi-ai/dist');
  const { processResponsesStream } = await import(pathToFileURL(path.join(ai, 'api/openai-responses-shared.js')).href);
  const catalog = JSON.parse(fs.readFileSync(path.join(ai, 'providers/data/openai.json')));
  for (const id of ['gpt-6-luna', 'gpt-6.1-sol']) {
    const model = catalog['openai-responses']['chat:' + id];
    async function measure(pricedModel) {
      const output = { content: [], usage: {}, stopReason: 'stop' };
      async function* events() {
        yield { type: 'response.completed', response: { id: 'Test-response', status: 'completed', output: [], usage: { input_tokens: 100, input_tokens_details: { cached_tokens: 20, cache_write_tokens: 10 }, output_tokens: 8, output_tokens_details: { reasoning_tokens: 3 }, total_tokens: 108 } } };
      }
      await processResponsesStream(events(), output, { push() {} }, pricedModel);
      return output;
    }
    const observed = await measure(model);
    assert.equal(observed.responseId, 'Test-response');
    for (const [key, value] of Object.entries({ input: 70, output: 8, cacheRead: 20, cacheWrite: 10, reasoning: 3, totalTokens: 108 })) assert.equal(observed.usage[key], value);
    const changed = structuredClone(model);
    for (const key of ['input', 'output', 'cacheRead', 'cacheWrite']) changed.cost[key] *= 2;
    assert.equal((await measure(changed)).usage.cost.total, observed.usage.cost.total * 2);
  }
  console.log('Metering parser: 2 selected models PASS; synthetic provider usage; local price change doubles estimated cost, not tokens');
  console.log(`Native runner characterization: ${cases} PASS; synthetic wire peer, zero model calls; source SHA256 ${createHash('sha256').update(fs.readFileSync(source)).digest('hex')}`);
} finally {
  for (const dir of fs.readdirSync(root, { withFileTypes: true }).filter(x => x.isDirectory())) {
    fs.writeFileSync(path.join(root, dir.name, 'Test-release'), 'Test final cleanup');
  }
  await delay(100);
  fs.rmSync(root, { recursive: true, force: true });
}
