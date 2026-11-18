"""Action-scoped lifecycle using the shared Goal/Ralph RPC and delivery bridge."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime
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
import time
import uuid

import action_protocol as p
import launch_diff
import output_snapshot as outputs
from bridge import Bridge, REPORT_GUIDANCE, digest, evidence_path, goal_snapshot, read, validate_checkpoint


class Terminated(Exception):
    pass


class WorkerBudgetExhausted(Exception):
    pass


class VerificationTechnical(Exception):
    pass


def pins(c):
    root = Path(c['root'])
    paths = (root / 'config.json', Path(c['task']))
    p.require(root.stat().st_mode & 0o077 == 0, 'Protocol 2 run directory must be private')
    for path in paths:
        p.require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0, 'Governing files must be private regular files')
        p.require(path.resolve().is_relative_to(root.resolve()) and not path.resolve().is_relative_to((root / 'work').resolve()), 'Governing files must be outside worker outputs inside the run')
    return {str(path.resolve()): digest(path) for path in paths}


def review_report(c, request, assessment):
    """Bind independent judgments to Core's immutable request, never Worker acceptance."""
    p.require(isinstance(assessment, dict), 'Reviewer assessment required')
    bound = {**p.header(c['run_id']), 'cycle': request['cycle'], 'review_id': request['review_id'],
             'state_sha256': request['state_sha256'], 'target': c['execution_contract']['target']}
    for key, value in bound.items():
        p.require(key not in assessment or type(assessment[key]) is type(value) and assessment[key] == value,
                  'Reviewer assessment identity/hash mismatch')
    return {**assessment, **bound}


def retain_evidence(c, hashes, deadline):
    archive = Path(c['root']) / 'evidence'
    archive.mkdir(exist_ok=True, mode=0o700)
    p.require(archive.is_dir() and not archive.is_symlink() and archive.stat().st_mode & 0o077 == 0, 'Evidence archive must be private and run-owned')
    retained = {}
    for name, expected in hashes.items():
        target = archive / expected
        if not target.exists():
            temporary = archive / (expected + '.' + uuid.uuid4().hex + '.tmp')
            hasher = hashlib.sha256()
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as output, evidence_path(c, name).open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Evidence retention exceeded active operation deadline')
                        output.write(chunk)
                        hasher.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                p.require(hasher.hexdigest() == expected, 'Evidence changed during immutable retention')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        p.require(not target.is_symlink() and digest(target) == expected, 'Retained evidence integrity changed')
        retained[name] = str(target)
    fd = os.open(archive, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return retained


def request_unchanged(c, request, state):
    p.envelope(request, c['run_id'])
    p.require(type(request['cycle']) is int and request['cycle'] == state['cycle'] and type(request['review_id']) is int and request['review_id'] == state['review_seq'], 'Stale review cycle/sequence identity')
    p.require(read(Path(c['root']) / 'reviews' / f'v2-{request["review_id"]:06}' / 'request.json') == request, 'Review request changed after creation/read')
    p.require(state['revision'] == request['state_revision'] and p.sha(state) == request['state_sha256'], 'Stale controller review state')
    p.require(pins(c) == state['pins'], 'Governing contract changed')
    for name, value in request['evidence_sha256'].items():
        retained = Path(c['root']) / 'evidence' / value
        p.require(request['evidence_archive'].get(name) == str(retained) and not retained.is_symlink() and digest(retained) == value, 'Retained evidence changed after request')
        p.require(digest(evidence_path(c, name)) == value, 'Evidence changed after request')
    if request['checkpoint_sha256'] is not None:
        p.require(digest(Path(c['root']) / 'work/checkpoint.json') == request['checkpoint_sha256'], 'Checkpoint changed after request')
    diff = request.get('launch_diff') or {}
    if diff.get('path') is not None:
        expected = Path(c['root']) / 'reviews' / f'v2-{request["review_id"]:06}' / 'launch-diff.txt'
        p.require(Path(diff['path']).resolve() == expected.resolve() and not expected.is_symlink() and digest(expected) == diff['sha256'], 'Launch diff changed after request')


def review_evidence(request):
    """Names a Reviewer may cite: retained evidence plus the hash-bound launch diff."""
    return set(request['evidence_sha256']) | ({launch_diff.REF} if (request.get('launch_diff') or {}).get('path') else set())


USAGE_KEYS = ('input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens')


def session_usage(path, session_id, base):
    """Report-only token sum of one owned Pi session file; recomputed whole, so repeated calls never double count."""
    try:
        path = Path(path or '')
        p.require(path.is_absolute() and not path.is_symlink() and path.resolve().is_relative_to(Path(base).resolve()), 'Owned session file unavailable')
        totals, status, seen = dict.fromkeys(USAGE_KEYS, 0), 'known', False
        with path.open() as stream:
            p.require(json.loads(stream.readline()).get('id') == session_id, 'Session identity changed')
            for line in stream:
                try:
                    entry = json.loads(line)
                except ValueError:
                    status = 'partial'  # Torn/incomplete line: the sum is a lower bound.
                    continue
                message = entry.get('message') if isinstance(entry, dict) and entry.get('type') == 'message' else None
                if not isinstance(message, dict) or message.get('role') != 'assistant':
                    continue
                seen = True
                usage = message.get('usage')
                if not isinstance(usage, dict) or type(usage.get('totalTokens')) is not int:
                    status = 'partial'
                    continue
                for key in USAGE_KEYS:
                    totals[key] += usage[key] if type(usage.get(key)) is int else 0
        if not seen:
            return dict(tokens=None, tokens_status='not_measured', tokens_error='No assistant usage recorded in the session')
        return dict(tokens=totals['totalTokens'], tokens_status=status, usage=totals)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return dict(tokens=None, tokens_status='not_measured', tokens_error=str(error)[:300])


def usage_total(rows):
    """Sum per-session report rows: known only when every row is known."""
    rows = list({row.get('id', index): row for index, row in enumerate(rows)}.values())  # Latest row per session id.
    statuses = [row.get('tokens_status', 'not_measured') for row in rows]
    if not rows or all(value == 'not_measured' for value in statuses):
        return None, 'not_measured'
    return sum(row.get('tokens') or 0 for row in rows), 'known' if all(value == 'known' for value in statuses) else 'partial'


def process_result(proc):
    ended = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if ended is None:
        return None
    return ended.si_status if ended.si_code == os.CLD_EXITED else -ended.si_status


def stop_owned(proc):
    # The leader remains unreaped, including on unexpected exit; its PID cannot be reused.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        time.sleep(0.05)
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin may deny a disappearing group before waitid exposes its exit.
        deadline = time.monotonic() + 0.05
        while process_result(proc) is None:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.005)
    proc.wait()


def record_review(c, args):
    root = Path(c['root'])
    store = p.Store(root, c['run_id'])
    if args.review_id is None:
        status = read(root / 'bridge-status.json')
        active_request = Path(status.get('request', '')).resolve()
        p.require(active_request.is_relative_to((root / 'reviews').resolve()) and active_request.name == 'request.json', 'No matching active review')
        request = read(active_request)
        args.review_id = request['review_id']
        directory = active_request.parent
    else:
        directory = root / 'reviews' / f'v2-{args.review_id:06}'
        request = read(directory / 'request.json')
    with (root / 'review-write.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ActionBridge(c).ingress(controls_only=True)
        state = store.read()
        status = read(root / 'bridge-status.json')
        p.require(isinstance(status.get('request'), str) and Path(status['request']).resolve() == (directory / 'request.json').resolve() and status['status'] in {'waiting_pi', 'waiting_codex'}, 'No matching active review')
        p.require(state['execution'] not in p.TERMINAL, 'Terminal run cannot accept review')
        request_unchanged(c, request, state)
        target = directory / 'review.json'
        p.require(not target.exists(), 'Review already recorded')
        p.text(args.feedback)
        value = {**p.header(c['run_id']), 'review_id': args.review_id, 'request_sha256': digest(directory / 'request.json'), 'decision': args.decision, 'feedback': args.feedback}
        p.require(args.decision in {'endorse', 'halt', 'stop'}, 'Invalid direct review decision')
        if args.decision == 'endorse':
            value['assessment'] = json.loads(getattr(args, 'assessment', None) or 'null')
            report = review_report(c, request, value['assessment'])
            p.Controller(c, deepcopy(state)).apply(report, review_evidence(request), str(target))
        else:
            p.require(not getattr(args, 'assessment', None), 'Assessment requires endorse decision')
        with ActionBridge(c).boundary(error=ValueError) as state:
            request_unchanged(c, request, state)
            p.durable(target, value)
    return 0


def console_human(c):
    p.require(p.human_channel(c) == 'console' and sys.stdin.isatty(), 'Human instruction requires interactive console input; no model/pipe approval flag')
    store = p.Store(c['root'], c['run_id'])
    s = store.read()
    p.require(s['execution'] not in p.TERMINAL, 'Terminal run cannot resume from a late response')
    print('Enter addressed human instruction JSON. Never paste secrets. Resolution: kind, blocker_ids, message. Grant: kind, request_id, cycles, message. Cancel/halt/signal: kind, message.')
    value = json.loads(input('Human instruction: '))
    p.require(isinstance(value, dict) and set(value) <= {'kind', 'blocker_ids', 'message', 'cycles', 'request_id'}, 'Unexpected human instruction fields')
    raw = {**p.header(c['run_id']), **value, 'id': uuid.uuid4().hex, 'source': 'console-command', 'session_id': 'console:' + c['run_id']}
    # Validate against a copy before confirmation or persistence; no instruction is applied yet.
    candidate = json.loads(p.canonical(s))
    p.Controller(c, candidate).ingress(raw, raw['session_id'])
    p.require('duplicate_of' not in candidate['human'][raw['id']], 'Budget request authorization already recorded')
    p.require(input(f'Type AUTHORIZE {c["run_id"]} to record this instruction: ') == 'AUTHORIZE ' + c['run_id'], 'Human confirmation cancelled')
    with store.transaction() as state:
        p.require(state['execution'] not in p.TERMINAL and pins(c) == state['pins'], 'Run changed during human confirmation')
        p.durable(Path(c['root']) / 'human-inbox' / (raw['id'] + '.json'), raw)
    return ActionBridge(c).run(resume=True, wake=True)


class ActionBridge(Bridge):
    def __init__(self, c):
        super().__init__(c)
        self.store = p.Store(self.root, c['run_id'])
        self.worker_lock = None
        self.writer_lock = None
        self.goal_started = False
        self.goal_session_id = None
        self.owner = None
        self.operation_deadline = float('inf')

    def remaining(self):
        return self.operation_deadline - time.monotonic()

    def wall_remaining(self):
        try:
            state = self.store.read()
            elapsed = state.get('worker_seconds', state.get('active_seconds', 0))
        except FileNotFoundError:
            elapsed = 0
        started = getattr(self, 'worker_started_at', None)
        if started is not None:
            elapsed += time.monotonic() - started
        return max(0, self.c['wall_seconds'] - elapsed)

    def verification_remaining(self):
        elapsed = 0
        started = getattr(self, 'verification_started_mono', None)
        if started is not None:
            elapsed += time.monotonic() - started
        return max(0, self.c['review_seconds'] - elapsed)

    def verify_pins(self):
        state = self.store.read()
        try:
            valid = pins(self.c) == state['pins']
        except (OSError, ValueError):
            valid = False
        if not valid:
            with self.store.transaction() as s:
                s['execution'] = 'halt'
                s['wait'] = None
                p.Controller(self.c, s).event('execution.halt', reason='Governing task/config integrity changed')
            self.project()
            raise Terminated('Governing contract changed; halted')

    def project(self, phase=None, request=None, reason=None):
        s = self.store.read()
        status = {'continue': 'running', 'replan': 'running', 'wait': 'waiting_human', 'paused_budget': 'paused_budget', 'halt': 'halted', 'stop': 'stopped', 'finish': 'complete', 'cancelled': 'cancelled'}[s['execution']]
        if s['execution'] == 'wait':
            verification = s.get('verification') or {}
            source = (s.get('wait') or {}).get('source')
            if verification:
                status = 'attention_required' if verification.get('status') == 'blocked' else 'running'
            elif source == 'human-response':
                status = 'waiting_human'
            else:
                status = 'waiting_resource' if source == 'resource-signal' else 'waiting_event'
        self.state.update(run_id=s['run_id'], protocol_version=2, schema_version=1, status=status, phase=phase or s['execution'], cycle=s['cycle'], execution=s['execution'], acceptance=s['acceptance'], blockers=list(s['blockers'].values()), main_remaining=(None if self.c['mode'] == 'goal' and s.get('goal_usage_status') == 'unknown' else p.Controller(self.c, s).remaining('main')), goal_usage_status=s.get('goal_usage_status'), goal_usage_error=s.get('goal_usage_error'), started_at=s['created_at'], updated_at=s['updated_at'], active_seconds=s['active_seconds'], worker_seconds=s.get('worker_seconds'), worker_tokens=s.get('worker_tokens') if self.c['mode'] == 'goal' else usage_total(s['sessions'])[0] if self.c['mode'] == 'ping-pong' else None, worker_tokens_status=None if self.c['mode'] == 'goal' else usage_total(s['sessions'])[1] if self.c['mode'] == 'ping-pong' else 'not_measured', worker_iterations=(sum(item.get('worker_iterations', 1) for item in s['consumption']) if self.c['mode'] == 'ralph' else None), checkpoint_repairs=sum(item.get('checkpoint_repairs', 0) for item in s['consumption']), verification_seconds=s.get('verification_seconds', 0), controller_pid=os.getpid())
        if s['execution'] == 'stop' and s.get('delivery'):
            self.state.update(outcome='delivered_unverified', unverified_criteria=s['delivery']['unverified_criteria'])
            reason = reason or 'Delivered, not verified (not acceptance): Reviewer found no defect; unverified criteria: ' + ', '.join(s['delivery']['unverified_criteria'])
        else:
            for key in ('outcome', 'unverified_criteria'):
                self.state.pop(key, None)
        reviewers = []
        for path in sorted((self.root / 'reviews').glob('v2-*/reviewer.json')):
            try:
                reviewers.append(read(path))
            except (OSError, ValueError):
                reviewers.append({})
        self.state['reviewer_tokens'], self.state['reviewer_tokens_status'] = usage_total(reviewers)
        if self.c['mode'] == 'ralph':
            self.state['worker_tokens_reason'] = 'Native Ralph 2.1.2 runs iterations with --no-session and reports no token usage.'
        if self.c['mode'] == 'ralph' and s['sessions']:
            session = s['sessions'][-1]
            self.state.update(ralph_usage_status=session.get('ralph_usage_status', 'legacy'),
                              ralph_snapshot_limitation=session.get('ralph_snapshot_limitation'),
                              ralph_path=session.get('ralph_path'), ralph_host_error=session.get('ralph_host_error'), ralph_freeze_error=getattr(self, 'ralph_freeze_error', None))
        if request:
            self.state.update(status='waiting_pi' if self.c['review_transport'] == 'pi' else 'waiting_codex', phase='review', request=str(request))
        else:
            self.state.pop('request', None)
        if reason:
            self.state['reason'] = reason
        else:
            self.state.pop('reason', None)
        p.durable(self.root / 'bridge-status.json', self.state)

    @contextmanager
    def boundary(self, error=Terminated):
        with self.store.transaction() as state:
            self.ingress(controls_only=True, locked_state=state)
            if state['execution'] not in p.TERMINAL:
                yield state
                return
        # Commit controls before rejecting the boundary; raising inside would roll them back.
        raise error('Terminal control takes precedence at locked boundary')

    def ingress(self, controls_only=False, locked_state=None):
        inbox = self.root / 'human-inbox'
        changed = False
        if not inbox.exists():
            return False
        p.require(inbox.is_dir() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077 == 0, 'Human inbox identity/permissions changed')
        for file in sorted(inbox.glob('*.json')):
            if file.name.endswith('.rejected.json'):
                continue
            raw = read(file)
            if controls_only and raw.get('kind') not in {'cancel', 'halt'}:
                continue
            s = locked_state if locked_state is not None else self.store.read()
            if raw.get('id') in s['human']:
                prior = s['human'][raw['id']]
                p.require(all(prior.get(k) == v for k, v in raw.items()), 'Authenticated human receipt mutated; halt for integrity investigation')
                continue
            stat = file.lstat()
            p.require(file.is_file() and not file.is_symlink() and stat.st_mode & 0o077 == 0, 'Human receipt must be private regular file')
            if p.human_channel(self.c) == 'pi':
                binding = read(self.root / 'pi-receiver.json')
                p.require(binding.get('run_id') == self.c['run_id'], 'Human receiver run identity mismatch')
                session_id = binding['session_id']
            else:
                session_id = 'console:' + self.c['run_id']
            with (nullcontext(locked_state) if locked_state is not None else self.store.transaction()) as state:
                p.Controller(self.c, state).ingress(raw, session_id)
            changed = True
        return changed

    def resource_events(self):
        s = self.store.read()
        if s['active'] is not None or s['execution'] in p.TERMINAL:
            return
        inbox = self.root / 'resource-inbox'
        if not inbox.exists():
            return
        p.require(inbox.is_dir() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077 == 0, 'Resource inbox identity/permissions changed')
        for file in sorted(inbox.glob('*.json')):
            raw = read(file)
            if raw.get('id') in self.store.read()['signals']:
                continue
            p.require(file.is_file() and not file.is_symlink() and file.stat().st_mode & 0o077 == 0, 'Resource event must be private regular file')
            with self.store.transaction() as state:
                p.Controller(self.c, state).resource_signal(raw)

    def check_control(self):
        self.control_point()

    def contract(self):
        script = Path(__file__).with_name('bridge.py')
        text = f'''# PPP action-scoped worker contract (protocol 2 / schema 1)
Worker executes and runs ordinary tests. Reviewer assesses. Core decides. Chat A is operated by the human and provides confirmed commands and Core reports, never Core authority to its model.
Read {self.c['task']} and {self.root / 'work/cycle-context.json'}. Start the requested deliverable promptly; read only guidance needed for this task, avoid repeating large guidance already in context, and use actual available skill paths. {'Pursue all dispatched actions as one native objective, not separate Core iterations.' if self.c['mode'] in {'goal', 'ralph'} else 'One authorized selected action per cycle.'}
Do not perform the independent reviewer role, submit review-v2, or decide continuation, acceptance, budgets or human resolutions. Your own tests and checkpoint are claims for independent verification, not acceptance.
Logical run identity persists across sessions. Prior evidence, blockers, grants and restrictions are in {self.root / 'execution-state.json'} (read-only).
{'cycle-context.action_ids is the authorized dispatch scope; action_id anchors its checkpoint/accounting, not a stopping boundary. Respect the real dependencies, complete prerequisites before dependent work, and continue independent scoped actions around blockers.' if self.c['mode'] in {'goal', 'ralph'} else 'Only cycle-context.action_id is executable now.'} Open blockers affect that action and its dependents, not unrelated work. Do not label work independent to bypass access, identity or approval.
Do not modify config, TASK, execution state, immutable evidence archive, review files, receiver binding, human inbox, baseline or launch Git record. No additional worker processes, queue calls, approvals or budget changes.
Product target: {self.c['execution_contract']['target']}. Product command cwd: {getattr(self, 'worker_cwd', self.root / 'work')}. {'Native Ralph shell initially starts in private service storage; change to the product command cwd for task commands.' if self.c['mode'] == 'ralph' else 'Worker initially starts in the product command cwd.'}
Work in the selected current project with its actual uncommitted files. For a new project use the requested repository root; edit an existing project in place; respect an explicit subdirectory or file target. The task authorizes ordinary product edits there, not unrelated paths. No mandatory clean Git, commit, fetch, separate worktree or routine approval.
work/ is an evidence directory, not a source checkout. Preserve unrelated user edits, staged/unstaged/untracked files and ignored local configuration; do not overwrite or copy them into a checkout. Edit source at task-authorized paths; cwd/Git ancestry grants no permission beyond the task. Secrets must never appear in evidence, chat or state. Simulated people must contain Test.
Ordinary local edits and tests within the task-authorized scope are not external operations and do not require operation reservation. Before each planned external side effect, journal its pre-authorized stable operation ID using:
python3 {script} operation --config {self.root / 'config.json'} --action-id <{'dispatched-action' if self.c['mode'] in {'goal', 'ralph'} else 'selected-action'}> --operation-id <planned-operation> --owner <cycle-context.owner>
Proceed only after successful durable reservation. Never replay started/uncertain/succeeded/failed operations. Investigate uncertain effects through independent reconciliation, never assume failure. A journal is not additional external authorization.
Closure is only resolved blocker -> unblocked action -> evidenced necessary fixes/verification. Missing provenance means main work. No numerical default closure cap overrides safety, approvals or action-local loop detection.
If cycle-context.feedback says Core rejected the checkpoint, correct only its schema or exact evidence references from already-produced artifacts; never change run/action/cycle identity or repeat task work or external operations.
cycle-context.budget reports remaining cumulative Worker time and Goal tokens at dispatch; verification/waiting are separate. {'Native Goal uses the cumulative Worker time/token limits, not a per-action cycle timeout.' if self.c['mode'] == 'goal' else 'Native Ralph uses cumulative Worker time and iteration grants; cycle_seconds bounds each native iteration.' if self.c['mode'] == 'ralph' else 'The cycle timeout is hard and unchanged.'} Start deliverables promptly, keep discovery bounded and save progress/checkpoint before time runs out; do not assume a fresh budget on correction/resume.
Browser runtime resolution (module load only, not browser/login verification): {json.dumps(getattr(self, 'browser_runtime', {}))}
When available, Node can require(process.env.PPP_PLAYWRIGHT_MODULE); use the same route for ordinary tests. Reuse it rather than searching the host. If unavailable, continue independent work and use other configured browser guidance/routes; do not infer missing access from one module-resolution failure.
Service paths are available to Worker commands as PPP_WORK_DIR, PPP_CHECKPOINT_PATH, PPP_CONTEXT_PATH and PPP_TARGET (the configured target, which may be descriptive rather than a filesystem path). Use these exact values rather than retyping paths; relative evidence resolves from PPP_WORK_DIR. Service context: {self.root / 'work/cycle-context.json'} (always this absolute path). Run the task’s ordinary targeted tests and retain commands, exit status, output and relevant artifacts in checkpoint evidence. When practical, save stdout/stderr and the actual exit status in the same ordinary shell command, and write the checkpoint in that call so budget exhaustion does not require another model turn. This is a recommendation, not a mandatory runner or extra test; an interrupted command has no known exit. Do not create a task-specific evaluator. Missing or broken checks are verification limitations, not invented product defects. Continue all independent authorized work.
At logical boundary write {self.root / 'work/checkpoint.json'} (always this absolute path, even after changing cwd) with protocol_version=2, schema_version=1, run_id, cycle, action_id, status=progress|ready|needs_human, summary, evidence (file paths), next_step, reason_code if needs_human. Evidence may directly reference files inside the absolute filesystem execution_contract.target, or files relative to this run's work directory. Never include secrets. Limit {self.c.get('max_evidence_files', 20)} references; raw evidence may be indexed without deletion. Optional helper (manual writing stays valid): python3 "$PPP_CHECKPOINT_CMD" --status ready --summary '...' --next-step '...' [--reason-code ...] EVIDENCE... fills identity from cycle-context, resolves bare/target/work paths, copies files outside target/work into work/evidence/, writes atomically and runs Core's checkpoint check. Claims of completion or human resolution are never acceptance. For needs_human use only missing_secret, missing_access, approval_required, user_choice or external_blocker, and only for a real human need. For a technical contradiction use progress with diagnostic evidence; do not fabricate human gates.
'''
        if self.c['mode'] == 'goal':
            text += 'Continue through native Goal turns until the full dispatched objective is complete or genuinely limited. Checkpoints are progress storage, not review or tool boundaries. Save the final checkpoint and call native goal_complete with the current goal_id when your authorized objective is complete; this is a lifecycle claim, not acceptance. Do not wait for independent acceptance before completing. Use goal_wait only for a genuine arranged external wake, never routine review. Independent Reviewer and Core assess after the native result.\n'
        elif self.c['mode'] == 'ralph':
            text += 'Continue the full dispatched objective through the bounded native Ralph loop. Checkpoints retain progress, not review boundaries. Save the final checkpoint and end the loop at completion or a real limitation after independent work. Native completion is not acceptance; Reviewer assesses the result afterwards. Do not launch another loop yourself.\n'
        else:
            text += 'End this ordinary Pi Worker iteration after checkpoint. No self-launch or next iteration.\n'
        (self.root / 'CONTRACT.md').write_text(text)

    def acquire_worker(self):
        self.worker_lock = (self.root / 'worker.lock').open('a')
        try:
            fcntl.flock(self.worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.worker_lock.close()
            self.worker_lock = None
            raise RuntimeError('Worker ownership still held; inspect existing Pi process, never launch a duplicate') from None
        self.spawn_options = {'pass_fds': (self.worker_lock.fileno(),)}

    def confirm_writer_available(self):
        with (self.root / 'writer.lock').open('a') as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Execution ownership still held by a Reviewer; inspect it, never start a duplicate') from None

    def acquire_writer(self):
        self.writer_lock = (self.root / 'writer.lock').open('a')
        try:
            fcntl.flock(self.writer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.writer_lock.close()
            self.writer_lock = None
            raise RuntimeError('Another execution phase still owns writable outputs') from None
        session_fd = (self.worker_lock.fileno(),) if self.worker_lock else ()
        self.spawn_options = {'pass_fds': session_fd + (self.writer_lock.fileno(),)}

    def release_writer(self):
        if self.writer_lock:
            fcntl.flock(self.writer_lock, fcntl.LOCK_UN)
            self.writer_lock.close()
            self.writer_lock = None

    def process_returncode(self):
        return process_result(self.proc)

    def shutdown(self):
        if self.proc is not None and self.c['mode'] == 'ralph':
            self.drain_ralph()
        if self.proc is not None:
            if self.proc.stdin and not self.proc.stdin.closed:
                try:
                    self.proc.stdin.close()
                except OSError:
                    pass
            if self.proc.returncode is None:
                stop_owned(self.proc)
            self.close_stdout()
        if hasattr(self, 'stderr'):
            self.stderr.close()
        if self.c['mode'] == 'ralph':
            self.ralph_freeze_error = self.ralph_children_error()
            if not self.ralph_freeze_error and self.store.path.exists():
                with self.store.transaction() as state:
                    if state['sessions'] and state['sessions'][-1].get('ralph_path'):
                        state['sessions'][-1]['ralph_cleanup_confirmed'] = True
            if getattr(self, 'ralph_storage_fd', None) is not None:
                os.close(self.ralph_storage_fd)
                self.ralph_storage_fd = None
        self.release_writer()
        if self.worker_lock:
            self.worker_lock.close()
            self.worker_lock = None
        self.proc = None
        self.records = queue.Queue()
        self.deferred = queue.Queue()
        self.outstanding.clear()

    def migrate_goal_cycle_grants(self):
        with self.store.transaction() as state:
            grant_cycles = {event['authority']: event['cycles'] for event in state['history'] if event['type'] == 'grant.added' and type(event.get('cycles')) is int}
            finite = [grant for grant in state['grants'] if grant['max_cycles'] is not None]
            for grant in state['grants']:
                if grant['scope'] == 'main' and grant['authority'] != 'initial-contract':
                    grant.setdefault('goal_token_windows', grant['max_cycles'] if grant['max_cycles'] is not None else grant_cycles.get(grant['authority'], 0))
            for grant in finite:
                grant['max_cycles'] = None
            if finite:
                p.Controller(self.c, state).event('goal.checkpoint_caps_removed', grant_ids=[grant['id'] for grant in finite], token_budget=p.Controller(self.c, state).goal_token_budget())

    def prepare_goal_session(self):
        state = self.store.read()
        prior_sessions = state['sessions']
        prior = prior_sessions[-1] if prior_sessions else None
        if state.get('goal_usage_status') == 'unknown':
            raise RuntimeError('Actual Goal usage is unknown; cannot allocate another Worker allowance')
        started = self.goal_started if self.goal_session_id else bool(prior and prior.get('goal_started', prior.get('status') != 'starting'))
        controller = p.Controller(self.c, state)
        native_goal_id = next((row['goal_native_id'] for row in reversed(prior_sessions) if row.get('goal_native_id')), None)
        renewed_budget = bool(prior and started and controller.remaining('main') > 0 and controller.goal_needs_new_window())
        restored = False
        if renewed_budget:
            self.goal_session_id = self.goal_session_id or prior['id']
            self.goal_started = False
            self.goal_window_id = uuid.uuid4().hex
            self.goal_previous_native_id = native_goal_id
            self.goal_native_id = None
        elif self.goal_session_id is None and prior:
            self.goal_session_id = prior['id']
            self.goal_window_id = prior.get('goal_window_id', prior['id'])
            self.goal_started = started
            self.goal_previous_native_id = prior.get('goal_previous_native_id')
            self.goal_native_id = prior.get('goal_native_id')
            restored = True
        elif self.goal_session_id is None:
            self.goal_session_id = uuid.uuid4().hex
            self.goal_window_id = uuid.uuid4().hex
            self.goal_previous_native_id = None
            self.goal_native_id = None
        elif not hasattr(self, 'goal_window_id'):
            self.goal_window_id = prior.get('goal_window_id', prior['id']) if prior else uuid.uuid4().hex
            self.goal_previous_native_id = prior.get('goal_previous_native_id') if prior else None
            self.goal_native_id = prior.get('goal_native_id') if prior else None
        self.c['worker_session_id'] = self.goal_session_id
        self.c['goal_session_tokens'] = controller.goal_tokens_remaining()
        return restored or bool(prior and self.goal_started and getattr(self, 'proc', None) is None)

    def record_goal_usage(self, usage, native_goal_id=None, session=None, usage_error=None):
        p.require(type(usage) is int and usage >= 0, 'Invalid native Goal usage')
        session_id = session['id'] if session else self.goal_session_id
        window_id = session.get('goal_window_id', session_id) if session else getattr(self, 'goal_window_id', session_id)
        with self.store.transaction() as state:
            sessions = [row for row in state['sessions'] if row['id'] == session_id and row.get('goal_window_id', row['id']) == window_id]
            session = sessions[-1]
            expected = next((row['goal_native_id'] for row in reversed(sessions) if row.get('goal_native_id')), None)
            p.require(not native_goal_id or (native_goal_id != session.get('goal_previous_native_id') and (not expected or native_goal_id == expected)), 'Native Goal window identity changed')
            previous = max((row.get('tokens_used', 0) for row in sessions), default=0)
            state['worker_tokens'] = state.get('worker_tokens', 0) + max(0, usage - previous)
            session['tokens_used'] = max(previous, usage)
            session['goal_started'] = True
            state.update(goal_usage_status='unknown' if usage_error else 'known', goal_usage_error=usage_error)
            if native_goal_id:
                session['goal_native_id'] = native_goal_id
                self.goal_native_id = native_goal_id

    def reconcile_goal_usage(self):
        # Native session snapshots survive expired RPC deadlines and controller restarts.
        state = self.store.read()
        if self.c['mode'] != 'goal' or not state['sessions']:
            return
        session = state['sessions'][-1]
        if session.get('pid') is None and not session.get('session_file') and not session.get('goal_started') and not session.get('goal_dispatch_attempted'):
            return  # A durable reservation is not a dispatched native window.
        with self.store.transaction() as pending:
            pending.update(goal_usage_status='unknown', goal_usage_error='Reconciling native Goal usage')
        error = None
        try:
            session_file = session.get('session_file') or next((row.get('session_file') for row in reversed(state['sessions']) if row['id'] == session['id'] and row.get('session_file')), None)
            if not session_file:
                # Startup can die before get_state returns the native session filename.
                candidates = []
                for candidate in (self.root / 'sessions').glob('*.jsonl'):
                    if candidate.is_symlink() or not candidate.is_file():
                        continue
                    try:
                        with candidate.open() as stream:
                            header = json.loads(stream.readline())
                        if header.get('type') == 'session' and header.get('id') == session['id']:
                            candidates.append(candidate)
                    except (OSError, ValueError):
                        continue
                p.require(len(candidates) == 1, 'Owned native Goal session file unavailable or ambiguous')
                session_file = str(candidates[0])
            path = Path(session_file)
            p.require(path.is_absolute() and path.resolve().is_relative_to((self.root / 'sessions').resolve()) and path.is_file() and not path.is_symlink(), 'Owned native Goal session file unavailable')
            entries = []
            for line in path.read_text().splitlines():
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    error = 'Native Goal session contains an incomplete entry'
            p.require(entries and entries[0].get('type') == 'session' and entries[0].get('id') == session['id'] and Path(entries[0].get('cwd', '')).is_absolute() and Path(entries[0]['cwd']).resolve() == Path(session.get('cwd', self.root / 'work')).resolve(), 'Native Goal session identity/cwd changed')
            goals = [(index, entry.get('data', {}).get('goal')) for index, entry in enumerate(entries) if entry.get('type') == 'custom' and entry.get('customType') == 'goal-state']
            window = session.get('goal_window_id', session['id'])
            peers = [row for row in state['sessions'] if row['id'] == session['id'] and row.get('goal_window_id', row['id']) == window]
            expected = next((row['goal_native_id'] for row in reversed(peers) if row.get('goal_native_id')), None)
            previous_index = max((index for index, goal in goals if isinstance(goal, dict) and goal.get('id') == session.get('goal_previous_native_id')), default=-1)
            candidates = {goal.get('id') for index, goal in goals if index > previous_index and isinstance(goal, dict) and goal.get('id')}
            if expected is None:
                p.require(len(candidates) == 1, 'Cannot identify the owned native Goal window')
                expected = candidates.pop()
            matching = [(index, goal) for index, goal in goals if isinstance(goal, dict) and goal.get('id') == expected and type(goal.get('tokensUsed')) is int and goal['tokensUsed'] >= 0]
            p.require(matching, 'Owned native Goal usage unavailable')
            last_index, last_goal = matching[-1]
            snapshot_index, snapshot = goal_snapshot(entries)
            post_completion = snapshot.get('postCompletionTokens', 0) if snapshot_index == last_index else 0
            if snapshot_index != last_index:
                error = 'Native Goal window identity changed or usage unavailable'
            elif 'postCompletionTokens' not in snapshot and any(entry.get('type') == 'message' and entry.get('message', {}).get('role') == 'assistant' for entry in entries[last_index + 1:]):
                error = 'Native Goal usage has an unaccounted assistant response'
            self.record_goal_usage(max(goal['tokensUsed'] for _, goal in matching) + post_completion, expected, session, usage_error=error)
            with self.store.transaction() as state:
                state['sessions'][-1].update(session_file=str(path), goal_status=last_goal.get('status'))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as failure:
            error = str(failure)
        if error:
            with self.store.transaction() as state:
                state.update(goal_usage_status='unknown', goal_usage_error=error)

    def reuse_ralph_storage(self, task, runner):
        prior = next((row for row in reversed(self.store.read()['sessions'][:-1]) if row.get('ralph_path') == str(task)), None)
        if not prior or prior.get('ralph_usage_status') != 'known' or not prior.get('ralph_cleanup_confirmed') or not prior.get('ralph_loop_token'):
            return None
        lease, fd = None, None
        try:
            lease = os.open(runner, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stat = os.fstat(lease)
            p.require([stat.st_dev, stat.st_ino] == prior.get('ralph_runner_identity'), 'Ralph runner ownership changed')
            fd = os.open(task, os.O_RDWR | os.O_NOFOLLOW)
            stat = os.fstat(fd)
            p.require([stat.st_dev, stat.st_ino] == prior.get('ralph_task_identity') and digest(task) == prior['ralph_task_sha256'], 'Ralph task ownership changed')
            status = runner / 'status.json'
            p.require(not status.is_symlink(), 'Ralph status ownership changed')
            native = read(status)
            p.require(native.get('completedAt') and native.get('loopToken') == prior['ralph_loop_token'] and native.get('ralphPath') == str(task)
                      and native.get('taskDir') == str(task.parent) and native.get('cwd') == prior['ralph_cwd']
                      and native.get('maxIterations') == prior['ralph_max_iterations'], 'Ralph result ownership changed')
            archive = Path(prior['ralph_cwd'])
            p.durable(archive / 'native-result.json', native)
            with (archive / 'native-task.md').open('x') as stream:
                stream.write(task.read_text())
            os.ftruncate(fd, 0)
            self.ralph_storage_fd = lease
            self.ralph_previous_loop_token = prior['ralph_loop_token']
            return fd
        except (OSError, ValueError, KeyError, TypeError):
            if fd is not None:
                os.close(fd)
            if lease is not None:
                os.close(lease)
            return None  # Modified/foreign storage never prevents in-place project work.

    def exclude_ralph_artifacts(self, target):
        """Hide native Ralph storage from the user's git status via local .git/info/exclude; never blocks work."""
        try:
            deadline = time.monotonic() + launch_diff.SECONDS
            if launch_diff.git(target, ['rev-parse', '--is-inside-work-tree'], deadline).stdout.strip() != b'true':
                return
            exclude = Path(target) / launch_diff.checked(target, ['rev-parse', '--git-path', 'info/exclude'], deadline).decode().strip()
            prefix = launch_diff.checked(target, ['rev-parse', '--show-prefix'], deadline).decode().strip()
            added = []
            for name in ('RALPH.md', '.ralph-runner/'):
                tracked = launch_diff.git(target, ['ls-files', '--error-unmatch', '--', name.rstrip('/')], deadline).returncode == 0
                ignored = launch_diff.git(target, ['check-ignore', '-q', '--no-index', '--', name], deadline).returncode == 0
                if not tracked and not ignored:
                    added.append('/' + prefix + name)
            if added:
                exclude.parent.mkdir(exist_ok=True)  # Same directory git init creates by default.
                text = exclude.read_text() if exclude.exists() else ''
                lines = [line for line in added if line not in text.splitlines()]
                if lines:
                    with exclude.open('a') as stream:
                        stream.write(('\n' if text and not text.endswith('\n') else '') + '\n'.join(['# pi-ping-pong native Ralph storage', *lines]) + '\n')
                    with self.store.transaction() as state:
                        p.Controller(self.c, state).event('ralph.storage_excluded', paths=lines, exclude=str(exclude))
        except (OSError, ValueError, UnicodeError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
            with self.store.transaction() as state:
                p.Controller(self.c, state).event('ralph.storage_exclude_unavailable', reason=str(error)[:300])

    def prepare_ralph(self, context):
        directory = self.root / 'ralph' / f'{context["cycle"]:03}'
        directory.mkdir(parents=True, mode=0o700)
        self.rpc_cwd = directory
        with self.store.transaction() as state:
            controller = p.Controller(self.c, state)
            scopes = state['consumption'][-1].get('worker_scope_grants', {state['actions'][context['action_id']]['scope']: []})
            available = min(controller.remaining(scope) for scope in scopes)
            # An unlimited closure grant still gets a finite native window.
            extra = min(49, self.c['max_cycles'] - 1 if available == float('inf') else int(available))  # Vendor 2.1.2 permits at most 50 per native loop.
            for _ in range(extra):
                controller.reserve_worker_iteration(context['action_id'])
            limit = state['consumption'][-1]['worker_iterations']
        # Native also writes a cwd registry: never point it at an existing user runner.
        raw_target = Path(self.c['execution_contract']['target'])
        target = raw_target.resolve() if raw_target.is_absolute() else raw_target
        relative = os.path.relpath(target, self.rpc_cwd) if target.is_absolute() else '.'
        argument = relative
        if any(char.isspace() for char in relative):
            argument = f'"{relative}"' if '"' not in relative else f"'{relative}'" if "'" not in relative else None
        limitation = 'Private task snapshot does not observe product edits.'
        fd = None
        self.ralph_previous_loop_token = None
        if target.is_absolute() and target.is_dir() and not raw_target.is_symlink() and target != directory and argument is not None:
            runner = target / '.ralph-runner'
            task = target / 'RALPH.md'
            if task.exists() and not task.is_symlink() and not runner.is_symlink():
                fd = self.reuse_ralph_storage(task, runner)
            if not task.exists() and not task.is_symlink():
                try:
                    runner.mkdir(mode=0o700)
                except OSError:
                    pass  # Existing or unavailable native storage must not block independent work.
                else:
                    try:
                        fd = os.open(task, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    except OSError:
                        try:
                            runner.rmdir()  # Only our still-empty directory, never existing artifacts.
                        except OSError:
                            pass
                    else:
                        self.ralph_storage_fd = os.open(runner, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                        fcntl.flock(self.ralph_storage_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if fd is not None:
                directory = target
                self.exclude_ralph_artifacts(target)
                limitation = 'Native snapshot observes the target, but can include PPP service changes from .pi/ping-pong and .pi-ping-pong and is bounded to 200 files / 2 MiB; not authorship or acceptance.'
        self.ralph_directory = directory
        self.ralph_argument = argument if directory == target else '.'
        self.ralph_guards = self.rpc_cwd / '.ralph-runner/ppp-guards'
        self.ralph_guards.mkdir(parents=True, mode=0o700)
        guard = Path(__file__).with_name('ralph-parent-guard.mjs').as_uri()
        self.rpc_env = {'PPP_RALPH_GUARDS': str(self.ralph_guards), 'PPP_RALPH_GUARD_IMPORT': '--import=' + guard,
                        'PPP_RALPH_ITERATION_SECONDS': str(min(self.c['cycle_seconds'], 3600)), 'RALPH_RUNNER_LOOP_TOKEN': '',
                        'NODE_OPTIONS': (os.environ.get('NODE_OPTIONS', '') + ' --import=' + guard).strip()}
        promise = 'PPP_RALPH_RESULT_' + uuid.uuid4().hex
        text = f'''---
max_iterations: {limit}
timeout: {min(self.c['cycle_seconds'], 3600)}
completion_promise: {promise}
completion_gate: disabled
---
Read {self.root / 'CONTRACT.md'}, {self.c['task']} and {self.root / 'work/cycle-context.json'}.
Pursue the full dispatched authorized task through your native multi-iteration loop, including ordinary tests. Do not stop at one action or checkpoint. Respect dependencies and continue independent work around actual blockers.
Your shell starts in private service storage {self.rpc_cwd}. Use the product command cwd {self.worker_cwd} and edit the authorized target in place, including dirty files. Cwd grants no extra scope.
Never modify RALPH.md, existing RALPH_PROGRESS.md, or .ralph-runner artifacts yourself. Native telemetry limitation: {limitation}
Core/Reviewer feedback: {context['feedback'] or 'Initial authorized work.'}
Save progress and final checkpoint at {self.root / 'work/checkpoint.json'}, cycle={context['cycle']}. On completing the full objective, or exhausting independent work at a genuine limitation, output <promise>{promise}</promise> and end. This only stops the native loop; it is not acceptance. Do not wait for Reviewer or invent approval. Otherwise continue useful remaining work on the next native iteration.
'''
        task = directory / 'RALPH.md'
        if directory == self.rpc_cwd:
            with task.open('x') as stream:
                stream.write(text)
            task.chmod(0o600)
        else:
            with os.fdopen(fd, 'w') as stream:
                stream.write(text)
        with self.store.transaction() as state:
            task_stat = task.stat()
            runner_stat = (directory / '.ralph-runner').stat()
            state['sessions'][-1].update(ralph_path=str(task), ralph_task_sha256=digest(task), ralph_max_iterations=limit,
                                        ralph_task_identity=[task_stat.st_dev, task_stat.st_ino], ralph_runner_identity=[runner_stat.st_dev, runner_stat.st_ino], ralph_previous_loop_token=self.ralph_previous_loop_token,
                                        ralph_cwd=str(self.rpc_cwd), ralph_snapshot_limitation=limitation, ralph_usage_status='reserved', ralph_guards=str(self.ralph_guards), cwd=str(self.rpc_cwd))
            p.Controller(self.c, state).event('ralph.loop_reserved', iterations=limit, task=str(task), snapshot_limitation=limitation)

    def ralph_state(self):
        session = self.store.read()['sessions'][-1]
        task = Path(session['ralph_path'])
        status = task.parent / '.ralph-runner/status.json'
        if not status.exists():
            return None
        p.require(not task.is_symlink() and digest(task) == session['ralph_task_sha256'], 'Native Ralph task changed')
        p.require(not status.is_symlink() and not status.parent.is_symlink(), 'Native Ralph storage changed')
        native = read(status)
        if session.get('ralph_previous_loop_token') and native.get('loopToken') == session['ralph_previous_loop_token']:
            return None  # Retained prior result is not the newly dispatched loop.
        p.require(native.get('ralphPath') == str(task) and native.get('taskDir') == str(task.parent)
                  and native.get('cwd') == session['ralph_cwd'] and native.get('maxIterations') == session['ralph_max_iterations']
                  and isinstance(native.get('loopToken'), str) and bool(native['loopToken']), 'Native Ralph identity/budget changed')
        p.require(type(native.get('currentIteration')) is int and 0 <= native['currentIteration'] <= session['ralph_max_iterations'], 'Invalid native Ralph iteration usage')
        if session.get('ralph_loop_token'):
            p.require(native['loopToken'] == session['ralph_loop_token'], 'Native Ralph loop identity changed')
        high_water = max(session.get('ralph_iterations_observed', 0), native['currentIteration'])
        if not session.get('ralph_loop_token') or high_water != session.get('ralph_iterations_observed'):
            with self.store.transaction() as state:
                state['sessions'][-1].update(ralph_loop_token=native['loopToken'], ralph_iterations_observed=high_water)
        return native

    def drain_ralph(self):
        try:
            session = self.store.read()['sessions'][-1]
            if not session.get('ralph_path'):
                return
            native = self.ralph_state()
            if not native or native.get('completedAt'):
                return
            stop = Path(session['ralph_guards']) / 'stop.flag'
            try:
                with stop.open('x') as stream:
                    stream.write(native['loopToken'] + '\n')
            except FileExistsError:
                p.require(not stop.is_symlink() and stop.read_text().strip() == native['loopToken'], 'Ralph guard stop identity changed')
            cleanup_deadline = time.monotonic() + 0.5
            while time.monotonic() < cleanup_deadline:
                if all(read(marker).get('cleaned') is True for marker in Path(session['ralph_guards']).glob('child-*.json')):
                    break
                time.sleep(0.02)
            flag = Path(session['ralph_path']).parent / '.ralph-runner/cancel.flag'
            try:
                with flag.open('x') as stream:
                    stream.write(native['loopToken'] + '\n')
            except FileExistsError:
                p.require(not flag.is_symlink() and flag.read_text().strip() == native['loopToken'], 'Ralph cancellation signal identity changed')
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and self.process_returncode() is None:
                native = self.ralph_state()
                if native and native.get('completedAt'):
                    return
                time.sleep(0.05)
        except (OSError, ValueError, KeyError, IndexError) as error:
            self.event('ralph.cancel_incomplete', reason=str(error))

    def ralph_children_error(self):
        try:
            state = self.store.read()
            if not state['sessions'] or not state['sessions'][-1].get('ralph_guards'):
                return None
            session = state['sessions'][-1]
            directory = Path(session['ralph_guards'])
            p.require(directory.resolve().is_relative_to(self.root.resolve()) and not directory.is_symlink(), 'Ralph guard storage changed')
            deadline = time.monotonic() + 3
            while True:
                alive, uncleaned, groups = [], [], set()
                for marker in directory.glob('child-*.json'):
                    p.require(not marker.is_symlink(), 'Ralph guard marker changed')
                    child = read(marker)
                    p.require(type(child.get('pid')) is int and child['pid'] > 1 and child.get('host') == session.get('pid'), 'Ralph child ownership changed')
                    if session.get('ralph_loop_token'):
                        p.require(child.get('loop_token') == session['ralph_loop_token'], 'Ralph child loop identity changed')
                    if child.get('cleaned') is not True:
                        uncleaned.append(child['pid'])
                    detached = child.get('detached_pids')
                    p.require(isinstance(detached, list) and all(type(pid) is int and pid > 1 for pid in detached), 'Ralph detached shell ownership is unknown')
                    groups.update(detached)
                    try:
                        os.kill(child['pid'], 0)  # Observation only; never signal a possibly reused PID.
                        observed = subprocess.run(['ps', '-o', 'stat=', '-p', str(child['pid'])], capture_output=True, text=True, timeout=1)
                        if not observed.stdout.strip().startswith('Z'):
                            alive.append(child['pid'])
                    except ProcessLookupError:
                        pass
                observed = subprocess.run(['ps', '-axo', 'pid=,pgid=,stat='], capture_output=True, text=True, timeout=1, check=True)
                shells = [int(pid) for line in observed.stdout.splitlines() for pid, pgid, stat in [line.split()] if int(pgid) in groups and not stat.startswith('Z')]
                if not alive and not uncleaned and not shells:
                    return None
                if time.monotonic() >= deadline:
                    return f'Native Ralph child cleanup is unconfirmed (alive={alive}, uncleaned={uncleaned}, shells={shells}); outputs are unverified, no new Worker/Reviewer or blind replay'
                time.sleep(0.05)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            return 'Native Ralph child ownership is unknown: ' + str(error)

    def reconcile_ralph_usage(self):
        state = self.store.read()
        if self.c['mode'] != 'ralph' or not state['sessions'] or not state['sessions'][-1].get('ralph_path'):
            return
        try:
            native = self.ralph_state()
            # Only a confirmed native result can release unused reservations; interruption keeps the full bound.
            if not native or not native.get('completedAt') or native.get('status') not in {'complete', 'max-iterations', 'no-progress-exhaustion'}:
                return
            with self.store.transaction() as state:
                session = state['sessions'][-1]
                row = next(row for row in state['consumption'] if row['cycle'] == session['cycle'])
                used = max(1, native['currentIteration'], session.get('ralph_iterations_observed', 0))
                row['worker_iterations'] = used
                row['worker_iteration_grants'] = row['worker_iteration_grants'][:used]
                if 'worker_scope_grants' in row:
                    row['worker_scope_grants'] = {scope: identities[:used] for scope, identities in row['worker_scope_grants'].items()}
                session.update(ralph_usage_status='known', ralph_iterations=used, ralph_status=native['status'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            with self.store.transaction() as state:
                state['sessions'][-1].update(ralph_usage_status='reserved', ralph_usage_error=str(error))

    def worker(self, aid, repair_feedback=None):
        self.control_point()
        persistent_goal = self.c['mode'] == 'goal'
        native_loop = self.c['mode'] in {'goal', 'ralph'}
        restored_goal = self.prepare_goal_session() if persistent_goal else False
        if self.worker_lock is None:
            self.acquire_worker()
        self.owner = uuid.uuid4().hex
        if not persistent_goal:
            self.c['worker_session_id'] = uuid.uuid4().hex
        started = time.monotonic()
        self.active_started_at = started
        self.worker_started_at = started
        try:
            with self.boundary() as s:
                e = p.Controller(self.c, s)
                if repair_feedback is None:
                    e.consume(aid, self.owner)
                else:
                    active = s['active']
                    p.require(active is not None and active['action_id'] == aid, 'Worker repair lost its reserved action')
                    prior = [session for session in s['sessions'] if session['cycle'] == active['cycle'] and session['action_id'] == aid]
                    p.require(bool(prior), 'Worker repair has no prior attempt in its reserved cycle')
                    active['owner'] = self.owner
                    attempt = None
                    if self.c['mode'] != 'goal':
                        try:
                            attempt = e.reserve_checkpoint_repair(aid)
                        except ValueError as error:
                            if 'Checkpoint repair limit exhausted' not in str(error):
                                raise
                            raise WorkerBudgetExhausted(str(error)) from None
                    e.event('worker.checkpoint_repair', action_id=aid, cycle=active['cycle'], diagnosis=repair_feedback, attempt=attempt)
                s['sessions'].append(dict(id=self.c['worker_session_id'], owner=self.owner, cycle=s['cycle'], action_id=aid, status='starting', pid=None, session_file=None, **({'action_ids': s['active'].get('action_ids', [aid])} if native_loop else {}), cwd=str(getattr(self, 'worker_cwd', self.root / 'work')), started_at=time.time(), **({'goal_window_id': self.goal_window_id, 'goal_started': self.goal_started, 'goal_token_baseline': s.get('worker_tokens', 0), 'goal_token_budget': p.Controller(self.c, s).goal_tokens_remaining(), 'goal_previous_native_id': self.goal_previous_native_id} if persistent_goal else {})))
            kill_marker = self.root / 'work/Test-goal-window-killed'
            if persistent_goal and os.environ.get('PPP_TEST_KILL_AFTER_GOAL_WINDOW_PERSIST') == str(s['cycle']) and not kill_marker.exists():
                kill_marker.touch()
                os.kill(os.getpid(), signal.SIGKILL)
            s = self.store.read()
            self.state['cycle'] = s['cycle']
            context = {**p.header(self.c['run_id']), 'budget': {'cycle_seconds': self.c.get('cycle_seconds'), 'worker_seconds_remaining': self.wall_remaining(), 'goal_tokens_used': s.get('worker_tokens') if persistent_goal else None, 'goal_tokens_remaining': p.Controller(self.c, s).goal_tokens_remaining() if persistent_goal else None, 'goal_launches_remaining': max(0, p.Controller(self.c, s).goal_launch_limit() - p.Controller(self.c, s).goal_launches_used()) if persistent_goal else None, 'usage_status': s.get('goal_usage_status', 'known')}, 'cycle': s['cycle'], 'action_id': aid, 'owner': self.owner, 'state_path': str(self.store.path), 'task': self.c['task'], 'feedback': repair_feedback or s.get('last_feedback') or s.get('last_review'), 'worker_attempt': sum(session['cycle'] == s['cycle'] and session['action_id'] == aid for session in s['sessions']), 'action': s['actions'][aid], 'blockers': s['blockers'], 'grants': s['grants'], 'consumption': s['consumption'], 'prior_sessions': s['sessions'][:-1]}
            if native_loop and repair_feedback is None and context['prior_sessions']:
                # Native loops have no checkpoint repair turn; carry Core's rejection diagnosis into the next dispatch.
                prior = context['prior_sessions'][-1]
                rejected = next((event['diagnosis'] for event in reversed(s['history']) if event['type'] == 'worker.checkpoint_invalid'
                                 and event.get('cycle') == prior['cycle'] and event.get('action_id') == prior['action_id']), None)
                if rejected and prior.get('status') == 'native_result':
                    context['checkpoint_rejected'] = rejected
                    context['feedback'] = f"{context['feedback'] or ''}\nCore rejected your previous checkpoint (cycle {prior['cycle']}): {rejected}. Fix it so this checkpoint is accepted.".lstrip()
            if native_loop:
                context['action_ids'] = s['active'].get('action_ids', [aid])
                context['actions'] = {item: s['actions'][item] for item in context['action_ids']}
            if repair_feedback is None:
                (self.root / 'work/checkpoint.json').unlink(missing_ok=True)
            prior_seconds = sum(max(0, session.get('ended_at', session.get('started_at', time.time())) - session.get('started_at', time.time())) for session in context['prior_sessions'] if session['cycle'] == s['cycle'] and session['action_id'] == aid)
            now = time.monotonic()
            remaining = self.wall_remaining() if native_loop else min(max(0, self.c['cycle_seconds'] + 45 - prior_seconds), self.wall_remaining())
            self.operation_deadline = now + remaining
            if remaining <= 0:
                raise TimeoutError('Cumulative worker cycle/wall budget exhausted during checkpoint repair')
            context['budget'].update(recorded_at=time.time(), cycle_seconds_remaining=remaining if persistent_goal else min(self.c['cycle_seconds'], remaining))
            self.acquire_writer()
            if self.c['mode'] == 'ralph':
                self.prepare_ralph(context)
                context['budget']['ralph_iterations_reserved'] = self.store.read()['sessions'][-1]['ralph_max_iterations']
                context['budget']['ralph_snapshot_limitation'] = self.store.read()['sessions'][-1]['ralph_snapshot_limitation']
            self.rpc_env = {**getattr(self, 'rpc_env', {}), 'PPP_WORK_DIR': str(self.root / 'work'),
                            'PPP_CHECKPOINT_PATH': str(self.root / 'work/checkpoint.json'),
                            'PPP_CONTEXT_PATH': str(self.root / 'work/cycle-context.json'),
                            'PPP_TARGET': self.c['execution_contract']['target'],
                            'PPP_CHECKPOINT_CMD': str(Path(__file__).with_name('ppp_checkpoint.py'))}
            p.durable(self.root / 'work/cycle-context.json', context)
            self.control_point()
            if self.proc is None:
                if persistent_goal:
                    with self.store.transaction() as state:
                        state['sessions'][-1]['goal_dispatch_attempted'] = True
                self.spawn()
            with self.store.transaction() as state:
                state['sessions'][-1].update(pid=self.proc.pid, session_file=self.state.get('pi_session'), status='running')
            self.project('working')
            def announce_worker():
                self.ui_notice(f'review-worker-{s["cycle"]}',
                               f'{self.root.name} · cycle {s["cycle"]}\nWorker started: {aid} ({self.c["mode"]}).')
            if self.c['mode'] == 'goal':
                # Checkpoint changes never start a second native Goal or reset its token allowance.
                cycle = self.state['cycle']
                self.state['cycle'] = 1
                try:
                    if restored_goal:
                        native = self.goal_state(deadline=self.operation_deadline)
                        native_goal_id = native.get('id')
                        same_window = bool(native_goal_id and (native_goal_id == self.goal_native_id if self.goal_native_id else native_goal_id != self.goal_previous_native_id))
                        p.require(not self.goal_started or same_window, 'Restored native Goal window identity changed')
                        self.goal_started = self.goal_started or same_window and native.get('status') == 'active'
                        usage = native.get('tokens_used')
                        if same_window and type(usage) is int and usage >= 0:
                            self.record_goal_usage(usage, native_goal_id)
                        if not self.goal_started:
                            self.c['goal_session_tokens'] = p.Controller(self.c, self.store.read()).goal_tokens_remaining()
                    replace_budget_limited = False
                    if not self.goal_started and self.goal_previous_native_id:
                        native = self.goal_state(deadline=self.operation_deadline)
                        previous = next(row for row in reversed(context['prior_sessions']) if row.get('goal_native_id') == self.goal_previous_native_id)
                        expected_status = previous.get('goal_status', 'budget_limited')
                        p.require(native.get('id') == self.goal_previous_native_id and native.get('status') == expected_status, 'Cannot renew Goal: previous native Goal identity or budget state changed')
                        replace_budget_limited = expected_status != 'complete'
                    try:
                        super().goal_cycle(context['feedback'], fresh_session=not self.goal_started,
                                           replace_budget_limited=replace_budget_limited, on_start=announce_worker)
                    except TimeoutError:
                        if self.remaining() > 0:
                            raise
                        self.shutdown()
                        with self.store.transaction() as state:
                            state['sessions'][-1].update(status='interrupted', goal_limit='worker_time')
                            p.Controller(self.c, state).event('worker.goal_time_limited', cycle=state['cycle'])
                        return None, None, None
                    self.goal_started = True
                    native = self.goal_boundary
                    usage = native.get('tokens_used')
                    p.require(type(usage) is int and usage >= 0 and native.get('id'), 'Native Goal usage unavailable')
                    self.record_goal_usage(usage, native.get('id'))
                    with self.store.transaction() as state:
                        state['sessions'][-1].update(goal_status=native.get('status'), goal_waiting=native.get('waiting'))
                        if self.goal_budget_limited:
                            state['sessions'][-1]['status'] = 'budget_limited'
                            p.Controller(self.c, state).event('worker.goal_budget_limited', action_id=aid, cycle=state['cycle'], tokens_used=usage)
                    self.shutdown()  # Freeze native wake timers before inspecting the result.
                    if not (self.root / 'work/checkpoint.json').is_file():
                        with self.store.transaction() as state:
                            if not self.goal_budget_limited:
                                state['sessions'][-1]['status'] = 'native_result'
                        return None, None, None
                finally:
                    self.state['cycle'] = cycle
            elif self.c['mode'] == 'ralph':
                try:
                    self.ralph_cycle(on_start=announce_worker)
                except TimeoutError:
                    if self.remaining() > 0:
                        raise
                    with self.store.transaction() as state:
                        state['sessions'][-1]['status'] = 'budget_limited'
                except RuntimeError as error:
                    if self.proc is None or self.process_returncode() is None:
                        raise
                    with self.store.transaction() as state:
                        state['sessions'][-1].update(status='native_result', ralph_host_error=str(error))
                        p.Controller(self.c, state).event('worker.ralph_host_exited', reason=str(error))
                self.shutdown()  # Native cancel and the parent guard cover detached RPC child groups.
                if self.ralph_freeze_error:
                    raise RuntimeError(self.ralph_freeze_error)
                self.reconcile_ralph_usage()
                if not (self.root / 'work/checkpoint.json').is_file():
                    with self.store.transaction() as state:
                        if state['sessions'][-1]['status'] != 'budget_limited':
                            state['sessions'][-1]['status'] = 'native_result'
                    return None, None, None
            else:
                self.ping_pong_cycle(on_start=announce_worker)
            try:
                cp, snap = validate_checkpoint(self.c, s['cycle'])
                p.envelope(cp, self.c['run_id'])
                p.require(cp.get('action_id') == aid and type(cp.get('cycle')) is int, f"Checkpoint action/cycle identity changed: action_id {cp.get('action_id')!r} (expected {aid!r})")
            except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
                # A missing/wrong identity is never accepted, but it is the Worker's checkpoint error, not a safety stop: repair or review available outputs.
                with self.store.transaction() as state:
                    state['sessions'][-1]['status'] = 'native_result' if native_loop else 'repair_needed'
                    p.Controller(self.c, state).event('worker.checkpoint_invalid', action_id=aid, cycle=s['cycle'], diagnosis=str(error))
                return None, None, None if native_loop else str(error)
            if cp.get('halt_reason') is not None:
                p.text(cp['halt_reason'])
                with self.store.transaction() as state:
                    state['execution'] = 'halt'
                    state['wait'] = None
                    p.Controller(self.c, state).event('execution.halt', reason=cp['halt_reason'], checkpoint_sha256=snap['checkpoint_sha256'])
                raise Terminated('Worker reported global safety risk; no further execution')
            with self.store.transaction() as state:
                if state['sessions'][-1]['status'] != 'budget_limited':
                    state['sessions'][-1]['status'] = 'checkpoint'
            if self.c['mode'] == 'ralph':
                directory = self.root / 'unverified-results' / f'cycle-{cp["cycle"]:06}'
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                p.require(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Unverified result directory must be private')
                p.durable(directory / 'checkpoint.json', cp)
                archive = retain_evidence(self.c, snap['evidence_sha256'], time.monotonic() + min(120, self.c['review_seconds']))
                result = dict(cycle=cp['cycle'], action_id=aid, summary=cp['summary'], status='unverified',
                              checkpoint=str(directory / 'checkpoint.json'), checkpoint_sha256=digest(directory / 'checkpoint.json'), workspace=str(self.root / 'work'),
                              available_files=list(snap['evidence_sha256']), evidence_sha256=snap['evidence_sha256'], evidence_archive=archive,
                              limitations=['Worker checkpoint/native completion is not independent acceptance.', self.store.read()['sessions'][-1]['ralph_snapshot_limitation']])
                p.durable(directory / 'result.json', result)
                with self.store.transaction() as state:
                    state.setdefault('available_results', []).append(result)
            return cp, snap, None
        finally:
            self.shutdown()
            self.reconcile_ralph_usage()
            if persistent_goal:
                # Shutdown may append the final native usage snapshot.
                self.reconcile_goal_usage()
            self.operation_deadline = float('inf')
            with self.store.transaction() as state:
                elapsed = time.monotonic() - started
                prior_active = state['active_seconds']
                state['active_seconds'] += elapsed
                state['worker_seconds'] = state.get('worker_seconds', prior_active) + elapsed
                self.active_started_at = None
                self.worker_started_at = None
                if state['sessions'] and state['sessions'][-1]['owner'] == self.owner:
                    state['sessions'][-1]['ended_at'] = time.time()
                    if self.c['mode'] == 'ping-pong':
                        row = state['sessions'][-1]
                        row.update(session_usage(row.get('session_file'), row['id'], self.root / 'sessions'))
                    if state['sessions'][-1]['status'] not in {'checkpoint', 'repair_needed', 'budget_limited', 'native_result'}:
                        state['sessions'][-1]['status'] = 'interrupted'

    def preserve_budget_result(self):
        try:
            self._preserve_partial_result()
        except (OSError, ValueError, KeyError, TypeError, TimeoutError) as error:
            with self.store.transaction() as state:
                p.Controller(self.c, state).event('outputs.retention_incomplete', reason=str(error))
            self.state['output_discovery_limitation'] = str(error)

    def _preserve_partial_result(self):
        state = self.store.read()
        # repair_needed as last session means checkpoint repair was abandoned at its limit.
        if not state['sessions'] or state['sessions'][-1]['status'] not in {'budget_limited', 'interrupted', 'native_result', 'repair_needed'}:
            return
        session = state['sessions'][-1]
        if not session.get('session_file') and not session.get('pid') and not session.get('goal_dispatch_attempted'):
            return
        if any(item['cycle'] == session['cycle'] for item in state.get('available_results', [])):
            return
        try:
            checkpoint, _ = validate_checkpoint(self.c, session['cycle'])
            p.envelope(checkpoint, self.c['run_id'])
            if type(checkpoint.get('cycle')) is int and checkpoint.get('action_id') == session['action_id']:
                return  # Existing checkpoints, not discovery, are the primary result.
        except (OSError, ValueError, KeyError, TypeError):
            pass
        files, calls, limitations = {}, {}, []
        if session.get('goal_limit') == 'worker_time':
            limitations.append(f'Cumulative Worker time budget exhausted ({self.c["wall_seconds"]} seconds); no further Worker allowance remains.')
        candidates = {}
        last_goal_id = None
        deadline = time.monotonic() + min(120, self.verification_remaining())
        try:
            path = Path(session.get('session_file') or '')
            p.require(path.is_absolute() and path.resolve().is_relative_to((self.root / 'sessions').resolve()) and not path.is_symlink(), 'Owned Worker session unavailable')
            with path.open() as stream:
                header = json.loads(stream.readline())
                p.require(header.get('type') == 'session' and header.get('id') == session['id'] and Path(header['cwd']).resolve() == Path(session.get('cwd', self.root / 'work')).resolve(), 'Owned Worker session identity/cwd changed')
                for line in stream:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Partial evidence collection deadline reached')
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        limitations.append('Incomplete session entry omitted.')
                        continue
                    if entry.get('type') == 'custom' and entry.get('customType') == 'goal-state':
                        # Native completion clears goal-state; the cleared window still owns this session's outputs.
                        last_goal_id = (entry.get('data', {}).get('goal') or {}).get('id') or last_goal_id
                    if entry.get('type') != 'message':
                        continue
                    timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).timestamp()
                    if not session['started_at'] <= timestamp <= session['ended_at']:
                        continue
                    message = entry['message']
                    if message.get('role') == 'assistant':
                        for call in message.get('content', []):
                            if call.get('type') == 'toolCall' and call.get('name') in {'write', 'edit', 'bash'}:
                                args = call['arguments']
                                # Never copy prompts, read results, or write/edit content from the transcript.
                                calls[call['id']] = dict(tool=call['name'], **{key: args[key] for key in ('path', 'command') if key in args})
                    elif message.get('role') == 'toolResult' and message.get('toolCallId') in calls:
                        call = calls[message['toolCallId']]
                        call['result'] = {key: message[key] for key in ('isError', 'exitCode') if key in message}
                        if call['tool'] == 'bash':
                            call['result']['content'] = [item for item in message.get('content', []) if item.get('type') == 'text']
            if self.c['mode'] == 'goal':
                p.require(last_goal_id and last_goal_id == session.get('goal_native_id'), 'Owned native Goal window changed or unavailable')
            for call in calls.values():
                if call['tool'] == 'bash':
                    try:
                        p.require(not re.search(r'(?:\.env\b|auth\.json\b|credentials\.json\b)', call.get('command', ''), re.I), 'Secret-bearing shell command')
                        for value in [call.get('command', '')] + [item['text'] for item in call.get('result', {}).get('content', [])]:
                            for line in value.splitlines():
                                if line.strip():
                                    p.text(line)
                    except ValueError:
                        call.clear()
                        call.update(tool='bash', omitted='Potentially private or unbounded shell evidence omitted.')
                        limitations.append(call['omitted'])
                    continue
                if call['tool'] not in {'write', 'edit'} or not isinstance(call.get('path'), str):
                    continue
                try:
                    raw = Path(session.get('cwd', self.root / 'work')) / call['path']
                    p.require(not outputs.private_path(raw.name) and raw.resolve() == raw.absolute(), 'Private or symlinked referenced output omitted')
                    candidate = evidence_path(self.c, str(raw))
                    scope = self.root / 'work' if candidate.is_relative_to(self.root / 'work') else Path(self.c['execution_contract']['target']).resolve()
                    p.require((scope == self.root / 'work' or not outputs.service_path(candidate)) and not outputs.private_path(candidate.relative_to(scope)), 'Private referenced output omitted')
                    if candidate.is_file():
                        p.require(candidate.stat().st_size <= outputs.MAX_FILE_BYTES, 'Oversized referenced output omitted')
                        name = str(candidate.relative_to(self.root / 'work')) if candidate.is_relative_to(self.root / 'work') else str(candidate)
                        files[name] = digest(candidate)
                except (OSError, ValueError) as error:
                    limitations.append('Referenced output omitted: ' + str(error))
        except (OSError, ValueError, KeyError, TypeError, TimeoutError) as error:
            calls, files = {}, {}
            limitations.append('Owned session evidence unavailable: ' + str(error))
        try:
            try:
                baseline = read(self.root / 'output-baseline.json')
            except (OSError, ValueError):
                baseline = None
            candidates, discovered_limits = outputs.changes(self.c, baseline)
            limitations.extend(discovered_limits)
        except (OSError, ValueError) as error:
            limitations.append('Scoped output discovery unavailable: ' + str(error))
        # Session references and launch comparisons are distinct evidence, never authorship.
        selected = {**files, **candidates}
        limit = self.c.get('max_evidence_files', 20)
        if len(selected) > limit:
            limitations.append(f'Fallback retention limited to {limit} file references; other scoped candidates remain listed in the result manifest.')
        files = {}
        for name, expected in list(selected.items())[:limit]:
            try:
                candidate = evidence_path(self.c, name)
                p.require((candidate.is_relative_to(self.root / 'work') or not outputs.service_path(candidate)) and not outputs.private_path(candidate.name), 'Private candidate omitted')
                with candidate.open('rb') as stream:
                    content = stream.read(outputs.MAX_FILE_BYTES + 1)
                p.require(len(content) <= outputs.MAX_FILE_BYTES and b'\0' not in content, 'Non-text or oversized candidate omitted')
                p.require(not re.search(rb'(?:password|passwd|private[_-]?key)\s*[:=]\s*\S+', content, re.I), 'Potentially private candidate omitted')
                for line in content.decode('utf-8').splitlines():
                    if line.strip():
                        p.text(line)
                p.require(hashlib.sha256(content).hexdigest() == expected, 'Candidate changed during collection')
                key = str(candidate.relative_to(self.root / 'work')) if candidate.is_relative_to(self.root / 'work') else str(candidate)
                files[key] = expected
            except (OSError, ValueError, UnicodeError) as error:
                files.pop(name, None)
                limitations.append('Candidate not copied: ' + str(error))
        limitations.append('Shell facts are not inferred exit codes or acceptance; unreferenced files may remain outside bounded discovery.')
        name = f'budget-result-{session["cycle"]:06}-{uuid.uuid4().hex}.json'
        material = dict(run_id=self.c['run_id'], cycle=session['cycle'], action_id=session['action_id'],
                        session_id=session['id'], goal_native_id=session.get('goal_native_id'),
                        checkpoint=None, tool_facts=calls, discovery_candidates=list(candidates), available_files=list(files), limitations=limitations)
        p.durable(self.root / 'work' / name, material)
        files[name] = digest(self.root / 'work' / name)
        archive = {}
        for key, value in list(files.items()):
            try:
                archive.update(retain_evidence(self.c, {key: value}, deadline))
            except (OSError, ValueError, TimeoutError) as error:
                files.pop(key)
                limitations.append('Available file retention incomplete: ' + str(error))
        result = dict(cycle=session['cycle'], action_id=session['action_id'], status='unverified',
                      summary='Worker stopped before checkpoint; scoped candidate files and available owned-session tool facts are retained, not accepted.',
                      checkpoint=None, workspace=str(self.root / 'work'), worker_tokens_total=state['worker_tokens'] if self.c['mode'] == 'goal' else None,
                      available_files=[key for key in files if key != name], discovery_candidates=list(candidates), evidence_sha256=files, evidence_archive=archive, limitations=limitations)
        directory = self.root / 'unverified-results' / f'cycle-{session["cycle"]:06}'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.require(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Unverified result directory must be private')
        p.durable(directory / 'result.json', result)
        with self.store.transaction() as current:
            current.setdefault('available_results', []).append(result)
            p.Controller(self.c, current).event('worker.partial_result_retained', cycle=session['cycle'], action_id=session['action_id'])

    def preserve_unverified_worker(self, checkpoint, snap):
        cycle = checkpoint['cycle']
        directory = self.root / 'unverified-results' / f'cycle-{cycle:06}'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.require(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Unverified result directory must be private')
        checkpoint_path = directory / 'checkpoint.json'
        p.durable(checkpoint_path, checkpoint)
        archive = retain_evidence(self.c, snap['evidence_sha256'], time.monotonic() + min(120, self.c['review_seconds']))
        result = dict(cycle=cycle, action_id=checkpoint['action_id'], summary=checkpoint['summary'], checkpoint=str(checkpoint_path),
                      checkpoint_sha256=snap['checkpoint_sha256'], evidence_archive=archive)
        with self.store.transaction() as state:
            verification = state.get('verification') or {}
            p.require(verification.get('status') == 'blocked', 'Only a blocked verification can preserve unverified Worker output')
            results = verification.setdefault('unverified_results', [])
            state['active'] = None
            if not any(item['cycle'] == cycle for item in results):
                results.append(result)
                p.Controller(self.c, state).event('worker.result_preserved_unverified', cycle=cycle, action_id=checkpoint['action_id'])

    def preserve_unverified_budget_limited_worker(self, action_id, locked_state=None):
        with (nullcontext(locked_state) if locked_state is not None else self.store.transaction()) as state:
            verification = state.get('verification') or {}
            p.require(verification.get('status') == 'blocked', 'Only a blocked verification can preserve unverified Worker output')
            active = state.get('active') or {}
            cycle = state['cycle']
            p.require(active.get('action_id') == action_id and active.get('owner') == self.owner and active.get('cycle') == cycle,
                      'Budget-limited Worker reservation changed')
            results = verification.setdefault('unverified_results', [])
            result = dict(cycle=cycle, action_id=action_id,
                          summary='Goal reached its token budget before writing a checkpoint; workspace output is retained but not independently verified.',
                          checkpoint=None, workspace=str(self.root / 'work'), worker_tokens_total=state['worker_tokens'])
            state['active'] = None
            if not any(item['cycle'] == cycle and item['action_id'] == action_id for item in results):
                results.append(result)
                p.Controller(self.c, state).event('worker.result_preserved_unverified', cycle=cycle, action_id=action_id, budget_limited=True)

    def control_point(self):
        self.ingress(controls_only=True)
        if self.store.read()['execution'] in p.TERMINAL:
            raise Terminated('Cancellation/halt takes precedence')
        self.verify_pins()

    def verification_failure(self, kind, diagnosis, phase, checkpoint, snap, review=None, directory=None):
        self.control_point()
        with self.boundary() as state:
            directory = directory or self.root / 'reviews' / f'v2-{state["review_seq"]:06}'
            blocked = sorted({aid for row in p.Controller(self.c, state).unassessed() for aid in row.get('action_ids', [row['action_id']])})
            state['verification'] = dict(status='blocked', kind=kind, diagnosis=diagnosis,
                blocked_action_ids=blocked, directory=str(directory), cycle=state['cycle'],
                phase=phase, checkpoint=checkpoint, snap=snap, review=review)
            if self.c['mode'] == 'goal' and state['active'] and state['sessions'][-1]['status'] == 'budget_limited':
                self.preserve_unverified_budget_limited_worker(state['active']['action_id'], locked_state=state)
            state.update(execution='wait', wait=None, active=None)
            state['acceptance'] = {cid: 'unknown' for cid in state['acceptance']}
            p.Controller(self.c, state).event('verification.' + kind, verification=deepcopy(state['verification']))
        if checkpoint is not None and snap is not None:
            self.preserve_unverified_worker(checkpoint, snap)
        self.project('verification_blocked', reason=diagnosis)

    def review_result(self, phase, checkpoint=None, snap=None):
        """One independent review after actual work or a concrete reconciliation event."""
        self.control_point()
        started = time.monotonic()
        self.active_started_at = started
        self.verification_started_mono = started
        try:
            self._review_result(phase, checkpoint, snap)
        except VerificationTechnical as error:
            self.verification_failure('technical', str(error), phase, checkpoint, snap)
        finally:
            self.verification_started_mono = None
            with self.store.transaction() as state:
                elapsed = time.monotonic() - started
                state['active_seconds'] += elapsed
                state['verification_seconds'] = state.get('verification_seconds', 0) + elapsed
                self.active_started_at = None

    def _review_result(self, phase, checkpoint=None, snap=None):
        self.verify_pins()
        self.ingress()
        self.resource_events()
        self.control_point()
        if snap is None:
            self.preserve_budget_result()
        with self.store.transaction() as state:
            state['review_seq'] += 1
        state = self.store.read()
        seq = state['review_seq']
        directory = self.root / 'reviews' / f'v2-{seq:06}'
        directory.mkdir(mode=0o700)
        context = {**p.header(self.c['run_id']), 'phase': phase, 'state': state,
                   'checkpoint': checkpoint, 'task': self.c['task'], 'contract': self.c['execution_contract']}
        p.durable(directory / 'context.json', context)
        # Retain all previously supplied evidence for human resolutions and recovery too.
        hashes = {}
        if (self.root / 'work/cycle-context.json').is_file():
            hashes['cycle-context.json'] = digest(self.root / 'work/cycle-context.json')
        prior = self.root / 'reviews' / f'v2-{seq-1:06}' / 'request.json'
        if prior.exists():
            for name in read(prior)['evidence_sha256']:
                if evidence_path(self.c, name).is_file():
                    hashes[name] = digest(evidence_path(self.c, name))
        for result in state.get('available_results', []):
            if result['cycle'] == state['cycle']:
                hashes.update(result['evidence_sha256'])
        if snap:
            p.require(digest(self.root / 'work/checkpoint.json') == snap['checkpoint_sha256'], 'Checkpoint changed before review')
            hashes.update(snap['evidence_sha256'])
        archive = retain_evidence(self.c, hashes, time.monotonic() + min(120, self.c['review_seconds']))
        request = {**p.header(self.c['run_id']), 'review_id': seq, 'cycle': state['cycle'],
            'phase': phase, 'state_revision': state['revision'], 'state_sha256': p.sha(state),
            'checkpoint_sha256': snap['checkpoint_sha256'] if snap else None,
            'checkpoint': checkpoint, 'evidence_sha256': hashes, 'evidence_archive': archive}
        try:
            request['launch_diff'] = launch_diff.build(self.c, self.root, directory)
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
            request['launch_diff'] = dict(coverage='unknown', files={}, truncated=False, limitations=['Launch diff unavailable: ' + str(error)[:300]])
        p.durable(directory / 'request.json', request)
        self.project(request=directory / 'request.json')
        script = Path(__file__).with_name('bridge.py')
        prompt = f'''Independent review of {self.c['task']} after Worker results or a concrete reconciliation event.
Worker executes and runs ordinary tests. Reviewer assesses. Core decides.
Read {directory / 'request.json'}, {directory / 'context.json'} and relevant source/evidence as needed; TASK and the contract/checkpoint are provided inline below, so do not reread them just for read events.
Each evidence_archive value is the complete path to an immutable FILE; read it directly.
Fallback discovery files are unattributed scoped candidates compared with launch hashes, not proof of Worker authorship or executed tests. Missing/partial baselines and concurrent edits leave provenance uncertain.
Launch diff (evidence ref "{launch_diff.REF}"): {request['launch_diff'].get('path', 'unavailable')}; coverage {request['launch_diff']['coverage']}. It is a Core fact, not a verdict: a line diff from launch (HEAD + the user's uncommitted edits) to now for files dirty/untracked at launch; authorship is not proven and concurrent user edits are possible. Removed or rewritten launch lines of the user that TASK does not justify are a concrete defect. Missing, partial or unknown launch material stays unknown, never a synthetic correction. Use the retained ordinary test results for exactly what they establish; do not rerun or re-prove deterministic checks. Assess only the remaining requirement fit, visual/semantic questions, omissions, and concrete contradictions. Ground each defect in an actual user requirement and relevant observed behavior. Do not invent selectors, names, scenarios, approvals, or acceptance gates. An unexecuted or missing check is unknown/not_tested, not a product failure or a reason to manufacture another Worker iteration.
Do not implement or repair the task, edit files, execute task work, start workers, extend budgets, or fabricate human input. Core owns continuation and acceptance. No task-specific evaluator exists or should be generated or repaired.
Return JSON with decision=endorse|halt|stop, nonempty feedback, and for endorse an assessment using the EXISTING action/criterion report schema below. Endorse submits independent judgments, not acceptance. Core binds identity/target/hashes and validates all judgments. Do not echo service identities. halt is a concrete global safety/integrity issue; stop is explicit abandonment. Missing evidence alone is neither.
assessment fields: source_state (specific inspected source state), safe (boolean), halt_reason (null unless unsafe), actions (every current action), blockers, resolutions, grants, criteria, reconciliation; optional decompositions and wake as in the existing action protocol.
Each action: {{action:{{id,description,depends_on,operations}}, status:pending|verified|stalled, eligible:boolean, scope_authorized:true, dependencies_valid:true, evidence_refs:[retained names], attempt:null|{{strategy,state_before,outcome,fingerprint,assessment:verified|informative|none,evidence_refs}}, experiment:null|{{hypothesis,material_difference,expected_evidence,next_step,fingerprint,evidence_refs}}}}.
For the selected unassessed cycle include its actual independent attempt assessment, never infer verified from Worker ready/exit0/native completion. A native Goal/Ralph cycle may dispatch action_ids as one full objective; assess the actual whole result, not separate technical-action ceremonies. The anchor action requires the cycle attempt; attempts for other dispatched actions are optional. To continue an eligible unfinished dispatched action without an experiment, add continuation:{{next_step,evidence_refs}} to its action judgment: identify specific remaining authorized work or a concrete correction and cite evidence. Set status pending and an informative attempt (on that action or the native loop anchor). Never use continuation or experiment merely for unknown verification, generic feedback, or unchanged unproductive work. Existing experiment remains supported. Unrelated eligible actions can continue.
criteria maps EVERY contract criterion to {{status:pass|fail|blocked|not_tested|unknown,evidence_refs:[retained names]}}. Pass requires relevant retained evidence, including ordinary test results where applicable; never fabricate pass from missing evidence. Missing evidence must remain unverified while useful independent work continues and existing results are delivered.
blockers: [{{blocker:{{key,reason:missing_secret|missing_access|approval_required|user_choice|external_blocker,needed,blocked_actions}},evidence_refs}}], only genuine human-dependent gaps. resolutions: [{{blocker_id,human_id,valid,approval_applicable,evidence_refs}}], using authentic addressed receipts. grants: [unprocessed authentic grant IDs].
reconciliation: {{fresh:true,approvals_applicable:true,evidence_refs:[retained names],operations:[{{id,outcome:succeeded|not_performed|failed|uncertain,evidence_refs}}]}}. Inspect uncertain external effects; no blind replay or assumed failure. Do not read secret/auth files.
Task and current contract/checkpoint JSON (delivered inline; no read-tool prerequisite for this content). The checkpoint is a Worker claim, not independent proof. Inspect other relevant material through the retained file paths as needed:
{json.dumps(dict(task=Path(self.c['task']).read_text(), contract=self.c['execution_contract'], checkpoint=checkpoint), ensure_ascii=False)}
For chat transport record the JSON assessment once with python3 {script} review-v2 --config {self.root / 'config.json'} --decision endorse --feedback '<finding>' --assessment '<JSON>'. Headless transport returns JSON only; do not execute that command.
'''
        try:
            self.queue_message(prompt, directory / 'queue-receipt.txt')
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            self.control_point()
            self.verification_failure('reviewer_unavailable', str(error), phase, checkpoint, snap, str(directory / 'request.json'))
            return
        deadline = time.monotonic() + self.verification_remaining()
        target = directory / 'review.json'
        while not target.exists():
            self.control_point()
            if time.monotonic() >= deadline:
                self.verification_failure('reviewer_unavailable', 'Independent review deadline reached; no blind redispatch', phase, checkpoint, snap, str(directory / 'request.json'))
                return
            time.sleep(0.05)
        self.control_point()
        try:
            review = read(target)
        except json.JSONDecodeError as error:
            raise VerificationTechnical('Malformed reviewer response: ' + str(error)) from None
        p.envelope(review, self.c['run_id'])
        p.require(review.get('review_id') == seq and review.get('request_sha256') == digest(directory / 'request.json'), 'Stale/wrong review identity/hash')
        with self.boundary() as current:
            request_unchanged(self.c, request, current)
            controller = p.Controller(self.c, current)
            p.text(review['feedback'])
            p.require(review['decision'] in {'endorse', 'halt', 'stop'}, 'Invalid review decision')
            if review['decision'] == 'endorse':
                try:
                    controller.apply(review_report(self.c, request, review.get('assessment')), review_evidence(request), str(target))
                except (ValueError, KeyError, TypeError, AttributeError) as error:
                    raise VerificationTechnical('Invalid independent assessment: ' + str(error)) from None
                current['last_feedback'] = review['feedback']
                current.pop('verification', None)
            else:
                controller.interrupted()
                current.update(execution=review['decision'], wait=None)
                controller.event('execution.' + review['decision'], reason=review['feedback'], review=str(target))
            for human in current['human'].values():
                human['processed'] = True
            for event in current['signals'].values():
                event['processed'] = True
        self.project()

    def queue_message(self, message, receipt, trigger_turn=None, notice_type=None, report_key=None):
        if receipt.parent.parent.name == 'reviews':
            self.control_point()
            with self.boundary() as state:
                request_unchanged(self.c, read(receipt.parent / 'request.json'), state)
            if self.c.get('review_execution') == 'headless':
                from headless_reviewer import run_review
                try:
                    return run_review(self, receipt.parent, message, receipt)
                except json.JSONDecodeError as error:
                    raise VerificationTechnical('Malformed reviewer response: ' + str(error)) from None
        return super().queue_message(message, receipt, trigger_turn, notice_type, report_key)

    def report_ui(self, ident):
        if self.c.get('review_execution') != 'headless':
            return
        receipt = self.root / 'notices' / (ident + '.receipt.json')
        if receipt.exists() or receipt.with_suffix('.attempt.json').exists():
            return
        s = self.store.read()
        directory = self.root / 'reviews' / f'v2-{s["review_seq"]:06}'
        measured = {}
        for name in ('request', 'review'):
            try:
                value = read(directory / (name + '.json'))
                measured[name] = value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                measured[name] = {}
        request = measured['request']
        criteria = '; '.join(f'{key}: {value}' for key, value in s['acceptance'].items())
        verification = s.get('verification') or {}
        if s['execution'] == 'finish':
            next_step = 'Nothing else will start: Core accepted the result.'
        elif s['execution'] == 'stop' and s.get('delivery'):
            next_step = 'Nothing else will start: result delivered, not verified (not acceptance); unverified criteria: ' + ', '.join(s['delivery']['unverified_criteria']) + '.'
        elif s['execution'] in p.TERMINAL:
            next_step = f'Nothing else will start: run {s["execution"]}; termination is not acceptance.'
        elif ident == 'review-error' or verification.get('status') == 'blocked':
            next_step = 'No new stage started: Core needs attention; see /ppp-status.'
        elif verification:
            next_step = 'Independent review is unavailable; available work is retained unverified.'
        elif s.get('wait'):
            next_step = f'No new stage started: waiting for {s["wait"]["source"]} ({s["wait"]["reference"]}).'
        else:
            next_step = 'Core selected the next action; no new stage has started yet.'
        lines = [f'{self.root.name} · check {s["review_seq"]} · cycle {s["cycle"]} · {"delivered, not verified" if s["execution"] == "stop" and s.get("delivery") else s["execution"]}',
                 f'Reviewer: {measured["review"].get("decision", "not received")}; ordinary tests: see retained Worker evidence.',
                 f'Criteria — {criteria}']
        if self.c['mode'] == 'goal' and s['sessions']:
            native = s['sessions'][-1]
            lines.append(f'Native Goal result — {native.get("goal_status", "unknown")}; not acceptance. Recorded tokens: {s["worker_tokens"]}; usage: {s.get("goal_usage_status", "unknown")}.')
            if native.get('goal_limit') == 'worker_time':
                lines.append(f'Worker time limit — cumulative {self.c["wall_seconds"]} seconds exhausted; no further Worker stage will start. Available results remain reviewable/deliverable.')
        checkpoint = request.get('checkpoint')
        if isinstance(checkpoint, dict) and checkpoint.get('summary'):
            lines.append('Worker checkpoint — ' + str(checkpoint['summary'])[:240])
        available_results = s.get('available_results', [])
        for item in available_results:
            lines.append(f'Available scoped files (unattributed candidates, retained unverified, not acceptance) — {json.dumps(item["available_files"])}; workspace: {item["workspace"]}; archive: {json.dumps(item["evidence_archive"])}')
            lines.append(f'Scoped discovery candidates (not authorship; may be unretained) — {json.dumps(item.get("discovery_candidates", [])[:20])}; full list: {self.root / "unverified-results" / f"cycle-{item['cycle']:06}" / "result.json"}')
            lines.append('Evidence limits — ' + ' '.join(item['limitations']))
        unverified_results = verification.get('unverified_results', [])
        lines.extend(f'Unverified Worker result — cycle {item["cycle"]}, {item["action_id"]}: {item["summary"][:200]} (evidence retained at {item.get("checkpoint") or item.get("workspace")})' for item in unverified_results)
        problem = verification.get('diagnosis') or self.state.get('reason')
        if problem:
            lines.append('Attention — ' + str(problem)[:400])
        if measured['review'].get('decision') in {'halt', 'stop'}:
            lines.append('Reviewer — ' + str(measured['review'].get('feedback', ''))[:400])
        lines.extend(['Next — ' + next_step, 'Details: /ppp-status'])
        context = dict(run_id=s['run_id'], cycle=s['cycle'], review_seq=s['review_seq'],
                       expected_status=self.state.get('status'), execution=s['execution'],
                       acceptance=s['acceptance'], actions={aid: action['status'] for aid, action in s['actions'].items()},
                       available_results=[{**item, 'discovery_candidates': item.get('discovery_candidates', [])[:20], 'discovery_candidates_count': len(item.get('discovery_candidates', []))} for item in available_results],
                       delivery=s.get('delivery'), wait=s.get('wait'), open_blockers=[item for item in s['blockers'].values() if item['status'] == 'open'],
                       verification={key: verification.get(key) for key in ('status', 'kind', 'diagnosis', 'blocked_action_ids', 'unverified_results')},
                       reviewer={key: measured['review'].get(key) for key in ('decision', 'feedback')},
                       review_applied=s.get('last_review') == str(directory / 'review.json'))
        self.ui_notice(ident, '\n'.join(lines) + '\nCore reporting context JSON:\n' + json.dumps(context), narrate=True)

    def ui_notice(self, ident, message, narrate=False):
        if self.c.get('review_execution') != 'headless':
            return
        try:
            self.notice(ident, message, narrate=narrate)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            self.event('report.delivery_failed', reason=str(error))

    def notice(self, ident, message, narrate=False):
        if self.c.get('review_execution') != 'headless':
            for item in self.store.read().get('available_results', []):
                message += f' Available scoped files (unattributed candidates, retained unverified, not acceptance): {json.dumps(item["available_files"])}. Workspace: {item["workspace"]}. Evidence archive: {json.dumps(item["evidence_archive"])}. Discovery candidates (unattributed; may be unretained): {json.dumps(item.get("discovery_candidates", [])[:20])}; full list: {self.root / "unverified-results" / f"cycle-{item['cycle']:06}" / "result.json"}. Limits: {" ".join(item["limitations"])}'
        directory = self.root / 'notices'
        directory.mkdir(exist_ok=True, mode=0o700)
        receipt = directory / (ident + '.receipt.json')
        if receipt.with_suffix('.attempt.json').exists() or receipt.exists():
            return
        if self.c['review_transport'] == 'pi':
            reporter = self.c.get('review_execution') == 'headless' and (narrate or ident.startswith('Q-'))
            if reporter:
                message = f'''PPP Chat A reporting request for {self.root.name}, event {ident}.
You are the human-facing reporter, NOT Reviewer, Worker or Core. Respond visibly in the user's language using STATUS, TL;DR, Summary, Report and Suggested action, followed by Full run status. Start with a standalone STATUS — <state and short explanation> line. Use these exact Markdown headings on separate lines: ### TL;DR, ### Summary, ### Report, ### Suggested action, ### Full run status. Leave a blank line before and after each heading; put content below it, never inline bold labels. Prefer short paragraphs and bullets; put any command in its own fenced text block. Keep Full run status compact, using only already available facts; do not read extra artifacts just to fill it or invent missing values. Do not merely acknowledge this message or list artifacts.
First read current {self.root / 'bridge-status.json'} ONLY. Use the compact Core reporting context below as facts, not as a request to repeat Reviewer work. For a healthy terminal result whose run_id, cycle and status match that context, write the report without reading any other files. For an addressed human question, use the grouped request below. Do not routinely read execution-state history, request.json, observations, source/tests, TASK/config or raw RPC/session logs. If status/cycle contradicts the context, read current {self.store.path} once; then read only the latest applied review or ONE measurement if a material fact is still missing. Full source/logs are for a concrete contradiction or failure diagnosis only, not a successful-report checklist. Do not seek optional counts or identities absent from the compact facts. Events may be old by delivery: distinguish this checkpoint from current state. If this conversation already contains a report of the same current terminal result, do not produce another full report. State what was checked, accepted versus unknown, why execution stopped or continued, and whether a next stage ACTUALLY started, is only planned, or nothing will start.
Explicitly say whether a human reply is needed, exactly what reply/choice is needed and why, or that no reply is needed. Internal verification retry/blockage is NOT a human-response request: check wait.source and requests. Missing review evidence is not a human approval gate. Deliver existing work with the exact unverified items; do not invent a verification-repair prerequisite.
Report only. Do not execute review-v2/decide, edit files, approve or submit human input, grant budget, resume/relaunch, repair the task, start workers or change Core state. Never report endorsement/exit 0 as acceptance. End the turn after the user-facing report; no polling or self-queued follow-ups. Current Chat A model is allowed; Reviewer remains in its separate session. This is a cooperative reporting instruction, not extra execution authority.
Recorded boundary snapshot (not necessarily current):
{message}'''
            self.queue_message(message, receipt, trigger_turn=reporter, notice_type='reporter' if reporter else 'terminal' if ident.startswith('terminal-') else 'report' if ident.startswith('review-') else 'waiting', report_key='state' if reporter and narrate and not ident.startswith('Q-') else None)
        elif ident.startswith('Q-') or ident in {'terminal-finish', 'terminal-stop', 'terminal-attention'}:
            # One logical escalation/final callback is permitted; recurring reminders never invoke a model.
            self.queue_message(message + ' Report the exact missing inputs or independently verified final outcome in this chat; do not restart, approve, rerun or expand scope. Human input uses the named interactive channel, never model flags.', receipt)
        else:
            p.durable(receipt, dict(channel='local-status', message=message, at=time.time()))

    def deliver(self):
        s = self.store.read()
        if s['execution'] in p.TERMINAL:
            return
        for event in s['history']:
            if event['type'] == 'wait.reminder':
                self.notice(event['id'], f'PPP {self.c["run_id"]} reminder: awaiting the recorded wake source; no worker or model polling. State: {self.store.path}. Use /ppp-respond; cancellation prevents continuation.')
        for rid, request in s['requests'].items():
            if not any(s['blockers'][bid]['status'] == 'open' for bid in request['blocker_ids']) and not (request['main_extension'] and p.Controller(self.c, s).remaining('main') <= 0):
                continue
            questions = '; '.join(b['blocker_id'] + ': ' + b['needed'] for b in request['questions'])
            if request['main_extension']:
                questions += ((f'; Distinct authorization needed: additional Goal windows (specify count using cycles; each adds one native Goal launch and {self.c["goal_tokens"]} tokens)'
                               if self.c.get('goal_tokens') is not None else '; Distinct authorization needed: additional Goal windows (specify count using cycles; each adds one native Goal launch)')
                              if self.c['mode'] == 'goal' else '; Distinct authorization needed: additional main cycles (specify count)')
            channel = '/ppp-respond' if p.human_channel(self.c) == 'pi' else f'python3 {Path(__file__).with_name("bridge.py")} human --config {self.root / "config.json"}'
            review_note = (' Existing results remain unverified; these inputs address task blockers, not the unavailable Reviewer.'
                           if (s.get('verification') or {}).get('status') == 'blocked' else '')
            self.notice(rid, f"PPP {self.c['run_id']} grouped request {rid}: {questions}. Configure secrets securely, never paste values. Use {channel} for addressed resolution or explicit grant. State: {self.store.path}.{review_note}")

    def recover_unstarted_goal_window(self, state):
        active = state.get('active')
        if not active or self.c['mode'] != 'goal':
            return False
        session = next((row for row in reversed(state['sessions']) if row['cycle'] == active['cycle'] and row['action_id'] == active['action_id']), None)
        if not session or session.get('status') != 'starting' or session.get('pid') is not None or session.get('goal_started') or session.get('goal_dispatch_attempted'):
            return False
        if any(op['cycle'] == active['cycle'] and op['owner'] == active['owner'] for op in state['operations'].values()):
            return False
        reservation = next(row for row in state['consumption'] if row['cycle'] == active['cycle'])
        reservation['not_started'] = True
        session['status'] = 'not_started_recovered'
        state['active'] = None
        p.Controller(self.c, state).event('goal.window_not_started_recovered', action_id=active['action_id'], cycle=active['cycle'], window_id=session['goal_window_id'])
        return True

    def recover_review(self):
        state = self.store.read()
        if (state.get('verification') or {}).get('status') == 'blocked':
            return
        settled = {event['review'] for event in state['history'] if event['type'] == 'review.applied'}
        settled.update(str(Path(event['verification']['directory']) / 'review.json') for event in state['history'] if event['type'].startswith('verification.') and 'verification' in event)
        if state.get('last_review'):
            settled.add(state['last_review'])
        for directory in sorted((self.root / 'reviews').glob('v2-*')):
            if (directory / 'queue-receipt.attempt.json').exists() and str(directory / 'review.json') not in settled:
                self.verification_failure('reviewer_unavailable', 'Crash left an attempted review without durable disposition; investigate delivery, no blind redispatch', 'recovery', None, None, directory=directory)
                return

    def run(self, resume=False, wake=False):
        if resume:
            p.require(self.store.read().get('lifecycle') == 'worker-reviewer', 'Evaluator-era runs cannot resume; preserved artifacts are read-only history')
        for folder in ('work', 'reviews', 'sessions', 'human-inbox'):
            (self.root / folder).mkdir(exist_ok=True, mode=0o700)
        with (self.root / 'bridge.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if wake:
                    return 0  # Existing controller will consume the durable ingress at its safe boundary.
                raise RuntimeError('Controller ownership already held; no duplicate continuation') from None
            if not resume:
                p.require(not (self.root / 'bridge-status.json').exists(), 'Run already started; use reconciled resume, never replay run')
                with self.store.transaction(create=p.initial(self.c, pins(self.c))):
                    pass
            else:
                s = self.store.read()
                p.require(s.get('lifecycle') == 'worker-reviewer', 'Evaluator-era runs cannot resume; preserved artifacts are read-only history')
                p.require(s['execution'] not in p.TERMINAL, 'Stopped/cancelled/halted/finished run cannot automatically resume')
            try:
                self.verify_pins()
                # An inherited worker lock survives a controller crash; never overlap an orphan Pi.
                self.acquire_worker()
                self.shutdown()
                if resume:
                    self.confirm_writer_available()
                    if self.c['mode'] == 'ralph':
                        freeze_error = self.ralph_children_error()
                        if freeze_error:
                            raise RuntimeError(freeze_error)
                        self.reconcile_ralph_usage()
                    if self.c['mode'] == 'goal':
                        self.reconcile_goal_usage()
                        self.migrate_goal_cycle_grants()
                with self.store.transaction() as state:
                    # Old native sessions retain their original work/ cwd on recovery.
                    state.setdefault('worker_cwd', str(Path(state['sessions'][-1].get('cwd', self.root / 'work')) if state['sessions'] else outputs.worker_directory(self.c)))
                    self.worker_cwd = Path(state['worker_cwd'])
                if not resume:
                    try:
                        p.durable(self.root / 'output-baseline.json', outputs.snapshot(self.c))
                    except (OSError, ValueError) as error:
                        with self.store.transaction() as state:
                            p.Controller(self.c, state).event('outputs.baseline_unavailable', reason=str(error))
                    try:
                        value = launch_diff.record(self.c)
                        if value is not None:
                            p.durable(self.root / launch_diff.RECORD, value)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                        with self.store.transaction() as state:
                            p.Controller(self.c, state).event('outputs.launch_git_unavailable', reason=str(error)[:500])
                self.prepare_browser_runtime()
                self.contract()
                self.control_point()
                if resume:
                    self.recover_review()
                if not resume:
                    with self.boundary() as state:
                        state['reconciled'] = True
                        for action in state['actions'].values():
                            action['eligible'] = True
                        p.Controller(self.c, state).event('execution.initial_authority')
                elif not (self.store.read().get('verification') or {}).get('status') == 'blocked':
                    with self.boundary() as state:
                        recovered = self.recover_unstarted_goal_window(state)
                        if not recovered and (state['active'] or any(op['outcome'] in {'started', 'uncertain'} for op in state['operations'].values())):
                            p.Controller(self.c, state).interrupted()
                    if not recovered:
                        with self.store.transaction() as state:
                            if state['sessions'] and state['sessions'][-1]['status'] in {'starting', 'running'}:
                                state['sessions'][-1].update(status='interrupted', ended_at=time.time())
                                if self.c['mode'] == 'ping-pong':
                                    row = state['sessions'][-1]
                                    row.update(session_usage(row.get('session_file'), row['id'], self.root / 'sessions'))
                    if not recovered and (not self.store.read()['reconciled'] or p.Controller(self.c, self.store.read()).unassessed()):
                        checkpoint, snap = None, None
                        try:
                            checkpoint, snap = validate_checkpoint(self.c, self.store.read()['cycle'])
                            p.envelope(checkpoint, self.c['run_id'])
                            p.require(type(checkpoint.get('cycle')) is int and checkpoint.get('action_id') == self.store.read()['sessions'][-1]['action_id'], 'Recovered checkpoint action/cycle changed')
                            if checkpoint.get('halt_reason'):
                                raise Terminated('Recovered Worker checkpoint reports global safety risk')
                            with self.store.transaction() as state:
                                state['sessions'][-1]['status'] = 'checkpoint'
                        except (OSError, ValueError, KeyError, TypeError, IndexError):
                            checkpoint, snap = None, None
                        self.review_result('recovery', checkpoint, snap)
                while True:
                    self.verify_pins()
                    self.ingress()
                    self.resource_events()
                    s = self.store.read()
                    verification_blocked = s.get('verification', {}).get('status') == 'blocked'
                    if s['execution'] not in p.TERMINAL and not verification_blocked and (any(not h['processed'] for h in s['human'].values()) or any(not event['processed'] for event in s['signals'].values())):
                        self.review_result('resolution' if any(not h['processed'] for h in s['human'].values()) else 'resource-signal')
                        continue
                    with self.boundary() as state:
                        e = p.Controller(self.c, state)
                        decision, aid = e.transition()
                    self.project()
                    if s.get('last_review'):
                        self.report_ui('terminal-' + decision if decision in p.TERMINAL else 'review-' + str(s['review_seq']))
                    if decision == 'verification_blocked':
                        self.deliver()
                        self.project('verification_blocked', reason=self.store.read()['verification']['diagnosis'])
                        if self.c.get('review_execution') == 'headless':
                            self.report_ui('verification-blocked-' + str(self.store.read()['review_seq']))
                        else:
                            self.notice('terminal-attention', f'PPP {self.c["run_id"]}: independent verification is blocked after available independent work. Existing results remain available; acceptance is unknown. Read {self.root / "bridge-status.json"}, {self.store.path}, unverified-results/ and retained review evidence. {REPORT_GUIDANCE} Do not restart or claim acceptance.')
                        return 1
                    if decision in p.TERMINAL:
                        if self.c.get('review_execution') == 'headless':
                            review_receipt = self.root / 'notices' / ('review-' + str(s['review_seq']) + '.receipt.json')
                            if not review_receipt.exists() and not review_receipt.with_suffix('.attempt.json').exists():
                                self.report_ui('terminal-' + decision)
                        else:
                            outcome = 'delivered, not verified' if self.store.read().get('delivery') else decision
                            self.notice('terminal-' + decision, f'PPP {self.c["run_id"]}: {outcome}; independent acceptance: {self.store.read()["acceptance"]}. Evidence: {self.store.path}. Never infer acceptance from lifecycle termination.')
                        return 0 if decision == 'finish' else 2
                    self.deliver()
                    if aid is not None:
                        repair_feedback = None
                        while True:
                            try:
                                checkpoint, snap, diagnosis = self.worker(aid, repair_feedback)
                            except WorkerBudgetExhausted as error:
                                with self.boundary() as state:
                                    p.Controller(self.c, state).abandon_worker_repair(str(error))
                                checkpoint, snap, diagnosis = None, None, None
                                break
                            if diagnosis is None:
                                break
                            repair_feedback = (f'Core rejected your checkpoint: {diagnosis}. Correct only checkpoint schema, exact evidence references and the run/action/cycle identity, which must equal cycle-context.json, using already-produced artifacts. Never repeat task work or external operations; preserve the reserved action and continue only within the cumulative cycle/wall budget.')
                        if self.store.read().get('verification', {}).get('status') == 'blocked':
                            if snap is None:
                                self.preserve_budget_result()
                            if checkpoint is not None and snap is not None:
                                self.preserve_unverified_worker(checkpoint, snap)
                            elif self.store.read()['sessions'][-1]['status'] == 'budget_limited':
                                self.preserve_unverified_budget_limited_worker(aid)
                            continue
                        self.review_result('checkpoint', checkpoint, snap)
                        continue
                    idle = self.store.read()
                    wait = idle.get('wait') or {}
                    if wait.get('source') != 'human-response' and idle['execution'] != 'paused_budget':
                        self.report_ui('review-' + str(idle['review_seq']))
                    self.ui_notice('review-idle-' + str(idle['review_seq']),
                                   f'{self.root.name} · {idle["execution"]}\nNo new stage started: waiting for {wait.get("source", "Core decision")} ({wait.get("reference", "see /ppp-status")}).')
                    with self.store.transaction() as state:
                        reminder = p.Controller(self.c, state).reminder()
                    if reminder:
                        self.notice(reminder, f'PPP {self.c["run_id"]} reminder: waiting for {self.store.read()["wait"]}; no worker/model polling, no cycles spent. Use /ppp-respond; cancellation prevents continuation.')
                    wait = self.store.read()['wait']
                    if wait and wait['source'] == 'bounded-recheck' and time.time() >= wait['at']:
                        with self.store.transaction() as state:
                            state['execution'] = 'replan'
                            state['wait'] = None
                        self.review_result('bounded-recheck')
                    else:
                        time.sleep(0.25)
            except Terminated:
                self.shutdown()
                self.preserve_budget_result()
                with self.store.transaction() as state:
                    p.Controller(self.c, state).interrupted()
                self.project()
                if self.c.get('review_execution') == 'headless':
                    self.report_ui('terminal-' + self.store.read()['execution'])
                return 2
            except Exception as error:
                if self.store.read()['execution'] in p.TERMINAL:
                    with self.store.transaction() as state:
                        p.Controller(self.c, state).event('report.delivery_failed', reason=str(error))
                    self.project()
                    self.state['delivery_error'] = str(error)
                    p.durable(self.root / 'bridge-status.json', self.state)
                    return 1
                self.shutdown()
                self.preserve_budget_result()
                with self.store.transaction() as state:
                    if state['execution'] != 'finish':
                        p.Controller(self.c, state).interrupted()
                    if state['execution'] not in p.TERMINAL and isinstance(error, (ValueError, KeyError, TypeError)):
                        state['execution'] = 'halt'
                        state['wait'] = None
                    p.Controller(self.c, state).event('attention.required', reason=str(error))
                self.project('attention_required', reason=str(error))
                if self.store.read()['execution'] != 'halt':
                    self.state['status'] = 'attention_required'
                p.durable(self.root / 'bridge-status.json', self.state)
                if self.c.get('review_execution') == 'headless':
                    self.report_ui('terminal-halt' if self.store.read()['execution'] == 'halt' else 'review-error')
                else:
                    self.notice('terminal-attention', f'PPP {self.c["run_id"]}: execution stopped after an internal failure: {error}. Existing files and measured results remain available; acceptance is unknown. Read {self.root / "bridge-status.json"}, {self.store.path}, the latest checkpoint, and retained review evidence. {REPORT_GUIDANCE} Do not restart or claim acceptance.')
                return 1
            finally:
                self.shutdown()


def dispatch(c, args):
    if args.command in {'run', 'resume', 'wake'}:
        return ActionBridge(c).run(resume=args.command != 'run', wake=args.command == 'wake')
    if args.command == 'review-v2':
        return record_review(c, args)
    if args.command == 'human':
        return console_human(c)
    if args.command == 'signal':
        store = p.Store(c['root'], c['run_id'])
        with store.transaction() as state:
            p.require(pins(c) == state['pins'], 'Governing contract changed')
            p.ident(args.event_id)
            p.text(args.wake_ref)
            p.require(state['execution'] not in p.TERMINAL and state['wait'] is not None and state['wait']['source'] == 'resource-signal' and state['wait']['reference'] == args.wake_ref, 'No matching arranged resource wake')
            p.require(args.event_id not in state['signals'], 'Resource signal already consumed')
            target = Path(c['root']) / 'resource-inbox' / (args.event_id + '.json')
            p.require(not target.exists(), 'Resource signal already recorded')
            p.durable(target, {**p.header(c['run_id']), 'id': args.event_id, 'reference': args.wake_ref})
        return ActionBridge(c).run(resume=True, wake=True)
    if args.command == 'operation':
        with ActionBridge(c).boundary(error=ValueError) as state:
            p.require(pins(c) == state['pins'], 'Governing contract changed')
            with (Path(c['root']) / 'writer.lock').open('a') as lease:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass  # The current worker/controller still holds its inherited execution lease.
                else:
                    raise ValueError('No live worker execution lease; stale owner token refused')
            key = p.Controller(c, state).operation(args.action_id, args.operation_id, args.owner)
        print(json.dumps({'reserved': key}))
        return 0
    raise ValueError('Legacy decisions/human-resolved flags do not apply to protocol 2')
