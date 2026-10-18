#!/usr/bin/env python3
"""Bounded Pi RPC transport + Codex queue checkpoints. Python stdlib only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid


REPORT_GUIDANCE = '''Write a concise, self-contained callback report using these headings:
Run summary; Steps; Verification and errors; Escalation; Completion; Next action.
State what happened this checkpoint and the overall run state. Include completed
steps, the fresh evaluator result, review findings/errors and whether anything
was corrected or rerun. Say "None" for errors or escalation when none occurred;
do not omit those sections. Distinguish verified completion from intermediate
progress, stopped work, and unknown outcomes. Cite the run directory and the
most relevant report/evidence paths. Do not claim checks or actions without
recorded evidence.
If user input is genuinely required, put the precise missing decision/input and
why it blocks progress under Escalation, then give the exact requested action
under Next action. If there are multiple valid choices, list at most three,
briefly state each option's main benefit and cost/risk, and recommend one with
reason. Separate actual approval/access requirements from ordinary preferences.
If no user action is needed, say so explicitly and state the automatic next step
or that the run is finished. Do not end by asking a vague question such as
"suggest the actions" or asking the user to confirm routine work.'''


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


def inside(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("Evidence escapes run work directory")
    if any(part.startswith('.env') or part.lower() in {'auth.json', 'credentials.json'} for part in p.parts):
        raise ValueError("Secret-bearing paths must not be checkpoint evidence")
    return p


def load_config(path):
    c = read(path)
    for key in ('run_id', 'mode', 'worker_model', 'review_model', 'task', 'eval_argv', 'max_cycles', 'wall_seconds', 'review_seconds', 'cycle_seconds'):
        if key not in c:
            raise ValueError(f'Missing config: {key}')
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
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}', c['run_id']):
        raise ValueError('Invalid run_id')
    if c['mode'] not in {'goal', 'ralph'}:
        raise ValueError('Invalid mode')
    for k in ('max_cycles', 'wall_seconds', 'review_seconds', 'cycle_seconds'):
        if type(c[k]) is not int or c[k] < 1:
            raise ValueError(f'Invalid limit: {k}')
    if not isinstance(c['eval_argv'], list) or not c['eval_argv'] or not all(isinstance(x, str) for x in c['eval_argv']):
        raise ValueError('eval_argv must be an argv array, never shell text')
    c['root'] = str(Path(path).resolve().parent)
    if not Path(c['task']).is_absolute():
        c['task'] = str(Path(c['root']) / c['task'])
    return c


def validate_checkpoint(c, cycle):
    root = Path(c['root'])
    p = root / 'work' / 'checkpoint.json'
    cp = read(p)
    if cp.get('run_id') != c['run_id'] or cp.get('cycle') != cycle:
        raise ValueError('Stale/wrong checkpoint identity')
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
        path = inside(root / 'work', name)
        if not path.is_file():
            raise ValueError(f'Missing evidence: {name}')
        hashes[name] = digest(path)
    if cp['status'] == 'needs_human' and cp.get('reason_code') not in {'missing_secret', 'missing_access', 'approval_required', 'user_choice', 'external_blocker'}:
        raise ValueError('Human checkpoint needs a concrete reason_code')
    return cp, {'checkpoint_sha256': digest(p), 'evidence_sha256': hashes}


def unchanged(c, snap):
    root = Path(c['root']) / 'work'
    return digest(root / 'checkpoint.json') == snap['checkpoint_sha256'] and all(digest(inside(root, n)) == h for n, h in snap['evidence_sha256'].items())


def validate_review(c, request, review):
    for key in ('run_id', 'cycle', 'checkpoint_sha256'):
        if review.get(key) != request.get(key):
            raise ValueError(f'Stale/wrong review {key}')
    decision = review.get('decision')
    if decision not in {'continue', 'revise', 'complete', 'wait_human', 'stop'}:
        raise ValueError('Invalid review decision')
    if not isinstance(review.get('feedback'), str) or not review['feedback'].strip():
        raise ValueError('Review needs explicit feedback')
    if decision in {'continue', 'complete'} and request['eval']['exit_code'] != 0:
        raise ValueError('Cannot accept failed independent eval')
    if decision == 'complete' and request['checkpoint']['status'] != 'ready':
        raise ValueError('Cannot complete an intermediate checkpoint')
    if request['checkpoint']['status'] == 'needs_human' and decision in {'continue', 'revise', 'complete'} and not review.get('human_resolved'):
        raise ValueError('Human blocker needs actual human resolution')
    return decision


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

    def next(self, seconds=0.25):
        if self.remaining() <= 0:
            raise TimeoutError('Overall wall-clock limit reached')
        try:
            record = self.deferred.get_nowait()
        except queue.Empty:
            try:
                record = self.records.get(timeout=seconds)
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise RuntimeError(f'Pi exited unexpectedly: {self.proc.returncode}')
                return {}
        if record.get('type') == 'response' and record.get('id') in self.outstanding:
            self.outstanding.discard(record['id'])
            if not record.get('success'):
                raise RuntimeError(f'Pi RPC command failed: {record.get("command")} {record.get("error")}')
        # Keep lifecycle metadata, not model deltas or full tool outputs.
        if record.get('type') in {'agent_start', 'agent_settled'}:
            self.event('pi.' + record['type'], aborted=record.get('aborted'))
        return record

    def spawn(self):
        home = Path.home()
        extension = self.c.get('extension') or str(home / '.pi/agent/npm/node_modules' / ('@narumitw/pi-goal/dist/index.ts' if self.c['mode'] == 'goal' else '@lnilluv/pi-ralph-loop/src/index.ts'))
        argv = ['pi', '--mode', 'rpc', '--no-extensions', '-e', extension, '--no-mcp', '--provider', self.c.get('worker_provider', 'openai-codex'), '--model', self.c['worker_model'], '--thinking', self.c.get('thinking', 'low'), '--session-dir', str(self.root / 'sessions'), '--session-id', self.c['run_id']]
        self.stderr = (self.root / 'pi-stderr.log').open('ab')
        self.proc = subprocess.Popen(argv, cwd=self.root / 'work', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        self.state['pid'] = self.proc.pid
        def reader():
            for line in self.proc.stdout:
                try:
                    self.records.put(json.loads(line))
                except (ValueError, UnicodeError):
                    self.event('protocol.non_json_line')
        threading.Thread(target=reader, daemon=True).start()
        req = self.send('get_state')
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            event = self.next()
            if event.get('id') == req:
                self.state['pi_session'] = event.get('data', {}).get('sessionFile')
                self.status('running')
                return
        raise TimeoutError('Pi RPC startup timeout')

    def contract(self):
        contract = f'''# Reviewed Pi work contract
Run directory: {self.root}
Checkpoint/evidence directory: {self.root / 'work'}
Task specification: {self.c['task']}
Read the task and cycle-context.json. Perform ONE logical deliverable or requested correction, not one tool call.
work/ is a report and checkpoint directory, not a source checkout. Missing source files there do not imply missing access.
The task may permit edits to explicitly authorized source paths outside work/, including project scripts. Use those source paths directly; keep reports, logs and checkpoint evidence inside work/.
Without explicit task authorization, write only inside work/; cwd or Git ancestry does not grant write permission. Do not create a checkout, worktree or copy of the project unless the task authorizes it.
Create outputs yourself. Missing files mean bootstrap work, never a reason to stop early.
Do not modify this run's config, task specification, reviewer files, evaluator, protocol state or preserved baseline files. Task-authorized project source edits do not grant permission to alter the active run machinery. Do not call codex queue yourself. Do not launch other Pi/Goal/Ralph processes.
At a logical checkpoint write work/checkpoint.json with run_id, cycle (from cycle-context.json), status (progress/ready/needs_human), summary (<=2000 characters), evidence (relative work file paths), next_step and reason_code.
Keep checkpoint evidence compact: report, manifest/measurement index, relevant code and final changed outputs only; do not list every intermediate tile/log. Link raw artifacts and their hashes from the manifest/index, and have the task evaluator verify them. evidence list limit: {self.c.get('max_evidence_files', 20)} files.
status=ready means all task deliverables ready for independent FINAL review, not just one step.
For missing env secret/access, user approval or user choice, status=needs_human with reason_code missing_secret/missing_access/approval_required/user_choice/external_blocker; identify required action WITHOUT printing any secret. Do not ask for permission for ordinary in-scope retries.
Run the task's targeted checks before checkpoint. Do not weaken checks or mark incomplete work complete.
No authority beyond the task. Simulated people's names must contain Test.
'''
        if self.c['mode'] == 'goal':
            contract += '''After EVERY checkpoint call goal_wait with the exact active goal_id and reason 'Codex review checkpoint', WITHOUT resume_after_ms. The external bridge arranges the wake source. Do not call goal_complete before a reviewer decision=complete. Wait without polling bash or paid model turns. A review reply will arrive through this same RPC session.
When final review is accepted, call goal_complete with evidence; do not change artifacts after final approval.
'''
        else:
            contract += '''This is one bounded Ralph iteration. Save checkpoint.json and end. The external bridge reviews it BEFORE starting the next iteration. Do not start the next link/step yourself.
'''
        (self.root / 'CONTRACT.md').write_text(contract)

    def goal_cycle(self, feedback=None, final=False):
        if self.state['cycle'] == 1 and feedback is None:
            message = f'/goal Read {self.root / "CONTRACT.md"} and the referenced task. Execute the first logical deliverable, save checkpoint, then goal_wait for the arranged external Codex reviewer. No goal_complete before final acceptance.'
        else:
            message = ('Final independent review ACCEPTED. Do not modify task artifacts. Call goal_complete for the current goal_id with evidence.' if final else f'Codex review for previous checkpoint: {feedback}. Read cycle-context.json and CONTRACT.md. Execute the next logical deliverable/correction and checkpoint, then goal_wait.')
        self.send('prompt', message=message)
        deadline = time.monotonic() + self.c['cycle_seconds']
        self.cycle_deadline = deadline
        outcome = None
        while time.monotonic() < deadline:
            e = self.next(min(0.25, max(0.01, deadline - time.monotonic())))
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
                if e.get('aborted'):
                    raise RuntimeError('Pi agent run aborted before Goal boundary')
                if outcome == 'goal_complete':
                    if not final:
                        raise RuntimeError('Pi completed before independent review')
                    return
                if outcome == 'goal_wait' and not final:
                    return
                native = self.goal_state()
                if native.get('status') != 'active' or native.get('safetyPauseCause') or native.get('waiting'):
                    raise RuntimeError(f'Goal stopped or entered an unexpected wait: {native}')
                if outcome == 'goal_blocked':
                    raise RuntimeError(f'Goal reported blocked before review: {native}')
                # A settled agent run is only one turn; Goal may continue automatically.
                outcome = None
        raise TimeoutError('Pi logical cycle timeout without an accepted Goal boundary')

    def goal_state(self):
        ident = self.send('get_entries')
        deadline = min(time.monotonic() + 10, time.monotonic() + max(0, self.remaining()), getattr(self, 'cycle_deadline', float('inf')))
        while time.monotonic() < deadline:
            try:
                e = self.records.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if self.proc and self.proc.poll() is not None:
                    raise RuntimeError(f'Pi exited during Goal state query: {self.proc.returncode}')
                continue
            if e.get('id') != ident or e.get('type') != 'response':
                self.deferred.put(e)
                continue
            self.outstanding.discard(ident)
            if not e.get('success'):
                raise RuntimeError(f'Pi RPC get_entries failed: {e.get("error")}')
            states = [x for x in e.get('data', {}).get('entries', []) if x.get('type') == 'custom' and x.get('customType') == 'goal-state']
            goal = (states[-1].get('data', {}).get('goal') or {}) if states else {}
            native = {k: goal.get(k) for k in ('id', 'status', 'waiting', 'safetyPauseCause', 'automaticModelTurns')}
            atomic(self.root / 'native-goal-state.json', native)
            return native
        raise TimeoutError('Pi Goal state query timeout')

    def ralph_cycle(self, feedback=None):
        n = self.state['cycle']
        directory = self.root / 'ralph' / f'{n:03}'
        directory.mkdir(parents=True)
        text = f'''---
max_iterations: 1
timeout: {min(self.c['cycle_seconds'], 3600)}
---
Read {self.root / 'CONTRACT.md'} and {self.c['task']}. You execute this iteration now; no waiting for another agent.
Shared outputs: {self.root / 'work'}. Checkpoint cycle={n}.
Previous reviewer feedback: {feedback or 'First pass: create missing deliverables.'}
Finish one logical deliverable/correction and save checkpoint.json. Missing outputs mean create them.
'''
        (directory / 'RALPH.md').write_text(text)
        self.send('prompt', message=f'/ralph --path {directory}')
        deadline = time.monotonic() + self.c['cycle_seconds'] + 30
        status_file = directory / '.ralph-runner/status.json'
        while time.monotonic() < deadline:
            self.next()
            if status_file.exists():
                state = read(status_file)
                if state.get('completedAt'):
                    self.event('ralph.iteration_finished', loop_token=state.get('loopToken'), native_status=state.get('status'))
                    return
        raise TimeoutError('Ralph iteration timeout')

    def queue_message(self, message, receipt):
        marker = receipt.with_suffix('.attempt.json')
        if marker.exists():
            raise RuntimeError('Queue delivery already attempted; inspect receipt instead of duplicating')
        atomic(marker, {'attempted_at': time.time()})
        if self.c['review_transport'] == 'pi':
            binding = read(self.root / 'pi-receiver.json')
            if binding.get('session_id') != self.c['pi_session_id'] or binding.get('run_id') != self.c['run_id']:
                raise RuntimeError('Pi receiver identity mismatch')
            inbox = self.root / 'pi-inbox'
            inbox.mkdir(exist_ok=True)
            ident = str(time.time_ns()) + '-' + uuid.uuid4().hex
            review = receipt.parent.parent.name == 'reviews'
            envelope = {'id': ident, 'run_id': self.c['run_id'], 'session_id': self.c['pi_session_id'], 'kind': 'review' if review else 'notice', 'message': message, 'receipt': str(receipt), 'created_at': time.time()}
            atomic(inbox / (ident + '.message.json'), envelope)
            atomic(receipt, {'transport': 'pi', 'status': 'queued', 'message_id': ident})
            return
        with receipt.open('wb') as output:
            p = subprocess.run(['codex', 'queue', '--thread', self.c['thread_id'], '--model', self.c['review_model'], '--message', message], cwd=self.root / 'work', stdout=output, stderr=subprocess.STDOUT, timeout=45)
        if p.returncode:
            raise RuntimeError('Codex queue failed; inspect local receipt. No automatic duplicate retry.')

    def review(self):
        cycle = self.state['cycle']
        cp, snap = validate_checkpoint(self.c, cycle)
        self.status('running', phase='evaluating', cycle=cycle)
        directory = self.root / 'reviews' / f'{cycle:03}'
        directory.mkdir(parents=True)
        stdout = directory / 'eval.stdout'
        stderr = directory / 'eval.stderr'
        try:
            with stdout.open('wb') as out, stderr.open('wb') as err:
                p = subprocess.run(self.c['eval_argv'], cwd=self.root / 'work', stdout=out, stderr=err, timeout=min(120, self.remaining()))
            code = p.returncode
        except subprocess.TimeoutExpired:
            code = 124
        if not unchanged(self.c, snap):
            raise RuntimeError('Artifacts changed during eval; checkpoint must be recreated')
        request = {'run_id': self.c['run_id'], 'cycle': cycle, **snap, 'checkpoint': cp, 'eval': {'exit_code': code, 'stdout': str(stdout), 'stderr': str(stderr)}}
        atomic(directory / 'request.json', request)
        atomic(directory / 'checkpoint.json', cp)
        failure = (code, snap['evidence_sha256'], digest(stdout), digest(stderr)) if code else None
        if failure is not None and failure == self.last_failure:
            raise RuntimeError('Repeated identical eval failure without artifact progress; human decision needed')
        self.last_failure = failure
        review_path = directory / 'review.json'
        script = Path(__file__).resolve()
        message = f'''Authorized Pi/{self.c['mode']} checkpoint review for run {self.c['run_id']}, cycle {cycle}.
Read {directory / 'request.json'}, {self.c['task']}, and only listed evidence in {self.root / 'work'}. Read eval outputs; independently check the logical result. Do not load full Pi logs unless needed for a blocker. Worker is waiting, no dependent work will run yet.
Return decision using: python3 {script} decide --config {self.root / 'config.json'} --cycle {cycle} --decision <continue|revise|complete|wait_human|stop> --feedback '<specific short feedback>'.
continue=verified intermediate result, revise=repairable within existing scope, complete=all task requirements verified and eval exit0, wait_human=actual missing access/secret/approval/user choice. An exhausted budget or repeated identical failure needs a user-facing report. Iteration completed/exit0 is never success by itself. Missing initial outputs mean bootstrap, not automatic human escalation.
If human action is required, write wait_human and ask the precise question here; do not fabricate approval or include secrets. Later, after the user's actual resolution, replace that decision with --human-resolved and continue/revise as appropriate. Otherwise finish automatic review without asking the human to confirm routine next steps. Only review; do not modify worker evidence, launch another Pi, navigate sites, or expand authorization. Do not disclose private raw outputs in chat. This callback was explicitly authorized by the user. {REPORT_GUIDANCE}
'''
        self.status('waiting_pi' if self.c['review_transport'] == 'pi' else 'waiting_codex', request=str(directory / 'request.json'))
        self.queue_message(message, directory / 'queue-receipt.txt')
        deadline = time.monotonic() + self.c['review_seconds']
        last_wait = False
        while time.monotonic() < deadline:
            self.next(0.25)
            if not review_path.exists():
                continue
            result = read(review_path)
            decision = validate_review(self.c, request, result)
            if not unchanged(self.c, snap):
                raise RuntimeError('Evidence changed after review request; refusing stale approval')
            if decision == 'wait_human':
                if not last_wait:
                    self.status('waiting_human', reason=result['feedback'])
                    last_wait = True
                continue
            self.event('review.applied', cycle=cycle, decision=decision)
            self.status('running')
            return result
        raise TimeoutError('Review/human wait limit reached; work remains stopped')

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

    def run(self):
        for folder in ('work', 'reviews', 'sessions'):
            (self.root / folder).mkdir(exist_ok=True)
        lock = (self.root / 'bridge.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (self.root / 'bridge-status.json').exists():
            raise RuntimeError('Run already started. Inspect saved session/state; never silently replay it.')
        self.contract()
        feedback = None
        try:
            self.spawn()
            for cycle in range(1, self.c['max_cycles'] + 1):
                self.state['cycle'] = cycle
                atomic(self.root / 'work/cycle-context.json', {'run_id': self.c['run_id'], 'cycle': cycle, 'feedback': feedback})
                self.status('running')
                if self.c['mode'] == 'goal':
                    self.goal_cycle(feedback)
                else:
                    self.ralph_cycle(feedback)
                result = self.review()
                if result['decision'] == 'stop':
                    self.status('stopped', reason=result['feedback'])
                    return 2
                if result['decision'] == 'complete':
                    if self.c['mode'] == 'goal':
                        self.goal_cycle(final=True)
                    request = read(self.root / 'reviews' / f'{cycle:03}' / 'request.json')
                    if not unchanged(self.c, request):
                        raise RuntimeError('Artifacts changed after final acceptance')
                    self.status('complete', reason=result['feedback'])
                    self.queue_message(f'Pi/{self.c["mode"]} reviewed run {self.c["run_id"]} is complete. Read {self.root / "bridge-status.json"}, {self.root / "reviews" / f"{cycle:03}" / "request.json"}, {self.root / "reviews" / f"{cycle:03}" / "review.json"}, and relevant checkpoint/evidence. {REPORT_GUIDANCE} Do not rerun anything.', self.root / 'final-queue-receipt.txt')
                    return 0
                feedback = result['feedback']
            raise RuntimeError('Cycle budget exhausted; human decision needed before further work')
        except Exception as error:
            self.status('attention_required', reason=str(error))
            try:
                self.queue_message(f'Pi/{self.c["mode"]} run {self.c["run_id"]} stopped and needs attention. Read {self.root / "bridge-status.json"}, compact bridge-events.jsonl, and the latest available checkpoint/review/eval evidence; inspect Pi session/stderr only if needed. {REPORT_GUIDANCE} Explain the failure or exhausted limit, what is verified versus unknown, and ask only for required human action. Do not automatically restart or expand scope.', self.root / 'attention-queue-receipt.txt')
            except Exception as delivery:
                self.event('attention.delivery_failed', reason=str(delivery))
            return 1
        finally:
            self.shutdown()


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
    args = parser.parse_args()
    c = load_config(args.config)
    if args.command == 'run':
        return Bridge(c).run()
    directory = Path(c['root']) / 'reviews' / f'{args.cycle:03}'
    request = read(directory / 'request.json')
    state = read(Path(c['root']) / 'bridge-status.json')
    if state['cycle'] != args.cycle or state['status'] not in {'waiting_codex', 'waiting_pi', 'waiting_human'}:
        raise ValueError('No matching live review wait')
    result = {key: request[key] for key in ('run_id', 'cycle', 'checkpoint_sha256')}
    result.update(decision=args.decision, feedback=args.feedback, human_resolved=args.human_resolved)
    validate_review(c, request, result)
    if not unchanged(c, request):
        raise ValueError('Worker evidence changed; refusing stale review')
    target = directory / 'review.json'
    if target.exists() and read(target).get('decision') != 'wait_human':
        raise ValueError('Decision already recorded; no duplicate delivery')
    atomic(target, result)
    print(json.dumps({'recorded': args.decision, 'cycle': args.cycle}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
