// Observe the standard Node spawn boundary, including Pi's bundled shell implementation.
import fs from 'node:fs';
import path from 'node:path';
import { ChildProcess } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { StringDecoder } from 'node:string_decoder';

function saveUsage(destination, record) {
  const temporary = `${destination}.${randomUUID()}.tmp`;
  const fd = fs.openSync(temporary, 'wx', 0o600);
  try {
    try {
      fs.writeFileSync(fd, JSON.stringify(record));
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(temporary, destination);
    const parent = fs.openSync(path.dirname(destination), 'r');
    try { fs.fsyncSync(parent); } finally { fs.closeSync(parent); }
  } finally {
    fs.rmSync(temporary, { force: true });
  }
}

function observeUsage(stdout, count) {
  const emit = stdout.emit;
  const decoder = new StringDecoder('utf8');
  const responseIds = new Set();
  let pending = '';
  let oversized = false;
  stdout.emit = function (event, ...args) {
    // Observe only bytes the runner already reads; adding a 'data' listener would start flowing.
    const result = emit.call(this, event, ...args);
    if (event !== 'data' || !Buffer.isBuffer(args[0])) return result;
    const chunk = decoder.write(args[0]);
    for (let start = 0; start < chunk.length;) {
      const newline = chunk.indexOf('\n', start);
      const end = newline < 0 ? chunk.length : newline;
      oversized ||= pending.length + end - start > 1024 * 1024;
      if (!oversized) pending += chunk.slice(start, end);
      if (newline < 0) break;
      try {
        const event = !oversized && JSON.parse(pending);
        const message = event?.type === 'message_end' ? event.message : null;
        const tokens = message?.usage?.totalTokens;
        const id = message?.responseId;
        if (message?.role === 'assistant' && Number.isSafeInteger(tokens) && tokens >= 0 &&
            (tokens > 0 || !['error', 'aborted'].includes(message.stopReason)) &&
            (!id || (typeof id === 'string' && id.length <= 512 && responseIds.size < 8192 && !responseIds.has(id)))) {
          if (id) responseIds.add(id);
          count(tokens);
        }
      } catch { /* Malformed frames or unavailable storage cannot interrupt Ralph. */ }
      pending = '';
      oversized = false;
      start = newline + 1;
    }
    return result;
  };
}

const directory = process.env.PPP_RALPH_GUARDS;
if (directory) {
  if (!process.env.RALPH_RUNNER_LOOP_TOKEN) {
    process.env.PPP_RALPH_HOST_PID = String(process.pid);
    const nativeChildren = new Map();
    const dispatch = process.env.PPP_RALPH_USAGE_DISPATCH;
    const taskDir = process.env.PPP_RALPH_USAGE_TASK_DIR;
    const cwd = process.cwd();
    const usage = { dispatch, host: process.pid, loop_token: null, tokens: 0 };
    const usagePath = path.join(directory, 'usage.json');
    const spawn = ChildProcess.prototype.spawn;
    ChildProcess.prototype.spawn = function (options) {
      const result = spawn.call(this, options);
      const token = options.envPairs?.find(pair => pair.startsWith('RALPH_RUNNER_LOOP_TOKEN='))?.slice('RALPH_RUNNER_LOOP_TOKEN='.length);
      if (options.detached && this.pid && token) {
        const pid = this.pid;
        nativeChildren.set(pid, this);
        this.once('exit', () => nativeChildren.delete(pid));
        const mode = options.args.indexOf('--mode');
        if (dispatch && taskDir && this.stdout && options.cwd === cwd && mode >= 0 && options.args[mode + 1] === 'rpc' &&
            options.args.includes('--no-session') && options.envPairs.includes(`RALPH_RUNNER_TASK_DIR=${taskDir}`) &&
            options.envPairs.includes(`RALPH_RUNNER_CWD=${cwd}`) && (!usage.loop_token || usage.loop_token === token)) {
          usage.loop_token = token;
          observeUsage(this.stdout, tokens => {
            if (!Number.isSafeInteger(usage.tokens + tokens)) return;
            usage.tokens += tokens;
            saveUsage(usagePath, usage);
          });
        }
      }
      return result;
    };
    // Native Ralph uses SIGKILL even on ordinary completion; allow the owned child's guard to drain shells first.
    const kill = process.kill.bind(process);
    process.kill = (pid, signal) => {
      const child = signal === 'SIGKILL' && pid < 0 ? nativeChildren.get(-pid) : undefined;
      if (!child) return kill(pid, signal);
      const result = kill(pid, 'SIGTERM');
      setTimeout(() => {
        if (nativeChildren.get(-pid) === child) {
          try { kill(pid, 'SIGKILL'); } catch { /* Already exited. */ }
        }
      }, 250).unref();
      return result;
    };
    fs.writeFileSync(path.join(directory, 'host.json'), JSON.stringify({ pid: process.pid, cleanup_supported: true }), { flag: 'wx', mode: 0o600 });
  } else {
    const host = Number(process.env.PPP_RALPH_HOST_PID);
    const token = process.env.RALPH_RUNNER_LOOP_TOKEN;
    const marker = path.join(directory, `child-${process.pid}.json`);
    const record = { pid: process.pid, host, loop_token: token, cleaned: false, detached_pids: [] };
    const save = () => {
      fs.writeFileSync(marker + '.tmp', JSON.stringify(record), { mode: 0o600 });
      fs.renameSync(marker + '.tmp', marker);
    };
    fs.writeFileSync(marker, JSON.stringify(record), { flag: 'wx', mode: 0o600 });
    // Project Node commands are not Ralph RPC children and must not inherit this preload.
    process.env.NODE_OPTIONS = (process.env.NODE_OPTIONS || '').replace(process.env.PPP_RALPH_GUARD_IMPORT || `--import=${import.meta.url}`, '').trim();
    const children = new Set();
    const kill = pid => {
      try { process.kill(-pid, 'SIGSTOP'); } catch { /* A failed stop must not skip the kill attempt. */ }
      try { process.kill(-pid, 'SIGKILL'); } catch (error) {
        if (error.code !== 'ESRCH') (record.cleanup_errors ??= []).push({ pid, code: error.code });
      }
    };
    const spawn = ChildProcess.prototype.spawn;
    ChildProcess.prototype.spawn = function (options) {
      const result = spawn.call(this, options);
      if (options.detached && this.pid) {
        const pid = this.pid;
        children.add(pid);
        record.detached_pids.push(pid);
        save();
        this.once('exit', () => {
          // A shell leader's exit does not establish that its background descendants exited.
          if (children.delete(pid)) kill(pid);
        });
      }
      return result;
    };
    const cleanup = () => {
      for (const pid of children) kill(pid);
      children.clear();
      record.cleaned = true; // Signals sent; Core independently checks every recorded group.
      save();
    };
    const stop = () => {
      try { cleanup(); } finally {
        try { process.kill(-process.pid, 'SIGKILL'); } catch { process.exit(1); }
      }
    };
    process.on('exit', cleanup);
    process.on('uncaughtExceptionMonitor', cleanup);
    process.on('SIGTERM', stop);
    process.on('SIGHUP', stop);
    const check = () => {
      let requested = false;
      try { requested = fs.readFileSync(path.join(directory, 'stop.flag'), 'utf8').trim() === token; } catch { /* No stop request yet. */ }
      if (process.ppid !== host || requested) stop();
    };
    check();
    setInterval(check, 100).unref();
    const seconds = Number(process.env.PPP_RALPH_ITERATION_SECONDS);
    if (seconds > 0) setTimeout(stop, Math.max(1, seconds * 1000 - 100)).unref();
  }
}
