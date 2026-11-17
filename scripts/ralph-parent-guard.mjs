// Observe the standard Node spawn boundary, including Pi's bundled shell implementation.
import fs from 'node:fs';
import path from 'node:path';
import { ChildProcess } from 'node:child_process';

const directory = process.env.PPP_RALPH_GUARDS;
if (directory) {
  if (!process.env.RALPH_RUNNER_LOOP_TOKEN) {
    process.env.PPP_RALPH_HOST_PID = String(process.pid);
    const nativeChildren = new Map();
    const spawn = ChildProcess.prototype.spawn;
    ChildProcess.prototype.spawn = function (options) {
      const result = spawn.call(this, options);
      if (options.detached && this.pid && options.envPairs?.some(pair => pair.startsWith('RALPH_RUNNER_LOOP_TOKEN=') && pair !== 'RALPH_RUNNER_LOOP_TOKEN=')) {
        const pid = this.pid;
        nativeChildren.set(pid, this);
        this.once('exit', () => nativeChildren.delete(pid));
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
