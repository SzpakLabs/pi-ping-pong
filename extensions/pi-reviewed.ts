import { spawn } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from '@earendil-works/pi-coding-agent';

type Binding = { root: string; runId: string; sessionId: string };
type Config = { run_id: string; review_model: string; review_provider?: string; [key: string]: unknown };
type Envelope = { id: string; run_id: string; session_id: string; kind: string; message: string; receipt: string };
const entryType = 'pi-reviewed-run';
const read = <T>(file: string): T => JSON.parse(fs.readFileSync(file, 'utf8')) as T;
function atomic(file: string, data: unknown) {
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(data, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(temporary, file);
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
          // Dispatch ambiguity after a crash is preserved, never replayed automatically.
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
  const startReviewedRun = async (args: string, ctx: ExtensionCommandContext) => {
      const argument = args.trim().replace(/^(["'])(.*)\1$/, '$2');
      if (!argument) {
        const reviewerDefault = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : 'not selected; choose a reviewer model';
        const preparationPrompt = `Prepare a Pi Ping Pong run from this conversation. First reuse every relevant detail the user has already provided; ask only for missing information. Do not start or launch the worker during preparation.

Collect or confirm these fields before creating files:
- task and independently checkable acceptance criteria;
- mode: Goal or Ralph;
- worker provider and exact model (the user must choose; never guess or silently reuse the reviewer model);
- reviewer provider/model (suggest the current Pi model ${reviewerDefault} as the default; use it if accepted, otherwise ask for the requested pair);
- target project and exact allowed filesystem paths (current Pi working directory: ${ctx.cwd} is context, not automatic authorization to modify it);
- finite positive max_cycles, cycle_seconds, review_seconds, and wall_seconds.

If any field is missing or ambiguous, ask concise grouped questions and do not create the run yet. Once resolved, prepare only these artifacts in a unique private run directory under ${path.join(os.homedir(), '.pi/reviewed-runs')} (the expanded path for ~/.pi/reviewed-runs/<UUID>, outside the source project): TASK.md, config.json, and eval.py. Generate a UUID run_id and create the directory exclusively with mode 0700; create TASK.md, config.json, and eval.py with mode 0600. Do not overwrite an existing run. Keep secrets out of all files.

The config must match the bridge contract: run_id, mode, worker_provider, worker_model, review_model, review_provider, finite max_cycles/cycle_seconds/review_seconds/wall_seconds, task: TASK.md, and eval_argv invoking python3 on the absolute eval.py path. Set review_transport to pi, but do not invent or write pi_session_id; the launcher binds it only when explicitly run. Do not put thread_id in this Pi-review config.

Write a task-specific independent evaluator that checks the acceptance criteria against actual project outputs/state, not the worker's checkpoint or self-report. It must return nonzero for missing or unmet criteria. Explain each criterion-to-check mapping; if a criterion cannot be independently evaluated, clarify it with the user rather than using a fake always-success evaluator or claiming verification.

After preparing, report the task, criteria, mode, worker and reviewer provider/models, exact allowed paths, eval command, all finite limits, and the actual config.json path. State that no worker was started, and give the ready command: /pi-ping-pong <actual-config-path>. Do not execute that command, invoke the bridge, create launch-attempt.json, attach the run to the reviewer session, append a run entry, or say “Started”.`;
        pi.sendUserMessage(preparationPrompt, ctx.isIdle() ? undefined : { deliverAs: 'followUp' });
        return;
      }
      const file = path.resolve(argument);
      if (path.basename(file) !== 'config.json') throw new Error('Expected /pi-ping-pong /absolute/run/config.json, or run /pi-ping-pong without arguments to prepare a run.');
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) throw new Error(`Config not found: ${file}. Run /pi-ping-pong without arguments to prepare a run.`);
      const root = path.dirname(file);
      const config = read<Config>(file);
      if (!config.run_id || !config.review_model || !['goal', 'ralph'].includes(String(config.mode))) throw new Error('Config needs run_id, mode=goal|ralph and review_model.');
      if (ctx.model?.id !== config.review_model) throw new Error(`Select reviewer model ${config.review_model} before launch.`);
      if (fs.existsSync(path.join(root, 'launch-attempt.json')) || fs.existsSync(path.join(root, 'bridge-status.json'))) throw new Error('Run already launched; inspect its state instead of replaying it.');
      const sessionId = ctx.sessionManager.getSessionId();
      config.review_transport = 'pi';
      config.pi_session_id = sessionId;
      config.review_provider = ctx.model.provider;
      delete config.thread_id;
      atomic(file, config);
      const binding = { root, runId: config.run_id, sessionId };
      receiver(binding, true);
      fs.mkdirSync(path.join(root, 'pi-inbox'), { recursive: true });
      bindings.push(binding);
      context = ctx;
      pi.appendEntry(entryType, binding);
      startTimer();
      const script = process.env.PI_PING_PONG_BRIDGE || path.join(os.homedir(), '.agents/skills/pi-ping-pong/scripts/bridge.py');
      const fd = fs.openSync(path.join(root, 'launcher.log'), 'a', 0o600);
      atomic(path.join(root, 'launch-attempt.json'), { session_id: sessionId, at: Date.now() });
      try {
        const child = spawn('python3', ['-B', script, 'run', '--config', file], { cwd: root, detached: true, stdio: ['ignore', fd, fd] });
        await new Promise<void>((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
        child.unref();
        ctx.ui.notify(`Started ${config.run_id} (pid ${child.pid}). Checkpoints return to this Pi session.`, 'info');
      } finally { fs.closeSync(fd); }
  };
  for (const command of ['pi-ping-pong', 'reviewed-run']) {
    pi.registerCommand(command, {
      description: command === 'pi-ping-pong'
        ? 'Prepare a run with no arguments, or launch one from config.json. Usage: /pi-ping-pong [/absolute/run/config.json]'
        : 'Compatibility alias for /pi-ping-pong.',
      handler: startReviewedRun,
    });
  }
  const showReviewedStatus = async (_args: string, ctx: ExtensionContext) => {
    for (const binding of bindings) {
      try {
        const state = read<{ status: string; cycle: number }>(path.join(binding.root, 'bridge-status.json'));
        ctx.ui.notify(`${binding.runId}: ${state.status}, cycle ${state.cycle}. ${binding.root}`, 'info');
      } catch { ctx.ui.notify(`${binding.runId}: starting or unavailable. ${binding.root}`, 'warning'); }
    }
    if (!bindings.length) ctx.ui.notify('No reviewed runs attached to this session.', 'info');
  };
  for (const command of ['pi-ping-pong-status', 'reviewed-status']) {
    pi.registerCommand(command, {
      description: command === 'pi-ping-pong-status'
        ? 'Show reviewed runs attached to this Pi session without starting model work.'
        : 'Compatibility alias for /pi-ping-pong-status.',
      handler: showReviewedStatus,
    });
  }
}
