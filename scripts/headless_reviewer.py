"""One Core-owned read-only Pi RPC review; no independent orchestration loop."""
import json
from pathlib import Path
import subprocess
import threading
import time
from types import SimpleNamespace
import uuid

from bridge import Bridge, digest, evidence_path
import action_protocol as p


class ReviewerRPC(Bridge):
    def __init__(self, controller, directory, session_id):
        super().__init__(controller.c)
        self.controller = controller
        self.directory = directory
        self.session_id = session_id
        self.read_calls = {}
        self.read_paths = set()
        self.read_errors = {}
        self.deadline = time.monotonic() + min(self.c['review_seconds'], controller.verification_remaining())

    def remaining(self):
        return self.deadline - time.monotonic()

    def next(self, seconds=0.25):
        try:
            return super().next(seconds)
        except TimeoutError:
            raise TimeoutError('Independent Reviewer deadline or verification budget reached') from None
        except RuntimeError as error:
            if str(error).startswith('Pi RPC command failed:'):
                raise RuntimeError(f'Independent Reviewer RPC command failed; private diagnostics: {self.directory / "reviewer.json"}') from None
            raise

    def check_control(self):
        self.controller.control_point()

    def process_returncode(self):
        from action_bridge import process_result
        return process_result(self.proc)

    def response(self, ident):
        pending = []
        while True:
            record = self.next(0.05)
            if record.get('type') == 'reviewer_error':
                raise RuntimeError(record['error'])
            if record.get('type') == 'response' and record.get('id') == ident:
                for event in pending:
                    self.deferred.put(event)
                return record.get('data', {})
            if record:
                pending.append(record)

    def start(self, lease, stderr):
        sessions = self.directory / 'reviewer-sessions'
        sessions.mkdir(mode=0o700)
        argv = ['pi', '--mode', 'rpc', '--no-extensions', '--no-mcp', '--no-skills',
                '--no-prompt-templates', '--no-context-files', '--tools', 'read',
                '--provider', self.c['review_provider'], '--model', self.c['review_model'],
                '--thinking', self.c.get('review_thinking', 'low'),
                '--session-dir', str(sessions), '--session-id', self.session_id]
        for extension in self.c.get('reviewer_extensions', []):
            argv += ['-e', extension]
        self.proc = subprocess.Popen(argv, cwd=self.root / 'work', stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=stderr, start_new_session=True,
                                     pass_fds=(lease.fileno(),))

        def reader():
            try:
                total = 0
                while line := self.proc.stdout.readline(8 * 1024 * 1024 + 1):
                    total += len(line)
                    if len(line) > 8 * 1024 * 1024 or total > 64 * 1024 * 1024:
                        raise ValueError('Reviewer RPC output limit exceeded')
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError('Reviewer RPC record must be an object')
                    self.records.put(record)
            except (ValueError, OSError) as error:
                self.records.put(dict(type='reviewer_error', error=str(error)))

        threading.Thread(target=reader, daemon=True).start()
        state = self.response(self.send('get_state'))
        model = state.get('model') or {}
        p.require(state.get('sessionId') == self.session_id, 'Reviewer session identity mismatch')
        p.require(model.get('provider') == self.c['review_provider'] and model.get('id') == self.c['review_model'],
                  'Reviewer actual provider/model mismatch')
        p.require(self.session_id != self.c.get('pi_session_id'), 'Reviewer must not use Chat A session')
        return state

    def read_path(self, value):
        path = Path(value.removeprefix('@')).expanduser()
        return str((path if path.is_absolute() else self.root / 'work' / path).resolve())

    def observe_read(self, record):
        if record.get('toolName') != 'read':
            return
        ident = record.get('toolCallId')
        if record.get('type') == 'tool_execution_start':
            value = (record.get('args') or {}).get('path')
            if ident and isinstance(value, str):
                self.read_calls[ident] = self.read_path(value)
        elif record.get('type') == 'tool_execution_end':
            path = self.read_calls.pop(ident, None)
            if path is None:
                return
            result = record.get('result') or {}
            if record.get('isError') is False and not result.get('isError') and result.get('content'):
                self.read_paths.add(path)
            else:
                self.read_errors[path] = str(result.get('content', 'Read did not succeed'))[:500]

    def read_report(self, required, optional=()):
        paths = {self.read_path(value) for value in required}
        extra = {self.read_path(value) for value in optional} - paths
        # Optional material (launch diff) is audited when actually read, never reported missing.
        return dict(required=sorted(paths), succeeded=sorted((paths | extra) & self.read_paths),
                    missing=sorted(paths - self.read_paths), optional=sorted(extra), errors=self.read_errors)

    def review(self, message, attempt=1):
        accepted = self.response(self.send('prompt', message=message))
        p.require(accepted.get('disposition') == 'started', 'Reviewer prompt did not start a fresh review')
        last_stop_reason = None
        while True:
            record = self.next(0.05)
            if record.get('type') == 'reviewer_error':
                raise RuntimeError(record['error'])
            self.observe_read(record)
            if record.get('type') == 'message_end' and (record.get('message') or {}).get('role') == 'assistant':
                last_stop_reason = record['message'].get('stopReason')
            if record.get('type') == 'agent_settled':
                p.require(not record.get('aborted'), 'Reviewer aborted without a valid result')
                # Pi may recover errors through native retry/compaction before settlement.
                if last_stop_reason in {'error', 'aborted'}:
                    raise RuntimeError(f'Independent Reviewer assistant ended with stopReason={last_stop_reason}; private diagnostics: {self.directory / "reviewer.json"}')
                break
        text = self.response(self.send('get_last_assistant_text')).get('text')
        if not isinstance(text, str):
            return None
        if not text or len(text.encode()) > 64 * 1024:
            return {'invalid_response': 'Reviewer response is empty or exceeds 64 KiB'}
        with (self.directory / f'reviewer-attempt-{attempt:03}.stdout').open('w', encoding='utf-8') as output:
            output.write(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def run_review(controller, directory, message, receipt):
    from action_bridge import VerificationTechnical, review_evidence, review_report, record_review, stop_owned
    import fcntl

    marker = receipt.with_suffix('.attempt.json')
    p.require(not marker.exists(), 'Review already attempted; no blind redispatch')
    session_id = uuid.uuid4().hex
    rpc = ReviewerRPC(controller, directory, session_id)
    metadata = dict(session_id=session_id, provider=controller.c['review_provider'],
                    model=controller.c['review_model'], status='starting', pid=None, session_file=None)
    with (controller.root / 'writer.lock').open('a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        controller.control_point()
        p.durable(marker, dict(attempted_at=time.time(), transport='pi-headless', session_id=session_id))
        p.durable(directory / 'reviewer.json', metadata)
        try:
            with (directory / 'reviewer.stderr').open('wb') as stderr:
                state = rpc.start(lease, stderr)
                metadata.update(pid=rpc.proc.pid, session_file=state.get('sessionFile'), status='running')
                p.durable(directory / 'reviewer.json', metadata)
                controller.ui_notice('review-reviewer-' + directory.name,
                                     f'{controller.root.name} · check {controller.store.read()["review_seq"]}\nHeadless Reviewer started: reviewing the findings. Core will decide whether work can continue.')
                request = json.loads((directory / 'request.json').read_text())
                # TASK is delivered inline in the prompt, so it is not a read-tool requirement.
                required = [str(directory / 'request.json'), str(directory / 'context.json')]
                instructions = ('\nTask and contract/checkpoint are inline. Inspect the context ledger and other material evidence as needed for remaining judgment questions, not to produce read events. '
                                'Use existing ordinary test results without re-proving deterministic checks. '
                                'Missing evidence remains unknown, never a product correction by itself. '
                                'The launch diff, when present, is a Core fact about user launch lines, not a verdict.\n')
                expected = dict(run_id=request['run_id'], cycle=request['cycle'], review_id=request['review_id'],
                                state_sha256=request['state_sha256'], request_sha256=digest(directory / 'request.json'))
                followup = message + instructions
                attempt = 0
                while True:
                    attempt += 1
                    result = rpc.review(followup, attempt)
                    controller.control_point()
                    try:
                        allowed = {'decision', 'feedback', 'assessment'} | set(expected)
                        p.require(isinstance(result, dict) and {'decision', 'feedback'} <= set(result) and set(result) <= allowed,
                                  'Invalid headless review fields')
                        p.require(result['decision'] in {'endorse', 'halt', 'stop'}, 'Invalid headless review decision')
                        p.text(result['feedback'])
                        if result['decision'] == 'endorse':
                            from copy import deepcopy
                            candidate = deepcopy(controller.store.read())
                            p.Controller(controller.c, candidate).apply(
                                review_report(controller.c, request, result.get('assessment')),
                                review_evidence(request), str(directory / 'review.json'))
                        if any(key in result for key in expected):
                            p.require(set(expected) <= set(result) and all(type(result[key]) is type(value) and result[key] == value for key, value in expected.items()),
                                      'Headless review identity/hash mismatch')
                    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
                        if rpc.remaining() <= 0:
                            raise VerificationTechnical(f'Reviewer response remained invalid when review budget expired: {error}') from None
                        followup = ('Your prior response was not accepted: ' + str(error) +
                                    '. Correct only the review response using the original request and already read evidence. '
                                    'Return decision and feedback, plus assessment for endorse; do not copy service identity fields or repeat tests. Preserve concrete negative findings.')
                        continue
                    optional = [request['launch_diff']['path']] if (request.get('launch_diff') or {}).get('path') else []
                    reads = {**rpc.read_report(required, optional), 'inline': [rpc.read_path(str(controller.c['task']))]}
                    final_text = (directory / f'reviewer-attempt-{attempt:03}.stdout').read_text()
                    (directory / 'reviewer.stdout').write_text(final_text)
                    p.durable(directory / f'reviewer-result-{attempt:03}.json', result)
                    p.durable(directory / 'reviewer-result.json', result)
                    p.durable(directory / 'reviewer-reads.json', reads)
                    if result['decision'] == 'endorse' and result['assessment']['safe']:
                        assessment = result['assessment']
                        verified = [value for value in assessment['criteria'].values() if value['status'] == 'pass']
                        verified.extend(value for value in assessment['actions'] if value['status'] == 'verified')
                        claimed = {ref for value in verified for ref in value['evidence_refs']}
                        unavailable = []
                        for ref in sorted(claimed):
                            if ref not in request['evidence_sha256']:
                                paths = {rpc.read_path(request['launch_diff']['path'])}
                            else:
                                paths = {rpc.read_path(request['evidence_archive'][ref])}
                                paths.update(str(evidence_path(controller.c, name)) for name, sha in request['evidence_sha256'].items()
                                             if sha == request['evidence_sha256'][ref])
                            if paths.intersection(rpc.read_errors) and not paths.intersection(rpc.read_paths):
                                unavailable.append(ref)
                        if unavailable:
                            raise VerificationTechnical('Reviewer could not access cited material for verified claims: ' + json.dumps(unavailable))
                    record_review(controller.c, SimpleNamespace(review_id=request['review_id'], decision=result['decision'],
                                  feedback=result['feedback'], assessment=json.dumps(result['assessment']) if 'assessment' in result else None))
                    metadata['status'] = 'submitted'
                    break
                p.durable(receipt, dict(transport='pi-headless', status='submitted', session_id=session_id))
        finally:
            try:
                if rpc.proc is not None:
                    stop_owned(rpc.proc)
                    rpc.proc.stdin.close()
                    rpc.proc.stdout.close()
            finally:
                from action_bridge import session_usage
                metadata.update(ended_at=time.time(), status=metadata['status'] if metadata['status'] == 'submitted' else 'interrupted')
                if metadata.get('session_file'):
                    metadata.update(session_usage(metadata['session_file'], session_id, directory / 'reviewer-sessions'))
                p.durable(directory / 'reviewer.json', metadata)
