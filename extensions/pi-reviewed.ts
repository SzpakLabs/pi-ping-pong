import { spawn, execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { randomUUID } from 'node:crypto';
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from '@earendil-works/pi-coding-agent';

type Binding = { root: string; runId: string; sessionId: string };
type Config = { run_id: string; review_model: string; review_provider?: string; [key: string]: unknown };
type Envelope = { id: string; run_id: string; session_id: string; kind: string; message: string; receipt: string };
type Project = { root: string; fallback: boolean; git: boolean };
type RunState = 'draft/incomplete' | 'ready to launch' | 'running' | 'waiting review' | 'waiting human' | 'completed' | 'stopped' | 'attention required' | 'unknown/malformed';
type RunInfo = { name: string; dir?: string; state: RunState; mode?: string; worker?: string; reviewer?: string; details?: string; config?: Config };
const entryType = 'pi-reviewed-run';
const maxRunNameLength = 48;
const runNamePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const read = <T>(file: string): T => JSON.parse(fs.readFileSync(file, 'utf8')) as T;
function atomic(file: string, data: unknown) {
  const temporary = `${file}.${process.pid}.${randomUUID()}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(data, null, 2)}\n`, { mode: 0o600, flag: 'wx' });
  fs.chmodSync(temporary, 0o600);
  fs.renameSync(temporary, file);
}
function isPrivate(stat: fs.Stats) { return (stat.mode & 0o077) === 0; }
function regularFile(file: string) {
  try { const stat = fs.lstatSync(file); return stat.isFile() && !stat.isSymbolicLink() && stat.size > 0; }
  catch { return false; }
}
function regularPrivateFile(file: string) {
  try {
    const stat = fs.lstatSync(file);
    return stat.isFile() && !stat.isSymbolicLink() && (stat.mode & 0o777) === 0o600 && stat.size > 0;
  } catch { return false; }
}
function regularPrivateRunFile(runDir: string, file: string) {
  if (!inside(runDir, file)) return false;
  let current = runDir;
  for (const part of path.relative(runDir, file).split(path.sep)) {
    current = path.join(current, part);
    try {
      const stat = fs.lstatSync(current);
      if (stat.isSymbolicLink()) return false;
      if (current === file) return stat.isFile() && (stat.mode & 0o777) === 0o600 && stat.size > 0;
      if (!stat.isDirectory() || !isPrivate(stat)) return false;
    } catch { return false; }
  }
  return false;
}
function validRunName(name: string) { return name.length <= maxRunNameLength && runNamePattern.test(name); }
function displayValue(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value !== 'string') return '—';
  const safe = value.replace(/[\r\n\t\x00-\x1f]/g, ' ').slice(0, 160);
  return /(?:\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9_]{12,}|\bbearer\s+\S+|(?:api[_-]?key|secret|token)\s*[:=])/i.test(safe) ? '[redacted]' : safe;
}
function inside(parent: string, child: string) {
  const relative = path.relative(parent, child);
  return relative !== '' && !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}
function assertPrivateDirectoryChain(root: string, target: string, create: boolean) {
  const resolvedRoot = fs.realpathSync(root);
  const resolvedTarget = path.resolve(target);
  if (!inside(resolvedRoot, resolvedTarget)) throw new Error('Run storage path escapes the confirmed project root.');
  const relative = path.relative(resolvedRoot, resolvedTarget).split(path.sep);
  let current = resolvedRoot;
  for (const part of relative) {
    current = path.join(current, part);
    try {
      const stat = fs.lstatSync(current);
      if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`Refusing non-directory or symlink in private run path: ${current}`);
      if (!isPrivate(stat)) throw new Error(`Private run directory has permissive permissions: ${current}`);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT' || !create) throw error;
      fs.mkdirSync(current, { mode: 0o700 });
      fs.chmodSync(current, 0o700);
      const stat = fs.lstatSync(current);
      if (!stat.isDirectory() || stat.isSymbolicLink() || !isPrivate(stat)) throw new Error(`Could not create a private run directory: ${current}`);
    }
  }
}
function existingPrivateDirectoryChain(root: string, target: string) {
  const resolvedRoot = fs.realpathSync(root);
  const resolvedTarget = path.resolve(target);
  if (!inside(resolvedRoot, resolvedTarget)) throw new Error('Run storage path escapes the confirmed project root.');
  let current = resolvedRoot;
  for (const part of path.relative(resolvedRoot, resolvedTarget).split(path.sep)) {
    current = path.join(current, part);
    try {
      const stat = fs.lstatSync(current);
      if (!stat.isDirectory() || stat.isSymbolicLink() || !isPrivate(stat)) throw new Error(`Refusing non-private or symlink run storage: ${current}`);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
      throw error;
    }
  }
  return true;
}
function runStorage(project: Project) {
  return project.fallback
    ? path.join(project.root, '.pi', 'reviewed-runs', 'named')
    : path.join(project.root, '.pi-ping-pong', 'runs');
}
function ignoredByGit(project: Project, name: string) {
  if (!project.git || project.fallback) return true;
  try {
    execFileSync('git', ['-C', project.root, 'check-ignore', '-q', '--', `.pi-ping-pong/runs/${name}`], { stdio: 'ignore' });
    return true;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException & { status?: number }).status;
    if (code === 1) return false;
    throw new Error('Could not verify Git ignore status for private run artifacts.');
  }
}
async function resolveProject(ctx: ExtensionContext): Promise<Project | undefined> {
  try {
    const root = execFileSync('git', ['-C', ctx.cwd, 'rev-parse', '--show-toplevel'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    return { root: fs.realpathSync(root), fallback: false, git: true };
  } catch {
    if (!ctx.hasUI) {
      ctx.ui.notify('No Git project root found. No project runs were read or created. Use a Git project or a UI-enabled Pi session to confirm a project folder/private fallback.', 'warning');
      return undefined;
    }
    const cwd = path.resolve(ctx.cwd);
    if (fs.existsSync(cwd) && fs.statSync(cwd).isDirectory() && await ctx.ui.confirm('Use this folder as the project root?', `${cwd}\nNo Git repository was found. Confirm only if this is the intended project root.`)) {
      return { root: fs.realpathSync(cwd), fallback: false, git: false };
    }
    const fallback = path.join(os.homedir(), '.pi', 'reviewed-runs');
    if (await ctx.ui.confirm('Use the private fallback run store?', `No project root was confirmed. Named runs will be stored under ${fallback}/named/<name>/; existing legacy runs remain untouched.`)) {
      return { root: fs.realpathSync(os.homedir()), fallback: true, git: false };
    }
    return undefined;
  }
}
function statusLabel(value: unknown): RunState | undefined {
  if (value === 'running' || value === 'starting') return 'running';
  if (value === 'waiting_pi' || value === 'waiting_codex') return 'waiting review';
  if (value === 'waiting_human') return 'waiting human';
  if (value === 'complete') return 'completed';
  if (value === 'stopped') return 'stopped';
  if (value === 'attention_required') return 'attention required';
  return undefined;
}
function inspectRun(name: string, dir: string): RunInfo {
  let dirStat: fs.Stats;
  try { dirStat = fs.lstatSync(dir); } catch { return { name, dir, state: 'unknown/malformed', details: 'Run directory is unavailable.' }; }
  if (!dirStat.isDirectory() || dirStat.isSymbolicLink() || !isPrivate(dirStat)) {
    return { name, dir, state: 'unknown/malformed', details: 'Run directory is not a private, regular directory.' };
  }
  let entries: string[];
  try { entries = fs.readdirSync(dir); } catch { return { name, dir, state: 'unknown/malformed', details: 'Run directory cannot be listed.' }; }
  let config: Config | undefined;
  if (entries.includes('config.json')) {
    if (!regularPrivateFile(path.join(dir, 'config.json'))) return { name, dir, state: 'unknown/malformed', details: 'config.json is not a private regular file.' };
    try { config = read<Config>(path.join(dir, 'config.json')); }
    catch { return { name, dir, state: 'unknown/malformed', details: 'config.json is malformed.' }; }
    if (!config || typeof config !== 'object' || Array.isArray(config)) return { name, dir, state: 'unknown/malformed', details: 'config.json is not an object.' };
  }
  const attempted = entries.includes('launch-attempt.json') || entries.includes('bridge-status.json') || Boolean(config?.pi_session_id);
  const mode = config && typeof config.mode === 'string' ? displayValue(config.mode) : undefined;
  const worker = config ? `${displayValue(config.worker_provider)}/${displayValue(config.worker_model)}` : undefined;
  const reviewer = config ? `${displayValue(config.review_provider)}/${displayValue(config.review_model)}` : undefined;
  if (attempted) {
    if (!config) return { name, dir, state: 'unknown/malformed', mode, worker, reviewer, details: 'A launch record exists but config.json is missing or malformed.', config };
    if (!entries.includes('bridge-status.json')) return { name, dir, state: 'attention required', mode, worker, reviewer, details: 'A launch was recorded but no bridge status is available; never replay automatically.', config };
    if (!regularFile(path.join(dir, 'bridge-status.json'))) return { name, dir, state: 'unknown/malformed', mode, worker, reviewer, details: 'bridge-status.json is not a regular non-symlink file.', config };
    try {
      const status = read<{ run_id?: unknown; status?: unknown }>(path.join(dir, 'bridge-status.json'));
      if (!status || typeof status !== 'object' || Array.isArray(status)) return { name, dir, state: 'unknown/malformed', mode, worker, reviewer, details: 'bridge-status.json is not an object.', config };
      const label = status.run_id === config.run_id ? statusLabel(status.status) : undefined;
      if (label) return { name, dir, state: label, mode, worker, reviewer, details: `Bridge status: ${String(status.status)}.`, config };
      return { name, dir, state: 'unknown/malformed', mode, worker, reviewer, details: 'Bridge status is malformed or has a different run identity.', config };
    } catch { return { name, dir, state: 'unknown/malformed', mode, worker, reviewer, details: 'bridge-status.json is malformed.', config }; }
  }
  if (!config) return { name, dir, state: 'draft/incomplete', details: 'No config.json yet.' };
  const requiredStrings = [config.run_id, config.mode, config.worker_provider, config.worker_model, config.review_provider, config.review_model, config.task];
  const bounds = ['max_cycles', 'cycle_seconds', 'review_seconds', 'wall_seconds'].map(key => config[key]);
  const argv = config.eval_argv;
  const taskFile = typeof config.task === 'string' ? path.resolve(dir, config.task) : '';
  const evalFile = Array.isArray(argv) && typeof argv[1] === 'string' ? path.resolve(dir, 'work', argv[1]) : '';
  const incomplete: string[] = [];
  if (!requiredStrings.every(value => typeof value === 'string' && value.trim().length > 0)) incomplete.push('required config fields');
  if (!uuidPattern.test(String(config.run_id))) incomplete.push('UUID run_id');
  if (!['goal', 'ralph'].includes(String(config.mode))) incomplete.push('mode');
  if (!bounds.every(value => Number.isSafeInteger(value) && Number(value) > 0)) incomplete.push('positive finite bounds');
  if (!Array.isArray(argv) || argv.length < 2 || !argv.every(value => typeof value === 'string' && value.length > 0)) incomplete.push('eval_argv');
  if (config.review_transport !== 'pi' || config.pi_session_id !== undefined || config.thread_id !== undefined) incomplete.push('unbound Pi config');
  if (!inside(dir, taskFile) || !regularPrivateRunFile(dir, taskFile)) incomplete.push('private TASK file');
  if (!inside(dir, evalFile) || !regularPrivateRunFile(dir, evalFile)) incomplete.push('private evaluator file');
  if (!regularPrivateFile(path.join(dir, 'config.json'))) incomplete.push('private config file');
  if (!incomplete.length) return { name, dir, state: 'ready to launch', mode, worker, reviewer, details: 'TASK, independent eval, UUID run_id, models and finite limits are present.', config };
  return { name, dir, state: 'draft/incomplete', mode, worker, reviewer, details: `Preparation is incomplete: ${incomplete.join(', ')}.`, config };
}
function listRuns(project: Project): RunInfo[] {
  const parent = runStorage(project);
  if (!existingPrivateDirectoryChain(project.root, parent)) return [];
  const stat = fs.lstatSync(parent);
  if (!stat.isDirectory() || stat.isSymbolicLink() || !isPrivate(stat)) throw new Error('Run storage must be a private, non-symlink directory.');
  const runs = fs.readdirSync(parent, { withFileTypes: true }).map(entry => {
    if (!validRunName(entry.name)) return { name: '[invalid run name]', dir: undefined, state: 'unknown/malformed' as const, details: 'A direct entry has an unsafe or unsupported name.' };
    if (entry.isSymbolicLink() || !entry.isDirectory()) return { name: entry.name, state: 'unknown/malformed' as const, details: 'Entry is not a regular run directory.' };
    return inspectRun(entry.name, path.join(parent, entry.name));
  });
  const ids = new Map<string, RunInfo[]>();
  for (const run of runs) {
    const id = run.config?.run_id;
    if (typeof id === 'string') ids.set(id, [...(ids.get(id) ?? []), run]);
  }
  for (const duplicates of ids.values()) {
    if (duplicates.length > 1) for (const run of duplicates) {
      run.state = 'unknown/malformed';
      run.details = 'Duplicate run_id detected in this project; launch is refused.';
    }
  }
  return runs;
}
function verifyNamedRun(project: Project, name: string, dir: string) {
  if (!validRunName(name)) throw new Error('Unsafe named run.');
  if (!ignoredByGit(project, name)) throw new Error(`Private run artifacts are not Git-ignored. Add .pi-ping-pong/ to ${project.root}/.gitignore and verify with git check-ignore before preparation or launch.`);
  assertPrivateDirectoryChain(project.root, runStorage(project), false);
  const expected = path.join(runStorage(project), name);
  if (path.resolve(dir) !== path.resolve(expected)) throw new Error('Named run path does not match its reserved project location.');
  const stat = fs.lstatSync(expected);
  if (!stat.isDirectory() || stat.isSymbolicLink() || (stat.mode & 0o777) !== 0o700) throw new Error('Named run directory is not a private 0700 directory.');
}
function reserveRun(project: Project, name: string) {
  if (!validRunName(name)) throw new Error(`Run name must be ASCII lowercase kebab-case, 1–${maxRunNameLength} characters (example: add-linters-2).`);
  if (!ignoredByGit(project, name)) throw new Error(`Private run artifacts are not Git-ignored. Add .pi-ping-pong/ to ${project.root}/.gitignore, verify with git check-ignore, then retry; no run was created.`);
  const parent = runStorage(project);
  assertPrivateDirectoryChain(project.root, parent, true);
  const dir = path.join(parent, name);
  fs.mkdirSync(dir, { mode: 0o700 }); // exclusive: EEXIST is never overwritten
  fs.chmodSync(dir, 0o700);
  const dirStat = fs.lstatSync(dir);
  if (!dirStat.isDirectory() || dirStat.isSymbolicLink() || (dirStat.mode & 0o777) !== 0o700) throw new Error('Could not reserve a private run directory.');
  const marker = path.join(dir, '.draft.json');
  const fd = fs.openSync(marker, 'wx', 0o600);
  try { fs.writeFileSync(fd, `${JSON.stringify({ name, project_root: project.root, created_at: new Date().toISOString() }, null, 2)}\n`); fs.fchmodSync(fd, 0o600); }
  finally { fs.closeSync(fd); }
  return dir;
}
function draftFiles(dir: string) {
  return fs.readdirSync(dir, { withFileTypes: true }).filter(entry => entry.isFile() && !entry.isSymbolicLink()).map(entry => entry.name).sort();
}
function preparationPrompt(project: Project, name: string, dir: string, continuation: boolean, reviewerDefault: string) {
  const files = continuation ? draftFiles(dir).filter(file => file !== '.draft.json') : [];
  return `Prepare a Pi Ping Pong run from this conversation. Reuse all task details, criteria, project context, and decisions already provided; ask only concise grouped questions for missing information. The run name is an identifier, not a complete task description. Do not start or launch the worker during preparation.\n\nConfirmed project root: ${project.root}\nSelected run name: ${name}\nExact reserved private run directory: ${dir}\n${project.fallback ? 'This is the explicitly confirmed private fallback store; do not use the project cwd.' : ''}\n${continuation ? `This is an incomplete existing run. Existing entries (read each listed regular file into context before deciding whether any change is needed): ${files.length ? files.join(', ') : '(none)'}. Do not overwrite existing files blindly; preserve valid content and write only missing/verified updates. It has never been launched, and this preparation must not touch any launched run/evidence.` : 'This directory was exclusively reserved for this new run.'}\n\nWrite only this run's TASK.md, config.json, and independent task-specific eval.py inside the exact reserved directory above. Do not use another run directory, do not create run files elsewhere, and do not overwrite .draft.json. Use already supplied conversation data; if essential inputs remain missing, ask instead of writing placeholder/fake values. Confirm the project root and allowed filesystem paths with the user; only the approved target paths may be modified by the worker.\n\nThe prepared TASK.md must state the actual task and independently checkable acceptance criteria. config.json must contain a unique RFC 4122 UUID run_id (UUID is for run_id only; do not put a UUID in the folder name), mode goal|ralph, explicit user-chosen worker_provider and worker_model (never guess the worker model), reviewer provider and model (suggest ${reviewerDefault}, but confirm the exact provider/model), the task path, eval_argv invoking the evaluator by its absolute path, and positive finite integer max_cycles, cycle_seconds, review_seconds, and wall_seconds. Do not invent an eval that always succeeds. The independent evaluator must check actual task-specific outputs/state, map every acceptance criterion to a check, and return nonzero for unmet criteria; clarify criteria that cannot be independently evaluated. Use review_transport=pi. Do not write pi_session_id, create launch-attempt.json, or attach a session entry; the launcher binds the session only when explicitly launched.\n\nKeep all run artifacts private: directory mode 0700 and TASK.md, config.json, eval.py mode 0600. Ensure paths are inside this exact run directory except explicitly user-approved task target paths. Do not copy secrets. Do not run the worker, Goal/Ralph, bridge, evaluator, or paid model-backed checks as part of preparation.\n\nWhen ready, report the task, checkable criteria, mode, worker/reviewer provider and models, allowed paths, evaluator command and criterion mapping, finite limits, exact run directory and config path. State explicitly that no worker was started and give the explicit launch command \`/pi-ping-pong ${name}\`. If incomplete, report only missing inputs and preserve the draft for continuation.`;
}
function sendPreparation(pi: ExtensionAPI, ctx: ExtensionCommandContext, project: Project, name: string, dir: string, continuation: boolean) {
  try { verifyNamedRun(project, name, dir); }
  catch (error) { ctx.ui.notify(String(error), 'error'); return; }
  const reviewerDefault = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : 'no Pi model is selected';
  const prompt = preparationPrompt(project, name, dir, continuation, reviewerDefault);
  pi.sendUserMessage(prompt, ctx.isIdle() ? undefined : { deliverAs: 'followUp' });
  ctx.ui.notify(`Preparation prompt sent for ${name}; no worker was started. After preparation, explicitly launch with /pi-ping-pong ${name}.`, 'info');
}
function details(info: RunInfo) {
  const config = info.config;
  const bounds = config
    ? `Limits: cycles=${displayValue(config.max_cycles)}, cycle_seconds=${displayValue(config.cycle_seconds)}, review_seconds=${displayValue(config.review_seconds)}, wall_seconds=${displayValue(config.wall_seconds)}`
    : '';
  return [
    `${info.name}: ${info.state}`,
    `Directory: ${info.dir ?? '(unsafe entry; not followed)'}`,
    `Config: ${info.dir ? path.join(info.dir, 'config.json') : '—'}`,
    `Mode: ${info.mode ?? '—'}`,
    `Worker: ${info.worker ?? '—'}`,
    `Reviewer: ${info.reviewer ?? '—'}`,
    bounds,
    info.details ?? '',
    info.state === 'ready to launch' ? `Explicit launch: /pi-ping-pong ${info.name}` : '',
  ].filter(Boolean).join('\n');
}
function formatRun(info: RunInfo) {
  return `${info.name} — ${info.state} — ${info.mode ?? 'mode unknown'} — ${info.worker ?? 'worker unknown'}`;
}
function isExplicitPath(argument: string) {
  return argument.startsWith('/') || argument.startsWith('./') || argument.startsWith('../') || argument.startsWith('~') || argument.includes('/') || argument.includes('\\') || path.basename(argument) === 'config.json';
}

export default function reviewedRuns(pi: ExtensionAPI) {
  let context: ExtensionContext | undefined;
  let bindings: Binding[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
  const warned = new Set<string>();
  function receiver(binding: Binding, connected: boolean) {
    atomic(path.join(binding.root, 'pi-receiver.json'), { run_id: binding.runId, session_id: binding.sessionId, connected, pid: process.pid });
  }
  function clear() {
    if (timer) clearInterval(timer);
    timer = undefined;
    for (const binding of bindings) {
      try { receiver(binding, false); } catch { /* Preserve pending queue if storage is unavailable. */ }
    }
    bindings = [];
    context = undefined;
    warned.clear();
  }
  function poll() {
    const ctx = context;
    if (!ctx) return;
    const sessionId = ctx.sessionManager.getSessionId();
    for (const binding of bindings) {
      if (sessionId !== binding.sessionId) continue;
      try {
        const config = read<Config>(path.join(binding.root, 'config.json'));
        if (config.run_id !== binding.runId || config.pi_session_id !== sessionId || config.review_transport !== 'pi') continue;
        const inbox = path.join(binding.root, 'pi-inbox');
        if (!fs.existsSync(inbox)) continue;
        const pending = fs.readdirSync(inbox).filter(name => name.endsWith('.message.json')).sort();
        for (const name of pending) {
          const file = path.join(inbox, name);
          const ack = file.replace(/\.message\.json$/, '.delivery.json');
          if (fs.existsSync(ack)) continue;
          const envelope = read<Envelope>(file);
          if (envelope.session_id !== sessionId || envelope.run_id !== binding.runId) {
            atomic(ack, { status: 'rejected_identity' });
            continue;
          }
          if (ctx.model?.id !== config.review_model || (config.review_provider && ctx.model?.provider !== config.review_provider)) {
            if (!warned.has(binding.runId)) {
              ctx.ui.notify(`Reviewed run ${binding.runId}: checkpoint held; select ${config.review_model} to review.`, 'warning');
              warned.add(binding.runId);
            }
            break;
          }
          atomic(ack, { status: 'dispatching', session_id: sessionId, id: envelope.id });
          pi.sendMessage({
            customType: 'reviewed-checkpoint',
            content: envelope.message.replaceAll('Codex', 'reviewer').replaceAll('this chat', 'this Pi session'),
            display: true,
            details: { run_id: binding.runId, message_id: envelope.id, kind: envelope.kind },
          }, { deliverAs: 'followUp', triggerTurn: true });
          atomic(ack, { status: 'enqueued_in_pi', session_id: sessionId, id: envelope.id, at: Date.now() });
        }
      } catch (error) {
        const key = `error:${binding.runId}`;
        if (!warned.has(key)) {
          ctx.ui.notify(`Reviewed queue ${binding.runId}: ${String(error)}`, 'error');
          warned.add(key);
        }
      }
    }
  }
  function startTimer() {
    if (!timer) {
      timer = setInterval(poll, 400);
      timer.unref?.();
    }
  }
  pi.on('session_start', async (_event, ctx) => {
    clear();
    context = ctx;
    const id = ctx.sessionManager.getSessionId();
    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type !== 'custom' || entry.customType !== entryType) continue;
      const value = entry.data as Binding;
      if (value?.sessionId !== id || bindings.some(b => b.root === value.root)) continue;
      try {
        const config = read<Config>(path.join(value.root, 'config.json'));
        if (config.run_id !== value.runId || config.pi_session_id !== id) continue;
        bindings.push(value);
        receiver(value, true);
      } catch { /* A removed run is not a reason to interrupt the user's session. */ }
    }
    startTimer();
    poll();
  });
  pi.on('session_shutdown', async () => clear());
  pi.on('model_select', async (_event, ctx) => { context = ctx; poll(); });

  const launchConfig = async (file: string, ctx: ExtensionCommandContext, namedRun?: { project: Project; name: string; dir: string }) => {
    if (namedRun) verifyNamedRun(namedRun.project, namedRun.name, namedRun.dir);
    if (path.basename(file) !== 'config.json') throw new Error('Expected an existing config.json path.');
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) throw new Error(`Config not found: ${file}`);
    const root = path.dirname(file);
    const config = read<Config>(file);
    if (!config.run_id || !config.review_model || !['goal', 'ralph'].includes(String(config.mode))) throw new Error('Config needs run_id, mode=goal|ralph and review_model.');
    if (ctx.model?.id !== config.review_model) throw new Error(`Select reviewer model ${config.review_model} before launch.`);
    if (config.review_provider && ctx.model?.provider !== config.review_provider) throw new Error(`Select reviewer provider ${config.review_provider} before launch.`);
    const attemptFile = path.join(root, 'launch-attempt.json');
    if (fs.existsSync(attemptFile) || fs.existsSync(path.join(root, 'bridge-status.json'))) throw new Error('Run already launched; inspect its state instead of replaying it.');
    const sessionId = ctx.sessionManager.getSessionId();
    config.review_transport = 'pi';
    config.pi_session_id = sessionId;
    config.review_provider = ctx.model.provider;
    delete config.thread_id;
    let attemptFd: number;
    try { attemptFd = fs.openSync(attemptFile, 'wx', 0o600); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') throw new Error('Run already launched; inspect its state instead of replaying it.');
      throw error;
    }
    try { fs.writeFileSync(attemptFd, `${JSON.stringify({ session_id: sessionId, at: Date.now() })}\n`); fs.fchmodSync(attemptFd, 0o600); }
    finally { fs.closeSync(attemptFd); }
    atomic(file, config);
    const binding = { root, runId: config.run_id, sessionId };
    receiver(binding, true);
    fs.mkdirSync(path.join(root, 'pi-inbox'), { recursive: true, mode: 0o700 });
    bindings.push(binding);
    context = ctx;
    pi.appendEntry(entryType, binding);
    startTimer();
    const script = process.env.PI_PING_PONG_BRIDGE || path.join(os.homedir(), '.agents/skills/pi-ping-pong/scripts/bridge.py');
    const logFile = path.join(root, 'launcher.log');
    const fd = fs.openSync(logFile, 'a', 0o600);
    fs.fchmodSync(fd, 0o600);
    try {
      const child = spawn('python3', ['-B', script, 'run', '--config', file], { cwd: root, detached: true, stdio: ['ignore', fd, fd] });
      await new Promise<void>((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
      child.unref();
      ctx.ui.notify(`Started ${config.run_id} (pid ${child.pid}). Checkpoints return to this Pi session.`, 'info');
    } finally { fs.closeSync(fd); }
  };
  const startReviewedRun = async (args: string, ctx: ExtensionCommandContext) => {
    const argument = args.trim().replace(/^("|')(.*)\1$/, '$2');
    if (!argument) {
      const project = await resolveProject(ctx);
      if (!project) return;
      if (!ctx.hasUI) { ctx.ui.notify('The project runs menu and preparation-name prompt require Pi UI. Use /pi-ping-pong <run-name> in a UI-enabled session.', 'warning'); return; }
      let runs: RunInfo[];
      try { runs = listRuns(project); }
      catch (error) { ctx.ui.notify(String(error), 'error'); return; }
      if (!runs.length) {
        const name = await ctx.ui.input('Create a named Pi Ping Pong run', 'ASCII kebab-case, e.g. add-linters');
        if (name === undefined || name.trim() === '') return;
        return startNamedRun(name.trim(), ctx, project);
      }
      const createOption = '＋ Create a new run';
      const labels = runs.map(formatRun);
      const selected = await ctx.ui.select('Pi Ping Pong runs (selection never launches)', [createOption, ...labels]);
      if (!selected) return;
      if (selected === createOption) {
        const name = await ctx.ui.input('Create a named Pi Ping Pong run', 'ASCII kebab-case, e.g. add-linters');
        if (name === undefined || name.trim() === '') return;
        return startNamedRun(name.trim(), ctx, project);
      }
      const info = runs[labels.indexOf(selected)];
      if (!info) return;
      ctx.ui.notify(details(info), info.state === 'unknown/malformed' || info.state === 'attention required' ? 'warning' : 'info');
      if (info.state === 'ready to launch') {
        const action = await ctx.ui.select(`Run ${info.name}`, ['Launch', 'Back']);
        if (action === 'Launch' && info.dir) return launchConfig(path.join(info.dir, 'config.json'), ctx, { project, name: info.name, dir: info.dir });
      } else if (info.state === 'draft/incomplete') {
        const action = await ctx.ui.select(`Run ${info.name}`, ['Continue preparation', 'Back']);
        if (action === 'Continue preparation' && info.dir) return sendPreparation(pi, ctx, project, info.name, info.dir, true);
      }
      return;
    }
    if (isExplicitPath(argument)) {
      const file = path.resolve(ctx.cwd, argument.startsWith('~') ? path.join(os.homedir(), argument.slice(1)) : argument);
      return launchConfig(file, ctx);
    }
    if (!validRunName(argument)) {
      ctx.ui.notify(`Invalid run name. Use lowercase ASCII kebab-case, 1–${maxRunNameLength} characters. A path must name an existing config.json; it will not create a run.`, 'error');
      return;
    }
    const project = await resolveProject(ctx);
    if (!project) return;
    return startNamedRun(argument, ctx, project);
  };
  async function startNamedRun(name: string, ctx: ExtensionCommandContext, project: Project) {
    if (!validRunName(name)) {
      ctx.ui.notify(`Invalid run name. Use lowercase ASCII kebab-case, 1–${maxRunNameLength} characters.`, 'error');
      return;
    }
    try {
      if (!ignoredByGit(project, name)) throw new Error(`Private run artifacts are not Git-ignored. Add .pi-ping-pong/ to ${project.root}/.gitignore, verify with git check-ignore, then retry; no run was created.`);
      assertPrivateDirectoryChain(project.root, runStorage(project), true);
    } catch (error) { ctx.ui.notify(String(error), 'error'); return; }
    const dir = path.join(runStorage(project), name);
    if (fs.existsSync(dir)) {
      let info: RunInfo;
      try { info = listRuns(project).find(run => run.name === name) ?? inspectRun(name, dir); }
      catch (error) { ctx.ui.notify(String(error), 'error'); return; }
      ctx.ui.notify(details(info), info.state === 'unknown/malformed' || info.state === 'attention required' ? 'warning' : 'info');
      if (info.state === 'ready to launch') return launchConfig(path.join(dir, 'config.json'), ctx, { project, name, dir });
      if (info.state === 'draft/incomplete') {
        const action = await ctx.ui.select(`Run ${name} is incomplete`, ['Continue preparation', 'Back']);
        if (action === 'Continue preparation') return sendPreparation(pi, ctx, project, name, dir, true);
      }
      return;
    }
    let reserved: string;
    try { reserved = reserveRun(project, name); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') {
        ctx.ui.notify(`Run ${name} was created concurrently. It was not overwritten; inspect it and retry.`, 'warning');
        return;
      }
      ctx.ui.notify(String(error), 'error');
      return;
    }
    sendPreparation(pi, ctx, project, name, reserved, false);
  }

  for (const command of ['pi-ping-pong', 'reviewed-run', 'ppp']) {
    pi.registerCommand(command, {
      description: command === 'ppp' ? 'Short alias for /pi-ping-pong.' : command === 'reviewed-run' ? 'Compatibility alias for /pi-ping-pong.' : 'Open runs, prepare a named run, or launch an existing run/config.',
      handler: startReviewedRun,
    });
  }
  const showReviewedStatus = async (_args: string, ctx: ExtensionCommandContext) => {
    const lines: string[] = [];
    const project = await resolveProject(ctx);
    if (project) {
      try {
        const runs = listRuns(project);
        lines.push(...runs.map(formatRun));
        if (!runs.length) lines.push(`No named runs in ${runStorage(project)}.`);
      } catch (error) { lines.push(`Project run status unavailable: ${String(error)}`); }
    }
    for (const binding of bindings) {
      try {
        const state = read<{ status: string; cycle: number; run_id?: string }>(path.join(binding.root, 'bridge-status.json'));
        const label = state.run_id === binding.runId ? statusLabel(state.status) ?? 'unknown/malformed' : 'unknown/malformed';
        const line = `${binding.runId}: ${label}, cycle ${Number.isSafeInteger(state.cycle) ? state.cycle : 'unknown'}. ${binding.root}`;
        const prior = lines.findIndex(value => value.includes(binding.runId));
        if (prior >= 0) lines[prior] = line; else lines.push(line);
      } catch {
        const line = `${binding.runId}: starting or unavailable. ${binding.root}`;
        const prior = lines.findIndex(value => value.includes(binding.runId));
        if (prior >= 0) lines[prior] = line; else lines.push(line);
      }
    }
    if (!lines.length) lines.push('No named or attached reviewed runs are available in this project/session.');
    ctx.ui.notify(lines.join('\n'), 'info');
  };
  for (const command of ['pi-ping-pong-status', 'reviewed-status', 'ppp-status']) {
    pi.registerCommand(command, {
      description: command === 'ppp-status' ? 'Short alias for /pi-ping-pong-status.' : command === 'reviewed-status' ? 'Compatibility alias for /pi-ping-pong-status.' : 'List local named and attached reviewed-run status; no model calls.',
      handler: showReviewedStatus,
    });
  }
}
