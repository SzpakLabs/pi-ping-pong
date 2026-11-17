#!/usr/bin/env python3
"""Bounded Pi RPC transport + Codex queue checkpoints. Python stdlib only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import select
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid


REPORT_GUIDANCE = '''Every report delivered to the launching chat must be self-contained, readable without
opening files, and use this order:
1. A prominent first line: STATUS — <current run state>, with lifecycle and acceptance
   kept distinct (never infer acceptance from exit/completion alone).
2. TL;DR — the essential result in one or two sentences.
3. Summary — what was done and what it means to the user's task.
4. Report — use these subsections: Steps; Verification and errors; Escalation;
   Completion. State the ordinary test results, independent review findings,
   errors/corrections, and verified versus outstanding criteria. Say "None" for
   errors or escalation when none occurred; do not omit these subsections.
5. Suggested action — give an exact action only when needed. Otherwise explicitly
   say no user action is needed and name the automatic next step or that the run
   is finished. Never ask for routine confirmation or vague suggestions.
6. Full run status — include run ID and mode; current phase/execution/lifecycle;
   cycle and remaining authorized budget; latest checkpoint/review; every criterion
   and action state; open blockers, human receipts/resolutions, grants and external
   operation outcomes; worker/reviewer roles and models when known; errors and
   unavailable/unknown data (including usage or process cleanup). Do not omit
   fields just because they are unknown; label them unknown/not observed.

Keep the summary ahead of paths and jargon. Include only the most relevant evidence
paths, with a short explanation of what each proves; paths supplement, never replace,
the account of what happened. Do not claim checks or actions without recorded
evidence. Distinguish verified completion from intermediate progress, waiting,
stopped work, and unknown outcomes. If user input is genuinely required, state the
precise missing decision/input and why it blocks progress under Escalation, then
give the exact requested action under Suggested action. If there are multiple valid
choices, list at most three, briefly state each option's main benefit and cost/risk,
and recommend one with reason. Separate actual approval/access requirements from
ordinary preferences. Do not end by asking a vague question or asking the user to confirm routine work.'''


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def goal_snapshot(entries):
    states = [(index, entry.get('data', {}).get('goal')) for index, entry in enumerate(entries)
              if entry.get('type') == 'custom' and entry.get('customType') == 'goal-state']
    if not states:
        return -1, {}
    index, goal = states[-1]
    # Native goal_complete persists complete, then clears it before returning its result.
    if len(states) > 1 and entries[index].get('data', {}).get('goal', {}) is None:
        completed_index, completed = states[-2]
        if isinstance(completed, dict) and completed.get('id') and completed.get('status') == 'complete' and type(completed.get('tokensUsed')) is int and completed['tokensUsed'] >= 0:
            tail = [entry.get('message', {}) for entry in entries[completed_index + 1:] if entry.get('type') == 'message']
            # Assistant turns after completion are outside native tokensUsed: meter them exactly or leave usage unknown.
            extra = [(message.get('usage') or {}).get('totalTokens') if isinstance(message.get('usage'), dict) else None for message in tail if message.get('role') == 'assistant']
            if all(type(tokens) is int and tokens >= 0 for tokens in extra) and any(
                entry.get('type') == 'message' and entry.get('message', {}).get('role') == 'toolResult'
                and entry['message'].get('toolName') == 'goal_complete' and entry['message'].get('isError') is False
                and entry['message'].get('details', {}).get('goal_id') == completed['id']
                and any(part.get('type') == 'text' and part.get('text', '').startswith('Goal complete:') for part in entry['message'].get('content', []))
                for entry in entries[index + 1:]
            ):
                return completed_index, {**completed, 'postCompletionTokens': sum(extra)}
    return index, goal or {}


def inside(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("Evidence escapes run work directory")
    if any(part.startswith('.env') or part.lower() in {'auth.json', 'credentials.json'} for part in p.parts):
        raise ValueError("Secret-bearing paths must not be checkpoint evidence")
    return p


def evidence_path(c, name):
    work = Path(c['root']) / 'work'
    path = (work / name).resolve()
    target = c.get('execution_contract', {}).get('target') if c.get('protocol_version', 1) == 2 else None
    if path.is_relative_to(work.resolve()):
        return inside(work, name)
    if isinstance(target, str) and Path(target).is_absolute() and path.is_relative_to(Path(target).resolve()):
        if any(part.startswith('.env') or part.lower() in {'auth.json', 'credentials.json'} for part in path.parts):
            raise ValueError('Secret-bearing paths must not be checkpoint evidence')
        return path
    raise ValueError(f'Evidence escapes run work directory and authorized target: {name!r} resolves to {path}; work base: {work.resolve()}; target: {target!r}')


def load_config(path):
    c = read(path)
    # Goal is bounded by wall/review seconds and goal_max_launches (+ optional goal_tokens); cycle fields stay optional.
    cycle_limits = () if c.get('mode') == 'goal' else ('max_cycles', 'cycle_seconds')
    for key in ('run_id', 'mode', 'worker_model', 'review_model', 'task', 'wall_seconds', 'review_seconds', *cycle_limits):
        if key not in c:
            raise ValueError(f'Missing config: {key}')
    for key in ('worker_extensions', 'reviewer_extensions'):
        if key in c:
            paths = c[key]
            if not isinstance(paths, list) or any(not isinstance(p, str) or not p.strip() or '\x00' in p for p in paths):
                raise ValueError(f'{key} must be a list of non-empty paths')
            c[key] = [str((Path(path).resolve().parent / p).resolve()) for p in paths]
    limit = c.setdefault('max_evidence_files', 20)
    if type(limit) is not int or limit < 1:
        raise ValueError('max_evidence_files must be a positive integer')
    transport = c.setdefault('review_transport', 'codex')
    if transport == 'codex':
        if not c.get('thread_id'):
            raise ValueError('Codex transport needs thread_id')
    elif transport == 'pi':
        if not c.get('pi_session_id'):
            raise ValueError('Pi transport must be bound by /reviewed-run to its launching session')
    else:
        raise ValueError('Unknown review_transport')
    execution = c.get('review_execution', 'chat')
    if execution not in {'chat', 'headless'}:
        raise ValueError('Unknown review_execution')
    if execution == 'headless':
        if c.get('protocol_version') != 2 or transport != 'pi':
            raise ValueError('Headless review requires protocol 2 and Pi UI transport')
        if not isinstance(c.get('review_provider'), str) or not c['review_provider'].strip():
            raise ValueError('Headless review needs explicit review_provider')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}', c['run_id']):
        raise ValueError('Invalid run_id')
    if c['mode'] not in {'goal', 'ralph', 'ping-pong'}:
        raise ValueError('Invalid mode')
    for k in ('max_cycles', 'wall_seconds', 'review_seconds', 'cycle_seconds'):
        if k in c and (type(c[k]) is not int or c[k] < 1):
            raise ValueError(f'Invalid limit: {k}')
    version = c.get('protocol_version')
    if type(version) is not int or version != 2:
        raise ValueError('Evaluator-era protocol 1 is no longer supported; prepare a new protocol 2 run, preserving old artifacts')
    if 'eval_argv' in c:
        raise ValueError('eval_argv is obsolete; prepare TASK/config without a separate evaluator')
    if version == 2:
        from action_protocol import validate_contract
        # goal_tokens is an optional cumulative cap; without it native Goal runs uncapped by tokens.
        if 'goal_tokens' in c and (type(c['goal_tokens']) is not int or c['goal_tokens'] < 1):
            raise ValueError('Invalid limit: goal_tokens')
        c.setdefault('goal_max_launches', 10)
        if type(c['goal_max_launches']) is not int or c['goal_max_launches'] < 1:
            raise ValueError('Invalid limit: goal_max_launches')
        c.setdefault('checkpoint_repair_attempts', 3)
        if type(c['checkpoint_repair_attempts']) is not int or c['checkpoint_repair_attempts'] < 0:
            raise ValueError('Invalid limit: checkpoint_repair_attempts')
        validate_contract(c)
    c['root'] = str(Path(path).resolve().parent)
    if not Path(c['task']).is_absolute():
        c['task'] = str(Path(c['root']) / c['task'])
    return c


def validate_checkpoint(c, cycle):
    root = Path(c['root'])
    p = root / 'work' / 'checkpoint.json'
    cp = read(p)
    if cp.get('run_id') != c['run_id'] or cp.get('cycle') != cycle:
        raise ValueError(f"Stale/wrong checkpoint identity: run_id {cp.get('run_id')!r} (expected {c['run_id']!r}), cycle {cp.get('cycle')!r} (expected {cycle!r})")
    if cp.get('status') not in {'progress', 'ready', 'needs_human'}:
        raise ValueError('Checkpoint requires progress/ready/needs_human status')
    if not isinstance(cp.get('summary'), str) or not 0 < len(cp['summary']) <= 2000:
        raise ValueError('Checkpoint summary must contain 1..2000 characters')
    evidence = cp.get('evidence')
    limit = c.get('max_evidence_files', 20)
    if not isinstance(evidence, list) or len(evidence) > limit:
        raise ValueError(f'Evidence must list <={limit} relative file paths')
    if cp['status'] != 'needs_human' and not evidence:
        raise ValueError('Results need evidence')
    hashes = {}
    for name in evidence:
        path = evidence_path(c, name)
        if not path.is_file():
            raise ValueError(f'Missing evidence: {name!r} resolves to {path}; work base: {(root / "work").resolve()}')
        hashes[name] = digest(path)
    if cp['status'] == 'needs_human' and cp.get('reason_code') not in {'missing_secret', 'missing_access', 'approval_required', 'user_choice', 'external_blocker'}:
        raise ValueError('Human checkpoint needs a concrete reason_code')
    return cp, {'checkpoint_sha256': digest(p), 'evidence_sha256': hashes}


def unchanged(c, snap):
    root = Path(c['root']) / 'work'
    return digest(root / 'checkpoint.json') == snap['checkpoint_sha256'] and all(digest(evidence_path(c, n)) == h for n, h in snap['evidence_sha256'].items())


class Bridge:
    def __init__(self, config):
        self.c = config
        self.root = Path(config['root'])
        self.proc = None
        self.records = queue.Queue()
        self.deferred = queue.Queue()
        self.started = time.monotonic()
        self.state = {'run_id': config['run_id'], 'mode': config['mode'], 'status': 'starting', 'phase': 'starting', 'cycle': 0, 'started_at': time.time(), 'updated_at': time.time()}
        self.outstanding = set()
        self.events_file = self.root / 'bridge-events.jsonl'
        self.last_failure = None

    def event(self, kind, **fields):
        record = {'type': kind, 'at': time.time(), **fields}
        with self.events_file.open('a') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def status(self, status, **fields):
        self.state.update(status=status, phase=fields.pop('phase', status), updated_at=time.time(), **fields)
        atomic(self.root / 'bridge-status.json', self.state)
        self.event('status', status=status, **fields)

    def remaining(self):
        return self.c['wall_seconds'] - (time.monotonic() - self.started)

    def send(self, kind, **values):
        ident = uuid.uuid4().hex
        self.outstanding.add(ident)
        self.proc.stdin.write((json.dumps({'id': ident, 'type': kind, **values}) + '\n').encode())
        self.proc.stdin.flush()
        return ident

    def process_returncode(self):
        return self.proc.poll()

    def check_control(self):
        pass

    def next(self, seconds=0.25):
        self.check_control()
        if self.remaining() <= 0:
            raise TimeoutError('Overall wall-clock limit reached')
        try:
            record = self.deferred.get_nowait()
        except queue.Empty:
            try:
                record = self.records.get(timeout=seconds)
            except queue.Empty:
                returncode = self.process_returncode()
                if returncode is not None:
                    raise RuntimeError(f'Pi exited unexpectedly: {returncode}')
                return {}
        if record.get('type') == 'response' and record.get('id') in self.outstanding:
            self.outstanding.discard(record['id'])
            if not record.get('success'):
                raise RuntimeError(f'Pi RPC command failed: {record.get("command")} {record.get("error")}')
        # Keep lifecycle metadata, not model deltas or full tool outputs.
        if record.get('type') in {'agent_start', 'agent_settled'}:
            self.event('pi.' + record['type'], aborted=record.get('aborted'))
        return record

    def prepare_browser_runtime(self):
        if hasattr(self, 'browser_runtime'):
            return
        self.browser_runtime = {'status': 'not_requested'}
        try:
            task = Path(self.c['task']).read_text()
            if not re.search(r'playwright|browser|браузер', task, re.I):
                return
            node = shutil.which('node')
            if not node:
                raise RuntimeError('Node executable unavailable')
            roots = [str(Path(self.c['task']).parent), str(self.root / 'work')]
            target = self.c.get('execution_contract', {}).get('target')
            if isinstance(target, str) and Path(target).is_absolute():
                roots.insert(0, str(Path(target) if Path(target).is_dir() else Path(target).parent))
            script = '''const fs = require('node:fs');
const {createRequire} = require('node:module');
const path = require('node:path');
const roots = JSON.parse(process.argv[1]);
const configured = process.env.PPP_PLAYWRIGHT_MODULE;
for (const root of roots) {
  const req = createRequire(path.join(root, 'package.json'));
  for (const name of configured ? [configured] : ['playwright', '@playwright/test', 'playwright-core']) {
    try {
      const module = req.resolve(name);
      const api = req(module);
      if (typeof api.chromium?.launch !== 'function') continue;
      console.log(JSON.stringify({status:'available', node:process.execPath, module:fs.realpathSync(module)}));
      process.exit(0);
    } catch {}
  }
}
process.exit(1);'''
            result = subprocess.run([node, '-e', script, json.dumps(roots)], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise RuntimeError('No loadable configured/project-installed Playwright module')
            runtime = json.loads(result.stdout)
            if not isinstance(runtime, dict) or runtime.get('status') != 'available' or not all(isinstance(runtime.get(key), str) and Path(runtime[key]).is_absolute() for key in ('node', 'module')):
                raise RuntimeError('Invalid browser module-resolution result')
            self.browser_runtime = runtime
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.browser_runtime = {'status': 'unavailable', 'error': str(error)}

    def browser_env(self):
        runtime = getattr(self, 'browser_runtime', {})
        return {'PPP_PLAYWRIGHT_MODULE': runtime['module']} if runtime.get('status') == 'available' else {}

    def spawn(self):
        home = Path.home()
        argv = ['pi', '--mode', 'rpc', '--no-extensions']
        if self.c['mode'] != 'ping-pong':
            extension = self.c.get('extension') or str(home / '.pi/agent/npm/node_modules' / ('@narumitw/pi-goal/dist/index.ts' if self.c['mode'] == 'goal' else '@lnilluv/pi-ralph-loop/src/index.ts'))
            argv += ['-e', extension]
        for extension in self.c.get('worker_extensions', []):
            argv += ['-e', extension]
        argv += ['--no-mcp', '--provider', self.c.get('worker_provider', 'openai-codex'), '--model', self.c['worker_model'], '--thinking', self.c.get('thinking', 'low'), '--session-dir', str(self.root / 'sessions'), '--session-id', (self.c.get('worker_session_id', self.c['run_id']) if self.c.get('protocol_version') == 2 else self.c['run_id'])]
        self.stderr = (self.root / 'pi-stderr.log').open('ab')
        self.proc = subprocess.Popen(argv, cwd=getattr(self, 'rpc_cwd', getattr(self, 'worker_cwd', self.root / 'work')), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True, env={**os.environ, **self.browser_env(), **getattr(self, 'rpc_env', {})}, umask=0o077, **getattr(self, 'spawn_options', {}))
        self.state['pid'] = self.proc.pid
        self.reader_stop = threading.Event()
        self.reader_thread = threading.Thread(target=self.read_stdout, args=(self.proc.stdout, self.records, self.reader_stop), daemon=True)
        self.reader_thread.start()
        req = self.send('get_state')
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            event = self.next()
            if event.get('id') == req:
                self.state['pi_session'] = event.get('data', {}).get('sessionFile')
                self.status('running')
                return
        raise TimeoutError('Pi RPC startup timeout')

    def read_stdout(self, stream, records, stopped):
        pending = bytearray()
        def record(line):
            try:
                records.put(json.loads(line))
            except (ValueError, UnicodeError):
                self.event('protocol.non_json_line')
        try:
            os.set_blocking(stream.fileno(), False)
            while not stopped.is_set():
                if not select.select([stream], [], [], 0.1)[0]:
                    continue
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    if pending:
                        record(pending)
                    break
                lines = chunk.split(b'\n')
                pending.extend(lines[0])
                if len(lines) > 1:
                    record(pending)
                    for line in lines[1:-1]:
                        record(line)
                    pending = bytearray(lines[-1])
        except (OSError, ValueError):
            self.event('protocol.stdout_read_error')
        finally:
            stream.close()

    def close_stdout(self):
        # Reap/stop the owned group first; a detached pipe holder must not stall cleanup.
        if hasattr(self, 'reader_thread'):
            self.reader_stop.set()
            self.reader_thread.join()
            del self.reader_thread
        elif self.proc is not None and self.proc.stdout:
            self.proc.stdout.close()

    def contract(self):
        contract = f'''# Reviewed Pi work contract
Run directory: {self.root}
Checkpoint/evidence directory: {self.root / 'work'}
Task specification: {self.c['task']}
Read the task and cycle-context.json. {'Pursue the full authorized objective through native Goal continuation.' if self.c['mode'] == 'goal' else 'Perform ONE logical deliverable or requested correction, not one tool call.'}
If cycle-context.feedback begins with 'Core rejected Worker checkpoint:', fix only checkpoint schema or exact evidence references from existing artifacts. Never change run/cycle identity or repeat task work or external actions.
work/ is a report and checkpoint directory, not a source checkout. Missing source files there do not imply missing access.
The task may permit edits to explicitly authorized source paths outside work/, including project scripts. Use those source paths directly; keep reports, logs and checkpoint evidence inside work/.
Without explicit task authorization, write only inside work/; cwd or Git ancestry does not grant write permission. Do not create a checkout, worktree or copy of the project unless the task authorizes it.
Create outputs yourself. Missing files mean bootstrap work, never a reason to stop early.
Do not modify this run's config, task specification, reviewer files, protocol state or preserved baseline files. Task-authorized project source edits do not grant permission to alter the active run machinery. Do not call codex queue yourself. Do not launch other Pi/Goal/Ralph processes.
At a logical checkpoint write work/checkpoint.json with run_id, cycle (from cycle-context.json), status (progress/ready/needs_human), summary (<=2000 characters), evidence (relative work file paths), next_step and reason_code.
Keep checkpoint evidence compact: report, manifest/measurement index, relevant code and final changed outputs only; do not list every intermediate tile/log. Link raw artifacts and their hashes from the manifest/index, and retain ordinary test results. evidence list limit: {self.c.get('max_evidence_files', 20)} files.
status=ready means all task deliverables ready for independent FINAL review, not just one step.
For missing env secret/access, user approval or user choice, status=needs_human with reason_code missing_secret/missing_access/approval_required/user_choice/external_blocker; identify required action WITHOUT printing any secret. Do not ask for permission for ordinary in-scope retries.
Run the task's targeted checks before checkpoint. Do not weaken checks or mark incomplete work complete.
Browser runtime resolution (module load only, not browser/login verification): {json.dumps(getattr(self, 'browser_runtime', {}))}
When available, Node can require(process.env.PPP_PLAYWRIGHT_MODULE); use the same route for tests. Reuse it rather than searching the host. If unavailable, continue independent work and use other configured browser guidance/routes; do not infer missing access from one module-resolution failure.
No authority beyond the task. Simulated people's names must contain Test.
'''
        if self.c['mode'] == 'goal':
            contract += '''Pursue the full authorized objective through native Goal continuation. Save the result checkpoint before native goal_complete, or a real limitation. Checkpoints do not request review or interrupt work. Native completion is a Worker claim, not independent acceptance. Use goal_wait only for a real arranged external wake, never for routine review.
'''
        else:
            contract += '''This is one bounded Ralph iteration. Save checkpoint.json and end. The external bridge reviews it BEFORE starting the next iteration. Do not start the next link/step yourself.
'''
        (self.root / 'CONTRACT.md').write_text(contract)

    def goal_cycle(self, feedback=None, fresh_session=False, replace_budget_limited=False, on_start=None):
        self.goal_budget_limited = False
        self.goal_boundary = None
        start = fresh_session or self.state['cycle'] == 1 and feedback is None and not getattr(self, 'goal_started', False)
        # Existing session already holds CONTRACT/TASK; only cycle-context.json carries changed budget/feedback.
        reads = f'Read {self.root / "CONTRACT.md"}, the task and {self.root / "work/cycle-context.json"}.' if start else f'Read {self.root / "work/cycle-context.json"}. CONTRACT.md and the task were already delivered in this session; reread them only if they are no longer in your context.'
        instruction = f'{reads} Pursue the full authorized objective autonomously through native Goal continuation, including ordinary tests. Save the result checkpoint before native completion or a real limitation. Native completion is not acceptance. Core/Reviewer feedback: {feedback or "Initial authorized work."}'
        if start:
            tokens = self.c.get('goal_session_tokens', self.c.get('goal_tokens'))
            token_option = f'--tokens {tokens} ' if self.c.get('protocol_version') == 2 and tokens is not None else ''
            message = f'/goal {token_option}{instruction}'
        else:
            message = instruction
        self.send('prompt', message=message)
        seconds = self.remaining() if self.c.get('protocol_version') == 2 else self.c['cycle_seconds']
        deadline = min(time.monotonic() + seconds, getattr(self, 'logical_cycle_deadline', float('inf')))
        self.cycle_deadline = deadline
        outcome = None
        replacement_confirmed = False
        announced = False
        while time.monotonic() < deadline:
            e = self.next(min(0.25, max(0.01, deadline - time.monotonic())))
            if e.get('type') == 'extension_ui_request' and e.get('method') in {'confirm', 'select', 'input', 'editor'}:
                if not (replace_budget_limited and fresh_session and not replacement_confirmed and e.get('method') == 'confirm' and e.get('title') == 'Replace goal?' and isinstance(e.get('id'), str)):
                    raise RuntimeError('Unexpected Pi Goal dialog; no confirmation was given')
                self.proc.stdin.write((json.dumps({'type': 'extension_ui_response', 'id': e['id'], 'confirmed': True}) + '\n').encode())
                self.proc.stdin.flush()
                replacement_confirmed = True
                self.event('pi.goal_budget_replacement_confirmed')
            if e.get('type') == 'agent_start' and not announced:
                announced = True
                if on_start:
                    on_start()
            if e.get('type') == 'tool_execution_end':
                name = e.get('toolName')
                if name in {'goal_wait', 'goal_complete', 'goal_blocked'}:
                    if e.get('isError'):
                        self.event('pi.goal_tool_rejected', tool=name)
                        continue
                    text = '\n'.join(x.get('text', '') for x in e.get('result', {}).get('content', []) if x.get('type') == 'text')
                    prefixes = {'goal_wait': 'Goal waiting:', 'goal_complete': 'Goal complete:', 'goal_blocked': 'Goal blocked:'}
                    if text.startswith(prefixes[name]):
                        outcome = name
                        self.event('pi.goal_tool_accepted', tool=name)
            if e.get('type') == 'agent_start' and outcome in {'goal_wait', 'goal_complete', 'goal_blocked'}:
                self.event('pi.goal_tool_boundary_superseded', tool=outcome)
                outcome = None
            if e.get('type') == 'agent_settled':
                native = self.goal_state()
                status = native.get('status')
                if status == 'budget_limited':
                    self.goal_budget_limited = True
                    self.event('pi.goal_budget_limited', goal_id=native.get('id'), tokens_used=native.get('tokens_used'))
                if status in {'complete', 'blocked', 'paused', 'usage_limited', 'budget_limited'} or native.get('safetyPauseCause') or native.get('waiting') or outcome:
                    self.goal_boundary = native
                    self.event('pi.goal_result', goal_id=native.get('id'), status=status, waiting=native.get('waiting'))
                    return
                if e.get('aborted'):
                    raise RuntimeError('Pi agent run aborted before Goal boundary')
                if status != 'active':
                    raise RuntimeError(f'Goal state unavailable at settlement: {native}')
                # A settled agent run is only one turn; native Goal continues itself.
                outcome = None
        raise TimeoutError('Pi logical cycle timeout without a native Goal result')

    def goal_state(self, deadline=None):
        self.check_control()
        ident = self.send('get_entries')
        deadline = min(time.monotonic() + max(0, self.remaining()), deadline if deadline is not None else getattr(self, 'cycle_deadline', float('inf')))
        while time.monotonic() < deadline:
            self.check_control()
            try:
                e = self.records.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                returncode = self.process_returncode() if self.proc else None
                if returncode is not None:
                    raise RuntimeError(f'Pi exited during Goal state query: {returncode}')
                continue
            if e.get('id') != ident or e.get('type') != 'response':
                self.deferred.put(e)
                continue
            self.outstanding.discard(ident)
            if not e.get('success'):
                raise RuntimeError(f'Pi RPC get_entries failed: {e.get("error")}')
            _, goal = goal_snapshot(e.get('data', {}).get('entries', []))
            native = {k: goal.get(k) for k in ('id', 'status', 'waiting', 'safetyPauseCause', 'automaticModelTurns', 'tokensUsed', 'tokenBudget', 'iteration')}
            native['tokens_used'] = goal['tokensUsed'] + goal['postCompletionTokens'] if 'postCompletionTokens' in goal else goal.get('tokensUsed')
            atomic(self.root / 'native-goal-state.json', native)
            return native
        raise TimeoutError('Pi Goal state query timeout')

    def ping_pong_cycle(self, on_start=None):
        self.send('prompt', message=f'Read {self.root / "CONTRACT.md"}, {self.c["task"]} and {self.root / "work/cycle-context.json"}. Execute the selected action or correction, save the checkpoint and end this iteration.')
        deadline = min(time.monotonic() + self.c['cycle_seconds'], getattr(self, 'logical_cycle_deadline', float('inf')))
        started = False
        while time.monotonic() < deadline:
            event = self.next(min(0.25, max(0.01, deadline - time.monotonic())))
            if event.get('type') == 'agent_start' and not started:
                started = True
                if on_start:
                    on_start()
            if event.get('type') == 'agent_settled' and started:
                if event.get('aborted'):
                    raise RuntimeError('Pi Worker aborted before iteration boundary')
                return
        raise TimeoutError('Pi Worker iteration timeout')

    def ralph_cycle(self, on_start=None):
        host = read(self.ralph_guards / 'host.json')
        if host.get('pid') != self.proc.pid or host.get('cleanup_supported') is not True:
            raise RuntimeError('Native Ralph parent guard did not initialize; no loop was launched')
        self.send('prompt', message=f'/ralph --path {self.ralph_argument}')
        announced = False
        while self.remaining() > 0:
            event = self.next(min(0.25, self.remaining()))
            if event.get('type') == 'extension_ui_request' and event.get('method') in {'confirm', 'select', 'input', 'editor'}:
                raise RuntimeError('Unexpected Ralph dialog; no confirmation was given')
            native = self.ralph_state()
            if native and native.get('currentIteration', 0) > 0 and not announced:
                announced = True
                if on_start:
                    on_start()
            if native and native.get('completedAt'):
                self.event('ralph.loop_finished', loop_token=native['loopToken'], native_status=native['status'])
                return
        raise TimeoutError('Cumulative Ralph Worker time exhausted')

    def queue_message(self, message, receipt, trigger_turn=None, notice_type=None, report_key=None):
        persist = atomic
        if self.c.get('protocol_version') == 2:
            from action_protocol import durable
            persist = durable
        marker = receipt.with_suffix('.attempt.json')
        if marker.exists():
            raise RuntimeError('Queue delivery already attempted; inspect receipt instead of duplicating')
        persist(marker, {'attempted_at': time.time()})
        if self.c['review_transport'] == 'pi':
            binding = read(self.root / 'pi-receiver.json')
            if binding.get('session_id') != self.c['pi_session_id'] or binding.get('run_id') != self.c['run_id']:
                raise RuntimeError('Pi receiver identity mismatch')
            inbox = self.root / 'pi-inbox'
            inbox.mkdir(exist_ok=True)
            ident = str(time.time_ns()) + '-' + uuid.uuid4().hex
            review = receipt.parent.parent.name == 'reviews'
            envelope = {'id': ident, 'run_id': self.c['run_id'], 'session_id': self.c['pi_session_id'], 'kind': 'review' if review else 'notice', 'message': message, 'receipt': str(receipt), 'created_at': time.time()}
            if self.c.get('protocol_version') == 2:
                envelope.update(protocol_version=2, schema_version=1)
            if trigger_turn is not None:
                envelope['trigger_turn'] = trigger_turn
            if notice_type is not None:
                envelope['notice_type'] = notice_type
            if report_key is not None:
                envelope['report_key'] = report_key
            persist(inbox / (ident + '.message.json'), envelope)
            persist(receipt, {'transport': 'pi', 'status': 'queued', 'message_id': ident})
            return
        with receipt.open('wb') as output:
            p = subprocess.run(['codex', 'queue', '--thread', self.c['thread_id'], '--model', self.c['review_model'], '--message', message], cwd=self.root / 'work', stdout=output, stderr=subprocess.STDOUT, timeout=45)
        if p.returncode:
            raise RuntimeError('Codex queue failed; inspect local receipt. No automatic duplicate retry.')

    def shutdown(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(self.proc.pid, signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.proc.pid, signal.SIGKILL)

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--config', required=True)
    decide = commands.add_parser('decide')
    decide.add_argument('--config', required=True)
    decide.add_argument('--cycle', type=int, required=True)
    decide.add_argument('--decision', required=True, choices=['continue', 'revise', 'complete', 'wait_human', 'stop'])
    decide.add_argument('--feedback', required=True)
    decide.add_argument('--human-resolved', action='store_true')
    for name in ('resume', 'wake'):
        resume = commands.add_parser(name)
        resume.add_argument('--config', required=True)
    review2 = commands.add_parser('review-v2')
    review2.add_argument('--config', required=True)
    review2.add_argument('--review-id', type=int)
    review2.add_argument('--decision', choices=['endorse', 'halt', 'stop'], required=True)
    review2.add_argument('--assessment', help='Independent action/criterion assessment JSON; required for endorse')
    review2.add_argument('--feedback', required=True)
    human = commands.add_parser('human')
    human.add_argument('--config', required=True)
    resource = commands.add_parser('signal')
    resource.add_argument('--config', required=True)
    resource.add_argument('--event-id', required=True)
    resource.add_argument('--wake-ref', required=True)
    operation = commands.add_parser('operation')
    operation.add_argument('--config', required=True)
    operation.add_argument('--action-id', required=True)
    operation.add_argument('--operation-id', required=True)
    operation.add_argument('--owner', required=True)
    args = parser.parse_args()
    c = load_config(args.config)
    from action_bridge import dispatch
    return dispatch(c, args)


if __name__ == '__main__':
    sys.exit(main())
