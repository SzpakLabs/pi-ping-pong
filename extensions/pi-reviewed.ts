import { spawn, execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { createHash, randomUUID } from 'node:crypto';
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from '@earendil-works/pi-coding-agent';

type Binding = { root: string; runId: string; sessionId: string };
type Config = { run_id: string; review_model: string; review_provider?: string; [key: string]: unknown };
type Envelope = { id: string; run_id: string; session_id: string; kind: string; message: string; receipt: string; trigger_turn?: boolean; notice_type?: string; report_key?: string; protocol_version?: number; schema_version?: number };
type Project = { root: string; fallback: boolean; git: 'repository' | 'absent' | 'unknown' };
type RunState = 'draft/incomplete' | 'ready to launch' | 'starting' | 'running' | 'waiting review' | 'waiting human' | 'waiting resource' | 'waiting event' | 'completed' | 'stopped' | 'attention required' | 'unknown/malformed';
type RunInfo = { name: string; store?: string; label?: string; dir?: string; state: RunState; mode?: string; worker?: string; reviewer?: string; details?: string; config?: Config };
type LaunchWatch = { root: string; runId: string; deadline: number; notified?: string };
const statusKey = 'pi-ping-pong';
const entryType = 'pi-reviewed-run';
const maxRunNameLength = 48;
const runNamePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const safeRunId = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(value);
const read = <T>(file: string): T => JSON.parse(fs.readFileSync(file, 'utf8')) as T;
function atomicText(file: string, text: string) {
  const temporary = `${file}.${process.pid}.${randomUUID()}.tmp`;
  fs.writeFileSync(temporary, text, { mode: 0o600, flag: 'wx' });
  fs.chmodSync(temporary, 0o600);
  const fd = fs.openSync(temporary, 'r');
  try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(temporary, file);
  const directory = fs.openSync(path.dirname(file), 'r');
  try { fs.fsyncSync(directory); } finally { fs.closeSync(directory); }
}
function atomic(file: string, data: unknown) {
  atomicText(file, `${JSON.stringify(data, null, 2)}\n`);
}
function skipWhitespace(text: string, from: number) {
  while (from < text.length && /\s/.test(text[from])) from++;
  return from;
}
function scanStringEnd(text: string, from: number) {
  if (text[from] !== '"') throw new Error('Malformed config.json object key.');
  for (let i = from + 1; i < text.length; i++) {
    if (text[i] === '\\') i++;
    else if (text[i] === '"') return i + 1;
  }
  throw new Error('Unterminated string in config.json.');
}
function scanValueEnd(text: string, from: number) {
  let i = skipWhitespace(text, from);
  if (text[i] === '"') return scanStringEnd(text, i);
  let depth = 0;
  let inString = false;
  for (; i < text.length; i++) {
    const char = text[i];
    if (inString) {
      if (char === '\\') i++;
      else if (char === '"') inString = false;
    } else if (char === '"') inString = true;
    else if (char === '{' || char === '[') depth++;
    else if (char === '}' || char === ']') {
      if (!depth) break;
      depth--;
    } else if (char === ',' && !depth) break;
  }
  return text.slice(from, i).trimEnd().length + from;
}
function bindConfigText(text: string, updates: Record<string, unknown>, removals: string[]) {
  let cursor = skipWhitespace(text, 0);
  if (text[cursor++] !== '{') throw new Error('config.json must contain an object.');
  const members: Array<{ key: string; keyStart: number; valueStart: number; valueEnd: number; comma?: number }> = [];
  cursor = skipWhitespace(text, cursor);
  while (text[cursor] !== '}') {
    const keyStart = cursor;
    const keyEnd = scanStringEnd(text, cursor);
    const key = JSON.parse(text.slice(keyStart, keyEnd)) as string;
    cursor = skipWhitespace(text, keyEnd);
    if (text[cursor++] !== ':') throw new Error('Malformed config.json object member.');
    const valueStart = skipWhitespace(text, cursor);
    const valueEnd = scanValueEnd(text, valueStart);
    cursor = skipWhitespace(text, valueEnd);
    const comma = text[cursor] === ',' ? cursor++ : undefined;
    members.push({ key, keyStart, valueStart, valueEnd, comma });
    cursor = skipWhitespace(text, cursor);
    if (comma === undefined) break;
  }
  if (text[cursor] !== '}' || skipWhitespace(text, cursor + 1) !== text.length) throw new Error('Malformed config.json object.');
  const touched = new Set([...Object.keys(updates), ...removals]);
  for (const key of touched) if (members.filter(member => member.key === key).length > 1) throw new Error(`Duplicate config field: ${key}`);
  const edits: Array<{ start: number; end: number; value: string }> = [];
  members.forEach((member, index) => {
    if (Object.hasOwn(updates, member.key)) edits.push({ start: member.valueStart, end: member.valueEnd, value: JSON.stringify(updates[member.key]) });
    if (removals.includes(member.key)) {
      const prior = members[index - 1];
      edits.push(member.comma !== undefined
        ? { start: member.keyStart, end: member.comma + 1, value: '' }
        : prior?.comma !== undefined ? { start: prior.comma, end: member.valueEnd, value: '' }
          : { start: member.keyStart, end: member.valueEnd, value: '' });
    }
  });
  const missing = Object.entries(updates).filter(([key]) => !members.some(member => member.key === key));
  if (missing.length) {
    const last = members.at(-1);
    const insertion = last ? last.valueEnd : cursor;
    edits.push({ start: insertion, end: insertion, value: `${last ? ',' : ''}${missing.map(([key, value]) => `${JSON.stringify(key)}:${JSON.stringify(value)}`).join(',')}` });
  }
  let result = text;
  for (const edit of edits.sort((a, b) => b.start - a.start)) result = result.slice(0, edit.start) + edit.value + result.slice(edit.end);
  JSON.parse(result);
  return result;
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
function generatedRunName(task: string) {
  const slug = task.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'task';
  const suffix = createHash('sha256').update(task).digest('hex').slice(0, 8);
  return `${slug.slice(0, maxRunNameLength - suffix.length - 1).replace(/-+$/g, '')}-${suffix}`;
}
function hasSecret(value: string) {
  return /(?:\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9_]{12,}|\bbearer\s+\S+|(?:api[_-]?key|secret|token)\s*[:=]\s*\S+)/i.test(value);
}
function displayValue(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value !== 'string') return '—';
  const safe = value.replace(/[\r\n\t\x00-\x1f]/g, ' ').slice(0, 160);
  return /(?:\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9_]{12,}|\bbearer\s+\S+|(?:api[_-]?key|secret|token)\s*[:=])/i.test(safe) ? '[redacted]' : safe;
}
function canonicalPath(value: string) {
  try { return fs.realpathSync(value); } catch { return path.resolve(value); }
}
function inside(parent: string, child: string) {
  const relative = path.relative(parent, child);
  return relative !== '' && !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}
const currentStore = '.pi/ping-pong/runs';
const legacyStore = '.pi-ping-pong/runs';
const fallbackStore = '.pi/reviewed-runs/named';
function projectStores(project: Project) {
  return project.fallback ? [fallbackStore] : [currentStore, legacyStore];
}
function privateDirectoryChain(root: string, target: string, create = false, sharedPi = false) {
  const resolvedRoot = fs.realpathSync(root);
  const resolvedTarget = path.resolve(target);
  if (!inside(resolvedRoot, resolvedTarget)) throw new Error('Run storage path escapes the confirmed project root.');
  let current = resolvedRoot;
  for (const part of path.relative(resolvedRoot, resolvedTarget).split(path.sep)) {
    current = path.join(current, part);
    let stat: fs.Stats;
    try { stat = fs.lstatSync(current); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      if (!create) return false;
      try { fs.mkdirSync(current, { mode: 0o700 }); fs.chmodSync(current, 0o700); }
      catch (race) {
        if ((race as NodeJS.ErrnoException).code !== 'EEXIST') throw race;
      }
      stat = fs.lstatSync(current);
    }
    // An existing project .pi also holds Pi settings. Keep its mode; only PPP's own chain must be private.
    const safeMode = sharedPi && current === path.join(resolvedRoot, '.pi') ? (stat.mode & 0o022) === 0 : isPrivate(stat);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`Refusing non-directory or symlink in run storage: ${current}`);
    if (!safeMode) throw new Error(`Run storage has permissive permissions: ${current}`);
  }
  return true;
}
function projectGitEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, LC_ALL: 'C', GIT_OPTIONAL_LOCKS: '0' };
  const localVars = execFileSync('git', ['rev-parse', '--local-env-vars'], { encoding: 'utf8', timeout: 2000, stdio: ['ignore', 'pipe', 'pipe'] });
  for (const name of localVars.trim().split(/\s+/)) delete env[name];
  return env;
}
function git(cwd: string, args: string[], env: NodeJS.ProcessEnv) {
  return execFileSync('git', ['-C', cwd, ...args], { env, timeout: 2000, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}
function gitProject(cwd: string): { root: string; git: Project['git'] } {
  try {
    const root = git(cwd, ['rev-parse', '--show-toplevel'], projectGitEnv()).replace(/\r?\n$/, '');
    return { root: fs.realpathSync(root), git: 'repository' };
  } catch (error) {
    const stderr = (error as { stderr?: string }).stderr;
    return { root: fs.realpathSync(cwd), git: stderr?.includes('not a git repository') ? 'absent' : 'unknown' };
  }
}
const localRule = '/.pi/ping-pong/';
function addLocalExclude(exclude: string) {
  if (!fs.lstatSync(path.dirname(exclude)).isDirectory()) throw new Error('Git info path is not a real directory.');
  // Serialize PPP writers (including linked worktrees) without replacing or truncating user rules.
  const lock = `${exclude}.lock`;
  const lease = fs.openSync(lock, 'wx', 0o600);
  try {
    const { O_RDWR, O_APPEND, O_CREAT, O_NOFOLLOW, O_NONBLOCK } = fs.constants;
    const fd = fs.openSync(exclude, O_RDWR | O_APPEND | O_CREAT | O_NOFOLLOW | O_NONBLOCK, 0o644);
    try {
      const stat = fs.fstatSync(fd);
      if (!stat.isFile() || stat.nlink !== 1) throw new Error('Git exclude is not a regular, unshared file.');
      const text = fs.readFileSync(fd).toString('latin1');
      if (!text.split(/\r?\n/).includes(localRule)) fs.writeFileSync(fd, `${text && !text.endsWith('\n') ? '\n' : ''}${localRule}\n`);
    } finally { fs.closeSync(fd); }
  } finally { fs.closeSync(lease); fs.unlinkSync(lock); }
}
function warnIfVisible(ctx: ExtensionCommandContext, project: Project, dir: string) {
  if (project.fallback || project.git === 'absent') return;
  let reason = 'Git ignore status could not be verified';
  try {
    if (project.git !== 'repository') throw new Error(reason);
    const env = projectGitEnv();
    const relative = path.relative(project.root, dir).split(path.sep).join('/');
    const ignored = () => {
      try { git(project.root, ['check-ignore', '-q', '--', `${relative}/`], env); return true; }
      catch (error) { if ((error as { status?: number }).status === 1) return false; throw error; }
    };
    let protectedByIgnore = ignored();
    if (!protectedByIgnore && path.dirname(dir) === path.join(project.root, currentStore)) {
      try {
        // Resolve the common Git directory, not the exclude file (Git can dereference the latter).
        const common = git(project.root, ['rev-parse', '--git-common-dir'], env).replace(/\r?\n$/, '');
        const exclude = path.resolve(project.root, common, 'info', 'exclude');
        addLocalExclude(exclude);
      } catch { reason = 'the local Git exclude could not be updated'; }
      protectedByIgnore = ignored();
    }
    if (git(project.root, ['ls-files', '-z', '--', `:(literal)${relative}/`], env)) reason = 'some run files are already tracked; ignore rules cannot hide them';
    else if (protectedByIgnore) return;
    else if (reason === 'Git ignore status could not be verified') reason = 'Git does not ignore this run directory';
  } catch { reason = 'Git ignore status could not be verified'; }
  const message = `Private run artifacts at ${dir} are not known to be fully Git-ignored: ${reason}. File permissions still apply; do not commit these artifacts.`;
  ctx.ui.notify(message, 'warning');
  if (!ctx.hasUI) process.stderr.write(`${message}\n`);
}
async function resolveProject(ctx: ExtensionContext): Promise<Project | undefined> {
  const cwd = path.resolve(ctx.cwd);
  if (fs.existsSync(cwd) && fs.statSync(cwd).isDirectory()) return { ...gitProject(cwd), fallback: false };
  if (!ctx.hasUI) {
    ctx.ui.notify('Current project folder is unavailable. No project runs were read or created; select an existing project folder.', 'warning');
    return undefined;
  }
  const fallback = path.join(os.homedir(), '.pi', 'reviewed-runs');
  if (await ctx.ui.confirm('Use the private fallback run store?', `No project root was confirmed. Named runs will be stored under ${fallback}/named/<name>/; existing legacy runs remain untouched.`)) {
    return { root: fs.realpathSync(os.homedir()), fallback: true, git: 'absent' };
  }
  return undefined;
}
function statusLabel(value: unknown): RunState | undefined {
  if (value === 'running') return 'running';
  if (value === 'starting') return 'starting';
  if (value === 'waiting_pi' || value === 'waiting_codex') return 'waiting review';
  if (value === 'waiting_human' || value === 'paused_budget') return 'waiting human';
  if (value === 'waiting_resource') return 'waiting resource';
  if (value === 'waiting_event') return 'waiting event';
  if (value === 'complete') return 'completed';
  if (value === 'stopped' || value === 'cancelled') return 'stopped';
  if (value === 'halted') return 'attention required';
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
  // Goal is bounded by wall/review seconds and goal_max_launches; cycle fields are optional there but still validated when set.
  const bounds = ['max_cycles', 'cycle_seconds', 'review_seconds', 'wall_seconds'].filter(key => config.mode !== 'goal' || !['max_cycles', 'cycle_seconds'].includes(key) || config[key] !== undefined).map(key => config[key]);
  const taskFile = typeof config.task === 'string' ? path.resolve(dir, config.task) : '';
  const incomplete: string[] = [];
  if (!requiredStrings.every(value => typeof value === 'string' && value.trim().length > 0)) incomplete.push('required config fields');
  if (!uuidPattern.test(String(config.run_id))) incomplete.push('UUID run_id');
  if (!['goal', 'ralph', 'ping-pong'].includes(String(config.mode))) incomplete.push('mode');
  if (!bounds.every(value => Number.isSafeInteger(value) && Number(value) > 0)) incomplete.push('positive finite bounds');
  for (const key of ['worker_extensions', 'reviewer_extensions']) {
    const value = config[key];
    if (value !== undefined && (!Array.isArray(value) || !value.every(item => typeof item === 'string' && item.trim() && !item.includes('\0')))) incomplete.push(`${key} must be a list of non-empty paths`);
  }
  if (config.eval_argv !== undefined) incomplete.push('eval_argv is obsolete; prepare without an evaluator');
  if (config.review_transport !== 'pi' || config.pi_session_id !== undefined || config.thread_id !== undefined) incomplete.push('unbound Pi config');
  if (config.review_execution !== undefined && !['chat', 'headless'].includes(String(config.review_execution))) incomplete.push('valid review_execution');
  if (config.review_execution === 'headless' && config.protocol_version !== 2) incomplete.push('protocol 2 for headless review');
  if (!inside(dir, taskFile) || !regularPrivateRunFile(dir, taskFile)) incomplete.push('private TASK file');
  if (!regularPrivateFile(path.join(dir, 'config.json'))) incomplete.push('private config file');
  const version = config.protocol_version;
  if (version !== 2) incomplete.push('protocol 2 required; evaluator-era runs are unsupported');
  if (version === 2 && (config.schema_version !== 1 || !config.execution_contract || typeof config.execution_contract !== 'object')) incomplete.push('protocol 2 schema/contract');
  if (!incomplete.length) return { name, dir, state: 'ready to launch', mode, worker, reviewer, details: 'TASK, UUID run_id, models and finite limits are present.', config };
  return { name, dir, state: 'draft/incomplete', mode, worker, reviewer, details: `Preparation is incomplete: ${incomplete.join(', ')}.`, config };
}
function listRuns(project: Project): RunInfo[] {
  const runs: RunInfo[] = [];
  for (const store of projectStores(project)) {
    const parent = path.join(project.root, store);
    try {
      if (!privateDirectoryChain(project.root, parent, false, store === currentStore)) continue;
      for (const entry of fs.readdirSync(parent, { withFileTypes: true })) {
        if (!validRunName(entry.name)) runs.push({ store, name: '[invalid run name]', state: 'unknown/malformed', details: 'A direct entry has an unsafe or unsupported name.' });
        else if (!entry.isDirectory()) runs.push({ store, name: entry.name, state: 'unknown/malformed', details: 'Entry is not a regular run directory.' });
        else runs.push({ ...inspectRun(entry.name, path.join(parent, entry.name)), store });
      }
    } catch (error) { runs.push({ store, name: store, state: 'unknown/malformed', details: String(error) }); }
  }
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
  return labelCollisions(runs);
}
function labelCollisions(runs: RunInfo[]) {
  const counts = new Map<string, number>();
  for (const { name } of runs) counts.set(name, (counts.get(name) ?? 0) + 1);
  for (const run of runs) if (counts.get(run.name)! > 1) run.label = `${run.name} [${run.store ?? run.dir}]`;
  return runs;
}
function managedPath(dir: string) {
  for (const store of [currentStore, legacyStore]) {
    const suffix = path.sep + store.split('/').join(path.sep);
    const parent = path.dirname(dir);
    if (parent.endsWith(suffix)) return { root: parent.slice(0, -suffix.length) || path.parse(parent).root, store };
  }
}
function verifyNamedRun(project: Project, name: string, dir: string) {
  if (!validRunName(name)) throw new Error('Unsafe named run.');
  const store = projectStores(project).find(candidate => dir === path.join(project.root, candidate, name));
  if (!store) throw new Error('Named run path does not match its reserved project location.');
  if (!privateDirectoryChain(project.root, dir, false, store === currentStore)) throw new Error('Named run directory is unavailable.');
  if ((fs.lstatSync(dir).mode & 0o777) !== 0o700) throw new Error('Named run directory is not a private 0700 directory.');
}
function reserveRun(project: Project, name: string) {
  const store = projectStores(project)[0];
  const parent = path.join(project.root, store);
  privateDirectoryChain(project.root, parent, true, store === currentStore);
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
function launchArgument(name: string, dir: string, usePath: boolean) {
  const file = path.join(dir, 'config.json');
  return usePath ? (file.includes(' ') ? `"${file}"` : file) : name;
}
function preparationPrompt(project: Project, name: string, dir: string, continuation: boolean, reviewerDefault: string, taskDescription = '', usePath = false) {
  const files = continuation ? draftFiles(dir).filter(file => file !== '.draft.json') : [];
  return `Prepare a Pi Ping Pong run from this conversation. Reuse all task details, criteria, project context, and decisions already provided; ask only concise grouped questions for genuinely missing inputs. Do not start or launch the worker during preparation.

${taskDescription ? `Task requested in the command: ${taskDescription}\n` : ''}${project.fallback ? 'Private fallback store root (not a product target)' : 'Confirmed project root'}: ${project.root}
Selected run name: ${name}
Exact reserved private run directory: ${dir}
${project.fallback ? 'Use this explicitly confirmed private fallback store, not the project cwd.' : ''}
${continuation ? `This is an incomplete existing run. Read existing entries before updating: ${files.join(', ')}. Do not overwrite existing files blindly; preserve valid content. Never touch launched run artifacts.` : 'This directory was exclusively reserved for this new run.'}

Write only TASK.md and config.json inside the exact reserved run directory. Do not overwrite .draft.json or write task outputs during preparation. Do not create eval.py, eval_argv or any separate evaluator/preflight. Worker implements the task and runs ordinary tests; independent Reviewer assesses only what tests cannot establish and concrete defects; Core validates and decides. Chat A receives reports, never becomes Core. No mandatory model preflight or pre/post review repeats.

TASK.md must state actual user requirements, allowed paths, checkable acceptance criteria and ordinary test commands where known. Work in the selected current project with its actual uncommitted changes. For a new project use the confirmed repository root as product target (a private fallback store is not a product target; take the actual authorized target from the task, ask only if missing); modify an existing project in place; respect an explicitly requested subdirectory or file. Record absolute product target and project command cwd in TASK.md and use that actual path in execution_contract.target. The reserved run/work is service storage only, never the default product directory. No mandatory auto-commit, clean Git, separate worktree, fetch or routine approval. Preserve unrelated user changes and existing untracked/ignored local configuration; do not read or copy secrets. A bounded launch snapshot is fallback discovery only, not a preflight or proof of authorship/tests/acceptance; missing or partial snapshots must not block work or delivery. Expected behavior follows the actual requirement and observed before/after state, including multiplicities; a merely changed value is not enough. Do not invent names, selectors, storage formats, scenarios or approvals. Missing checks are unknown/not_tested, not automatic product failures. Worker retains test commands, exits, output and relevant artifacts with its checkpoint; Reviewer uses those results without rerunning or re-proving deterministic checks. Missing review evidence must not hide available work or prevent independent authorized work. Report delivery separately from verified acceptance.

For browser tasks, determine one usable Playwright route when practical: prefer explicitly configured/project-installed runtime, then ordinary installed Pi-accessible runtime. Verify module resolution/browser availability where practical without a model or installing dependencies. Record actual command/module resolution and cwd in TASK.md for both Goal and Ralph. Core resolves the module once and passes its absolute entry as PPP_PLAYWRIGHT_MODULE to Worker; prefer require(process.env.PPP_PLAYWRIGHT_MODULE). Module resolution does not establish browser/auth availability. Do not hardcode a host-specific path or make availability a launch gate; record the limitation and continue independent work.

Use protocol_version=2 and schema_version=1. config.json needs a unique RFC 4122 UUID run_id (not the folder name), mode goal|ralph|ping-pong, worker_provider, worker_model, thinking, review_provider, review_model, task and positive finite integer review_seconds, wall_seconds, plus max_cycles and cycle_seconds for ralph/ping-pong (optional for goal, which is bounded by wall_seconds, goal_max_launches and optional goal_tokens). Defaults: worker_provider=openai-codex, worker_model=gpt-6-luna, thinking=low, max_cycles=10 unless user requested alternatives; do not ask to confirm approved defaults. Review provider/model default to the current Pi model (${reviewerDefault}), without confirmation unless missing or explicitly overridden. Use review_transport=pi and review_execution=headless for a separate Core-owned read-only Reviewer session; its model need not match Chat A at launch.

Include execution_contract: target (absolute authorized output/source path for filesystem tasks), actions (stable id, description, depends_on, pre-authorized operations), complete criteria ID/description map, closure={authorized:true,max_cycles:null} only where actual initial task authority permits closure, reminder_seconds=86400 unless configured otherwise. Cwd/Git ancestry grants no authority. Retain actual scope, approval and side-effect restrictions. Never fabricate closure authorization, identity, human input or budget. Old evaluator-era runs cannot resume with this implementation; preserve their files, do not migrate them silently.

Keep PPP run directories private 0700; leave existing Pi settings permissions unchanged. Keep TASK.md and config.json mode 0600. No secrets. Do not write pi_session_id, launch-attempt.json or session entries; explicit launch binds identity. Do not run Worker, Goal/Ralph, bridge run, or paid/live checks during preparation.

Report task, criteria and ordinary tests, mode, worker/reviewer models, allowed paths, finite limits, exact run/config paths and limitations. State no worker started; give explicit launch command \`/pi-ping-pong ${launchArgument(name, dir, usePath)}\`. Incomplete: list grouped genuine missing inputs and preserve draft. Visible report: standalone STATUS — line; blank lines around separate headings ### TL;DR, ### Summary, ### Report, ### Suggested action, ### Full run status. Put content below headings; short paragraphs/bullets, commands in fenced text. Use available facts only; no extra reads just to fill status.`;
}
function sendPreparation(pi: ExtensionAPI, ctx: ExtensionCommandContext, project: Project, name: string, dir: string, continuation: boolean, taskDescription = '', usePath = false) {
  try { verifyNamedRun(project, name, dir); }
  catch (error) { ctx.ui.notify(String(error), 'error'); return; }
  warnIfVisible(ctx, project, dir);
  const reviewerDefault = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : 'no Pi model is selected';
  const prompt = preparationPrompt(project, name, dir, continuation, reviewerDefault, taskDescription, usePath);
  pi.sendUserMessage(prompt, ctx.isIdle() ? undefined : { deliverAs: 'followUp' });
  ctx.ui.notify(`Preparation prompt sent for ${name}; no worker was started. After preparation, explicitly launch with /pi-ping-pong ${launchArgument(name, dir, usePath)}.`, 'info');
}
function details(info: RunInfo) {
  const config = info.config;
  const bounds = config
    ? `Limits: cycles=${displayValue(config.max_cycles)}, cycle_seconds=${displayValue(config.cycle_seconds)}, review_seconds=${displayValue(config.review_seconds)}, wall_seconds=${displayValue(config.wall_seconds)}`
    : '';
  return [
    `${info.label ?? info.name}: ${info.state}`,
    `Directory: ${info.dir ?? '(unsafe entry; not followed)'}`,
    `Config: ${info.dir ? path.join(info.dir, 'config.json') : '—'}`,
    `Mode: ${info.mode ?? '—'}`,
    `Worker: ${info.worker ?? '—'}`,
    `Reviewer: ${info.reviewer ?? '—'}`,
    bounds,
    info.details ?? '',
    info.state === 'ready to launch' ? `Explicit launch: /pi-ping-pong ${launchArgument(info.name, info.dir!, Boolean(info.label))}` : '',
  ].filter(Boolean).join('\n');
}
function formatRun(info: RunInfo) {
  return `${info.label ?? info.name} — ${info.state} — ${info.mode ?? 'mode unknown'} — ${info.worker ?? 'worker unknown'}`;
}
function statusView(info: RunInfo, binding?: Binding) {
  const root = info.dir ?? binding?.root;
  const config = info.config;
  let state: { run_id?: unknown; status?: unknown; outcome?: unknown; phase?: unknown; cycle?: unknown; max_cycles?: unknown; started_at?: unknown; updated_at?: unknown; reason?: unknown; main_remaining?: unknown; worker_tokens?: unknown; worker_tokens_status?: unknown; goal_usage_status?: unknown; blockers?: { id: string; status: string; escalation: string; needed: string }[] } | undefined;
  const validatedRunId = safeRunId(config?.run_id) && (!binding || (safeRunId(binding.runId) && binding.runId === config.run_id));
  const validatedInfoState = ['running', 'starting', 'waiting review', 'waiting human', 'waiting resource', 'waiting event', 'completed', 'stopped', 'attention required'].includes(info.state);
  const invalidLifecycleIdentity = validatedInfoState && (!validatedRunId || (binding !== undefined && binding.runId !== config?.run_id));
  if (root && validatedRunId && validatedInfoState) {
    try {
      const candidate = read<typeof state>(path.join(root, 'bridge-status.json'));
      if (candidate && candidate.run_id === config!.run_id && (!binding || candidate.run_id === binding.runId)) state = candidate;
    } catch { /* Legacy and unavailable status files remain explicitly unknown. */ }
  }
  const label = state ? (state.status === 'running' && state.phase === 'evaluating' ? 'evaluating' : statusLabel(state.status) ?? 'unknown/malformed') : invalidLifecycleIdentity ? 'unknown/malformed' : info.state;
  const phase = state && typeof state.phase === 'string' && (state.phase !== 'evaluating' || state.status === 'running') ? displayValue(state.phase) : label;
  const cycle = Number.isSafeInteger(state?.cycle) && Number(state!.cycle) >= 0 ? String(state!.cycle) : 'unavailable';
  const maximum = Number.isSafeInteger(state?.max_cycles) && Number(state!.max_cycles) > 0 ? String(state!.max_cycles) : displayValue(config?.max_cycles);
  const seconds = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.floor(value) : undefined;
  const now = Date.now() / 1000;
  const duration = (value: unknown) => {
    const timestamp = seconds(value);
    if (timestamp === undefined) return 'unavailable';
    const total = Math.min(Number.MAX_SAFE_INTEGER, Math.floor(Math.max(0, now - timestamp)));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    return hours ? `${hours}h${String(minutes).padStart(2, '0')}m` : `${minutes}m${String(secs).padStart(2, '0')}s`;
  };
  const elapsed = duration(state?.started_at);
  const age = duration(state?.updated_at);
  const reason = state?.reason === undefined ? '' : `Reason: ${displayValue(state.reason)}`;
  const next = label === 'completed' ? 'No further action.' : label === 'stopped' && state?.outcome === 'delivered_unverified' ? 'Result delivered, not verified (not acceptance); no further stage starts. Check the unverified criteria yourself if needed.' : label === 'attention required' || label === 'unknown/malformed' ? 'Inspect saved state and launcher.log; do not relaunch automatically.' : label === 'waiting resource' || label === 'waiting event' ? 'No Worker is running; awaiting the recorded resource/event or scheduled check, not a review reply.' : label === 'waiting human' ? config?.review_execution === 'headless' ? 'Reply in Chat A using /ppp-respond; choose the run and request, then confirm your instruction. No JSON is needed.' : 'Provide the requested input in the reviewer session.' : label === 'waiting review' ? config?.review_execution === 'headless' ? 'Independent Reviewer is running; no human reply is needed.' : 'Review the pending checkpoint.' : label === 'ready to launch' ? 'Launch explicitly when ready.' : 'Monitor local status; no action is required.';
  const goalUsageUnknown = config?.mode === 'goal' && state?.goal_usage_status !== 'known';
  const mainRemaining = goalUsageUnknown ? 'unknown (actual Goal usage unavailable)' : displayValue(state?.main_remaining);
  const tokenUsage = config?.mode === 'goal' ? `Goal tokens: ${displayValue(state?.worker_tokens)} recorded${goalUsageUnknown ? '; actual usage unknown (recorded value is a lower bound)' : ''}` : config?.mode === 'ralph'
    ? state?.worker_tokens_status === 'partial' && Number.isSafeInteger(state.worker_tokens) && Number(state.worker_tokens) >= 0
      ? `Ralph Worker tokens: ${state.worker_tokens} observed (partial, lower bound)` : 'Ralph Worker tokens: not measured'
    : '';
  return { root, config, state, label, phase, cycle, maximum, elapsed, age, reason, next, mainRemaining, tokenUsage };
}
function compactStatus(info: RunInfo, binding?: Binding) {
  const view = statusView(info, binding);
  const detail = view.reason || (['unknown/malformed', 'draft/incomplete', 'attention required'].includes(view.label) ? info.details : '');
  return [`${info.label ?? info.name} — ${view.label}`, `Cycles: ${view.cycle}${view.config?.protocol_version === 2 ? ` · Main remaining: ${view.mainRemaining}` : `/${view.maximum}`}`,
    ...(view.tokenUsage ? [view.tokenUsage] : []), ...(detail ? [detail] : []), `Next: ${view.next}`].join('\n');
}
function detailedStatus(info: RunInfo, binding?: Binding) {
  const { root, config, state, label, phase, cycle, maximum, elapsed, age, reason, next, mainRemaining, tokenUsage } = statusView(info, binding);
  return [
    `${info.label ?? info.name}: ${label} (phase ${phase})`,
    `Mode: ${info.mode ?? 'unavailable'}; cycle ${cycle}/${maximum}; elapsed ${elapsed}; state age ${age}`,
    ...(config?.protocol_version === 2 ? [`Protocol: 2/schema 1; cumulative ledger: ${root ? path.join(root, 'execution-state.json') : 'unavailable'}`, `Main remaining: ${mainRemaining}; closure uses separate initial authority. Initial max_cycles is not a cumulative total.`, ...(Array.isArray(state?.blockers) ? state.blockers.map(b => `${displayValue(b.id)}: ${displayValue(b.status)} / ${displayValue(b.escalation)} — ${displayValue(b.needed)}`) : []), 'Human input: /ppp-respond opens a confirmed action menu; questions are not authorizations. Advanced: /ppp-respond <run-id> <JSON>.'] : []),
    ...(tokenUsage ? [tokenUsage] : []),
    `Worker: ${info.worker ?? 'unavailable'}`,
    `Reviewer: ${info.reviewer ?? 'unavailable'}`,
    `Directory: ${root ?? 'unavailable'}`,
    `Config: ${root ? path.join(root, 'config.json') : 'unavailable'}`,
    `Launcher log: ${root ? path.join(root, 'launcher.log') : 'unavailable'}`,
    info.details ? `Details: ${displayValue(info.details)}` : '',
    reason,
    `Next: ${next}`,
  ].filter(Boolean).join('\n');
}
function isExplicitPath(argument: string) {
  return argument.startsWith('/') || argument.startsWith('./') || argument.startsWith('../') || argument.startsWith('~') || argument.includes('/') || argument.includes('\\') || path.basename(argument) === 'config.json';
}

export default function reviewedRuns(pi: ExtensionAPI) {
  let context: ExtensionContext | undefined;
  let bindings: Binding[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
  const warned = new Set<string>();
  const launchWatches = new Map<string, LaunchWatch>();
  function receiver(binding: Binding, connected: boolean) {
    atomic(path.join(binding.root, 'pi-receiver.json'), { run_id: binding.runId, session_id: binding.sessionId, connected, pid: process.pid });
  }
  function clear() {
    if (timer) clearInterval(timer);
    launchWatches.clear();
    context?.ui.setStatus(statusKey, undefined);
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
    const statusLines: string[] = [];
    for (const binding of bindings) {
      if (sessionId !== binding.sessionId) continue;
      let config: Config | undefined;
      let state: { run_id?: string; status?: string; outcome?: string; phase?: string; cycle?: number; max_cycles?: number; started_at?: number; updated_at?: number; reason?: unknown; pi_session?: string; controller_pid?: number; main_remaining?: number } | undefined;
      try {
        if (!safeRunId(binding.runId)) throw new Error('invalid binding run_id');
        config = read<Config>(path.join(binding.root, 'config.json'));
        if (!safeRunId(config.run_id) || config.run_id !== binding.runId || config.pi_session_id !== sessionId || config.review_transport !== 'pi') throw new Error('identity mismatch');
        state = read<typeof state>(path.join(binding.root, 'bridge-status.json'));
        if (!state || state.run_id !== binding.runId) throw new Error('state identity mismatch');
      } catch { state = undefined; }
      const launchWatch = launchWatches.get(binding.runId);
      if (launchWatch && state && ['running', 'waiting_pi', 'waiting_codex', 'waiting_human', 'waiting_resource', 'waiting_event', 'complete', 'stopped'].includes(String(state.status))
        && ((typeof state.pi_session === 'string' && state.pi_session.trim().length > 0) || (config?.protocol_version === 2 && Number.isSafeInteger(state.controller_pid) && state.controller_pid! > 0)) && config?.run_id === binding.runId) {
        launchWatches.delete(binding.runId);
        ctx.ui.notify(`Pi Ping Pong ${binding.runId}: ${config?.protocol_version === 2 ? 'controller startup confirmed; workers follow verified action selection' : 'worker/session startup confirmed'}.`, 'info');
      }
      const status = state ? String(state.status ?? '') : 'unknown';
      const notificationState = statusLabel(state?.status);
      if (state) {
        try {
          const directory = path.join(binding.root, 'pi-notifications');
          fs.mkdirSync(directory, { mode: 0o700, recursive: true });
          fs.chmodSync(directory, 0o700);
          const receipt = path.join(directory, `${createHash('sha256').update(sessionId).digest('hex')}.json`);
          let prior: { run_id?: string; session_id?: string; state?: string; observed?: string; last_notified?: string } | undefined;
          try { prior = read<typeof prior>(receipt); } catch { /* A missing or malformed receipt permits one safe notice. */ }
          const reasonValue = state.reason === undefined ? '' : displayValue(state.reason);
          const cycleValue = Number.isSafeInteger(state.cycle) ? String(state.cycle) : 'unavailable';
          const event = notificationState ? JSON.stringify([notificationState, cycleValue, reasonValue]) : undefined;
          const sameBinding = prior?.run_id === binding.runId && prior?.session_id === sessionId;
          // Migrate old state-only receipts without repeating the currently observed event.
          const legacyDuplicate = sameBinding && prior?.last_notified === undefined && prior?.state === notificationState;
          const notify = Boolean(event && notificationState && ['completed', 'stopped', 'attention required', 'waiting human'].includes(notificationState)
            && !legacyDuplicate && (!sameBinding || prior?.last_notified !== event || prior.observed !== notificationState));
          const next = {
            run_id: binding.runId, session_id: sessionId, observed: notificationState ?? String(state.status ?? 'unknown'),
            ...(event && notificationState && ['completed', 'stopped', 'attention required', 'waiting human'].includes(notificationState)
              ? { last_notified: notify || legacyDuplicate ? event : prior?.last_notified } : { last_notified: prior?.last_notified }),
          };
          if (!sameBinding || prior?.observed !== next.observed || prior?.last_notified !== next.last_notified) atomic(receipt, { ...next, at: Date.now() });
          if (notify) {
            const reason = reasonValue ? ` Reason: ${reasonValue}` : '';
            ctx.ui.notify(`Pi Ping Pong ${path.basename(binding.root).slice(0, 48)}: ${notificationState}.${reason} Details: /ppp-status`, notificationState === 'attention required' ? 'warning' : 'info');
          }
        } catch { /* Status refresh must remain available if notification storage is unavailable. */ }
      }
      const statusForDisplay = status === 'running' && state?.phase === 'evaluating' ? 'evaluating' : status;
      const phase = status === 'starting' ? 'starting' : status === 'running' ? (statusForDisplay === 'evaluating' ? 'evaluating' : 'working')
        : status === 'waiting_resource' ? 'awaiting resource (Worker idle)' : status === 'waiting_event' ? 'awaiting event (Worker idle)'
        : ['waiting_pi', 'waiting_codex'].includes(status) ? 'awaiting review' : status === 'waiting_human' ? 'awaiting your input'
        : status === 'paused_budget' ? 'main budget paused' : status === 'halted' ? 'halted' : status === 'cancelled' ? 'cancelled'
        : status === 'complete' ? 'completed' : status === 'stopped' ? (state?.outcome === 'delivered_unverified' ? 'delivered, not verified' : 'stopped') : status === 'attention_required' ? 'attention' : 'unknown';
      const maximum = Number.isSafeInteger(state?.max_cycles) && state!.max_cycles! > 0 ? state!.max_cycles : config?.max_cycles;
      const cycle = state && Number.isSafeInteger(state.cycle) && state.cycle! >= 0
        ? config?.protocol_version === 2 ? ` cycles=${state.cycle} main=${displayValue(state.main_remaining)}` : ` ${state.cycle}${Number.isSafeInteger(maximum) && Number(maximum) > 0 ? `/${maximum}` : ''}` : '';
      const started = state?.started_at;
      const elapsed = typeof started === 'number' && Number.isFinite(started) && started >= 0
        ? ` ${Math.floor(Math.max(0, Date.now() / 1000 - started) / 60)}m${String(Math.floor(Math.max(0, Date.now() / 1000 - started) % 60)).padStart(2, '0')}s` : ' elapsed unavailable';
      const name = path.basename(binding.root).slice(0, 48) || 'unknown run';
      statusLines.push(`PPP ${name} ${phase}${cycle}${elapsed}`.slice(0, 120));
      const launch = launchWatches.get(binding.runId);
      if (launch && Date.now() > launch.deadline) {
        launchWatches.delete(binding.runId);
        ctx.ui.notify(`Pi Ping Pong ${binding.runId}: startup confirmation timed out; inspect ${path.join(binding.root, 'launcher.log')}. Do not relaunch.`, 'warning');
      }
      try {
        const config = read<Config>(path.join(binding.root, 'config.json'));
        if (config.run_id !== binding.runId || config.pi_session_id !== sessionId || config.review_transport !== 'pi') continue;
        const inbox = path.join(binding.root, 'pi-inbox');
        if (!fs.existsSync(inbox)) continue;
        const pending = fs.readdirSync(inbox).filter(name => name.endsWith('.message.json')).sort();
        const stateReport = (e: Envelope) => config.protocol_version === 2 && config.review_execution === 'headless'
          && e.run_id === binding.runId && e.session_id === sessionId && e.protocol_version === 2 && e.schema_version === 1
          && e.kind === 'notice' && e.notice_type === 'reporter' && e.trigger_turn === true && e.report_key === 'state'
          && typeof e.id === 'string' && e.id.length > 0 && typeof e.message === 'string' && e.message.length > 0;
        let newestStateReport: string | undefined;
        for (const name of pending) {
          const file = path.join(inbox, name);
          if (fs.existsSync(file.replace(/\.message\.json$/, '.delivery.json'))) continue;
          try { if (stateReport(read<Envelope>(file))) newestStateReport = name; }
          catch { /* Malformed messages cannot supersede valid reports. */ }
        }
        for (const name of pending) {
          const file = path.join(inbox, name);
          const ack = file.replace(/\.message\.json$/, '.delivery.json');
          if (fs.existsSync(ack)) continue;
          const envelope = read<Envelope>(file);
          if (envelope.session_id !== sessionId || envelope.run_id !== binding.runId) {
            atomic(ack, { status: 'rejected_identity' });
            continue;
          }
          if (config.protocol_version === 2 && (envelope.protocol_version !== 2 || envelope.schema_version !== 1 || (envelope.kind === 'notice' && envelope.trigger_turn === false && !['waiting', 'terminal', 'report'].includes(String(envelope.notice_type))))) {
            atomic(ack, { status: 'rejected_schema', session_id: sessionId, id: envelope.id });
            continue;
          }
          const passive = config.protocol_version === 2 && envelope.kind === 'notice' && envelope.trigger_turn === false;
          if (config.protocol_version === 2 && state && ['cancelled', 'halted', 'complete', 'stopped'].includes(String(state.status)) && (envelope.kind === 'review' || envelope.notice_type === 'waiting')) {
            atomic(ack, { status: 'suppressed_terminal', session_id: sessionId, id: envelope.id });
            continue;
          }
          const reporter = config.protocol_version === 2 && config.review_execution === 'headless' && envelope.kind === 'notice' && envelope.notice_type === 'reporter' && envelope.trigger_turn === true;
          if (stateReport(envelope) && newestStateReport && name !== newestStateReport) {
            atomic(ack, { status: 'superseded_report', session_id: sessionId, id: envelope.id, superseded_by: newestStateReport });
            continue;
          }
          if (!passive && !reporter && config.review_execution === 'headless') {
            atomic(ack, { status: 'rejected_headless_model_turn', session_id: sessionId, id: envelope.id });
            continue;
          }
          if (!passive && !reporter && (ctx.model?.id !== config.review_model || (config.review_provider && ctx.model?.provider !== config.review_provider))) {
            if (!warned.has(binding.runId)) {
              ctx.ui.notify(`Reviewed run ${binding.runId}: checkpoint held; select ${config.review_model} to review.`, 'warning');
              warned.add(binding.runId);
            }
            if (config.protocol_version === 2) continue;
            break;
          }
          atomic(ack, { status: 'dispatching', session_id: sessionId, id: envelope.id });
          pi.sendMessage({
            customType: reporter ? 'reviewed-report-request' : 'reviewed-checkpoint',
            content: envelope.message.replaceAll('Codex', 'reviewer').replaceAll('this chat', 'this Pi session'),
            display: !reporter,
            details: { run_id: binding.runId, message_id: envelope.id, kind: envelope.kind },
          }, { deliverAs: 'followUp', triggerTurn: !passive });
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
    ctx.ui.setStatus(statusKey, statusLines.length ? statusLines.slice(0, 3).join(' | ') : undefined);
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
        if (!safeRunId(value.runId) || !safeRunId(config.run_id) || config.run_id !== value.runId || config.pi_session_id !== id) continue;
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
    // Validate both managed trees without changing arbitrary explicit-path or session-entry semantics.
    const managed = managedPath(root);
    let project = namedRun?.project;
    let canonicalRun = root;
    if (managed) {
      const canonicalRoot = fs.realpathSync(managed.root);
      project ??= { ...gitProject(canonicalRoot), fallback: false };
      canonicalRun = path.join(canonicalRoot, managed.store, path.basename(root));
      if (!privateDirectoryChain(canonicalRoot, canonicalRun, false, managed.store === currentStore)) throw new Error('Run directory is unavailable.');
    }
    if (!regularPrivateFile(file)) throw new Error('Config must be a private regular non-symlink file.');
    const config = read<Config>(file);
    if (!config.run_id || !config.review_model || !['goal', 'ralph', 'ping-pong'].includes(String(config.mode))) throw new Error('Config needs run_id, mode=goal|ralph|ping-pong and review_model.');
    if (project && listRuns({ ...project, root: fs.realpathSync(managed?.root ?? project.root) })
      .some(info => info.dir !== canonicalRun && info.config?.run_id === config.run_id)) {
      throw new Error('Duplicate run_id detected in this project; launch is refused.');
    }
    const headless = config.review_execution === 'headless';
    if (config.review_execution !== undefined && !['chat', 'headless'].includes(String(config.review_execution))) throw new Error('Unknown review_execution.');
    if (headless && (config.protocol_version !== 2 || typeof config.review_provider !== 'string' || !config.review_provider.trim())) throw new Error('Headless review needs protocol 2 and explicit review_provider.');
    if (!headless && ctx.model?.id !== config.review_model) throw new Error(`Select reviewer model ${config.review_model} before launch.`);
    if (!headless && config.review_provider && ctx.model?.provider !== config.review_provider) throw new Error(`Select reviewer provider ${config.review_provider} before launch.`);
    const attemptFile = path.join(root, 'launch-attempt.json');
    if (fs.existsSync(attemptFile) || fs.existsSync(path.join(root, 'bridge-status.json')) || config.pi_session_id) throw new Error('Run already launched; inspect its state instead of replaying it.');
    const script = process.env.PI_PING_PONG_BRIDGE || path.join(os.homedir(), '.agents/skills/pi-ping-pong/scripts/bridge.py');
    if (config.protocol_version !== 2 || config.eval_argv !== undefined) throw new Error('Evaluator-era configs are unsupported; prepare a new protocol 2 run without eval_argv. Old run files are preserved.');
    const task = typeof config.task === 'string' ? path.resolve(root, config.task) : '';
    if (!regularPrivateRunFile(root, task)) throw new Error('Launch needs a private TASK file inside the run.');
    const sessionId = ctx.sessionManager.getSessionId();
    const boundConfigText = bindConfigText(fs.readFileSync(file, 'utf8'), {
      review_transport: 'pi', pi_session_id: sessionId,
      ...(!headless ? { review_provider: ctx.model!.provider } : {}),
    }, ['thread_id']);
    if (project) warnIfVisible(ctx, project, canonicalRun);
    let attemptFd: number;
    try { attemptFd = fs.openSync(attemptFile, 'wx', 0o600); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') throw new Error('Run already launched; inspect its state instead of replaying it.');
      throw error;
    }
    try { fs.writeFileSync(attemptFd, `${JSON.stringify({ session_id: sessionId, at: Date.now() })}\n`); fs.fchmodSync(attemptFd, 0o600); }
    finally { fs.closeSync(attemptFd); }
    atomicText(file, boundConfigText);
    config.review_transport = 'pi';
    config.pi_session_id = sessionId;
    if (!headless) config.review_provider = ctx.model!.provider;
    delete config.thread_id;
    const binding = { root, runId: config.run_id, sessionId };
    receiver(binding, true);
    fs.mkdirSync(path.join(root, 'pi-inbox'), { recursive: true, mode: 0o700 });
    bindings.push(binding);
    context = ctx;
    pi.appendEntry(entryType, binding);
    startTimer();
    const logFile = path.join(root, 'launcher.log');
    const fd = fs.openSync(logFile, 'a', 0o600);
    fs.fchmodSync(fd, 0o600);
    try {
      const child = spawn('python3', ['-B', script, 'run', '--config', file], { cwd: root, detached: true, stdio: ['ignore', fd, fd] });
      try {
        await new Promise<void>((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
      } catch (error) {
        launchWatches.delete(config.run_id);
        bindings = bindings.filter(item => item.root !== root || item.runId !== config.run_id || item.sessionId !== sessionId);
        try { receiver(binding, false); } catch { /* Durable launch record remains authoritative. */ }
        ctx.ui.notify(`Pi Ping Pong ${namedRun?.name ?? path.basename(root)}: bridge could not start (${String(error)}). The launch attempt is recorded; do not relaunch. Inspect ${logFile}.`, 'error');
        return;
      }
      child.unref();
      launchWatches.set(config.run_id, { root, runId: config.run_id, deadline: Date.now() + 45_000 });
      child.once('exit', code => {
        const watch = launchWatches.get(config.run_id);
        if (!watch || watch.root !== root) return;
        try {
          const state = read<{ run_id?: string; status?: string; pi_session?: string; controller_pid?: number }>(path.join(root, 'bridge-status.json'));
          const bound = read<Config>(file);
          if (state.run_id === config.run_id && bound.run_id === config.run_id && bound.pi_session_id === sessionId
            && bound.review_transport === 'pi' && ((typeof state.pi_session === 'string' && state.pi_session.trim().length > 0) || (bound.protocol_version === 2 && Number.isSafeInteger(state.controller_pid) && state.controller_pid! > 0))
            && ['running', 'waiting_pi', 'waiting_codex', 'waiting_human', 'waiting_resource', 'waiting_event', 'complete', 'stopped'].includes(String(state.status))) {
            launchWatches.delete(config.run_id);
            ctx.ui.notify(`Pi Ping Pong ${config.run_id}: ${config.protocol_version === 2 ? 'controller startup confirmed; workers follow verified action selection' : 'worker/session startup confirmed'}.`, 'info');
            return;
          }
        } catch { /* Missing startup state is diagnosed below. */ }
        launchWatches.delete(config.run_id);
        ctx.ui.notify(`Pi Ping Pong ${config.run_id}: bridge exited before worker/session startup was confirmed (exit ${code ?? 'unknown'}); inspect ${logFile}. Do not relaunch.`, 'error');
      });
      ctx.ui.notify(`Launch accepted for ${config.run_id} (bridge pid ${child.pid}); worker/session startup is not yet confirmed. Monitoring for up to 45 seconds; diagnostics: ${logFile}`, 'info');
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
        return startNamedRun(name.trim(), ctx, project, '', false, true);
      }
      const createOption = '＋ Create a new run';
      const labels = runs.map(formatRun);
      const selected = await ctx.ui.select('Pi Ping Pong runs (selection never launches)', [createOption, ...labels]);
      if (!selected) return;
      if (selected === createOption) {
        const name = await ctx.ui.input('Create a named Pi Ping Pong run', 'ASCII kebab-case, e.g. add-linters');
        if (name === undefined || name.trim() === '') return;
        return startNamedRun(name.trim(), ctx, project, '', false, true);
      }
      const info = runs[labels.indexOf(selected)];
      if (!info) return;
      ctx.ui.notify(details(info), info.state === 'unknown/malformed' || info.state === 'attention required' ? 'warning' : 'info');
      if (info.state === 'ready to launch') {
        const action = await ctx.ui.select(`Run ${info.name}`, ['Launch', 'Back']);
        if (action === 'Launch' && info.dir) return launchConfig(path.join(info.dir, 'config.json'), ctx, { project, name: info.name, dir: info.dir });
      } else if (info.state === 'draft/incomplete') {
        const action = await ctx.ui.select(`Run ${info.name}`, ['Continue preparation', 'Back']);
        if (action === 'Continue preparation' && info.dir) return sendPreparation(pi, ctx, project, info.name, info.dir, true, '', Boolean(info.label));
      }
      return;
    }
    if (isExplicitPath(argument) && path.basename(argument) === 'config.json') {
      const file = path.resolve(ctx.cwd, argument.startsWith('~') ? path.join(os.homedir(), argument.slice(1)) : argument);
      return launchConfig(file, ctx);
    }
    const taskOrName = argument.trim();
    const isNameOnly = validRunName(taskOrName);
    const name = isNameOnly ? taskOrName : generatedRunName(taskOrName);
    const project = await resolveProject(ctx);
    if (!project) return;
    return startNamedRun(name, ctx, project, isNameOnly ? '' : taskOrName, !isNameOnly);
  };
  async function startNamedRun(name: string, ctx: ExtensionCommandContext, project: Project, taskDescription = '', taskGenerated = false, createOnly = false) {
    if (!validRunName(name)) {
      ctx.ui.notify(`Invalid run name. Use lowercase ASCII kebab-case, 1–${maxRunNameLength} characters.`, 'error');
      return;
    }
    const current = projectStores(project)[0];
    const matches = listRuns(project).filter(run => run.name === name);
    if (matches.length > 1 && !createOnly) {
      ctx.ui.notify(`More than one run is named ${name}. Use /ppp to select a store, or pass the exact config.json path to launch.\n${matches.map(details).join('\n\n')}`, 'warning');
      return;
    }
    const info = createOnly ? matches.find(run => run.store === current) : matches[0];
    if (info) {
      if (createOnly || taskGenerated) {
        ctx.ui.notify(`This run already exists (${name}); it was not relaunched. ${details(info)}`, 'warning');
        return;
      }
      ctx.ui.notify(details(info), info.state === 'unknown/malformed' || info.state === 'attention required' ? 'warning' : 'info');
      if (info.state === 'ready to launch' && info.dir) return launchConfig(path.join(info.dir, 'config.json'), ctx, { project, name, dir: info.dir });
      if (info.state === 'draft/incomplete' && info.dir) {
        const action = await ctx.ui.select(`Run ${name} is incomplete`, ['Continue preparation', 'Back']);
        if (action === 'Continue preparation') return sendPreparation(pi, ctx, project, name, info.dir, true, taskDescription);
      }
      return;
    }
    try {
      const dir = reserveRun(project, name);
      sendPreparation(pi, ctx, project, name, dir, false, taskDescription, matches.length > 0);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') {
        ctx.ui.notify(`Run ${name} was created concurrently. It was not overwritten; inspect it and retry.`, 'warning');
        return;
      }
      ctx.ui.notify(String(error), 'error');
    }
  }

  // Grant cycles map to native Goal launches; each also adds goal_tokens when that optional cap is configured.
  function goalGrantText(config: Config, count: number, prefix = ''): string | undefined {
    const launches = `${count.toLocaleString('en-US')} ${prefix}Goal ${count === 1 ? 'launch' : 'launches'}`;
    if (config.goal_tokens === undefined || config.goal_tokens === null) return launches;
    const tokens = Number(config.goal_tokens) * count;
    return Number.isSafeInteger(Number(config.goal_tokens)) && Number(config.goal_tokens) > 0 && Number.isSafeInteger(tokens) ? `${launches} and ${tokens.toLocaleString('en-US')} ${prefix}Goal tokens` : undefined;
  }
  type HumanState = { run_id: string; execution: string; wait?: { source?: string; reference?: string } | null; blockers: Record<string, { status?: string; needed?: string }>; requests: Record<string, { main_extension: boolean; main_grant_count?: number; blocker_ids?: string[] }>; grants: { request_id?: string; scope?: string; authority?: string; max_cycles?: number | null; goal_token_windows?: number }[] };
  function humanState(binding: Binding, sessionId: string) {
    const config = read<Config>(path.join(binding.root, 'config.json'));
    if (config.protocol_version !== 2 || config.schema_version !== 1 || config.pi_session_id !== sessionId || config.run_id !== binding.runId || (config.human_transport !== undefined && config.human_transport !== 'pi')) throw new Error('Protocol/session/human-channel identity mismatch; legacy approvals remain unchanged.');
    const state = read<HumanState>(path.join(binding.root, 'execution-state.json'));
    if (state.run_id !== binding.runId || ['halt', 'stop', 'finish', 'cancelled'].includes(state.execution)) throw new Error('Terminal/wrong run: late responses cannot restart it.');
    return state;
  }
  async function humanDialog(binding: Binding, ctx: ExtensionCommandContext): Promise<Record<string, unknown> | undefined> {
    const state = humanState(binding, ctx.sessionManager.getSessionId());
    const choices: { label: string; instruction: Record<string, unknown> }[] = [];
    for (const [id, request] of Object.entries(state.requests)) {
      for (const bid of request.blocker_ids ?? []) {
        const blocker = state.blockers[bid];
        if (blocker?.status === 'open' && !choices.some(choice => (choice.instruction.blocker_ids as string[] | undefined)?.includes(bid))) {
          choices.push({ label: `Answer request: ${blocker.needed ?? bid} (${bid})`, instruction: { kind: 'resolution', blocker_ids: [bid] } });
        }
      }
      if (request.main_extension && state.wait?.source === 'human-response' && state.wait.reference === id && request.main_grant_count === state.grants.length && !state.grants.some(grant => grant.request_id === id)) {
        const config = read<Config>(path.join(binding.root, 'config.json'));
        if (config.mode === 'goal' && goalGrantText(config, 3)) {
          for (const count of [1, 3]) choices.push({ label: `Continue work — add ${goalGrantText(config, count)}`, instruction: { kind: 'grant', request_id: id, cycles: count, message: 'Continue work with the selected additional Goal budget.' } });
          choices.push({ label: 'Continue work — choose another number of Goal launches', instruction: { kind: 'grant', request_id: id } });
        } else if (config.mode === 'ralph' || config.mode === 'ping-pong') {
          for (const count of [1, 3]) choices.push({ label: `Continue work — add ${count} Worker ${count === 1 ? 'iteration' : 'iterations'}`, instruction: { kind: 'grant', request_id: id, cycles: count, message: 'Continue work with the selected additional Worker iterations.' } });
          choices.push({ label: 'Continue work — choose another number of Worker iterations', instruction: { kind: 'grant', request_id: id } });
        } else {
          throw new Error('Cannot show a budget choice: run mode or Goal token budget is invalid.');
        }
      }
    }
    choices.push({ label: 'Send a message to Core (not a resolution or budget grant)', instruction: { kind: 'signal' } },
      { label: 'Cancel this run', instruction: { kind: 'cancel' } },
      { label: 'Halt this run', instruction: { kind: 'halt' } });
    const explain = 'Explain current status (no changes)';
    const action = await ctx.ui.select(`Respond to ${path.basename(binding.root)}`, [explain, ...choices.map(choice => choice.label)]);
    if (!action) return;
    if (action === explain) {
      ctx.ui.notify(compactStatus(inspectRun(path.basename(binding.root), binding.root), binding), 'info');
      return;
    }
    const choice = choices.find(item => item.label === action);
    if (!choice) return;
    const input = { ...choice.instruction };
    if (input.kind === 'grant' && input.cycles === undefined) {
      const config = read<Config>(path.join(binding.root, 'config.json'));
      const goal = config.mode === 'goal';
      const perLaunch = config.goal_tokens === undefined || config.goal_tokens === null ? '' : ` Each launch also adds ${Number(config.goal_tokens).toLocaleString('en-US')} Goal tokens.`;
      const count = await ctx.ui.input(goal ? 'How many more Goal launches?' : 'How many more Worker iterations?', goal ? `Enter a positive whole number. Each launch can start one new native Goal.${perLaunch}` : 'Enter a positive whole number. Reviews do not use these iterations.');
      if (count === undefined) return;
      const amount = Number(count.replaceAll(',', '').trim());
      if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(count.trim()) || !Number.isSafeInteger(amount) || amount <= 0 || (goal && !goalGrantText(config, amount))) throw new Error(goal ? 'Enter a positive whole number of Goal launches. No budget was added.' : 'Enter a positive whole number of Worker iterations. No budget was added.');
      input.cycles = amount;
      input.message = goal ? 'Continue work with the selected additional Goal budget.' : 'Continue work with the selected additional Worker iterations.';
    }
    if (input.kind === 'grant') return input;
    const message = await ctx.ui.input(input.kind === 'resolution' ? 'Your answer: what changed or was configured?' : 'Describe your instruction', 'Ordinary text, no JSON or secrets. A response is independently checked.');
    if (message === undefined) return;
    input.message = message;
    return input;
  }
  pi.registerCommand('ppp-respond', {
    description: 'Choose a run and human action without JSON; confirm before recording. Advanced: <run-id> <JSON>. Never paste secrets.',
    handler: async (args, ctx) => {
      try {
        if (!ctx.hasUI || ctx.mode !== 'tui') throw new Error('Human authority requires the interactive receiver confirmation, not a worker/RPC flag.');
        const sessionId = ctx.sessionManager.getSessionId();
        const argument = args.trim();
        const match = /^(\S+)\s+(\{[\s\S]*)$/.exec(argument);
        let binding: Binding | undefined;
        let input: Record<string, unknown> | undefined;
        if (match) {
          binding = bindings.find(b => b.runId === match[1] && b.sessionId === sessionId);
          if (!binding) throw new Error('No run attached to this receiver session.');
          try { input = JSON.parse(match[2]) as Record<string, unknown>; }
          catch { throw new Error('Invalid advanced JSON. Use /ppp-respond without arguments for the action menu.'); }
        } else {
          const candidates = bindings.filter(b => {
            if (b.sessionId !== sessionId) return false;
            try { humanState(b, sessionId); return true; } catch { return false; }
          });
          if (argument) {
            const matches = candidates.filter(b => b.runId === argument || path.basename(b.root) === argument);
            if (matches.length === 1) binding = matches[0];
            else {
              ctx.ui.notify('Questions are not authorizations: ask Chat A in ordinary chat, or inspect /ppp-status. Use /ppp-respond without arguments to choose a run and action; no ID or JSON is needed.', 'info');
              return;
            }
          } else if (candidates.length === 1) binding = candidates[0];
          else if (candidates.length > 1) {
            const names = candidates.map(b => path.basename(b.root));
            const labels = candidates.map((b, i) => {
              const info = inspectRun(names[i], b.root);
              const name = names.indexOf(names[i]) === names.lastIndexOf(names[i]) ? names[i] : b.root;
              return `${name} — ${info.mode ?? 'run'} · ${info.state}`;
            });
            const selected = await ctx.ui.select('Choose the run to respond to', labels);
            if (!selected) return;
            binding = candidates[labels.indexOf(selected)];
          } else throw new Error('No active protocol-2 run is attached to this chat. Inspect /ppp-status; completed runs cannot be restarted by a response.');
          if (!binding) return;
          input = await humanDialog(binding, ctx);
          if (!input) return;
        }
        const state = humanState(binding, sessionId);
        if (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).some(k => !['kind', 'message', 'blocker_ids', 'cycles', 'request_id'].includes(k))) throw new Error('Unexpected human response fields.');
        if (!['resolution', 'grant', 'cancel', 'halt', 'signal'].includes(String(input.kind))) throw new Error('Unknown response kind.');
        if (typeof input.message !== 'string' || !input.message.trim() || input.message.length > 4000 || hasSecret(input.message)) throw new Error('Use a short non-secret description; configure credentials securely outside chat.');
        if (input.kind === 'resolution' && (!Array.isArray(input.blocker_ids) || input.blocker_ids.length === 0 || !input.blocker_ids.every(b => typeof b === 'string' && Object.hasOwn(state.blockers, b)))) throw new Error('Address existing blocker IDs explicitly.');
        if (input.kind === 'grant' && (!Number.isSafeInteger(input.cycles) || Number(input.cycles) <= 0 || typeof input.request_id !== 'string' || !state.requests[input.request_id]?.main_extension || state.requests[input.request_id].main_grant_count !== state.grants.length || state.grants.some(g => g.request_id === input.request_id))) throw new Error('This budget request is no longer current. Open /ppp-respond again; no budget was added.');
        const inbox = path.join(binding.root, 'human-inbox');
        if (fs.existsSync(inbox) && (fs.lstatSync(inbox).isSymbolicLink() || !isPrivate(fs.statSync(inbox)))) throw new Error('Human inbox must be a private non-symlink directory.');
        if (input.kind === 'grant' && fs.existsSync(inbox) && fs.readdirSync(inbox).filter(name => name.endsWith('.json')).some(name => {
          const prior = read<{ kind?: string; request_id?: string }>(path.join(inbox, name));
          return prior.kind === 'grant' && prior.request_id === input.request_id;
        })) throw new Error('Authorization for this main-budget request is already recorded; no duplicate grant.');
        const actionLabels: Record<string, string> = { resolution: 'Answer an addressed request', grant: 'Authorize additional main cycles', signal: 'Send a non-authorizing message', cancel: 'Cancel this run permanently', halt: 'Halt this run permanently' };
        const config = read<Config>(path.join(binding.root, 'config.json'));
        const goalGrant = config.mode === 'goal';
        const goalTokens = config.goal_tokens === undefined || config.goal_tokens === null ? undefined : Number(config.goal_tokens);
        const grantAmount = goalGrant
          ? goalGrantText(config, Number(input.cycles), 'additional ')
          : `${input.cycles} additional Worker iterations`;
        if (input.kind === 'grant' && goalGrant && !grantAmount) throw new Error('Invalid Goal budget configuration; no budget was added.');
        const windows = state.grants.filter(g => g.scope === 'main' && g.authority !== 'initial-contract').map(g => g.goal_token_windows ?? g.max_cycles);
        const total = goalGrant && goalTokens !== undefined && state.grants.some(g => g.scope === 'main' && g.authority === 'initial-contract') && windows.every(w => Number.isSafeInteger(w) && Number(w) >= 0)
          ? goalTokens * (1 + windows.reduce<number>((sum, w) => sum + Number(w), 0) + Number(input.cycles)) : undefined;
        const totalText = Number.isSafeInteger(total) ? ` Total Goal limit: ${Number(total).toLocaleString('en-US')} tokens.` : '';
        const summary = input.kind === 'grant' ? `Run: ${path.basename(binding.root)}\nContinue work with ${grantAmount}.${totalText} No automatic renewal.\n${goalGrant && goalTokens !== undefined ? 'Includes repeated context and cache reads; the last response may exceed the limit. This is not a dollar cap.\n' : ''}Independent checks have a separate budget.` : [`Run: ${path.basename(binding.root)} (${binding.runId})`, `Action: ${actionLabels[String(input.kind)]}`,
          ...(Array.isArray(input.blocker_ids) ? [`Addresses: ${input.blocker_ids.join(', ')}`] : []),
          ...(input.kind === 'grant' ? [`Explicitly authorize ${input.cycles} additional main cycles for ${input.request_id}.`] : []),
          `Message: ${input.message}`, 'Responses are independently checked; this is not acceptance. Cancel/halt stops the run, not a pause. No secrets.'].join('\n');
        if (!await ctx.ui.confirm(input.kind === 'grant' ? 'Continue work?' : 'Record this human instruction?', summary)) return;
        if (ctx.sessionManager.getSessionId() !== sessionId) throw new Error('Session changed; instruction was not recorded.');
        const current = humanState(binding, sessionId);
        if (input.kind === 'grant' && (typeof input.request_id !== 'string' || !current.requests[input.request_id]?.main_extension || current.requests[input.request_id].main_grant_count !== current.grants.length || (!match && (current.wait?.source !== 'human-response' || current.wait.reference !== input.request_id)) || current.grants.some(g => g.request_id === input.request_id))) throw new Error('The budget request changed while you were deciding. Open /ppp-respond again; no budget was added.');
        const id = randomUUID();
        fs.mkdirSync(inbox, { recursive: true, mode: 0o700 });
        if (fs.lstatSync(inbox).isSymbolicLink() || !isPrivate(fs.statSync(inbox))) throw new Error('Human inbox must be a private non-symlink directory.');
        atomic(path.join(inbox, `${id}.json`), { protocol_version: 2, schema_version: 1, run_id: binding.runId, session_id: binding.sessionId, id, source: 'pi-command', ...input });
        pi.appendEntry('pi-ppp-human', { run_id: binding.runId, response_id: id, kind: input.kind });
        const script = process.env.PI_PING_PONG_BRIDGE || path.join(os.homedir(), '.agents/skills/pi-ping-pong/scripts/bridge.py');
        const fd = fs.openSync(path.join(binding.root, 'launcher.log'), 'a', 0o600);
        try {
          const child = spawn('python3', ['-B', script, 'wake', '--config', path.join(binding.root, 'config.json')], { cwd: binding.root, detached: true, stdio: ['ignore', fd, fd] });
          child.once('error', error => ctx.ui.notify(`Response is durable; wake failed: ${String(error)}. Inspect launcher.log before explicit reconciled resume.`, 'error'));
          child.unref();
        } finally { fs.closeSync(fd); }
        ctx.ui.notify(input.kind === 'grant' ? 'Budget recorded. Work can continue after the controller applies it.' : `Recorded ${id}. Controller applies it at a safe boundary; a response alone never resolves a blocker.`, 'info');
      } catch (error) { ctx.ui.notify(String(error), 'error'); }
    },
  });

  for (const command of ['pi-ping-pong', 'reviewed-run', 'ppp']) {
    pi.registerCommand(command, {
      description: command === 'ppp' ? 'Short alias for /pi-ping-pong.' : command === 'reviewed-run' ? 'Compatibility alias for /pi-ping-pong.' : 'Open runs, prepare a named run, or launch an existing run/config.',
      handler: startReviewedRun,
    });
  }
  async function statusRuns(ctx: ExtensionCommandContext, all: boolean) {
    const byPath = new Map<string, { info: RunInfo; binding?: Binding }>();
    if (all) {
      const project = await resolveProject(ctx);
      if (project) {
        try {
          for (const info of listRuns(project)) byPath.set(info.dir ? canonicalPath(info.dir) : `invalid:${info.store}:${info.name}`, { info });
        } catch (error) { byPath.set(`project-error:${project.root}`, { info: { name: 'Project runs', state: 'unknown/malformed', details: String(error) } }); }
      }
    }
    const sessionId = ctx.sessionManager.getSessionId();
    for (const binding of bindings) {
      if (binding.sessionId !== sessionId) continue;
      const canonical = canonicalPath(binding.root);
      const prior = byPath.get(canonical);
      if (prior) { prior.binding = binding; continue; }
      let info: RunInfo;
      try { info = inspectRun(path.basename(binding.root), binding.root); }
      catch { info = { name: path.basename(binding.root), dir: binding.root, state: 'unknown/malformed' }; }
      byPath.set(canonical, { info, binding });
    }
    const runs = [...byPath.values()];
    labelCollisions(runs.map(row => row.info));
    return runs;
  }
  const showReviewedStatus = async (args: string, ctx: ExtensionCommandContext) => {
    const flags = args.trim() ? args.trim().split(/\s+/) : [];
    if (flags.some(flag => !['--all', '--details'].includes(flag))) {
      ctx.ui.notify('Use /ppp-status for this chat, --all for project runs, or --details for explicit technical output.', 'info');
      return;
    }
    let all = flags.includes('--all');
    while (true) {
      const runs = await statusRuns(ctx, all);
      if (flags.includes('--details') || !ctx.hasUI || ctx.mode !== 'tui') {
        const render = flags.includes('--details') ? detailedStatus : compactStatus;
        ctx.ui.notify(runs.map(({ info, binding }) => render(info, binding)).join('\n\n') || 'No runs attached to this chat. Use /ppp-status --all to inspect project runs.', 'info');
        return;
      }
      const labels = runs.map(({ info, binding }, index) => {
        const view = statusView(info, binding);
        return `${index + 1}. ${info.label ?? info.name} — ${view.label} · cycles ${view.cycle}`;
      });
      const switchScope = all ? 'Back to runs in this chat' : 'All runs in this project…';
      const title = all ? 'All project and attached runs (read-only)' : runs.length ? 'Runs in this chat, including completed (read-only)' : 'No runs attached to this chat (read-only)';
      const selected = await ctx.ui.select(title, [...labels, switchScope]);
      if (!selected) return;
      if (selected === switchScope) { all = !all; continue; }
      const row = runs[labels.indexOf(selected)];
      if (!row) return;
      ctx.ui.notify(compactStatus(row.info, row.binding), 'info');
      const action = await ctx.ui.select(`Details: ${row.info.name}`, ['Technical details', 'Done']);
      if (action === 'Technical details') ctx.ui.notify(detailedStatus(row.info, row.binding), 'info');
      return;
    }
  };
  for (const command of ['pi-ping-pong-status', 'reviewed-status', 'ppp-status']) {
    pi.registerCommand(command, {
      description: command === 'ppp-status' ? 'Short alias for /pi-ping-pong-status.' : command === 'reviewed-status' ? 'Compatibility alias for /pi-ping-pong-status.' : 'Browse runs in this chat; project runs and technical details are optional. Read-only; no model calls.',
      handler: showReviewedStatus,
    });
  }
}
