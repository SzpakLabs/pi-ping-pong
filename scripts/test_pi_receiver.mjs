import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const packageJson = process.env.PI_PACKAGE_JSON || path.join(os.homedir(), '.pi/agent/install/releases/1.3.0/node_modules/@earendil-works/pi-coding-agent/package.json');
const require = createRequire(packageJson);
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url);
const module = await jiti.import(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../extensions/pi-reviewed.ts'));
const extension = module.default ?? module;
const packageRoot = path.dirname(packageJson);
const { loadExtensions } = await import(pathToFileURL(path.join(packageRoot, 'dist/core/extensions/loader.js')).href);
const { ExtensionRunner } = await import(pathToFileURL(path.join(packageRoot, 'dist/core/extensions/runner.js')).href);
const receiverPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../extensions/pi-reviewed.ts');
const loaded = await loadExtensions([receiverPath], process.cwd());
assert.deepEqual(loaded.errors, [], 'real Pi loader must accept the receiver before runtime initialization');
assert.equal(loaded.extensions.length, 1);
assert.throws(() => loaded.runtime.getCommands(), /not initialized/, 'loader smoke test must use an unbound runtime');
for (const name of ['pi-ping-pong', 'reviewed-run', 'ppp', 'pi-ping-pong-status', 'reviewed-status', 'ppp-status']) {
  assert.ok(loaded.extensions[0].commands.has(name), `${name} must register during real extension loading`);
}
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pi-ping-pong-test-'));
const projectPath = path.join(root, 'project');
const childMarker = path.join(root, 'fake-child-started');
const fakeBridge = path.join(root, 'fake-bridge.py');
fs.mkdirSync(projectPath, { mode: 0o700 });
execFileSync('git', ['init', '--quiet', projectPath]);
const project = fs.realpathSync(projectPath);
fs.writeFileSync(path.join(project, '.gitignore'), '.pi-ping-pong/\n');
fs.writeFileSync(fakeBridge, `from pathlib import Path\nPath(${JSON.stringify(childMarker)}).write_text('spawned')\n`);
const previousBridge = process.env.PI_PING_PONG_BRIDGE;
const previousHome = process.env.HOME;
process.env.PI_PING_PONG_BRIDGE = fakeBridge;
process.env.HOME = root;
const storage = path.join(project, '.pi-ping-pong', 'runs');
const chmodPrivate = file => fs.chmodSync(file, 0o600);
const write = (file, data, mode = 0o600) => {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  fs.writeFileSync(file, typeof data === 'string' ? data : JSON.stringify(data), { mode });
  chmodPrivate(file);
};
const tempConfig = (dir, runId = randomUUID()) => ({
  run_id: runId,
  mode: 'ralph',
  worker_provider: 'test-worker-provider',
  worker_model: 'test-worker-model',
  review_provider: 'test-review-provider',
  review_model: 'test-review-model',
  review_transport: 'pi',
  task: 'TASK.md',
  eval_argv: ['python3', path.join(dir, 'eval.py')],
  max_cycles: 3,
  cycle_seconds: 60,
  review_seconds: 120,
  wall_seconds: 600,
});
const makeRun = (name, { config = tempConfig(path.join(storage, name)), status, files = {}, malformedConfig = false, launched = status !== undefined } = {}) => {
  const dir = path.join(storage, name);
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  fs.chmodSync(dir, 0o700);
  for (const [file, content] of Object.entries(files)) write(path.join(dir, file), content);
  if (malformedConfig) write(path.join(dir, 'config.json'), '{bad json');
  else if (config) write(path.join(dir, 'config.json'), config);
  if (launched) {
    write(path.join(dir, 'launch-attempt.json'), { session_id: 'Test-session', at: 1 });
    if (status) write(path.join(dir, 'bridge-status.json'), { run_id: config.run_id, status, cycle: 1 });
  }
  return dir;
};
const makeReadyRun = (name, runId = randomUUID()) => {
  const dir = makeRun(name, { config: null, launched: false });
  write(path.join(dir, 'TASK.md'), 'Synthetic task criteria; no real user run.');
  write(path.join(dir, 'eval.py'), 'raise SystemExit(1)  # deterministic fixture; never executed');
  write(path.join(dir, 'config.json'), tempConfig(dir, runId));
  return dir;
};
const hooks = new Map(), commands = new Map(), messages = [], userMessages = [], entries = [], notices = [], selectCalls = [];
const selectAnswers = [], inputAnswers = [], confirmAnswers = [];
const statusValues = new Map();
const entry = { type: 'custom', customType: 'pi-reviewed-run', data: { root: path.join(root, 'legacy-run'), runId: 'Test-run', sessionId: 'Test-session' } };
const ctx = {
  model: { id: 'test-review-model', provider: 'test-review-provider' }, cwd: project, mode: 'tui', hasUI: true,
  isIdle: () => true,
  sessionManager: { getSessionId: () => 'Test-session', getEntries: () => [entry] },
  ui: {
    notify: (...args) => notices.push(args),
    setStatus: (key, value) => { if (value === undefined) statusValues.delete(key); else statusValues.set(key, value); },
    select: async (title, options) => { selectCalls.push({ title, options }); const answer = selectAnswers.shift(); return typeof answer === 'function' ? answer(title, options) : answer; },
    input: async (title, placeholder) => { const answer = inputAnswers.shift(); return typeof answer === 'function' ? answer(title, placeholder) : answer; },
    confirm: async (title, message) => { const answer = confirmAnswers.shift(); return typeof answer === 'function' ? answer(title, message) : (answer ?? false); },
  },
};
const pi = {
  on: (name, handler) => hooks.set(name, handler),
  registerCommand: (name, command) => commands.set(name, command),
  getCommands: () => { throw new Error('Extension runtime not initialized'); },
  sendMessage: (message, options) => messages.push({ message, options }),
  sendUserMessage: (message, options) => userMessages.push({ message, options }),
  appendEntry: (...args) => entries.push(args),
};
extension(pi);
const runCommand = (name, args = '') => commands.get(name).handler(args, ctx);
const waitForChild = async () => {
  for (let attempt = 0; attempt < 50 && !fs.existsSync(childMarker); attempt++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(fs.existsSync(childMarker), true, 'only an explicit launch should start the synthetic fake bridge');
  fs.rmSync(childMarker, { force: true });
};
try {
  for (const alias of ['reviewed-run', 'ppp']) assert.strictEqual(commands.get(alias).handler, commands.get('pi-ping-pong').handler, `${alias} must use the same launcher/menu handler`);
  for (const alias of ['reviewed-status', 'ppp-status']) assert.strictEqual(commands.get(alias).handler, commands.get('pi-ping-pong-status').handler, `${alias} must use the same status handler`);

  const beforeEmpty = userMessages.length;
  inputAnswers.push('add-linters');
  await runCommand('pi-ping-pong');
  const draft = path.join(storage, 'add-linters');
  assert.equal(userMessages.length, beforeEmpty + 1, 'empty project menu starts preparation through the current model');
  assert.equal(fs.statSync(draft).mode & 0o777, 0o700, 'run reservation directory is private');
  assert.equal(fs.statSync(path.join(draft, '.draft.json')).mode & 0o777, 0o600, 'draft reservation metadata is private');
  assert.equal(fs.existsSync(path.join(draft, 'config.json')), false, 'reservation never creates a config placeholder');
  assert.equal(fs.existsSync(path.join(draft, 'launch-attempt.json')), false, 'preparation does not create launch state');
  assert.equal(entries.length, 0, 'preparation does not attach a run to the Pi session');
  const prompt = userMessages.at(-1).message;
  for (const required of [project, 'Selected run name: add-linters', draft, 'unique RFC 4122 UUID run_id', 'UUID is for run_id only', 'worker_model to gpt-6-luna', 'thinking to low', 'max_cycles to 10', 'do not ask the user to confirm them', 'test-review-provider/test-review-model', 'use it without confirmation unless no model is selected', 'positive finite integer', 'independent task-specific', 'Do not start or launch the worker', 'Do not write pi_session_id', 'do not overwrite .draft.json', '/pi-ping-pong add-linters']) {
    assert.ok(prompt.includes(required), `preparation prompt must include ${required}`);
  }
  assert.equal(fs.existsSync(childMarker), false, 'preparation never spawns a worker');

  const oneLineTask = 'analyze changes in src/index.ts, suggest commit names, list files, and wait for approval';
  const generatedName = `${oneLineTask.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 39).replace(/-+$/g, '')}-${createHash('sha256').update(oneLineTask).digest('hex').slice(0, 8)}`;
  const beforeOneLineCommand = userMessages.length;
  await runCommand('ppp', oneLineTask);
  assert.equal(userMessages.length, beforeOneLineCommand + 1, 'task-only command starts preparation');
  assert.ok(userMessages.at(-1).message.includes(`Task requested in the command: ${oneLineTask}`), 'task text is passed into preparation');
  assert.ok(fs.existsSync(path.join(storage, generatedName, '.draft.json')), 'task content determines its automatic run name');
  await runCommand('ppp', 'analyze the bugreport');
  const bugreportRun = fs.readdirSync(storage).find(name => name.startsWith('analyze-the-bugreport-'));
  assert.ok(bugreportRun && bugreportRun !== generatedName, 'distinct tasks sharing the same first word receive distinct names');
  const beforeDuplicateTask = userMessages.length;
  await runCommand('ppp', oneLineTask);
  assert.equal(userMessages.length, beforeDuplicateTask, 'repeating identical task does not prepare or launch the existing run');
  assert.match(String(notices.at(-1)[0]), /was not relaunched/, 'duplicate task reports the existing run without launching it');
  assert.equal(fs.existsSync(childMarker), false, 'task preparation and duplicate detection never launch a worker');

  write(path.join(draft, 'TASK.md'), 'Synthetic partial task content; preserve it.', 0o600);
  const partialBefore = fs.readFileSync(path.join(draft, 'TASK.md'), 'utf8');
  const promptCount = userMessages.length;
  selectAnswers.push('Back');
  await runCommand('pi-ping-pong', 'add-linters');
  assert.equal(userMessages.length, promptCount, 'repeated incomplete name offers continuation but cancellation does nothing');
  selectAnswers.push('Continue preparation');
  await runCommand('reviewed-run', 'add-linters');
  assert.equal(userMessages.length, promptCount + 1, 'explicit continuation uses prompt-based preparation');
  assert.ok(userMessages.at(-1).message.includes('TASK.md'), 'continuation lists existing files for model context');
  assert.ok(userMessages.at(-1).message.includes('Do not overwrite existing files blindly'));
  assert.equal(fs.readFileSync(path.join(draft, 'TASK.md'), 'utf8'), partialBefore, 'continuation never overwrites an existing file itself');
  assert.equal(fs.existsSync(path.join(draft, 'launch-attempt.json')), false);

  const beforeCancel = fs.existsSync(path.join(storage, 'cancelled-run'));
  selectAnswers.push(undefined);
  const callsBeforeCancel = userMessages.length;
  await runCommand('ppp');
  assert.equal(fs.existsSync(path.join(storage, 'cancelled-run')), beforeCancel, 'menu cancellation has no filesystem side effects');
  assert.equal(userMessages.length, callsBeforeCancel, 'menu cancellation does not call a model');

  const raceBefore = userMessages.length;
  await Promise.all([runCommand('pi-ping-pong', 'race-run'), runCommand('ppp', 'race-run')]);
  assert.equal(fs.existsSync(path.join(storage, 'race-run', '.draft.json')), true, 'race reserves exactly one directory');
  assert.equal(userMessages.length, raceBefore + 1, 'same-name race starts at most one preparation');
  assert.equal(fs.existsSync(path.join(storage, 'race-run-2')), false, 'race never silently adds a suffix');

  const raceTarget = path.join(storage, 'race-window');
  const raceBin = path.join(root, 'race-bin');
  fs.mkdirSync(raceBin, { mode: 0o700 });
  const realGit = execFileSync('which', ['git'], { encoding: 'utf8' }).trim();
  const raceCounter = path.join(root, 'race-git-count');
  const raceWrapper = path.join(raceBin, 'git');
  fs.writeFileSync(raceWrapper, `#!/bin/sh\nif [ "$3" = "check-ignore" ]; then\n  count=0\n  [ -f "$PPP_RACE_COUNTER" ] && count=$(cat "$PPP_RACE_COUNTER")\n  count=$((count + 1))\n  printf '%s' "$count" > "$PPP_RACE_COUNTER"\n  if [ "$count" -eq 2 ]; then\n    mkdir -p "$PPP_RACE_TARGET"\n    chmod 700 "$PPP_RACE_DIR" "$PPP_RACE_PARENT" "$PPP_RACE_TARGET"\n    printf 'created by competing process' > "$PPP_RACE_TARGET/.draft.json"\n    chmod 600 "$PPP_RACE_TARGET/.draft.json"\n  fi\nfi\nexec "$PPP_REAL_GIT" "$@"\n`);
  fs.chmodSync(raceWrapper, 0o700);
  process.env.PPP_RACE_COUNTER = raceCounter;
  process.env.PPP_RACE_TARGET = raceTarget;
  process.env.PPP_RACE_DIR = path.join(project, '.pi-ping-pong');
  process.env.PPP_RACE_PARENT = storage;
  process.env.PPP_REAL_GIT = realGit;
  const previousPath = process.env.PATH;
  process.env.PATH = `${raceBin}${path.delimiter}${previousPath ?? ''}`;
  const raceModelCalls = userMessages.length;
  await runCommand('pi-ping-pong', 'race-window');
  assert.equal(userMessages.length, raceModelCalls, 'exclusive create race does not start a second preparation');
  assert.equal(fs.readFileSync(path.join(raceTarget, '.draft.json'), 'utf8'), 'created by competing process', 'exclusive run reservation never overwrites a concurrent directory');
  process.env.PATH = previousPath;
  for (const key of ['PPP_RACE_COUNTER', 'PPP_RACE_TARGET', 'PPP_RACE_DIR', 'PPP_RACE_PARENT', 'PPP_REAL_GIT']) delete process.env[key];

  for (const taskText of ['.hidden', 'Bad-Name', 'bad_name', 'a'.repeat(49), '../escape']) {
    const before = userMessages.length;
    await runCommand('pi-ping-pong', taskText);
    assert.equal(userMessages.length, before + 1, `non-kebab input ${taskText} is task content`);
    assert.equal(fs.existsSync(path.join(project, 'escape')), false, 'task text must never become an unsanitized run path');
  }
  await assert.rejects(runCommand('pi-ping-pong', 'missing/config.json'), /Config not found/);
  await assert.rejects(runCommand('pi-ping-pong', path.join(root, 'missing-absolute', 'config.json')), /Config not found/);
  assert.equal(fs.existsSync(path.join(storage, 'missing')), false, 'nonexistent explicit paths are not treated as names');

  const emptyProject = path.join(root, 'empty-project');
  fs.mkdirSync(emptyProject, { mode: 0o700 });
  execFileSync('git', ['init', '--quiet', emptyProject]);
  fs.writeFileSync(path.join(emptyProject, '.gitignore'), '.pi-ping-pong/\n');
  const originalCwd = ctx.cwd;
  ctx.cwd = emptyProject;
  inputAnswers.push(undefined);
  const beforeEmptyCancel = fs.readdirSync(emptyProject).sort();
  await runCommand('pi-ping-pong');
  assert.deepEqual(fs.readdirSync(emptyProject).sort(), beforeEmptyCancel, 'cancelling the new-run name prompt has no side effects');
  ctx.cwd = originalCwd;

  const nonGit = path.join(root, 'confirmed-project');
  fs.mkdirSync(nonGit, { mode: 0o700 });
  ctx.cwd = nonGit;
  confirmAnswers.push(true);
  await runCommand('ppp', 'confirmed-run');
  assert.ok(fs.existsSync(path.join(nonGit, '.pi-ping-pong', 'runs', 'confirmed-run', '.draft.json')), 'non-Git project is used only after explicit folder confirmation');
  const fallbackHome = path.join(root, 'fallback-home');
  fs.mkdirSync(fallbackHome, { mode: 0o700 });
  process.env.HOME = fallbackHome;
  const fallbackCwd = path.join(root, 'unconfirmed-folder');
  fs.mkdirSync(fallbackCwd, { mode: 0o700 });
  ctx.cwd = fallbackCwd;
  confirmAnswers.push(false, true);
  await runCommand('pi-ping-pong', 'fallback-run');
  assert.ok(fs.existsSync(path.join(fallbackHome, '.pi', 'reviewed-runs', 'named', 'fallback-run', '.draft.json')), 'explicit fallback confirmation uses a separate private named store');
  ctx.cwd = originalCwd;
  const nestedCwd = path.join(project, 'nested', 'working-directory');
  fs.mkdirSync(nestedCwd, { recursive: true, mode: 0o700 });
  ctx.cwd = nestedCwd;
  await runCommand('pi-ping-pong', 'root-from-git');
  assert.ok(fs.existsSync(path.join(storage, 'root-from-git', '.draft.json')), 'Git top-level, not cwd subdirectory, determines project storage');
  assert.equal(fs.existsSync(path.join(nestedCwd, '.pi-ping-pong')), false);
  ctx.cwd = originalCwd;

  const readyDir = makeReadyRun('test-ready-menu');
  const readyInfoText = `test-ready-menu — ready to launch — ralph — test-worker-provider/test-worker-model`;
  const modelCallsBeforeMenu = userMessages.length;
  selectAnswers.push((_title, options) => options.find(option => option.startsWith('test-ready-menu')), 'Back');
  await runCommand('pi-ping-pong');
  assert.equal(fs.existsSync(path.join(readyDir, 'launch-attempt.json')), false, 'choosing a menu row only shows details; it does not launch');
  assert.equal(userMessages.length, modelCallsBeforeMenu, 'run menu is local and does not call a model');
  assert.ok(selectCalls.some(call => call.options.some(option => option.includes(readyInfoText))), `menu lists ready run name, state, mode and worker: ${JSON.stringify({ selectCalls, notices })}`);

  const stoppedPrefix = makeRun('test-prefix', { status: 'attention_required' });
  const readyPrefix = makeReadyRun('test-prefix-2');
  const noticeStart = notices.length;
  selectAnswers.push((_title, options) => options.find(option => option.startsWith('test-prefix-2 —')), 'Back');
  await runCommand('ppp');
  const selectedNotices = notices.slice(noticeStart).map(notice => notice[0]);
  assert.ok(selectedNotices.some(text => text.includes(`Directory: ${readyPrefix}`) && text.startsWith('test-prefix-2: ready to launch')), 'selecting the longer name must not inspect the stopped prefix run');
  assert.equal(selectedNotices.some(text => text.includes(`Directory: ${stoppedPrefix}\n`)), false);
  assert.ok(selectedNotices.some(text => text.includes('Limits: cycles=3, cycle_seconds=60, review_seconds=120, wall_seconds=600')), 'numeric limits must be visible in run details');
  assert.equal(fs.existsSync(path.join(readyPrefix, 'launch-attempt.json')), false, 'inspection does not launch the ready run');
  const stoppedNoticeStart = notices.length;
  await runCommand('ppp', 'test-prefix');
  assert.ok(notices.slice(stoppedNoticeStart).some(notice => notice[0].startsWith('test-prefix: attention required')), 'explicit old name shows only its own stopped status');
  assert.equal(fs.existsSync(childMarker), false, 'inspecting a stopped run never starts a worker');

  const menuCreatedBefore = userMessages.length;
  selectAnswers.push('＋ Create a new run');
  inputAnswers.push('menu-run');
  await runCommand('pi-ping-pong');
  assert.equal(userMessages.length, menuCreatedBefore + 1, 'menu Create new starts preparation but never launches');
  assert.ok(fs.existsSync(path.join(storage, 'menu-run', '.draft.json')));
  assert.equal(fs.existsSync(path.join(storage, 'menu-run', 'launch-attempt.json')), false);

  const providerRun = makeReadyRun('provider-check-run');
  ctx.model.provider = 'different-provider';
  await assert.rejects(runCommand('pi-ping-pong', 'provider-check-run'), /Select reviewer provider test-review-provider/);
  assert.equal(fs.existsSync(path.join(providerRun, 'launch-attempt.json')), false, 'provider mismatch must refuse launch before recording an attempt');
  ctx.model.provider = 'test-review-provider';

  const launchedDir = makeRun('test-started', { config: tempConfig(path.join(storage, 'test-started')), launched: true });
  const noStatusAttempt = userMessages.length;
  await runCommand('pi-ping-pong', 'test-started');
  assert.equal(userMessages.length, noStatusAttempt, 'previously launched run shows status without preparation');
  assert.equal(fs.existsSync(path.join(launchedDir, 'bridge-status.json')), false, 'missing bridge status is not permission to relaunch');
  assert.ok(notices.at(-1)[0].includes('attention required'));

  const statusRuns = [
    ['test-running', 'running'], ['test-starting', 'starting'], ['test-wait-review', 'waiting_pi'], ['test-wait-human', 'waiting_human'],
    ['test-completed', 'complete'], ['test-stopped', 'stopped'], ['test-attention', 'attention_required'],
  ];
  for (const [name, state] of statusRuns) makeRun(name, { status: state });
  makeRun('test-malformed', { malformedConfig: true, launched: false });
  makeRun('test-incomplete', { config: null, launched: false });
  makeRun('test-bound-no-status', { config: { ...tempConfig(path.join(storage, 'test-bound-no-status')), pi_session_id: 'Test-session' }, launched: false });
  const duplicateId = randomUUID();
  const duplicateA = path.join(storage, 'duplicate-a');
  const duplicateB = path.join(storage, 'duplicate-b');
  makeRun('duplicate-a', { config: tempConfig(duplicateA, duplicateId), status: 'running' });
  makeRun('duplicate-b', { config: tempConfig(duplicateB, duplicateId), status: 'running' });
  const missingIdentity = makeRun('test-missing-config-identity', { config: null, launched: true });
  write(path.join(missingIdentity, 'bridge-status.json'), { status: 'running', phase: 'evaluating', cycle: 1 });
  const legacyExternal = makeRun('test-legacy-external', { config: tempConfig(path.join(storage, 'test-legacy-external'), 'Test-legacy-run'), status: 'waiting_human' });
  write(path.join(legacyExternal, 'bridge-status.json'), { run_id: 'Test-legacy-run', status: 'waiting_human', cycle: 2, max_cycles: 3, started_at: 100, updated_at: 110, reason: 'Test input required' });
  const emptyIdentity = makeRun('test-empty-identity', { config: { ...tempConfig(path.join(storage, 'test-empty-identity')), run_id: '' }, status: 'running' });
  write(path.join(emptyIdentity, 'bridge-status.json'), { run_id: '', status: 'running', phase: 'working', cycle: 2, reason: 'Test invalid identity' });
  const malformedIdentity = makeRun('test-malformed-identity', { config: { ...tempConfig(path.join(storage, 'test-malformed-identity')), run_id: 'Test/bad' }, status: 'running' });
  write(path.join(malformedIdentity, 'bridge-status.json'), { run_id: 'Test/bad', status: 'running', phase: 'working', cycle: 2 });
  const beforeStatus = userMessages.length;
  await runCommand('pi-ping-pong-status');
  const statusText = notices.at(-1)[0];
  for (const fragment of ['test-running: running', 'test-starting: starting', 'test-wait-review: waiting review', 'test-wait-human: waiting human', 'test-completed: completed', 'test-stopped: stopped', 'test-attention: attention required', 'test-malformed: unknown/malformed', 'test-incomplete: draft/incomplete', 'test-bound-no-status: attention required', 'duplicate-a: unknown/malformed', 'duplicate-b: unknown/malformed', 'test-missing-config-identity: unknown/malformed', 'test-legacy-external: waiting human', 'test-empty-identity: unknown/malformed', 'test-malformed-identity: unknown/malformed']) {
    assert.ok(statusText.includes(fragment), `local status should include ${fragment}`);
  }
  assert.equal(userMessages.length, beforeStatus, 'status inspection never calls a model');
  assert.doesNotMatch(statusText, /duplicate-[ab]: (?:running|evaluating)/, 'duplicate run identities must remain unknown despite matching raw status');
  assert.match(statusText, /test-missing-config-identity: unknown\/malformed \(phase unknown\/malformed\)/, 'missing config/run identity must not validate raw evaluating metadata');
  assert.match(statusText, /test-legacy-external: waiting human \(phase waiting human\)[\s\S]*?cycle 2\/3[\s\S]*?Reason: Test input required/, 'safe external legacy IDs retain validated lifecycle metadata');
  assert.match(statusText, /test-empty-identity: unknown\/malformed \(phase unknown\/malformed\)[\s\S]*?cycle unavailable/, 'empty IDs cannot fall back to cached active state or expose unvalidated metadata');
  assert.match(statusText, /test-malformed-identity: unknown\/malformed \(phase unknown\/malformed\)/, 'unsafe malformed IDs cannot validate matching raw lifecycle status');
  assert.ok(statusText.includes('Reviewer: test-review-provider/test-review-model'), 'detailed status includes reviewer identity');
  assert.match(statusText, /Directory: .*test-running/, 'detailed status includes the relevant run path');
  assert.ok(statusText.includes('cycle 1/3'), 'detailed status includes cycle and configured budget');
  assert.match(statusText, /Next:/, 'detailed status includes an actionable next step');
  const primaryStatus = statusText;
  await runCommand('reviewed-status');
  assert.equal(notices.at(-1)[0], primaryStatus, 'legacy status alias is equivalent');
  await runCommand('ppp-status');
  assert.equal(notices.at(-1)[0], primaryStatus, 'short status alias is equivalent');
  const boundRun = path.join(storage, 'test-bound-no-status');
  const beforeBound = userMessages.length;
  await runCommand('pi-ping-pong', 'test-bound-no-status');
  assert.equal(userMessages.length, beforeBound, 'a config session binding without status is not treated as an unlaunched draft');
  assert.equal(fs.existsSync(path.join(boundRun, 'launch-attempt.json')), false);
  assert.ok(!statusText.includes('Synthetic task criteria'), 'status never exposes task contents');
  await runCommand('ppp-status');
  assert.equal(userMessages.length, beforeStatus, 'short status alias is also local');

  const symlinkTarget = path.join(root, 'external-target');
  fs.mkdirSync(symlinkTarget, { mode: 0o700 });
  write(path.join(symlinkTarget, 'sentinel.txt'), 'must not be read or changed');
  fs.symlinkSync(symlinkTarget, path.join(storage, 'test-linked-run'));
  const linkedBefore = fs.readFileSync(path.join(symlinkTarget, 'sentinel.txt'), 'utf8');
  const beforeLinkedPrompt = userMessages.length;
  await runCommand('pi-ping-pong', 'test-linked-run');
  assert.equal(userMessages.length, beforeLinkedPrompt, 'symlink runs are not followed or prepared');
  assert.equal(fs.readFileSync(path.join(symlinkTarget, 'sentinel.txt'), 'utf8'), linkedBefore);

  const symlinkProject = path.join(root, 'symlink-project');
  fs.mkdirSync(symlinkProject, { mode: 0o700 });
  execFileSync('git', ['init', '--quiet', symlinkProject]);
  fs.writeFileSync(path.join(symlinkProject, '.gitignore'), '.pi-ping-pong/\n');
  const externalStorage = path.join(root, 'external-storage');
  fs.mkdirSync(externalStorage, { mode: 0o700 });
  fs.symlinkSync(externalStorage, path.join(symlinkProject, '.pi-ping-pong'));
  ctx.cwd = symlinkProject;
  const beforeSymlinkProject = userMessages.length;
  await runCommand('ppp', 'escape-run');
  assert.equal(userMessages.length, beforeSymlinkProject, 'symlinked project storage is refused');
  assert.deepEqual(fs.readdirSync(externalStorage), [], 'storage symlink target remains untouched');
  ctx.cwd = originalCwd;

  const nonIgnored = path.join(root, 'non-ignored-project');
  fs.mkdirSync(nonIgnored, { mode: 0o700 });
  execFileSync('git', ['init', '--quiet', nonIgnored]);
  ctx.cwd = nonIgnored;
  const beforeUnignored = userMessages.length;
  await runCommand('pi-ping-pong', 'must-not-save');
  assert.equal(userMessages.length, beforeUnignored, 'project preparation is refused until run artifacts are Git-ignored');
  assert.match(notices.at(-1)[0], /not Git-ignored/);
  assert.equal(fs.existsSync(path.join(nonIgnored, '.pi-ping-pong')), false);
  ctx.cwd = originalCwd;

  const legacyRoot = path.join(root, 'legacy-run');
  fs.mkdirSync(legacyRoot, { mode: 0o700 });
  write(path.join(legacyRoot, 'config.json'), { run_id: 'Test-run', mode: 'goal', review_transport: 'pi', pi_session_id: 'Test-session', review_model: 'test-review-model', review_provider: 'test-review-provider' });
  fs.mkdirSync(path.join(legacyRoot, 'pi-inbox'), { mode: 0o700 });
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'running', phase: 'working', cycle: 1, started_at: Math.floor(Date.now() / 1000) });
  const envelope = { id: 'one', run_id: 'Test-run', session_id: 'Test-session', kind: 'review', message: 'Codex checkpoint: read evidence', receipt: path.join(legacyRoot, 'receipt.txt') };
  write(path.join(legacyRoot, 'pi-inbox', '001.message.json'), envelope);
  await hooks.get('session_start')({}, ctx);
  assert.equal(commands.size, 6, 'all aliases remain registered after session start');
  assert.equal(messages.length, 1);
  const completionNotices = notices.filter(notice => String(notice[0]).includes('Pi Ping Pong legacy-run: completed')).length;
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'complete', phase: 'complete', cycle: 1, updated_at: Date.now() / 1000 });
  await hooks.get('model_select')({}, ctx);
  const noticesAfterComplete = notices.filter(notice => String(notice[0]).includes('Pi Ping Pong legacy-run: completed')).length;
  assert.equal(noticesAfterComplete, completionNotices + 1, 'material terminal transition is notified once');
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, ctx);
  assert.equal(notices.filter(notice => String(notice[0]).includes('Pi Ping Pong legacy-run: completed')).length, completionNotices + 1, 'persisted terminal notification receipt prevents reload spam');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'complete', phase: 'evaluating', cycle: 1 });
  await runCommand('ppp-status');
  assert.match(notices.at(-1)[0], /legacy-run: completed \(phase completed\)/, 'terminal status must override a stale evaluating phase in detailed status');
  assert.doesNotMatch(notices.at(-1)[0].split('\n')[0], /evaluating/);
  const blockerCount = () => notices.filter(notice => String(notice[0]).includes('Pi Ping Pong legacy-run: waiting human.')).length;
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'waiting_human', cycle: 1, reason: 'Test first input', updated_at: 1 });
  await hooks.get('model_select')({}, ctx);
  let blockerNotices = blockerCount();
  assert.equal(blockerNotices, 1, 'first human blocker emits a notification');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'waiting_human', cycle: 1, reason: 'Test first input', updated_at: 2 });
  await hooks.get('model_select')({}, ctx);
  assert.equal(blockerCount(), blockerNotices, 'timestamp-only refresh does not spam blocker notices');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'running', cycle: 2 });
  await hooks.get('model_select')({}, ctx);
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'waiting_human', cycle: 2, reason: 'Test first input' });
  await hooks.get('model_select')({}, ctx);
  blockerNotices = blockerCount();
  assert.equal(blockerNotices, 2, 'same blocker re-entered after observed work in a new cycle emits again');
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, ctx);
  assert.equal(blockerCount(), blockerNotices, 'durable receipt prevents blocker replay after reload');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'waiting_human', cycle: 2, reason: 'Test changed input' });
  await hooks.get('model_select')({}, ctx);
  assert.equal(blockerCount(), blockerNotices + 1, 'changed blocker reason emits a new notification');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'running', cycle: 2 });
  await hooks.get('model_select')({}, ctx);
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'waiting_human', cycle: 2, reason: 'Test changed input' });
  await hooks.get('model_select')({}, ctx);
  assert.equal(blockerCount(), blockerNotices + 2, 'observed blocker re-entry emits again even with unchanged cycle and reason');
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, ctx);
  assert.equal(blockerCount(), blockerNotices + 2, 're-entry notification remains deduplicated after reload');
  write(path.join(legacyRoot, 'bridge-status.json'), { run_id: 'Test-run', status: 'running', phase: 'working', cycle: 1, started_at: Date.now() / 1000 });
  await hooks.get('model_select')({}, ctx);
  assert.match(statusValues.get('pi-ping-pong'), /PPP legacy-run working 1/, 'poll publishes a readable basename through the native PPP footer status API');
  assert.ok(commands.has('pi-ping-pong-status') && commands.has('reviewed-status') && commands.has('ppp-status'));
  assert.equal(messages[0].options.deliverAs, 'followUp');
  assert.equal(messages[0].options.triggerTurn, true);
  assert.equal(JSON.parse(fs.readFileSync(path.join(legacyRoot, 'pi-inbox', '001.delivery.json'), 'utf8')).status, 'enqueued_in_pi');
  await hooks.get('session_shutdown')();
  assert.equal(statusValues.has('pi-ping-pong'), false, 'session shutdown clears only the receiver-owned footer status');
  await hooks.get('session_start')({}, ctx);
  assert.equal(messages.length, 1, 'reload does not duplicate durable delivery');
  ctx.model.id = 'test-other-review-model';
  write(path.join(legacyRoot, 'pi-inbox', '002.message.json'), { ...envelope, id: 'two' });
  await hooks.get('model_select')({}, ctx);
  assert.equal(messages.length, 1, 'model mismatch holds queue');
  assert.ok(notices.some(notice => notice[0].includes('select test-review-model')));
  ctx.model.id = 'test-review-model';
  await hooks.get('model_select')({}, ctx);
  assert.equal(messages.length, 2);
  write(path.join(legacyRoot, 'pi-inbox', '003.message.json'), { ...envelope, id: 'three', session_id: 'wrong-session' });
  await hooks.get('model_select')({}, ctx);
  assert.equal(messages.length, 2, 'wrong session is rejected');
  assert.equal(JSON.parse(fs.readFileSync(path.join(legacyRoot, 'pi-inbox', '003.delivery.json'), 'utf8')).status, 'rejected_identity');
  await hooks.get('session_shutdown')();

  const invalidBindings = [];
  for (const [name, runId] of [['empty-run-id', ''], ['unsafe-run-id', 'Test/bad']]) {
    const dir = path.join(root, name);
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    write(path.join(dir, 'config.json'), { run_id: runId, mode: 'ralph', review_transport: 'pi', pi_session_id: 'Test-session', review_model: 'test-review-model' });
    write(path.join(dir, 'bridge-status.json'), { run_id: runId, status: 'complete', phase: 'evaluating', cycle: 1, pi_session: 'Test-worker-session' });
    const binding = { root: dir, runId, sessionId: 'Test-session' };
    invalidBindings.push(binding);
    entries.push({ type: 'custom', customType: 'pi-reviewed-run', data: binding });
  }
  const noticesBeforeInvalidRestore = notices.length;
  const messagesBeforeInvalidRestore = messages.length;
  const invalidRestoreEntries = [entry, ...invalidBindings.map(data => ({ type: 'custom', customType: 'pi-reviewed-run', data }))];
  let restoredEntries;
  const invalidRestoreContext = {
    ...ctx,
    sessionManager: {
      getSessionId: () => 'Test-session',
      getEntries: () => { restoredEntries = invalidRestoreEntries; return restoredEntries; },
    },
  };
  await hooks.get('session_start')({}, invalidRestoreContext);
  assert.strictEqual(restoredEntries, invalidRestoreEntries, 'session restoration must receive the actual invalid bindings and valid legacy control');
  assert.equal(restoredEntries.length, 1 + invalidBindings.length, 'all invalid fixture entries reach restoration alongside the valid legacy binding');
  assert.match(String(statusValues.get('pi-ping-pong') ?? ''), /PPP legacy-run working/, 'valid legacy control restores while invalid external bindings are rejected');
  assert.doesNotMatch(String(statusValues.get('pi-ping-pong') ?? ''), /empty-run-id|unsafe-run-id|completed|evaluating/, 'restored invalid external bindings cannot publish active or terminal lifecycle footer state');
  assert.equal(notices.length, noticesBeforeInvalidRestore, 'invalid restored identities cannot emit startup or terminal notices');
  assert.equal(messages.length, messagesBeforeInvalidRestore, 'invalid restored identities cannot trigger model turns');
  await hooks.get('session_shutdown')();
  const otherSession = { ...ctx, sessionManager: { getSessionId: () => 'Test-other-session', getEntries: () => [entry] } };
  await hooks.get('session_start')({}, otherSession);
  write(path.join(legacyRoot, 'pi-inbox', '004.message.json'), { ...envelope, id: 'four' });
  await hooks.get('model_select')({}, otherSession);
  assert.equal(messages.length, 2, 'session switch does not inherit another session subscription');
  await hooks.get('session_shutdown')();

  const relativeDir = path.join(project, 'relative-external');
  fs.mkdirSync(relativeDir, { mode: 0o700 });
  write(path.join(relativeDir, 'config.json'), { run_id: 'Test-relative', mode: 'ralph', review_model: 'test-review-model' });
  await runCommand('reviewed-run', 'relative-external/config.json');
  await waitForChild();
  assert.ok(fs.existsSync(path.join(relativeDir, 'launch-attempt.json')), 'relative explicit config path uses the existing launcher');
  await assert.rejects(runCommand('pi-ping-pong', 'relative-external/config.json'), /already launched/);

  const oldExternal = path.join(root, '.pi', 'reviewed-runs', randomUUID());
  fs.mkdirSync(oldExternal, { recursive: true, mode: 0o700 });
  write(path.join(oldExternal, 'config.json'), { run_id: 'Test-legacy', mode: 'goal', review_model: 'test-review-model' });
  await runCommand('ppp', path.join(oldExternal, 'config.json'));
  await waitForChild();
  assert.ok(fs.existsSync(path.join(oldExternal, 'launch-attempt.json')), 'absolute legacy external run path remains compatible');

  const missingPython = path.join(root, 'spawn-error', 'config.json');
  write(missingPython, { run_id: 'Test-spawn-error', mode: 'ralph', review_model: 'test-review-model' });
  const previousSpawnPath = process.env.PATH;
  process.env.PATH = path.join(root, 'empty-path');
  fs.mkdirSync(process.env.PATH, { mode: 0o700 });
  const noticesBeforeSpawnError = notices.length;
  try { await runCommand('ppp', missingPython); }
  finally { process.env.PATH = previousSpawnPath; }
  const spawnNotices = notices.slice(noticesBeforeSpawnError).map(notice => String(notice[0]));
  assert.ok(spawnNotices.some(notice => /spawn-error/.test(notice) && /could not start|failed/i.test(notice) && /launcher\.log/.test(notice)), 'spawn error must notify with readable run name and launcher.log path');
  assert.ok(!spawnNotices.some(notice => /confirmed|worker.*started/i.test(notice)), 'spawn error must never confirm worker startup');
  assert.ok(fs.existsSync(path.join(path.dirname(missingPython), 'launch-attempt.json')), 'spawn failure preserves launch-attempt duplicate-refusal record');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(path.dirname(missingPython), 'pi-receiver.json'), 'utf8')), {
    run_id: 'Test-spawn-error', session_id: 'Test-session', connected: false, pid: process.pid,
  }, 'spawn failure disconnects the run-local receiver while retaining matching run/session identity');
  await assert.rejects(runCommand('ppp', missingPython), /already launched/);
  assert.equal(notices.length, noticesBeforeSpawnError + spawnNotices.length, 'duplicate launch refusal does not emit a second spawn report');

  const evaluatorReadiness = (name, argv, evaluatorSetup) => {
    const dir = makeRun(name, { config: null, launched: false });
    write(path.join(dir, 'TASK.md'), 'Synthetic task criteria; no real user run.');
    write(path.join(dir, 'eval.py'), `from pathlib import Path\\nPath(${JSON.stringify(childMarker)}).write_text('evaluator executed')\\n`, 0o600);
    if (evaluatorSetup) evaluatorSetup(dir);
    write(path.join(dir, 'config.json'), { ...tempConfig(dir), eval_argv: argv(dir) });
    return dir;
  };
  evaluatorReadiness('test-python-absolute', dir => ['python3', path.join(dir, 'eval.py')]);
  evaluatorReadiness('test-python-no-bytecode', dir => ['python3', '-B', path.join(dir, 'eval.py')]);
  evaluatorReadiness('test-python-relative', dir => {
    fs.mkdirSync(path.join(dir, 'work'), { mode: 0o700 });
    write(path.join(dir, 'work', 'eval.py'), `from pathlib import Path\\nPath(${JSON.stringify(childMarker)}).write_text('evaluator executed')\\n`, 0o600);
    return ['python3', 'eval.py'];
  });
  evaluatorReadiness('test-python-bad-b', dir => ['python3', path.join(dir, 'eval.py'), '-B']);
  evaluatorReadiness('test-python-unsupported-flag', dir => ['python3', '-I', path.join(dir, 'eval.py')]);
  evaluatorReadiness('test-python-missing', dir => ['python3', path.join(dir, 'missing.py')]);
  evaluatorReadiness('test-python-non-private', dir => {
    write(path.join(dir, 'eval.py'), 'raise SystemExit(1)');
    fs.chmodSync(path.join(dir, 'eval.py'), 0o644);
    return ['python3', path.join(dir, 'eval.py')];
  });
  evaluatorReadiness('test-python-symlink', dir => {
    fs.rmSync(path.join(dir, 'eval.py'));
    write(path.join(root, 'linked-eval.py'), 'raise SystemExit(1)');
    fs.symlinkSync(path.join(root, 'linked-eval.py'), path.join(dir, 'eval.py'));
    return ['python3', path.join(dir, 'eval.py')];
  });
  evaluatorReadiness('test-python-outside', () => ['python3', path.join(root, 'linked-eval.py')]);
  const beforeEvaluatorInspection = userMessages.length;
  await runCommand('pi-ping-pong-status');
  const evaluatorStatus = notices.at(-1)[0];
  for (const name of ['test-python-absolute', 'test-python-no-bytecode', 'test-python-relative']) {
    assert.match(evaluatorStatus, new RegExp(`${name}: ready to launch`), `${name} must resolve the evaluator command to a private in-run file`);
  }
  for (const name of ['test-python-bad-b', 'test-python-unsupported-flag', 'test-python-missing', 'test-python-non-private', 'test-python-symlink', 'test-python-outside']) {
    assert.match(evaluatorStatus, new RegExp(`${name}: draft/incomplete`), `${name} must not pass evaluator readiness`);
  }
  assert.ok(evaluatorStatus.includes('unsupported eval_argv; use ["python3", "<script>"] or ["python3", "-B", "<script>"]'), 'unsupported command diagnostics must show exact supported forms');
  assert.ok(evaluatorStatus.includes('unsupported eval_argv'), 'unsupported flags receive an actionable command diagnostic');
  assert.ok(evaluatorStatus.includes('private evaluator file'), 'missing, non-private, symlinked and outside-run evaluators fail the private-file check');
  assert.equal(userMessages.length, beforeEvaluatorInspection, 'readiness inspection never calls a model');
  assert.equal(fs.existsSync(childMarker), false, 'readiness inspection never executes evaluator code');

  const readyLaunch = makeReadyRun('ready-launch-run');
  await runCommand('pi-ping-pong', 'ready-launch-run');
  await waitForChild();
  const launchedConfig = JSON.parse(fs.readFileSync(path.join(readyLaunch, 'config.json'), 'utf8'));
  assert.equal(launchedConfig.pi_session_id, 'Test-session', 'session binding happens only at actual launcher time');
  assert.equal(launchedConfig.review_transport, 'pi');
  assert.ok(fs.existsSync(path.join(readyLaunch, 'launch-attempt.json')), 'ready named run uses the shared existing launcher');
  assert.ok(entries.length >= 2, 'only actual launches attach run session entries');

  const unready = path.join(storage, 'test-incomplete');
  const beforeUnready = userMessages.length;
  selectAnswers.push('Back');
  await runCommand('pi-ping-pong', 'test-incomplete');
  assert.equal(userMessages.length, beforeUnready, 'incomplete named run never launches or prepares until continuation is selected');
  assert.equal(fs.existsSync(path.join(unready, 'launch-attempt.json')), false);

  const snapshotBeforeMenuBack = fs.readdirSync(storage).sort();
  const launchesBeforeMenuBack = fs.readdirSync(storage).filter(name => fs.existsSync(path.join(storage, name, 'launch-attempt.json'))).length;
  selectAnswers.push((_title, options) => options.find(option => option.startsWith('ready-launch-run')), 'Back');
  await runCommand('pi-ping-pong');
  assert.equal(fs.readdirSync(storage).filter(name => fs.existsSync(path.join(storage, name, 'launch-attempt.json'))).length, launchesBeforeMenuBack, 'menu run selection followed by Back never launches');
  assert.deepEqual(fs.readdirSync(storage).sort(), snapshotBeforeMenuBack, 'menu detail inspection does not mutate runs');

  const receiver = loaded.extensions[0];
  const conflictingExtension = {
    ...receiver,
    path: 'Test-conflicting-extension',
    commands: new Map([['ppp', { ...receiver.commands.get('ppp'), extensionPath: 'Test-conflicting-extension' }]]),
  };
  const runner = new ExtensionRunner([receiver, conflictingExtension], loaded.runtime, project, {}, {});
  const resolvedCommands = runner.getRegisteredCommands();
  assert.equal(resolvedCommands.some(command => command.invocationName === 'ppp'), false, 'Pi does not silently choose one colliding alias');
  assert.deepEqual(resolvedCommands.filter(command => command.name === 'ppp').map(command => command.invocationName), ['ppp:1', 'ppp:2'], 'native Pi resolver disambiguates extension collisions');
  assert.ok(runner.getCommand('pi-ping-pong'), 'non-conflicting primary command remains available');

  const installerSource = path.join(root, 'install-source');
  const installSkill = path.join(installerSource, 'skill');
  fs.mkdirSync(path.join(installSkill, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(installSkill, 'extensions'), { recursive: true });
  fs.mkdirSync(path.join(installSkill, '.pi-ping-pong', 'runs', 'test-secret-run'), { recursive: true });
  fs.copyFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'install.py'), path.join(installSkill, 'scripts', 'install.py'));
  write(path.join(installSkill, 'SKILL.md'), 'Synthetic installer fixture.');
  write(path.join(installSkill, 'extensions', 'pi-reviewed.ts'), 'export {};');
  write(path.join(installSkill, '.pi-ping-pong', 'runs', 'test-secret-run', 'TASK.md'), 'private synthetic artifact');
  write(path.join(installSkill, '.pi-ping-pong', 'runs', 'test-secret-run', 'eval.py'), 'raise SystemExit(1)');
  const installOut = path.join(root, 'installed-skill');
  const extensionOut = path.join(root, 'installed-extensions');
  const install = spawnSync('python3', ['-B', path.join(installSkill, 'scripts', 'install.py'), '--skills-dir', installOut, '--extensions-dir', extensionOut], { encoding: 'utf8' });
  assert.equal(install.status, 0, install.stderr);
  assert.equal(fs.existsSync(path.join(installOut, 'pi-ping-pong', '.pi-ping-pong')), false, 'installer excludes project run data');
  assert.equal(fs.existsSync(path.join(installOut, 'pi-ping-pong', 'extensions', 'pi-reviewed.ts')), true, 'installer still installs receiver source');
  console.log('Pi receiver: named runs, secure reservation, menus/status, explicit path compatibility, aliases, launch refusal and installer exclusions passed.');
} finally {
  await hooks.get('session_shutdown')?.();
  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(childMarker, { force: true });
  if (previousBridge === undefined) delete process.env.PI_PING_PONG_BRIDGE; else process.env.PI_PING_PONG_BRIDGE = previousBridge;
  if (previousHome === undefined) delete process.env.HOME; else process.env.HOME = previousHome;
}
