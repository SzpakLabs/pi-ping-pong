import { spawn } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import type { ExtensionAPI, ExtensionContext } from '@earendil-works/pi-coding-agent';

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
  const startReviewedRun = async (args: string, ctx: ExtensionContext) => {
      const file = path.resolve(args.trim().replace(/^(["'])(.*)\1$/, '$2'));
      if (!args.trim() || path.basename(file) !== 'config.json') throw new Error('Usage: /pi-ping-pong /absolute/run/config.json');
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
        ? 'Start a bounded Goal/Ralph run from config.json. Usage: /pi-ping-pong /absolute/run/config.json'
        : 'Compatibility alias for /pi-ping-pong.',
      handler: startReviewedRun,
    });
  }
  pi.registerCommand('reviewed-status', {
    description: 'Show reviewed runs attached to this Pi session without starting model work.',
    handler: async (_args, ctx) => {
      for (const binding of bindings) {
        try {
          const state = read<{ status: string; cycle: number }>(path.join(binding.root, 'bridge-status.json'));
          ctx.ui.notify(`${binding.runId}: ${state.status}, cycle ${state.cycle}. ${binding.root}`, 'info');
        } catch { ctx.ui.notify(`${binding.runId}: starting or unavailable. ${binding.root}`, 'warning'); }
      }
      if (!bindings.length) ctx.ui.notify('No reviewed runs attached to this session.', 'info');
    },
  });
}
