import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const gitLocalVars = execFileSync('git', ['rev-parse', '--local-env-vars'], { encoding: 'utf8' }).trim().split(/\s+/);
for (const name of gitLocalVars) delete process.env[name];

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
for (const name of ['pi-ping-pong', 'reviewed-run', 'ppp', 'pi-ping-pong-status', 'reviewed-status', 'ppp-status', 'ppp-respond']) {
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
  protocol_version: 2, schema_version: 1,
  execution_contract: { target: 'Test fixture', actions: [{ id: 'Test-action', description: 'Test authorized task' }], criteria: { 'Test-ok': 'Test output' }, closure: { authorized: true, max_cycles: null }, reminder_seconds: 86400 },
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
const makeReadyRun = (name, runId = randomUUID(), overrides = {}) => {
  const dir = makeRun(name, { config: null, launched: false });
  write(path.join(dir, 'TASK.md'), 'Synthetic task criteria; no real user run.');
  const config = { ...tempConfig(dir, runId), ...overrides };
  for (const [key, value] of Object.entries(overrides)) if (value === undefined) delete config[key];
  write(path.join(dir, 'config.json'), config);
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
  for (const required of [project, 'Selected run name: add-linters', draft, 'unique RFC 4122 UUID run_id', 'worker_model=gpt-6-luna', 'thinking=low', 'max_cycles=10', 'approved defaults', 'test-review-provider/test-review-model', 'positive finite integer', 'Do not create eval.py, eval_argv', 'ordinary tests', 'only what tests cannot establish', 'No mandatory model preflight', 'Do not start or launch the worker', 'Do not write pi_session_id', 'Do not overwrite .draft.json', '/pi-ping-pong add-linters']) {
    assert.ok(prompt.includes(required), `preparation prompt must include ${required}`);
  }
  for (const rule of ['one usable Playwright route', 'project-installed runtime', 'for both Goal and Ralph', 'PPP_PLAYWRIGHT_MODULE', 'Module resolution does not establish browser/auth availability', 'absolute authorized output/source path', 'a merely changed value is not enough', 'Missing checks are unknown/not_tested', 'actual uncommitted changes', 'confirmed repository root as product target', 'modify an existing project in place', 'subdirectory or file', 'service storage only', 'No mandatory auto-commit', 'missing or partial snapshots must not block']) {
    assert.ok(prompt.includes(rule), `preparation guidance must include ${rule}`);
  }
  for (const format of ['standalone STATUS', '### TL;DR', '### Summary', '### Report', '### Suggested action', '### Full run status', 'blank lines around', 'no extra reads just to fill status']) {
    assert.ok(prompt.includes(format), `preparation report formatting must include ${format}`);
  }

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
  const beforeNonGitConfirmations = confirmAnswers.length;
  ctx.hasUI = false;
  process.env.GIT_DIR = path.join(project, '.git');
  process.env.GIT_WORK_TREE = project;
  process.env.GIT_INDEX_FILE = path.join(project, '.git', 'index');
  await runCommand('ppp', 'confirmed-run');
  assert.ok(fs.existsSync(path.join(nonGit, '.pi-ping-pong', 'runs', 'confirmed-run', '.draft.json')), 'selected non-Git project works without a routine approval gate or UI');
  assert.equal(confirmAnswers.length, beforeNonGitConfirmations);
  ctx.hasUI = true;
  const fallbackHome = path.join(root, 'fallback-home');
  fs.mkdirSync(fallbackHome, { mode: 0o700 });
  process.env.HOME = fallbackHome;
  const fallbackCwd = path.join(root, 'unconfirmed-folder');
  ctx.cwd = fallbackCwd;
  confirmAnswers.push(true);
  await runCommand('pi-ping-pong', 'fallback-run');
  assert.ok(fs.existsSync(path.join(fallbackHome, '.pi', 'reviewed-runs', 'named', 'fallback-run', '.draft.json')), 'explicit fallback confirmation uses a separate private named store');
  assert.ok(userMessages.at(-1).message.includes('Private fallback store root (not a product target)'), 'fallback storage never silently authorizes a product in HOME');
  ctx.cwd = originalCwd;
  const nestedCwd = path.join(project, 'nested', 'working-directory');
  fs.mkdirSync(nestedCwd, { recursive: true, mode: 0o700 });
  ctx.cwd = nestedCwd;
  await runCommand('pi-ping-pong', 'root-from-git');
  assert.ok(fs.existsSync(path.join(storage, 'root-from-git', '.draft.json')), 'Git top-level, not cwd subdirectory, determines project storage');
  assert.equal(fs.existsSync(path.join(nestedCwd, '.pi-ping-pong')), false);
  ctx.cwd = originalCwd;
  for (const name of gitLocalVars) delete process.env[name];

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
  await runCommand('pi-ping-pong-status', '--all --details');
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
  await runCommand('reviewed-status', '--all --details');
  assert.equal(notices.at(-1)[0], primaryStatus, 'legacy status alias is equivalent');
  await runCommand('ppp-status', '--all --details');
  assert.equal(notices.at(-1)[0], primaryStatus, 'short status alias is equivalent');
  const boundRun = path.join(storage, 'test-bound-no-status');
  const beforeBound = userMessages.length;
  await runCommand('pi-ping-pong', 'test-bound-no-status');
  assert.equal(userMessages.length, beforeBound, 'a config session binding without status is not treated as an unlaunched draft');
  assert.equal(fs.existsSync(path.join(boundRun, 'launch-attempt.json')), false);
  assert.ok(!statusText.includes('Synthetic task criteria'), 'status never exposes task contents');
  await runCommand('ppp-status', '--all --details');
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
  assert.equal(commands.size, 7, 'legacy aliases and protocol-2 human ingress remain registered after session start');
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
  await runCommand('ppp-status', '--all --details');
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
  write(path.join(relativeDir, 'TASK.md'), 'Test authorized task');
  write(path.join(relativeDir, 'config.json'), tempConfig(relativeDir, 'Test-relative'));
  await runCommand('reviewed-run', 'relative-external/config.json');
  await waitForChild();
  assert.ok(fs.existsSync(path.join(relativeDir, 'launch-attempt.json')), 'relative explicit config path uses the existing launcher');
  await assert.rejects(runCommand('pi-ping-pong', 'relative-external/config.json'), /already launched/);

  const oldExternal = path.join(root, '.pi', 'reviewed-runs', randomUUID());
  fs.mkdirSync(oldExternal, { recursive: true, mode: 0o700 });
  write(path.join(oldExternal, 'TASK.md'), 'Test current config at compatible external path');
  write(path.join(oldExternal, 'config.json'), { ...tempConfig(oldExternal, 'Test-external'), mode: 'goal' });
  await runCommand('ppp', path.join(oldExternal, 'config.json'));
  await waitForChild();
  assert.ok(fs.existsSync(path.join(oldExternal, 'launch-attempt.json')), 'absolute legacy external run path remains compatible');

  const missingPython = path.join(root, 'spawn-error', 'config.json');
  write(path.join(path.dirname(missingPython), 'TASK.md'), 'Test authorized task');
  write(missingPython, tempConfig(path.dirname(missingPython), 'Test-spawn-error'));
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

  const legacyDir = makeReadyRun('test-evaluator-era');
  const legacyConfig = { ...tempConfig(legacyDir), eval_argv: ['python3', path.join(legacyDir, 'eval.py')] };
  write(path.join(legacyDir, 'config.json'), legacyConfig);
  const legacyBytes = fs.readFileSync(path.join(legacyDir, 'config.json'), 'utf8');
  await assert.rejects(runCommand('ppp', path.join(legacyDir, 'config.json')), /Evaluator-era configs are unsupported/);
  assert.equal(fs.readFileSync(path.join(legacyDir, 'config.json'), 'utf8'), legacyBytes, 'old run files are never migrated');
  assert.equal(fs.existsSync(path.join(legacyDir, 'launch-attempt.json')), false);
  const noEvaluatorDir = makeReadyRun('test-no-evaluator');
  const beforeInspection = userMessages.length;
  await runCommand('pi-ping-pong-status', '--all --details');
  assert.match(notices.at(-1)[0], /test-no-evaluator: ready to launch/);
  makeReadyRun('test-goal-no-cycles', randomUUID(), { mode: 'goal', max_cycles: undefined, cycle_seconds: undefined });
  makeReadyRun('test-ralph-no-cycles', randomUUID(), { max_cycles: undefined, cycle_seconds: undefined });
  makeReadyRun('test-goal-bad-cycles', randomUUID(), { mode: 'goal', max_cycles: 0 });
  makeReadyRun('test-bad-extension', randomUUID(), { worker_extensions: [''] });
  makeReadyRun('test-good-extensions', randomUUID(), { worker_extensions: ['Test-worker.ts'], reviewer_extensions: ['/tmp/Test-review.ts'] });
  await runCommand('pi-ping-pong-status', '--all --details');
  assert.match(notices.at(-1)[0], /test-goal-no-cycles: ready to launch/, 'Goal needs no max_cycles/cycle_seconds');
  assert.match(notices.at(-1)[0], /test-ralph-no-cycles: draft\/incomplete/, 'Ralph still needs cycle limits');
  assert.match(notices.at(-1)[0], /test-goal-bad-cycles: draft\/incomplete/, 'set Goal cycle fields are still validated');
  assert.match(notices.at(-1)[0], /test-evaluator-era: draft\/incomplete/);
  assert.match(notices.at(-1)[0], /test-bad-extension: draft\/incomplete/);
  assert.match(notices.at(-1)[0], /test-good-extensions: ready to launch/);
  assert.equal(userMessages.length, beforeInspection, 'readiness never calls a model');
  assert.equal(fs.existsSync(path.join(noEvaluatorDir, 'eval.py')), false);
  assert.equal(fs.existsSync(childMarker), false);

  const preflightDir = makeReadyRun('test-preflight');
  const preflightConfig = { ...tempConfig(preflightDir), protocol_version: 2, schema_version: 1,
    execution_contract: { target: 'Test fixture', reminder_seconds: 86400,
      actions: [{ id: 'a', description: 'Test action', depends_on: [], operations: [] }],
      criteria: { ok: 'Test output' }, closure: { authorized: true, max_cycles: null } } };
  write(path.join(preflightDir, 'config.json'), preflightConfig);
  const unchangedConfig = fs.readFileSync(path.join(preflightDir, 'config.json'), 'utf8');
  const entriesBeforePreflight = entries.length;
  fs.chmodSync(storage, 0o755);
  await assert.rejects(runCommand('ppp', path.join(preflightDir, 'config.json')), /permissive permissions/);
  await runCommand('ppp', 'test-preflight');
  assert.match(String(notices.at(-1)[0]), /permissive permissions/);
  assert.equal(fs.existsSync(path.join(preflightDir, 'preflight')), false, 'storage rejection starts no process');
  fs.chmodSync(storage, 0o700);
  await runCommand('ppp', path.join(preflightDir, 'config.json'));
  await waitForChild();
  assert.equal(fs.existsSync(path.join(preflightDir, 'preflight')), false, 'launch does not execute an optional diagnostic');
  assert.equal(fs.existsSync(path.join(preflightDir, 'launch-attempt.json')), true, 'no separate evaluator is needed for launch');
  assert.notEqual(fs.readFileSync(path.join(preflightDir, 'config.json'), 'utf8'), unchangedConfig, 'launch binds the session');
  assert.equal(entries.length, entriesBeforePreflight + 1, 'launch attaches a session');
  await assert.rejects(runCommand('ppp', path.join(preflightDir, 'config.json')), /already launched/);

  const headlessDir = makeReadyRun('test-headless-review');
  const headlessConfig = { ...tempConfig(headlessDir), protocol_version: 2, schema_version: 1,
    review_execution: 'headless', review_provider: 'Test-independent-provider', review_model: 'Test-independent-model',
    execution_contract: preflightConfig.execution_contract };
  write(path.join(headlessDir, 'config.json'), headlessConfig);
  const modelBeforeHeadless = ctx.model;
  ctx.model = { id: 'Test-human-chat-model', provider: 'Test-human-chat-provider' };
  await runCommand('ppp', path.join(headlessDir, 'config.json'));
  await waitForChild();
  const boundHeadless = JSON.parse(fs.readFileSync(path.join(headlessDir, 'config.json'), 'utf8'));
  assert.equal(boundHeadless.review_model, 'Test-independent-model', 'headless reviewer model does not depend on Chat A model');
  assert.equal(boundHeadless.review_provider, 'Test-independent-provider', 'launcher must not overwrite independent reviewer provider');
  assert.equal(boundHeadless.pi_session_id, 'Test-session', 'Chat A remains the human/report binding only');
  const inboxBeforeHeadless = messages.length;
  for (const [id, kind, trigger, noticeType] of [['Test-independent-report', 'notice', false, 'report'], ['Test-forbidden-review-turn', 'review', true, undefined], ['Test-chat-a-reporter', 'notice', true, 'reporter'], ['Test-disguised-review', 'review', true, 'reporter']]) {
    write(path.join(headlessDir, 'pi-inbox', `${id}.message.json`), {
      id, kind, trigger_turn: trigger, notice_type: noticeType, run_id: boundHeadless.run_id, session_id: 'Test-session',
      protocol_version: 2, schema_version: 1, message: 'Test Core report, not a model review turn',
    });
  }
  await new Promise(resolve => setTimeout(resolve, 850));
  const headlessMessages = messages.slice(inboxBeforeHeadless);
  assert.equal(headlessMessages.length, 2, 'only passive notices and explicitly typed reporter requests are delivered');
  const passiveReport = headlessMessages.find(row => row.message.customType === 'reviewed-checkpoint');
  const reporterRequest = headlessMessages.find(row => row.message.customType === 'reviewed-report-request');
  assert.equal(passiveReport.options.triggerTurn, false, 'stage notices remain passive');
  assert.equal(reporterRequest.options.triggerTurn, true, 'reporter requests invoke Chat A independently of Reviewer model');
  assert.equal(reporterRequest.message.display, false, 'internal report prompt is hidden; Chat A supplies the visible report');
  assert.equal(JSON.parse(fs.readFileSync(path.join(headlessDir, 'pi-inbox/Test-disguised-review.delivery.json'), 'utf8')).status, 'rejected_headless_model_turn');
  assert.equal(JSON.parse(fs.readFileSync(path.join(headlessDir, 'pi-inbox/Test-forbidden-review-turn.delivery.json'), 'utf8')).status, 'rejected_headless_model_turn');
  const beforeCoalescing = messages.length;
  for (const [id, change] of [
    ['Test-coalesce-001-old', {}],
    ['Test-coalesce-002-latest', {}],
    ['Test-coalesce-003-disguised', { kind: 'review' }],
    ['Test-coalesce-004-wrong-session', { session_id: 'Test-other-session' }],
    ['Test-coalesce-005-wrong-schema', { schema_version: 99 }],
    ['Test-coalesce-006-human', { report_key: undefined }],
  ]) {
    write(path.join(headlessDir, 'pi-inbox', `${id}.message.json`), {
      id, kind: 'notice', trigger_turn: true, notice_type: 'reporter', report_key: 'state',
      run_id: boundHeadless.run_id, session_id: 'Test-session', protocol_version: 2, schema_version: 1,
      message: id, ...change,
    });
  }
  await hooks.get('model_select')({}, ctx);
  assert.deepEqual(messages.slice(beforeCoalescing).map(row => row.message.content), ['Test-coalesce-002-latest', 'Test-coalesce-006-human'], 'only the latest pending state report is sent; addressed human requests are never coalesced');
  for (const [id, status] of [['001-old', 'superseded_report'], ['002-latest', 'enqueued_in_pi'], ['003-disguised', 'rejected_headless_model_turn'], ['004-wrong-session', 'rejected_identity'], ['005-wrong-schema', 'rejected_schema']]) {
    assert.equal(JSON.parse(fs.readFileSync(path.join(headlessDir, 'pi-inbox', `Test-coalesce-${id}.delivery.json`), 'utf8')).status, status);
  }
  await hooks.get('model_select')({}, ctx);
  assert.equal(messages.length, beforeCoalescing + 2, 'durable supersession/delivery receipts prevent replay on another poll');
  ctx.model = modelBeforeHeadless;

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
  fs.copyFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'output_snapshot.py'), path.join(installSkill, 'scripts', 'output_snapshot.py'));
  write(path.join(installSkill, 'extensions', 'pi-reviewed.ts'), 'export {};');
  write(path.join(installSkill, '.pi-ping-pong', 'runs', 'test-secret-run', 'TASK.md'), 'private synthetic artifact');
  write(path.join(installSkill, '.pi-ping-pong', 'runs', 'test-secret-run', 'eval.py'), 'raise SystemExit(1)');
  const installOut = path.join(root, 'installed-skill');
  const extensionOut = path.join(root, 'installed-extensions');
  const install = spawnSync('python3', ['-B', path.join(installSkill, 'scripts', 'install.py'), '--skills-dir', installOut, '--extensions-dir', extensionOut], { encoding: 'utf8' });
  assert.equal(install.status, 0, install.stderr);
  assert.equal(fs.existsSync(path.join(installOut, 'pi-ping-pong', '.pi-ping-pong')), false, 'installer excludes project run data');
  assert.equal(fs.existsSync(path.join(installOut, 'pi-ping-pong', 'extensions', 'pi-reviewed.ts')), true, 'installer still installs receiver source');
  assert.equal(fs.existsSync(path.join(installOut, 'pi-ping-pong', 'scripts', 'output_snapshot.py')), true, 'installer includes scoped discovery helper without run artifacts');
  // Protocol-2 ingress is a native, explicitly confirmed human command, never a review/model flag.
  await hooks.get('session_shutdown')();
  const actionRoot = path.join(root, 'Test-action-scoped');
  const actionBinding = { root: actionRoot, runId: 'Test-action', sessionId: 'Test-session' };
  write(path.join(actionRoot, 'config.json'), { run_id: 'Test-action', protocol_version: 2, schema_version: 1, review_execution: 'headless', review_transport: 'pi', pi_session_id: 'Test-session', review_model: 'test-review-model', review_provider: 'test-review-provider' });
  write(path.join(actionRoot, 'execution-state.json'), { run_id: 'Test-action', execution: 'wait', blockers: { B1: { status: 'open' }, B2: { status: 'open' } }, requests: { Q1: { main_extension: true, main_grant_count: 0 } }, grants: [] });
  write(path.join(actionRoot, 'bridge-status.json'), { run_id: 'Test-action', status: 'waiting_human', cycle: 1 });
  const actionContext = { ...ctx, sessionManager: { getSessionId: () => 'Test-session', getEntries: () => [{ type: 'custom', customType: 'pi-reviewed-run', data: actionBinding }] } };
  await hooks.get('session_start')({}, actionContext);
  await commands.get('ppp-status').handler('--all --details', actionContext);
  const headlessHumanStatus = String(notices.at(-1)[0]).split('Test-action-scoped:')[1];
  assert.ok(headlessHumanStatus.includes('Reply in Chat A using /ppp-respond; choose the run and request'), 'headless human input uses the no-JSON menu in Chat A');
  assert.ok(!headlessHumanStatus.includes('in the reviewer session'), 'headless status must not direct the human to Reviewer');
  for (const [status, label, footer] of [['waiting_resource', 'waiting resource', 'awaiting resource (Worker idle)'], ['waiting_event', 'waiting event', 'awaiting event (Worker idle)']]) {
    write(path.join(actionRoot, 'bridge-status.json'), { run_id: 'Test-action', status, phase: 'wait', cycle: 1 });
    await hooks.get('model_select')({}, actionContext);
    assert.ok(statusValues.get('pi-ping-pong').includes(footer), 'external waits explicitly show an idle Worker in the footer');
    assert.ok(!statusValues.get('pi-ping-pong').includes('working'), 'an external wait is not active work');
    await commands.get('ppp-status').handler('--all --details', actionContext);
    const waitingStatus = String(notices.at(-1)[0]).split('Test-action-scoped:')[1];
    assert.ok(waitingStatus.startsWith(` ${label} (phase wait)`), 'detailed status preserves validated wait metadata');
    assert.ok(waitingStatus.includes('No Worker is running; awaiting the recorded resource/event or scheduled check, not a review reply.'));
  }
  write(path.join(actionRoot, 'bridge-status.json'), { run_id: 'Test-action', status: 'waiting_human', cycle: 1 });
  await hooks.get('model_select')({}, actionContext);
  const respond = async input => commands.get('ppp-respond').handler(`Test-action ${JSON.stringify(input)}`, actionContext);
  const humanFiles = () => fs.existsSync(path.join(actionRoot, 'human-inbox')) ? fs.readdirSync(path.join(actionRoot, 'human-inbox')) : [];
  const modelCallsBefore = userMessages.length;
  confirmAnswers.push(false);
  await respond({ kind: 'resolution', blocker_ids: ['B1'], message: 'Test configured securely' });
  assert.equal(humanFiles().length, 0, 'cancelled human dialog creates no authority');
  confirmAnswers.push(true);
  await respond({ kind: 'resolution', blocker_ids: ['B1'], message: 'Test configured securely' });
  await waitForChild();
  assert.equal(humanFiles().length, 1);
  const addressed = JSON.parse(fs.readFileSync(path.join(actionRoot, 'human-inbox', humanFiles()[0]), 'utf8'));
  assert.deepEqual(addressed.blocker_ids, ['B1'], 'partial resolution addresses only specified blockers');
  assert.equal(addressed.session_id, 'Test-session');
  assert.equal(addressed.source, 'pi-command');
  assert.equal(addressed.protocol_version, 2);
  assert.equal(fs.statSync(path.join(actionRoot, 'human-inbox', humanFiles()[0])).mode & 0o777, 0o600);
  assert.equal(JSON.parse(fs.readFileSync(path.join(actionRoot, 'execution-state.json'), 'utf8')).blockers.B1.status, 'open', 'human claim does not resolve blocker in receiver');
  await respond({ kind: 'resolution', blocker_ids: ['B9'], message: 'Test wrong identity' });
  await respond({ kind: 'resolution', blocker_ids: ['B1'], message: 'RESEND_API_KEY=Test-not-a-real-key' });
  await respond({ kind: 'resolution', blocker_ids: ['B1'], message: `${'Test '.repeat(40)}RESEND_API_KEY=Test-not-a-real-key` });
  await respond({ kind: 'grant', cycles: 0, request_id: 'Q1', message: 'Test invalid budget' });
  assert.equal(humanFiles().length, 1, 'invalid identities, secrets and grants create no receipts');
  confirmAnswers.push(true);
  await respond({ kind: 'grant', cycles: 3, request_id: 'Q1', message: 'Test explicitly grant three additional main cycles' });
  await waitForChild();
  assert.equal(humanFiles().length, 2);
  await respond({ kind: 'grant', cycles: 3, request_id: 'Q1', message: 'Test duplicate authorization' });
  assert.equal(humanFiles().length, 2, 'pending main grant cannot be authorized twice');
  const wrongHumanContext = { ...actionContext, sessionManager: { getSessionId: () => 'Test-wrong-session', getEntries: () => [] } };
  await commands.get('ppp-respond').handler('Test-action {"kind":"cancel","message":"Test wrong session"}', wrongHumanContext);
  assert.equal(humanFiles().length, 2, 'wrong session cannot create human authority');
  const rpcContext = { ...actionContext, mode: 'rpc' };
  await commands.get('ppp-respond').handler('Test-action {"kind":"cancel","message":"Test model attempt"}', rpcContext);
  assert.equal(humanFiles().length, 2, 'RPC worker cannot create human authority');
  write(path.join(actionRoot, 'execution-state.json'), { run_id: 'Test-action', execution: 'cancelled', blockers: { B1: {} }, requests: {}, grants: [] });
  await respond({ kind: 'resolution', blocker_ids: ['B1'], message: 'Test late answer' });
  assert.equal(humanFiles().length, 2, 'late response cannot restart cancelled run');
  assert.equal(userMessages.length, modelCallsBefore, 'human ingress/wake invokes no parent model');
  write(path.join(actionRoot, 'pi-inbox', 'notice.message.json'), { protocol_version: 2, schema_version: 1, id: 'Test-reminder', run_id: 'Test-action', session_id: 'Test-session', kind: 'notice', trigger_turn: false, notice_type: 'waiting', message: 'Test durable reminder without paid polling', receipt: path.join(actionRoot, 'Test-receipt') });
  actionContext.model = { id: 'Test-other-model', provider: 'Test-other-provider' };
  const messagesBeforePassive = messages.length;
  await hooks.get('model_select')({}, actionContext);
  assert.equal(messages.length, messagesBeforePassive + 1, 'passive reminders deliver without selecting reviewer model');
  assert.equal(messages.at(-1).options.triggerTurn, false, 'protocol-2 reminders never trigger paid model turns');
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, actionContext);
  assert.equal(messages.length, messagesBeforePassive + 1, 'reminder dispatch remains durably deduplicated across reload');
  write(path.join(actionRoot, 'bridge-status.json'), { run_id: 'Test-action', status: 'cancelled', cycle: 1 });
  for (const kind of ['notice', 'review']) {
    write(path.join(actionRoot, 'pi-inbox', `late-${kind}.message.json`), { protocol_version: 2, schema_version: 1, id: `Test-late-${kind}`, run_id: 'Test-action', session_id: 'Test-session', kind, trigger_turn: kind === 'review', notice_type: 'waiting', message: 'Test stale queued work after cancellation', receipt: path.join(actionRoot, 'Test-late-receipt') });
  }
  await hooks.get('model_select')({}, actionContext);
  assert.equal(messages.length, messagesBeforePassive + 1, 'cancellation suppresses stale queued reviews and reminders');
  for (const kind of ['notice', 'review']) assert.equal(JSON.parse(fs.readFileSync(path.join(actionRoot, 'pi-inbox', `late-${kind}.delivery.json`), 'utf8')).status, 'suppressed_terminal');
  // The interactive path selects authority explicitly; ordinary questions never become Core input.
  const dialogRoot = path.join(root, 'Test-human-dialog');
  const otherDialogRoot = path.join(root, 'Test-other-human-dialog');
  const dialogState = { run_id: 'Test-dialog', execution: 'wait', wait: { source: 'human-response', reference: 'Q1' }, blockers: { B1: { status: 'open', needed: 'Configure Test service securely' } }, requests: { Qold: { main_extension: true, main_grant_count: 0 }, Q1: { main_extension: true, main_grant_count: 0, blocker_ids: ['B1'] } }, grants: [] };
  for (const [dir, runId] of [[dialogRoot, 'Test-dialog'], [otherDialogRoot, 'Test-other-dialog']]) {
    write(path.join(dir, 'config.json'), { run_id: runId, protocol_version: 2, schema_version: 1, mode: runId === 'Test-dialog' ? 'goal' : 'ralph', goal_tokens: 150000, review_execution: 'headless', review_transport: 'pi', pi_session_id: 'Test-session' });
    write(path.join(dir, 'execution-state.json'), { ...dialogState, run_id: runId });
    write(path.join(dir, 'bridge-status.json'), { run_id: runId, status: 'waiting_human', reason: 'Test addressed request', cycle: 1 });
  }
  const dialogContext = { ...ctx, sessionManager: { getSessionId: () => 'Test-session', getEntries: () => [dialogRoot, otherDialogRoot].map((dir, index) => ({ type: 'custom', customType: 'pi-reviewed-run', data: { root: dir, runId: index ? 'Test-other-dialog' : 'Test-dialog', sessionId: 'Test-session' } })) } };
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, dialogContext);
  const dialogFiles = () => fs.existsSync(path.join(dialogRoot, 'human-inbox')) ? fs.readdirSync(path.join(dialogRoot, 'human-inbox')) : [];
  const dialogRespond = args => commands.get('ppp-respond').handler(args, dialogContext);
  const chooseRun = (_title, options) => options.find(label => label.startsWith('Test-human-dialog —'));
  const chooseAction = prefix => (_title, options) => options.find(label => label.startsWith(prefix));
  const beforeDialogs = userMessages.length;
  await dialogRespond('');
  assert.equal(dialogFiles().length, 0, 'cancelling run selection records nothing');
  selectAnswers.push(chooseRun, chooseAction('Explain current status'));
  await dialogRespond('');
  assert.match(String(notices.at(-1)[0]), /Test addressed request/);
  assert.equal(dialogFiles().length, 0, 'explaining status records no authority');
  await dialogRespond('в чём проблема?');
  assert.match(String(notices.at(-1)[0]), /Questions are not authorizations/);
  assert.doesNotMatch(String(notices.at(-1)[0]), /SyntaxError/);
  selectAnswers.push(chooseAction('Answer request:'));
  inputAnswers.push('Test configured without secrets');
  confirmAnswers.push(false);
  await dialogRespond('Test-human-dialog');
  assert.equal(dialogFiles().length, 0, 'declining the action confirmation records nothing');
  selectAnswers.push(chooseRun, chooseAction('Answer request:'));
  inputAnswers.push('Test configured securely');
  confirmAnswers.push((_title, message) => { assert.match(message, /Action: Answer an addressed request/); assert.match(message, /Addresses: B1/); assert.doesNotMatch(message, /\{"kind"/); return true; });
  await dialogRespond('');
  await waitForChild();
  assert.equal(dialogFiles().length, 1);
  const dialogResolution = JSON.parse(fs.readFileSync(path.join(dialogRoot, 'human-inbox', dialogFiles()[0]), 'utf8'));
  assert.deepEqual(dialogResolution.blocker_ids, ['B1']);
  assert.equal(dialogResolution.kind, 'resolution');
  assert.equal(dialogResolution.run_id, 'Test-dialog');
  assert.equal(JSON.parse(fs.readFileSync(path.join(dialogRoot, 'execution-state.json'), 'utf8')).blockers.B1.status, 'open');
  await dialogRespond('Test-dialog {broken json');
  assert.match(String(notices.at(-1)[0]), /Use \/ppp-respond without arguments/);
  assert.doesNotMatch(String(notices.at(-1)[0]), /SyntaxError/);
  assert.equal(dialogFiles().length, 1, 'malformed advanced input has a friendly menu fallback and records nothing');
  selectAnswers.push(chooseAction('Answer request:'));
  inputAnswers.push('RESEND_API_KEY=Test-not-a-real-key');
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 1, 'interactive text retains secret rejection');
  for (const invalid of ['0', '1.5']) {
    selectAnswers.push(chooseAction('Continue work — choose another number of Goal launches'));
    inputAnswers.push(invalid);
    await dialogRespond('Test-dialog');
    assert.equal(dialogFiles().length, 1, 'Goal launch count must be a positive whole number');
  }
  const dialogConfig = JSON.parse(fs.readFileSync(path.join(dialogRoot, 'config.json'), 'utf8'));
  write(path.join(dialogRoot, 'config.json'), { ...dialogConfig, goal_tokens: undefined });
  selectAnswers.push((_title, options) => {
    assert.ok(options.includes('Continue work — add 1 Goal launch'));
    assert.ok(options.includes('Continue work — add 3 Goal launches'));
    assert.ok(!options.some(label => /tokens/.test(label)), 'no token labels without goal_tokens');
    return options.find(label => label === 'Continue work — choose another number of Goal launches');
  });
  inputAnswers.push((_title, placeholder) => { assert.doesNotMatch(placeholder, /tokens|multiple/); return '2'; });
  confirmAnswers.push((_title, message) => { assert.match(message, /2 additional Goal launches/); assert.doesNotMatch(message, /tokens|Total Goal limit/); return false; });
  await dialogRespond('Test-dialog');
  write(path.join(dialogRoot, 'config.json'), dialogConfig);
  assert.equal(dialogFiles().length, 1, 'declining an uncapped Goal launch grant records nothing');
  selectAnswers.push(chooseAction('Continue work — choose another number of Goal launches'));
  inputAnswers.push('2');
  confirmAnswers.push((_title, message) => { assert.match(message, /2 additional Goal launches and 300,000 additional Goal tokens/); return false; });
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 1, 'manual Goal launch count need not be a token multiple');
  selectAnswers.push((_title, options) => { assert.equal(options.filter(label => label === 'Continue work — add 3 Goal launches and 450,000 Goal tokens').length, 1); return options.find(label => label === 'Continue work — add 3 Goal launches and 450,000 Goal tokens'); });
  confirmAnswers.push(() => { write(path.join(dialogRoot, 'execution-state.json'), { ...dialogState, grants: [{ request_id: 'Test-other' }] }); return true; });
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 1, 'a changed request generation cannot be authorized');
  write(path.join(dialogRoot, 'execution-state.json'), dialogState);
  selectAnswers.push(chooseAction('Continue work — add 3 Goal launches and 450,000 Goal tokens'));
  confirmAnswers.push(() => { write(path.join(dialogRoot, 'execution-state.json'), { ...dialogState, wait: { source: 'human-response', reference: 'Qold' } }); return true; });
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 1, 'a changed current request cannot be authorized');
  write(path.join(dialogRoot, 'execution-state.json'), dialogState);
  const fundedState = { ...dialogState, grants: [{ scope: 'main', authority: 'initial-contract', max_cycles: 1 }, { scope: 'closure', authority: 'initial-contract', max_cycles: null }, { scope: 'main', authority: 'Test-prior', max_cycles: 2 }], requests: { Q1: { main_extension: true, main_grant_count: 3 } } };
  write(path.join(dialogRoot, 'execution-state.json'), fundedState);
  selectAnswers.push(chooseAction('Continue work — add 3 Goal launches and 450,000 Goal tokens'));
  confirmAnswers.push((_title, message) => { assert.match(message, /Total Goal limit: 900,000 tokens/); return false; });
  await dialogRespond('Test-dialog');
  write(path.join(dialogRoot, 'execution-state.json'), dialogState);
  assert.equal(dialogFiles().length, 1, 'declining a budget grant records nothing');
  selectAnswers.push(chooseAction('Continue work — add 3 Goal launches and 450,000 Goal tokens'));
  confirmAnswers.push((title, message) => { assert.equal(title, 'Continue work?'); assert.match(message, /3 additional Goal launches and 450,000 additional Goal tokens/); assert.doesNotMatch(message, /Q1|cycles/); return true; });
  await dialogRespond('Test-dialog');
  await waitForChild();
  assert.equal(dialogFiles().length, 2);
  const grant = dialogFiles().map(file => JSON.parse(fs.readFileSync(path.join(dialogRoot, 'human-inbox', file), 'utf8'))).find(row => row.kind === 'grant');
  assert.equal(grant.cycles, 3);
  assert.equal(grant.request_id, 'Q1');
  selectAnswers.push(chooseAction('Continue work — add 3 Goal launches and 450,000 Goal tokens'));
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 2, 'pending grants cannot be duplicated through the menu');
  selectAnswers.push(chooseAction('Cancel this run'));
  inputAnswers.push('Test cancel after state changes');
  confirmAnswers.push(() => { write(path.join(dialogRoot, 'execution-state.json'), { ...dialogState, execution: 'finish' }); return true; });
  await dialogRespond('Test-dialog');
  assert.equal(dialogFiles().length, 2, 'a run finishing during confirmation cannot be woken by a late instruction');
  assert.equal(fs.existsSync(path.join(otherDialogRoot, 'human-inbox')), false, 'other runs receive no instruction before being selected');
  // Only the other run remains active: no UUID or run selector is needed.
  const selectorsBeforeSoleRun = selectCalls.length;
  selectAnswers.push((_title, options) => { assert.ok(options.includes('Continue work — add 1 Worker iteration')); assert.ok(options.includes('Continue work — add 3 Worker iterations')); return options.find(label => label.startsWith('Send a message')); });
  inputAnswers.push('Test non-authorizing message');
  confirmAnswers.push(true);
  await dialogRespond('');
  await waitForChild();
  assert.equal(selectCalls.length, selectorsBeforeSoleRun + 1, 'a single active run skips only the run selector, never action selection');
  const otherFiles = () => fs.readdirSync(path.join(otherDialogRoot, 'human-inbox'));
  assert.equal(otherFiles().length, 1);
  const signal = JSON.parse(fs.readFileSync(path.join(otherDialogRoot, 'human-inbox', otherFiles()[0]), 'utf8'));
  assert.equal(signal.kind, 'signal');
  assert.equal(signal.run_id, 'Test-other-dialog');
  assert.equal(Object.hasOwn(signal, 'cycles'), false, 'plain messages cannot grant cycles');
  selectAnswers.push(chooseAction('Continue work — choose another number'));
  inputAnswers.push('1,5');
  await dialogRespond('Test-other-dialog');
  assert.equal(otherFiles().length, 1, 'ambiguous separators cannot increase a grant');
  selectAnswers.push(chooseAction('Continue work — add 3 Worker iterations'));
  confirmAnswers.push((_title, message) => { assert.match(message, /3 additional Worker iterations/); assert.doesNotMatch(message, /tokens|Q1/); return true; });
  await dialogRespond('Test-other-dialog');
  await waitForChild();
  assert.equal(otherFiles().length, 2);
  assert.ok(otherFiles().map(file => JSON.parse(fs.readFileSync(path.join(otherDialogRoot, 'human-inbox', file), 'utf8'))).some(row => row.kind === 'grant' && row.cycles === 3));
  selectAnswers.push(chooseAction('Cancel this run'));
  inputAnswers.push(undefined);
  await dialogRespond('');
  assert.equal(otherFiles().length, 2, 'cancelling text entry records nothing');
  selectAnswers.push(chooseAction('Cancel this run'));
  inputAnswers.push('Test explicit cancellation');
  confirmAnswers.push((_title, message) => { assert.match(message, /Cancel\/halt stops the run, not a pause/); return true; });
  await dialogRespond('');
  await waitForChild();
  assert.equal(otherFiles().length, 3);
  assert.ok(otherFiles().map(file => JSON.parse(fs.readFileSync(path.join(otherDialogRoot, 'human-inbox', file), 'utf8'))).some(row => row.kind === 'cancel'));
  const beforeRPCDialog = selectCalls.length;
  await commands.get('ppp-respond').handler('', { ...dialogContext, mode: 'rpc' });
  assert.equal(selectCalls.length, beforeRPCDialog, 'RPC cannot open a human authority dialog');
  write(path.join(otherDialogRoot, 'execution-state.json'), { ...dialogState, run_id: 'Test-other-dialog', execution: 'cancelled' });
  await dialogRespond('');
  assert.match(String(notices.at(-1)[0]), /No active protocol-2 run is attached/);
  assert.equal(otherFiles().length, 3, 'no-active-run guidance does not restart a terminal run');
  assert.equal(userMessages.length, beforeDialogs, 'dialogs and status explanation never call a model');
  // Status defaults to this chat, includes terminal runs, and reveals technical output only on demand.
  write(path.join(dialogRoot, 'bridge-status.json'), { run_id: 'Test-dialog', status: 'complete', phase: 'finish', cycle: 4, main_remaining: 6, worker_tokens: 148808, goal_usage_status: 'known' });
  write(path.join(otherDialogRoot, 'bridge-status.json'), { run_id: 'Test-other-dialog', status: 'attention_required', phase: 'verification_blocked', cycle: 0, reason: 'Test required evidence is missing' });
  makeRun('test-unrelated-status', { status: 'complete' });
  const statusBefore = fs.readFileSync(path.join(dialogRoot, 'execution-state.json'), 'utf8');
  const otherStatusBefore = fs.readFileSync(path.join(otherDialogRoot, 'execution-state.json'), 'utf8');
  const statusModelsBefore = userMessages.length;
  const statusMessagesBefore = messages.length;
  const selectCompletedStatus = (_title, options) => {
    assert.ok(options.some(row => row.includes('Test-human-dialog — completed · cycles 4')), 'terminal runs remain visible for inspection');
    assert.ok(options.some(row => row.includes('Test-other-human-dialog — attention required')), 'blocked runs remain visible');
    assert.ok(!options.some(row => row.includes('test-unrelated-status')), 'unattached project runs are absent by default');
    assert.ok(options.every(row => !row.includes(root) && !row.includes('Protocol:') && !row.includes('Config:')), 'list rows omit paths and diagnostics');
    return options.find(row => row.includes('Test-human-dialog —'));
  };
  const beforeDefaultSelectors = selectCalls.length;
  selectAnswers.push(selectCompletedStatus, 'Done');
  await commands.get('ppp-status').handler('', { ...dialogContext, cwd: path.join(root, 'Test-absent-project') });
  assert.equal(selectCalls.length, beforeDefaultSelectors + 2, 'chat status needs no project discovery or root-confirmation dialog');
  const compactComplete = String(notices.at(-1)[0]);
  assert.match(compactComplete, /Test-human-dialog — completed/);
  assert.match(compactComplete, /Cycles: 4 · Main remaining: 6/);
  assert.match(compactComplete, /Goal tokens: 148808 recorded/);
  assert.match(compactComplete, /No further action/);
  assert.doesNotMatch(compactComplete, /Directory:|Config:|Launcher log:|Protocol:|Reviewer:/);
  assert.ok(compactComplete.split('\n').length <= 5, 'selected summary is bounded and compact');
  write(path.join(dialogRoot, 'bridge-status.json'), { run_id: 'Test-dialog', status: 'complete', phase: 'finish', cycle: 4, main_remaining: 300000, worker_tokens: 0, goal_usage_status: 'unknown' });
  selectAnswers.push(selectCompletedStatus, 'Done');
  await commands.get('ppp-status').handler('', dialogContext);
  assert.match(String(notices.at(-1)[0]), /Main remaining: unknown/);
  assert.match(String(notices.at(-1)[0]), /0 recorded; actual usage unknown/);
  assert.doesNotMatch(String(notices.at(-1)[0]), /Main remaining: 300000/);
  selectAnswers.push((_title, options) => options.find(row => row.includes('Test-other-human-dialog —')), 'Done');
  await commands.get('ppp-status').handler('', dialogContext);
  assert.match(String(notices.at(-1)[0]), /Test required evidence is missing/);
  selectAnswers.push(selectCompletedStatus, 'Technical details');
  await commands.get('ppp-status').handler('', dialogContext);
  const selectedTechnical = String(notices.at(-1)[0]);
  assert.match(selectedTechnical, /Directory: .*Test-human-dialog/);
  assert.equal((selectedTechnical.match(/Config:/g) ?? []).length, 1, 'technical details are for the selected run only');
  assert.doesNotMatch(selectedTechnical, /Test-other-human-dialog/);
  selectAnswers.push('All runs in this project…', (_title, options) => {
    assert.ok(options.some(row => row.includes('test-unrelated-status — completed')), 'project scope is explicitly available');
    assert.equal(options.filter(row => row.includes('Test-human-dialog —')).length, 1, 'attached runs are deduplicated');
    return options.find(row => row.includes('test-unrelated-status —'));
  }, 'Done');
  await commands.get('ppp-status').handler('', dialogContext);
  assert.match(String(notices.at(-1)[0]), /test-unrelated-status — completed/);
  const noUISelects = selectCalls.length;
  await commands.get('ppp-status').handler('', { ...dialogContext, hasUI: false, mode: 'rpc' });
  assert.equal(selectCalls.length, noUISelects, 'non-TUI status falls back to compact text without dialogs');
  assert.doesNotMatch(String(notices.at(-1)[0]), /test-unrelated-status|Config:|Protocol:/);
  assert.equal(fs.readFileSync(path.join(dialogRoot, 'execution-state.json'), 'utf8'), statusBefore);
  assert.equal(fs.readFileSync(path.join(otherDialogRoot, 'execution-state.json'), 'utf8'), otherStatusBefore);
  assert.equal(userMessages.length, statusModelsBefore, 'status does not invoke parent models');
  assert.equal(messages.length, statusMessagesBefore, 'status does not queue reporter or reviewer turns');
  const emptyStatusContext = { ...dialogContext, sessionManager: { getSessionId: () => 'Test-empty-status', getEntries: () => [] } };
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({}, emptyStatusContext);
  selectAnswers.push((_title, options) => { assert.deepEqual(options, ['All runs in this project…']); return undefined; });
  await commands.get('ppp-status').handler('', emptyStatusContext);
  console.log('Pi receiver: scoped status menus, interactive human actions, legacy contracts, private receipts and passive durable reminders passed.');
} finally {
  await hooks.get('session_shutdown')?.();
  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(childMarker, { force: true });
  if (previousBridge === undefined) delete process.env.PI_PING_PONG_BRIDGE; else process.env.PI_PING_PONG_BRIDGE = previousBridge;
  if (previousHome === undefined) delete process.env.HOME; else process.env.HOME = previousHome;
}
