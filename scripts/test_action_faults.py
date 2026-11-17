#!/usr/bin/env python3
"""Deterministic F1–F4 fault boundaries. Synthetic local processes only."""
from contextlib import contextmanager
from copy import deepcopy
import errno
import gc
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import warnings
from unittest.mock import Mock, patch

import action_bridge as ab
import action_protocol as p
import bridge as b
import test_action_bridge as fixtures
from test_action_protocol import assess_cycle, attempt, config, report


class FaultTests(unittest.TestCase):
    fixture = fixtures.Bridge2Tests.fixture
    launch = fixtures.Bridge2Tests.launch
    await_state = fixtures.Bridge2Tests.await_state
    human = fixtures.Bridge2Tests.human
    kill_group = staticmethod(fixtures.Bridge2Tests.kill_group)

    def test_native_ralph_guard_cleans_detached_shells_on_host_crash_timeout_and_stop(self):
        for cause in ('host-crash', 'timeout', 'stop', 'native-kill', 'normal-exit'):
            with self.subTest(cause=cause), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                link = directory / 'Test-guard-link.mjs'
                link.symlink_to(Path(__file__).with_name('ralph-parent-guard.mjs'))
                guard = link.as_uri()
                package = Path(os.environ.get('PI_PACKAGE_JSON', Path.home() / '.pi/agent/install/releases/1.5.0/node_modules/@earendil-works/pi-coding-agent/package.json'))
                if not package.is_file():
                    self.skipTest('Installed Pi package unavailable for non-live bundle probe')
                cli = package.parent / b.read(package)['bin']['pi']
                shell = directory / 'Test-shell.mjs'
                heartbeat, shell_heartbeat = directory / 'Test-heartbeat', directory / 'Test-shell-heartbeat'
                shell.write_text('import fs from "node:fs"; fs.writeFileSync(' + repr(str(directory / 'Test-shell-pid')) + ',String(process.pid)); setInterval(()=>fs.writeFileSync(' + repr(str(shell_heartbeat)) + ',String(Date.now())),20);')
                command = "node -e 'process.stdout.write(\"Test nested Node command\")' > Test-nested; node " + str(shell)
                args = [str(cli), '--mode', 'rpc', '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-session']
                host_script = ('import fs from "node:fs"; import {spawn} from "node:child_process"; '
                               'const child=spawn(process.execPath,' + p.canonical(args) + ',{detached:true,stdio:["pipe","pipe","inherit"],env:{...process.env,RALPH_RUNNER_LOOP_TOKEN:"Test-loop"}}); '
                               'child.stdout.on("data",data=>fs.appendFileSync("Test-rpc-output",data)); '
                               'child.stdin.write(' + repr(p.canonical(dict(id='Test-bash', type='bash', command=command)) + '\n') + '); '
                               'let stopped=false; setInterval(()=>{if(!stopped&&fs.existsSync("Test-native-kill")){stopped=true;process.kill(-child.pid,"SIGKILL")} if(!stopped&&fs.existsSync("Test-normal-exit")){stopped=true;child.stdin.end()}},20); '
                               'setInterval(()=>fs.writeFileSync(' + repr(str(heartbeat)) + ',String(Date.now())),20);')
                env = {'PATH': os.environ['PATH'], 'HOME': str(directory), 'PI_CODING_AGENT_DIR': str(directory / 'Test-agent'), 'PI_OFFLINE': '1',
                       'PPP_RALPH_GUARDS': str(directory), 'PPP_RALPH_GUARD_IMPORT': '--import=' + guard,
                       'PPP_RALPH_ITERATION_SECONDS': '4' if cause == 'timeout' else '0', 'RALPH_RUNNER_LOOP_TOKEN': '', 'NODE_OPTIONS': '--import=' + guard}
                diagnostic = (directory / 'Test-stderr').open('wb')
                host = subprocess.Popen(['node', '--input-type=module', '-e', host_script], env=env, cwd=directory, start_new_session=True, stdout=subprocess.DEVNULL, stderr=diagnostic)
                try:
                    deadline = time.monotonic() + 12
                    while not (heartbeat.exists() and shell_heartbeat.exists()) and time.monotonic() < deadline:
                        self.assertIsNone(host.poll(), 'Test guard host exited before native child startup')
                        time.sleep(0.02)
                    self.assertTrue(heartbeat.exists() and shell_heartbeat.exists(), (directory / 'Test-rpc-output').read_text() if (directory / 'Test-rpc-output').exists() else 'Pi bundle did not start bash')
                    self.assertEqual((directory / 'Test-nested').read_text(), 'Test nested Node command')
                    markers = list(directory.glob('child-*.json'))
                    self.assertEqual(len(markers), 1)
                    marker = b.read(markers[0])
                    self.assertEqual((marker['host'], marker['loop_token']), (host.pid, 'Test-loop'))
                    if cause == 'host-crash':
                        os.kill(host.pid, 9)
                        host.wait(timeout=5)
                    elif cause == 'stop':
                        (directory / 'stop.flag').write_text('Test-loop\n')
                    elif cause in {'native-kill', 'normal-exit'}:
                        (directory / ('Test-' + cause)).touch()
                    self.assertTrue(marker['detached_pids'], 'Real bundled Pi bash must cross the tracked spawn boundary')
                    deadline = time.monotonic() + 6
                    while not b.read(markers[0]).get('cleaned') and time.monotonic() < deadline:
                        time.sleep(0.02)
                    if not b.read(markers[0]).get('cleaned'):
                        diagnostics = subprocess.run(['ps', '-axo', 'pid=,ppid=,pgid=,stat=,command='], capture_output=True, text=True).stdout
                        self.fail('Guard cleanup missing: ' + p.canonical(b.read(markers[0])) + '\n' + (directory / 'Test-stderr').read_text() + '\n' + '\n'.join(line for line in diagnostics.splitlines() if line.split()[0] == str(marker['pid'])))
                    time.sleep(0.1)
                    stopped = shell_heartbeat.read_text()
                    time.sleep(0.2)
                    self.assertEqual(shell_heartbeat.read_text(), stopped)
                    observed = subprocess.run(['ps', '-axo', 'pgid=,stat='], capture_output=True, text=True, check=True)
                    live_groups = {int(pgid) for line in observed.stdout.splitlines() for pgid, stat in [line.split()] if not stat.startswith('Z')}
                    self.assertTrue(set(marker['detached_pids']).isdisjoint(live_groups), 'No live members of the actual bundled shell groups may remain')
                finally:
                    if host.poll() is None:
                        os.kill(host.pid, 9)
                        host.wait(timeout=5)
                    diagnostic.close()
                    pids = [pid for marker in directory.glob('child-*.json') for pid in [b.read(marker)['pid'], *b.read(marker).get('detached_pids', [])]]
                    if (directory / 'Test-shell-pid').exists():
                        pids.append(int((directory / 'Test-shell-pid').read_text()))
                    for pid in pids:
                        try:
                            os.killpg(pid, 9)
                        except ProcessLookupError:
                            pass

    def test_native_ralph_cleaned_marker_does_not_hide_live_detached_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)
            guards = root / 'Test-guards'
            guards.mkdir()
            shell = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
            dead = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
            dead.wait(timeout=5)
            try:
                with core.store.transaction() as state:
                    state['sessions'].append(dict(pid=os.getpid(), ralph_guards=str(guards), ralph_loop_token='Test-loop'))
                p.durable(guards / 'child-Test.json', dict(pid=dead.pid, host=os.getpid(), loop_token='Test-loop', cleaned=True, detached_pids=[shell.pid]))
                self.assertIn('shells=[' + str(shell.pid), core.ralph_children_error())
                self.kill_group(shell.pid)
                shell.wait(timeout=5)
                self.assertIsNone(core.ralph_children_error())
                marker = b.read(guards / 'child-Test.json')
                marker.pop('detached_pids')
                p.durable(guards / 'child-Test.json', marker)
                self.assertIn('ownership is unknown', core.ralph_children_error())
            finally:
                self.kill_group(shell.pid)
                shell.wait(timeout=5)

    def local(self, root, effect=False):
        self.fixture(root, effect=effect)
        for folder in ('work', 'reviews', 'human-inbox', 'sessions'):
            (root / folder).mkdir(exist_ok=True, mode=0o700)
        c = b.load_config(root / 'config.json')
        core = ab.ActionBridge(c)
        with core.store.transaction(create=p.initial(c, ab.pins(c))):
            pass
        (root / 'work/test-proof').write_text('Test independently inspected local fixture')
        (root / 'work/cycle-context.json').write_text('{}')
        p.durable(root / 'work/checkpoint.json', dict(run_id=c['run_id'],cycle=0,status='ready',summary='Test local fixture',evidence=['test-proof']))
        return core

    def accept_fixture(self, core):
        value = report(core.c, core.store.read())
        for result in value['actions']:
            result['status'] = 'verified'
        for result in value['criteria'].values():
            result.update(status='pass', evidence_refs=['test-proof'])
        return p.canonical(value)

    def test_eperm_exit_visibility_window_waits_without_reaping_identity(self):
        for signal_failure in ('term', 'kill'):
            with self.subTest(signal_failure=signal_failure):
                proc = SimpleNamespace(pid=12345, wait=Mock())
                denied = PermissionError(errno.EPERM, 'Test exiting group visibility window')
                signals = [denied] if signal_failure == 'term' else [None, denied]
                with patch.object(ab.os, 'killpg', side_effect=signals), patch.object(ab, 'process_result', side_effect=[None, 0]), patch.object(ab.time, 'monotonic', side_effect=[0, 0.01]), patch.object(ab.time, 'sleep'):
                    ab.stop_owned(proc)
                proc.wait.assert_called_once_with()

    def test_eperm_live_leader_is_not_silently_accepted(self):
        proc = SimpleNamespace(pid=12345, wait=Mock())
        with patch.object(ab.os, 'killpg', side_effect=PermissionError(errno.EPERM, 'Test live permission denial')), patch.object(ab, 'process_result', return_value=None), patch.object(ab.time, 'monotonic', side_effect=[0, 0.1]), patch.object(ab.time, 'sleep'):
            with self.assertRaises(PermissionError):
                ab.stop_owned(proc)
        proc.wait.assert_not_called()


    def test_worker_stdout_is_closed_after_reaping_and_reader_stops(self):
        script = '''import json, os, subprocess, sys, time
holder = None
if sys.argv[1] == 'detached':
    holder = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
cmd = json.loads(sys.stdin.readline())
reply = json.dumps(dict(type='response', id=cmd['id'], success=True, data=dict(sessionFile=str(holder.pid) if holder else 'Test-session'))) + '\\n'
os.write(1, reply[:9].encode())
os.write(1, reply[9:].encode())
os.write(1, b'Test non-json\\n\\xff\\n')
if sys.argv[1] == 'eof-tail':
    os.write(1, b'{"type":"Test-tail"}')
if sys.argv[1] == 'large':
    print(json.dumps(dict(type='Test-large', text='Test \\u2603' * 30000), ensure_ascii=False), flush=True)
if sys.argv[1] not in ('exited', 'eof-tail', 'large'):
    for line in sys.stdin:
        pass
'''
        popen = subprocess.Popen
        for mode in ('running', 'exited', 'reaped', 'detached', 'read-error', 'eof-tail', 'large'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', ResourceWarning)
                root = Path(tmp)
                core = self.local(root)
                def spawn(*args, **kwargs):
                    return popen([sys.executable, '-c', script, mode], **kwargs)
                with patch.object(b.subprocess, 'Popen', side_effect=spawn):
                    core.spawn()
                proc, reader = core.proc, core.reader_thread
                holder = int(core.state['pi_session']) if mode == 'detached' else None
                try:
                    if mode == 'reaped':
                        proc.stdin.close()
                        proc.wait(timeout=2)
                    if mode == 'exited':
                        deadline = time.monotonic() + 2
                        while ab.process_result(proc) is None and time.monotonic() < deadline:
                            time.sleep(0.01)
                        self.assertIsNotNone(ab.process_result(proc))
                    if mode in ('eof-tail', 'large'):
                        reader.join(timeout=2)
                        self.assertFalse(reader.is_alive())
                        expected = {'type': 'Test-tail'} if mode == 'eof-tail' else {'type': 'Test-large', 'text': 'Test \u2603' * 30000}
                        self.assertEqual(core.records.get_nowait(), expected)
                        self.assertEqual((root / 'bridge-events.jsonl').read_text().count('protocol.non_json_line'), 2)
                    if mode == 'read-error':
                        with patch.object(b.select, 'select', side_effect=OSError('Test reader failure')):
                            reader.join(timeout=2)
                        self.assertFalse(reader.is_alive())
                        self.assertIn('protocol.stdout_read_error', (root / 'bridge-events.jsonl').read_text())
                    started = time.monotonic()
                    core.shutdown()
                    self.assertLess(time.monotonic() - started, 2, 'Detached stdout holder must not block cleanup')
                    self.assertIsNotNone(proc.returncode)
                    self.assertTrue(proc.stdout.closed)
                    self.assertTrue(proc.stdin.closed)
                    self.assertFalse(reader.is_alive())
                    self.assertIsNone(core.proc)
                    core.shutdown()
                finally:
                    if holder is not None:
                        os.kill(holder, 9)
                    if core.proc is not None:
                        core.shutdown()
                del proc, reader, core
                gc.collect()
                self.assertFalse([str(item.message) for item in caught if issubclass(item.category, ResourceWarning)])

    def test_evidence_symlink_cannot_escape_authorized_work_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp)
            root = lab / 'Test-run'
            root.mkdir(mode=0o700)
            core = self.local(root)
            outside = lab / 'Test-other-target'
            outside.write_text('Test shared host resource; not a worker output')
            (root / 'work/Test-escape').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'Evidence escapes'):
                b.inside(root / 'work', 'Test-escape')
            with self.assertRaisesRegex(ValueError, 'Evidence escapes'):
                b.inside(root / 'work', '../../Test-other-target')
            self.assertEqual(core.store.read()['cycle'], 0)
            # The same UID can still write outside work: evidence validation is not a sandbox.
            outside.write_text('Test host write remains possible without OS isolation')
            self.assertTrue(outside.exists())

    def test_moved_run_with_identical_bytes_refuses_realpath_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Test-original'
            root.mkdir(mode=0o700)
            core = self.local(root)
            before = core.store.read()
            moved = root.with_name('Test-moved')
            root.rename(moved)
            restored = ab.ActionBridge(b.load_config(moved / 'config.json'))
            with self.assertRaisesRegex(ab.Terminated, 'Governing contract changed'):
                restored.verify_pins()
            state = restored.store.read()
            self.assertEqual(state['run_id'], before['run_id'])
            self.assertEqual(state['execution'], 'halt')
            self.assertEqual(state['consumption'][:len(before['consumption'])], before['consumption'])
            self.assertEqual(state['pins'], before['pins'])

    def test_disposable_worktrees_isolate_outputs_not_git_or_host_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp)
            repo = lab / 'Test-clone'
            source = Path(__file__).resolve().parent.parent

            git_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
            git_env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)

            def git(*args):
                return subprocess.check_output(['git', '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.fsmonitor=false', *map(str, args)], env=git_env, stderr=subprocess.STDOUT, text=True).strip()

            git('clone', '--quiet', '--local', '--no-hardlinks', '--no-checkout', source, repo)
            git('-C', repo, 'remote', 'remove', 'origin')
            workers = [lab / 'Test-worktree-a', lab / 'Test-worktree-b']
            commit = git('-C', repo, 'rev-parse', 'HEAD')
            for worker in workers:
                git('-C', repo, 'worktree', 'add', '--quiet', '--detach', worker, commit)
                self.assertEqual(git('-C', worker, 'rev-parse', 'HEAD'), commit)
            relative = Path('.pi-ping-pong/runs/Test-case/work/Test-output')
            output = workers[0] / relative
            output.parent.mkdir(parents=True)
            output.write_text('Test worktree-local output')
            self.assertFalse((workers[1] / relative).exists())
            common = [git('-C', worker, 'rev-parse', '--path-format=absolute', '--git-common-dir') for worker in workers]
            self.assertEqual(common[0], common[1])
            shared = lab / 'Test-shared-host-file'
            shared.write_text('Test not isolated by Git worktree')
            self.assertEqual(shared.read_text(), 'Test not isolated by Git worktree')
            self.assertEqual(git('-C', repo, 'remote'), '')
            self.assertEqual(git('-C', repo, 'rev-parse', 'HEAD'), commit)

    def test_cancel_halt_receipts_at_locked_apply_boundary_win(self):
        for decision in ('endorse', 'stop'):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                core = self.local(root)
                armed = False
                original = core.store.transaction

                @contextmanager
                def raced(*args, **kwargs):
                    nonlocal armed
                    with original(*args, **kwargs) as state:
                        if armed:
                            armed = False
                            self.human(root, core.c, 'cancel')
                            self.human(root, core.c, 'halt')
                        yield state

                def reviewer(message, receipt):
                    req = b.read(receipt.parent / 'request.json')
                    ab.record_review(core.c, SimpleNamespace(review_id=req['review_id'], decision=decision, feedback='Test independently rejected observation', assessment=self.accept_fixture(core) if decision == 'endorse' else None))
                    nonlocal armed
                    armed = True

                with patch.object(core, 'queue_message', side_effect=reviewer), patch.object(core.store, 'transaction', side_effect=raced):
                    with self.assertRaises(ab.Terminated):
                        core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
                state = core.store.read()
                self.assertEqual(state['execution'], 'halt')
                self.assertIsNone(state.get('last_review'))
                self.assertNotIn('verification', state)
                self.assertNotEqual(set(state['acceptance'].values()), {'pass'})
                self.assertEqual(state['cycle'], 0)

    def test_cancel_halt_finish_race_at_transition_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            original = core.store.transaction
            armed = False

            def verified(*args):
                nonlocal armed
                with original() as state:
                    state['reconciled'] = True
                    state['acceptance'] = {cid: 'pass' for cid in state['acceptance']}
                    state['last_review'] = 'Test independent fixture review'
                    for action in state['actions'].values():
                        action['status'] = 'verified'
                armed = True

            @contextmanager
            def raced(*args, **kwargs):
                nonlocal armed
                with original(*args, **kwargs) as state:
                    if armed:
                        armed = False
                        self.human(root, core.c, 'cancel')
                        self.human(root, core.c, 'halt')
                    yield state

            with patch.dict(os.environ, env), patch.object(core, 'review_result', side_effect=verified), patch.object(core, 'notice'), patch.object(core.store, 'transaction', side_effect=raced):
                self.assertEqual(core.run(), 2)
            state = core.store.read()
            self.assertEqual(state['execution'], 'halt')
            self.assertFalse(any(x['type'] == 'execution.finish' for x in state['history']))
            self.assertEqual(state['cycle'], 1)

    def test_crash_after_review_dispatch_never_blindly_redispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c['review_transport'] = 'pi'
            p.durable(root / 'config.json', c)
            proc = self.launch(root, env)
            before = self.await_state(root, lambda s: (root / 'reviews/v2-000001/queue-receipt.attempt.json').exists(), proc)
            proc.kill()
            proc.wait(timeout=5)
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=8), 1)
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['review_seq'], before['review_seq'])
            self.assertEqual(state['verification']['kind'], 'reviewer_unavailable')
            self.assertEqual(state['verification']['status'], 'blocked')
            self.assertEqual(len(list((root / 'reviews').glob('*/queue-receipt.attempt.json'))), 1)
            self.assertEqual(state['consumption'][:len(before['consumption'])], before['consumption'])

    def test_orphan_headless_reviewer_lease_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_HOLD'] = '1'
            metadata = root / 'reviews/v2-000001/reviewer.json'
            proc = self.launch(root, env)
            self.await_state(root, lambda s: metadata.exists() and metadata.with_name('Test-reviewer-prompt-started').exists() and b.read(metadata)['status'] == 'running', proc)
            pid = b.read(metadata)['pid']
            self.addCleanup(lambda: self.kill_group(pid))
            proc.kill()
            proc.wait(timeout=5)
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=3), 1)
            self.assertIn('ownership still held', b.read(root / 'bridge-status.json')['reason'])
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['cycle'], 1)
            self.assertEqual(state['review_seq'], 1)
            self.assertEqual(len(list((root / 'reviews').glob('*/queue-receipt.attempt.json'))), 1)
            self.assertFalse(metadata.with_name('review.json').exists())


    def test_cancel_worker_cleans_term_ignoring_child_even_after_leader_exit(self):
        self.worker_child_cleanup(False)

    def test_unexpected_worker_exit_retains_group_identity_for_child_cleanup(self):
        self.worker_child_cleanup(True)

    def test_goal_query_exit_retains_group_identity_for_child_cleanup(self):
        self.worker_child_cleanup(True, goal_query=True)

    def test_cancel_during_goal_state_query_is_not_delayed_or_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal')
            worker = root / 'bin/pi'
            text = worker.read_text()
            # Replace the exact accepted-tool line; settlement now requires native get_entries.
            text = '\n'.join('  pass' if "emit(dict(type='tool_execution_end',toolName='goal_wait'" in line else line for line in text.splitlines()) + '\n'
            text = text.replace(" if cmd['type'] == 'get_entries':\n  goal=", " if cmd['type'] == 'get_entries':\n  Path('Test-query-started').touch()\n  time.sleep(30)\n  goal=")
            worker.write_text(text)
            proc = self.launch(root, env)
            self.await_state(root, lambda s: (root / 'work/Test-query-started').exists(), proc)
            started = time.monotonic()
            self.human(root, c, 'cancel')
            self.assertEqual(proc.wait(timeout=8), 2)
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'cancelled')

    def worker_child_cleanup(self, exit_leader, goal_query=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal' if goal_query else 'ping-pong', effect=True)
            worker = root / 'bin/pi'
            text = worker.read_text()
            child_code = "import signal,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nPath('Test-worker-child').touch()\ntime.sleep(2)\nPath('Test-leaked-worker-effect').touch()\nwhile not Path('Test-worker-stop').exists(): time.sleep(.01)\n"
            child = f"child=subprocess.Popen([sys.executable,'-c',{child_code!r}]);\n   while not Path('Test-worker-child').exists(): time.sleep(.01)\n   "
            text = text.replace("Path('Test-effect-performed').write_text", child + "Path('Test-effect-performed').write_text")
            if goal_query:
                text = text.replace("if os.environ.get('PPP_TEST_EFFECT'): time.sleep(30)", 'pass')
                text = '\n'.join('  pass' if "emit(dict(type='tool_execution_end',toolName='goal_wait'" in line else line for line in text.splitlines()) + '\n'
                text = text.replace(" if cmd['type'] == 'get_entries':\n  goal=", " if cmd['type'] == 'get_entries':\n  os._exit(7)\n  goal=")
            elif exit_leader:
                text = text.replace("if os.environ.get('PPP_TEST_EFFECT'): time.sleep(30)", "if os.environ.get('PPP_TEST_EFFECT'): os._exit(7)")
            worker.write_text(text)
            proc = self.launch(root, env)
            state = self.await_state(root, lambda s: (root / 'work/Test-worker-child').exists(), proc)
            try:
                if not exit_leader:
                    self.human(root, c, 'cancel')
                self.assertEqual(proc.wait(timeout=10), 1 if exit_leader else 2)
                time.sleep(2.1)
                self.assertFalse((root / 'work/Test-leaked-worker-effect').exists())
                self.assertEqual(b.read(root / 'execution-state.json')['operations']['email:send']['outcome'], 'uncertain')
                self.assertEqual(state['cycle'], 1)
            finally:
                (root / 'work/Test-worker-stop').touch()

    def driver(self, root, env, point):
        path = root / 'Test-crash-driver.py'
        path.write_text('''import os,sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import action_protocol as p
import action_bridge as ab
import bridge as b
point=sys.argv[3]
original_check=ab.request_unchanged
def checked(c,request,state):
 original_check(c,request,state)
 if point=='after_review_response' and (Path(c['root'])/'reviews'/f"v2-{request['review_id']:06}"/'review.json').exists(): os._exit(91)
ab.request_unchanged=checked
original=p.durable
def durable(path,value):
 hit=Path(path).name=='execution-state.json' and (
  (point in {'before_reservation','after_reservation'} and value.get('cycle')==1 and value.get('active') is not None) or
  (point=='after_assessment' and value.get('cycle')==1 and value.get('consumption',[{}])[0].get('assessment')))
 if hit and point=='before_reservation': os._exit(91)
 original(path,value)
 if hit: os._exit(91)
p.durable=durable
sys.exit(ab.ActionBridge(b.load_config(sys.argv[2])).run())
''')
        log = (root / 'Test-run.log').open('wb')
        self.addCleanup(log.close)
        proc = subprocess.Popen([sys.executable, '-B', str(path), str(fixtures.HERE), str(root / 'config.json'), point], env=env, stdout=log, stderr=log)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def test_crash_after_response_before_apply_requires_delivery_investigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            crashed = self.driver(root, env, 'after_review_response')
            self.assertEqual(crashed.wait(timeout=10), 91)
            before = b.read(root / 'execution-state.json')
            self.assertTrue((root / 'reviews/v2-000001/review.json').is_file())
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=5), 1)
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['review_seq'], before['review_seq'])
            self.assertEqual(state['verification']['status'], 'blocked')
            self.assertEqual(state['cycle'], 2, 'missing review cannot suppress independent authorized work')
            self.assertIsNone(state.get('last_review'))


    def test_cancel_immediately_before_dispatch_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)
            original = core.store.transaction
            armed = False
            project = core.project

            def published(*args, **kwargs):
                nonlocal armed
                project(*args, **kwargs)
                if kwargs.get('request'):
                    armed = True

            @contextmanager
            def raced(*args, **kwargs):
                nonlocal armed
                with original(*args, **kwargs) as state:
                    if armed:
                        armed = False
                        self.human(root, core.c, 'cancel')
                    yield state

            with patch.object(core, 'project', side_effect=published), patch.object(core.store, 'transaction', side_effect=raced), patch.object(b.Bridge, 'queue_message') as transport:
                with self.assertRaises(ab.Terminated):
                    core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
                transport.assert_not_called()
            self.assertEqual(core.store.read()['execution'], 'cancelled')

    def test_pending_cancel_prevents_operation_reservation_before_worker_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root, effect=True)
            with core.store.transaction() as state:
                controller = p.Controller(core.c, state)
                controller.apply(report(core.c, state), {'test-proof'}, 'Test independent eligibility')
                controller.consume('email', 'Test-owner')
                state['sessions'].append(dict(owner='Test-owner', status='running'))
            core.acquire_worker()
            try:
                self.human(root, core.c, 'cancel')
                with self.assertRaises(ValueError):
                    ab.dispatch(core.c, SimpleNamespace(command='operation', action_id='email', operation_id='send', owner='Test-owner'))
                state = core.store.read()
                self.assertEqual(state['execution'], 'cancelled')
                self.assertFalse(state['operations'])
                self.assertEqual(state['cycle'], 1)
            finally:
                core.shutdown()

    def test_cancel_at_locked_callback_recording_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)
            original = p.Store.transaction

            @contextmanager
            def raced(store, *args, **kwargs):
                with original(store, *args, **kwargs) as state:
                    self.human(root, core.c, 'cancel')
                    yield state

            def reviewer(message, receipt):
                with patch.object(p.Store, 'transaction', new=raced), self.assertRaises(ValueError):
                    ab.record_review(core.c, SimpleNamespace(review_id=1, decision='endorse', feedback='Test cancel during callback recording', assessment=self.accept_fixture(core)))

            with patch.object(core, 'queue_message', side_effect=reviewer):
                with self.assertRaises(ab.Terminated):
                    core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
            self.assertEqual(core.store.read()['execution'], 'cancelled')
            self.assertFalse((root / 'reviews/v2-000001/review.json').exists())

    def test_ambiguous_queue_ack_even_with_valid_response_never_accepts_or_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            queue = root / 'bin/codex'
            queue.write_text(queue.read_text().replace(' subprocess.run(cmd,check=True)', ' subprocess.run(cmd,check=True)\n sys.exit(2)'))
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=10), 1)
            before = b.read(root / 'execution-state.json')
            self.assertTrue((root / 'reviews/v2-000001/review.json').is_file())
            self.assertEqual(before['verification']['kind'], 'reviewer_unavailable')
            self.assertEqual(before['cycle'], 2)
            self.assertTrue(all(value == 'unknown' for value in before['acceptance'].values()))
            self.assertIsNone(before.get('last_review'))
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=5), 1)
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['verification'], before['verification'])
            self.assertEqual(state['review_seq'], 1)
            self.assertEqual(len((root / 'work/Test-dispatch.jsonl').read_text().splitlines()), 1)

    def test_wait_recovery_duplicate_receipt_preserves_blocker_ledger_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, blocker=True, cycles=2)
            proc = self.launch(root, env)
            before = self.await_state(root, lambda s: s['execution'] == 'wait', proc)
            archived = {str(path): b.digest(path) for path in (root / 'evidence').iterdir()}
            proc.kill()
            proc.wait(timeout=5)
            (root / 'work/Test-secure-configured').touch()
            raw = self.human(root, c, blocker_ids=['B1'])
            p.durable(root / 'human-inbox/Test-duplicate-copy.json', raw)
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=10), 0, (root / 'Test-resume.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['run_id'], before['run_id'])
            self.assertEqual(state['pins'], before['pins'])
            self.assertEqual(state['grants'], before['grants'])
            self.assertEqual([row['scope'] for row in state['consumption']], ['main', 'main', 'closure'])
            self.assertEqual(len(state['human']), 1)
            self.assertEqual(state['blockers']['B1']['found_cycle'], before['blockers']['B1']['found_cycle'])
            self.assertEqual(state['blockers']['B1']['evidence'], before['blockers']['B1']['evidence'])
            self.assertEqual(len(state['blockers']['B1']['resolutions']), 1)
            self.assertTrue(all(b.digest(path) == digest for path, digest in archived.items()))
            again = self.launch(root, env, 'resume')
            self.assertNotEqual(again.wait(timeout=5), 0)
            self.assertEqual(b.read(root / 'execution-state.json')['cycle'], state['cycle'])

    def test_crash_before_after_durable_cycle_reservation(self):
        for point in ('before_reservation', 'after_reservation'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                crashed = self.driver(root, env, point)
                self.assertEqual(crashed.wait(timeout=10), 91)
                before = b.read(root / 'execution-state.json')
                self.assertEqual(before['cycle'], int(point == 'after_reservation'))
                self.assertFalse((root / 'work/footer.txt').exists())
                resumed = self.launch(root, env, 'resume')
                self.assertEqual(resumed.wait(timeout=10), 0 if point == 'before_reservation' else 2)
                state = b.read(root / 'execution-state.json')
                self.assertEqual(state['run_id'], c['run_id'])
                self.assertEqual(state['cycle'], len(state['consumption']))
                self.assertEqual(state['grants'], before['grants'])
                self.assertEqual(state['cycle'], 2)
                if point == 'after_reservation':
                    self.assertEqual(state['consumption'][0]['owner'], before['consumption'][0]['owner'])
                    self.assertEqual(state['consumption'][0]['assessment']['attempt']['assessment'], 'informative')
                    self.assertEqual(state['actions'][state['consumption'][0]['action_id']]['status'], 'stalled')
                    self.assertNotEqual(set(state['acceptance'].values()), {'pass'})

    def test_crash_after_assessment_preserves_exactly_once_cycle(self):
        for point in ('after_assessment',):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                crashed = self.driver(root, env, point)
                self.assertEqual(crashed.wait(timeout=10), 91)
                before = b.read(root / 'execution-state.json')
                self.assertEqual(before['cycle'], 1)
                self.assertTrue(before['consumption'][0]['assessment'])
                resumed = self.launch(root, env, 'resume')
                self.assertEqual(resumed.wait(timeout=10), 0, (root / 'Test-resume.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual(state['run_id'], c['run_id'])
                self.assertEqual(state['cycle'], 2)
                self.assertEqual(state['grants'], before['grants'])
                self.assertTrue(all(len(a['attempts']) == 1 for a in state['actions'].values()))
                self.assertEqual(len([e for e in state['history'] if e['type'] == 'cycle.assessed' and e['cycle'] == 1]), 1)
                self.assertEqual(len(state['sessions']), 2)
                self.assertNotIn('verification', state)
                self.assertTrue(all(Path(path).is_file() for req in (root / 'reviews').glob('*/request.json') for path in b.read(req)['evidence_archive'].values()))

    def test_crash_before_after_synthetic_effect_reconciles_without_replay(self):
        for effected, contradictory in ((False, False), (True, False), (True, True)):
            with self.subTest(effected=effected, contradictory=contradictory), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, effect=True, cycles=3)
                worker = root / 'bin/pi'
                if not effected:
                    worker.write_text(worker.read_text().replace("Path('Test-effect-performed').write_text", "Path('Test-before-effect').touch()\n   while not Path('Test-release-effect').exists(): time.sleep(.01)\n   Path('Test-effect-performed').write_text"))
                reviewer = root / 'bin/codex'
                text = reviewer.read_text().replace(" return report", " if s['operations'] and ctx['phase']=='recovery' and Path('Test-effect-performed').exists():\n  for row in report['actions']: row['eligible']=False\n  report['wake']=dict(source='resource-signal',reference='Test investigate prior effect',at=None)\n return report")
                reviewer.write_text(text)
                proc = self.launch(root, env)
                marker = 'Test-effect-performed' if effected else 'Test-before-effect'
                before = self.await_state(root, lambda s: (root / ('work/' + marker)).exists(), proc)
                pid = before['sessions'][-1]['pid']
                proc.kill()
                proc.wait(timeout=5)
                self.kill_group(pid)
                # The frozen fixture already supports both outcomes; change env, never governing pins.
                env.pop('PPP_TEST_EFFECT')
                env['PPP_TEST_JOURNAL'] = '1'
                if not effected:
                    (root / 'work/Test-release-effect').touch()
                resumed = self.launch(root, env, 'resume')
                if effected:
                    state = self.await_state(root, lambda s: bool(s['operations']) and s['operations']['email:send']['outcome'] == 'succeeded', resumed)
                    if contradictory:
                        established = deepcopy(state['operations']['email:send'])
                        resumed.kill()
                        resumed.wait(timeout=5)
                        env['PPP_TEST_OUTCOME_CONFLICT'] = '1'
                        again = subprocess.run([sys.executable, str(fixtures.HERE / 'bridge.py'), 'signal', '--config', str(root / 'config.json'), '--event-id', 'Test-conflict-wake', '--wake-ref', 'Test investigate prior effect'], env=env, capture_output=True, timeout=10)
                        self.assertEqual(again.returncode, 2, again.stderr.decode())
                        state = b.read(root / 'execution-state.json')
                        self.assertEqual(state['execution'], 'halt')
                        self.assertEqual(state['operations']['email:send'], established)
                        self.assertEqual(len([e for e in state['history'] if e['type'] == 'operation.conflict']), 1)
                    else:
                        self.human(root, c, 'cancel')
                        self.assertEqual(resumed.wait(timeout=5), 2)
                else:
                    self.assertEqual(resumed.wait(timeout=10), 2)
                state = b.read(root / 'execution-state.json')
                op = state['operations']['email:send']
                self.assertEqual(op['outcome'], 'succeeded' if effected else 'not_performed')
                self.assertEqual(op['owner'], before['operations']['email:send']['owner'])
                self.assertEqual(op['cycle'], 1)
                self.assertEqual(len([e for e in state['history'] if e['type'] == 'operation.started']), 1)
                self.assertEqual(state['run_id'], c['run_id'])
                self.assertEqual(state['grants'], before['grants'])
                self.assertTrue(state['consumption'][0]['assessment'])
                if not effected:
                    self.assertFalse((root / 'work/Test-effect-performed').exists())


    def test_live_evidence_hash_has_no_legacy_worker_prefix_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)
            source = root / 'work/worker:Test-proof'
            source.write_text('Test original source')
            hashes = {source.name: b.digest(source)}
            archive = ab.retain_evidence(core.c, hashes, time.monotonic() + 5)
            with core.store.transaction() as state:
                state['review_seq'] = 1
            state = core.store.read()
            request = {**p.header(core.c['run_id']), 'review_id': 1, 'cycle': 0,
                       'state_revision': state['revision'], 'state_sha256': p.sha(state),
                       'checkpoint_sha256': None, 'evidence_sha256': hashes, 'evidence_archive': archive}
            p.durable(root / 'reviews/v2-000001/request.json', request)
            ab.request_unchanged(core.c, request, state)
            source.write_text('Test mutated live source')
            with self.assertRaisesRegex(ValueError, 'Evidence changed after request'):
                ab.request_unchanged(core.c, request, state)

    def test_launch_diff_is_hash_bound_to_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)
            with core.store.transaction() as state:
                state['review_seq'] = 1
            state = core.store.read()
            diff = root / 'reviews/v2-000001/launch-diff.txt'
            diff.parent.mkdir(parents=True)
            diff.write_text('-# Test user line removed\n')
            request = {**p.header(core.c['run_id']), 'review_id': 1, 'cycle': 0,
                       'state_revision': state['revision'], 'state_sha256': p.sha(state),
                       'checkpoint_sha256': None, 'evidence_sha256': {}, 'evidence_archive': {},
                       'launch_diff': dict(coverage='complete', files={}, truncated=False, limitations=[], path=str(diff), sha256=b.digest(diff))}
            p.durable(diff.parent / 'request.json', request)
            ab.request_unchanged(core.c, request, state)
            self.assertEqual(ab.review_evidence(request), {'launch-diff'})
            diff.write_text('Test substituted diff\n')
            with self.assertRaisesRegex(ValueError, 'Launch diff changed after request'):
                ab.request_unchanged(core.c, request, state)

    def test_modified_request_cannot_rebind_review_to_different_core_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)

            def reviewer(message, receipt):
                target = receipt.parent / 'request.json'
                request = b.read(target)
                request['checkpoint']['summary'] = 'Test mutated request'
                p.durable(target, request)
                ab.record_review(core.c, SimpleNamespace(review_id=1, decision='endorse', feedback='Test endorsement of altered request', assessment=self.accept_fixture(core)))

            with patch.object(core, 'queue_message', side_effect=reviewer):
                with self.assertRaisesRegex(ValueError, 'Review request changed'):
                    core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
            state = core.store.read()
            self.assertIsNone(state.get('last_review'))
            self.assertNotEqual(set(state['acceptance'].values()), {'pass'})
            self.assertEqual(state['cycle'], 0)

    def test_replayed_assessment_cannot_apply_to_new_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = self.local(root)

            def reviewer(message, receipt):
                ab.record_review(core.c, SimpleNamespace(review_id=1, decision='endorse', feedback='Test independent assessment', assessment=self.accept_fixture(core)))

            with patch.object(core, 'queue_message', side_effect=reviewer):
                core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
            prior = core.store.read()

            def replay(message, receipt):
                p.durable(receipt.parent / 'review.json', b.read(root / 'reviews/v2-000001/review.json'))

            with patch.object(core, 'queue_message', side_effect=replay):
                with self.assertRaisesRegex(ValueError, 'Stale/wrong review identity'):
                    core.review_result('recovery', *b.validate_checkpoint(core.c, 0))
            state = core.store.read()
            self.assertEqual(state.get('verification'), prior.get('verification'))
            self.assertEqual(state['consumption'], prior['consumption'])
            self.assertEqual(state.get('last_review'), prior.get('last_review'))

    def test_concrete_worker_correction_then_material_replan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, cycles=4)
            env['PPP_TEST_CORRECTIONS'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=15), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual([row['action_id'] for row in state['consumption']], ['email', 'email', 'email', 'footer'])
            self.assertEqual([row['assessment']['attempt']['assessment'] for row in state['consumption']], ['informative', 'informative', 'verified', 'verified'])
            self.assertEqual(state['review_seq'], 4)
            self.assertEqual(state['execution'], 'finish')


class ProtocolFaultTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.c['pi_session_id'] = 'Test-session'
        self.s = p.initial(self.c, {})
        self.e = p.Controller(self.c, self.s)
        self.e.apply(report(self.c, self.s), {'test-proof'}, 'Test fresh independent eligibility')

    def human(self, hid, qid):
        self.e.ingress({**p.header(self.c['run_id']), 'id': hid, 'kind': 'grant', 'source': 'pi-command', 'session_id': 'Test-session', 'request_id': qid, 'cycles': 1, 'message': 'Test explicit scoped main extension'}, 'Test-session')

    def test_stale_different_request_cannot_reuse_budget_generation(self):
        for _ in range(2):
            self.e.consume('footer', 'Test-owner')
            assess_cycle(self.c, self.s)
        bid = self.e.blocker(dict(key='Test-access', reason='missing_access', needed='Test real missing access', blocked_actions=['email']), ['test-proof'])
        self.e.transition()
        old = next(iter(self.s['requests']))
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=bid, human_id=None, valid=True, approval_applicable=False, evidence_refs=['test-proof'])]
        next(x for x in r['actions'] if x['action']['id'] == 'email')['status'] = 'verified'
        self.e.apply(r, {'test-proof'}, 'Test independently restored access')
        self.e.transition()
        current = next(qid for qid in self.s['requests'] if qid != old)
        self.human('Test-first', current)
        r = report(self.c, self.s)
        r['grants'] = ['Test-first']
        self.e.apply(r, {'test-proof'}, 'Test single fresh main grant')
        before = deepcopy(self.s)
        self.human('Test-stale', old)
        self.assertTrue(self.s['human']['Test-stale']['processed'])
        self.assertEqual(self.s['human']['Test-stale']['rejected'], 'stale_budget_request')
        self.assertEqual(self.s['execution'], before['execution'])
        self.assertEqual(self.s['grants'], before['grants'])
        self.assertEqual(self.e.remaining('main'), 1)

    def test_two_pending_requests_same_budget_generation_cannot_double_grant(self):
        for _ in range(2):
            self.e.consume('footer', 'Test-owner')
            assess_cycle(self.c, self.s)
        old = self.e.request([], True, time.time())
        bid = self.e.blocker(dict(key='Test-access', reason='missing_access', needed='Test missing access', blocked_actions=['email']), ['test-proof'])
        current = self.e.request([self.s['blockers'][bid]], True, time.time())
        self.human('Test-pending-1', old)
        self.human('Test-pending-2', current)
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            before = store.read()
            r = report(self.c, before)
            r['grants'] = ['Test-pending-1', 'Test-pending-2']
            with self.assertRaisesRegex(ValueError, 'Stale budget request'):
                with store.transaction() as state:
                    p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test stale second grant')
            self.assertEqual(store.read(), before)

    def test_missing_duplicate_stale_contradictory_assessments_roll_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s) as state:
                p.Controller(self.c, state).consume('footer', 'Test-owner')
            before = store.read()
            for fault in ('missing', 'duplicate', 'stale', 'contradictory'):
                r = report(self.c, before)
                selected = next(x for x in r['actions'] if x['action']['id'] == 'footer')
                selected['attempt'] = attempt('Test fresh attempt', 'verified')
                if fault == 'missing': selected['attempt'] = None
                if fault == 'duplicate': r['actions'].append(deepcopy(selected))
                if fault == 'stale': r['state_sha256'] = 'Test-stale'
                if fault == 'contradictory':
                    selected['status'] = 'verified'
                    selected['attempt']['assessment'] = 'informative'
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    with store.transaction() as state:
                        p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test invalid assessment')
                self.assertEqual(store.read(), before)


if __name__ == '__main__':
    unittest.main()
