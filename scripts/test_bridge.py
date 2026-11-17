#!/usr/bin/env python3
"""Protocol tests use fake executables; no paid providers or real queue calls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import output_snapshot as outputs

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bridge', HERE / 'bridge.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class OutputDiscoveryTests(unittest.TestCase):
    def setup_scope(self, root, target=None):
        work = root / 'run/work'
        work.mkdir(parents=True)
        project = root / 'project'
        project.mkdir()
        return dict(run_id='Test-run', root=str(work.parent), execution_contract=dict(target=str(target or project))), work, project

    def test_hashes_detect_repeated_dirty_and_untracked_edits_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, work, project = self.setup_scope(Path(tmp).resolve())
            dirty = project / 'Test-already-dirty.txt'
            dirty.write_text('Test old user changes')
            original_time = dirty.stat().st_mtime_ns
            untouched = project / 'Test-existing.txt'
            untouched.write_text('Test preserve user file')
            baseline = outputs.snapshot(c)
            dirty.write_text('Test new user changes')
            os.utime(dirty, ns=(original_time, original_time))
            shell = project / 'Test-shell-created.txt'
            shell.write_text('Test shell result')
            (work / 'Test-log.txt').write_text('Test evidence')
            changes, limitations = outputs.changes(c, baseline)
            self.assertEqual(set(changes), {str(dirty), str(shell), str(work / 'Test-log.txt')})
            self.assertEqual(untouched.read_text(), 'Test preserve user file')
            self.assertIn('no authorship, test execution or acceptance', ' '.join(limitations))
            self.assertNotIn('Test old user changes', json.dumps(baseline), 'baseline stores hashes, not user content')

    def test_git_dirty_untracked_and_ignored_inputs_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, _, project = self.setup_scope(Path(tmp).resolve())
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            dirty = project / 'Test-staged.txt'
            dirty.write_text('Test staged user value')
            subprocess.run(['git', '-C', str(project), 'add', dirty.name], check=True)
            dirty.write_text('Test dirty user value')
            (project / '.gitignore').write_text('Test-ignored.txt\nconfig.local.json\n')
            local = project / 'config.local.json'
            local.write_text('Test private local configuration')
            ignored = project / 'Test-ignored.txt'
            ignored.write_text('Test existing ignored product')
            baseline = outputs.snapshot(c)
            before_index = subprocess.check_output(['git', '-C', str(project), 'show', ':' + dirty.name])
            dirty.write_text('Test continued dirty value')
            ignored.write_text('Test changed ignored product')
            changes, _ = outputs.changes(c, baseline)
            self.assertEqual(set(changes), {str(dirty), str(ignored)})
            self.assertNotIn(str(local), baseline['files'])
            self.assertEqual(local.read_text(), 'Test private local configuration')
            self.assertEqual(subprocess.check_output(['git', '-C', str(project), 'show', ':' + dirty.name]), before_index)

    def test_file_missing_target_scope_and_worker_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, work, project = self.setup_scope(Path(tmp).resolve())
            self.assertEqual(outputs.worker_directory(c), project)
            selected = project / 'Test-selected.txt'
            selected.write_text('Test old')
            c['execution_contract']['target'] = str(selected)
            baseline = outputs.snapshot(c)
            selected.write_text('Test changed')
            (project / 'Test-sibling.txt').write_text('Test not in scope')
            self.assertEqual(set(outputs.changes(c, baseline)[0]), {str(selected)})
            self.assertEqual(outputs.worker_directory(c), project)
            c['execution_contract']['target'] = str(project / 'missing/site')
            self.assertEqual(outputs.worker_directory(c), project)
            baseline = outputs.snapshot(c)
            (project / 'missing/site').mkdir(parents=True)
            result = project / 'missing/site/index.html'
            result.write_text('Test new project')
            self.assertEqual(set(outputs.changes(c, baseline)[0]), {str(result)})
            c['execution_contract']['target'] = 'Test descriptive target'
            self.assertEqual(outputs.worker_directory(c), work)

    def test_partial_missing_baselines_and_private_large_symlink_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, _, project = self.setup_scope(Path(tmp).resolve())
            safe = project / 'Test-safe.txt'
            safe.write_text('Test visible')
            (project / '.env').write_text('Test private')
            (project / 'config.local.json').write_text('Test private')
            (project / 'Test-large.txt').write_bytes(b'x' * (outputs.MAX_FILE_BYTES + 1))
            outside = Path(tmp).resolve() / 'Test-outside.txt'
            outside.write_text('Test out of scope')
            (project / 'Test-link').symlink_to(outside)
            original_open = os.open
            def checked_open(path, *args, **kwargs):
                self.assertNotIn(Path(path).name, {'.env', 'config.local.json', 'Test-large.txt', 'Test-link'}, 'private/large/symlink paths must not be read')
                return original_open(path, *args, **kwargs)
            with patch.object(outputs.os, 'open', side_effect=checked_open):
                self.assertEqual(set(outputs.snapshot(c)['files']), {str(safe)})
            with patch.object(outputs, 'MAX_FILES', 1):
                partial = outputs.snapshot(c)
            self.assertTrue(partial['limitations'])
            for baseline in (None, partial, {'run_id': 'Test-foreign', 'files': {}}):
                changes, limitations = outputs.changes(c, baseline)
                self.assertEqual(set(changes), {str(safe)})
                self.assertTrue(limitations)
                if baseline is None or baseline.get('run_id') == 'Test-foreign':
                    self.assertIn('unknown origin', ' '.join(limitations))
            c['execution_contract']['target'] = str(project / '.env')
            self.assertFalse(outputs.snapshot(c)['files'])


class ProtocolTests(unittest.TestCase):
    def test_bridge_status_keeps_start_and_update_timestamps_and_evaluation_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = b.Bridge(dict(run_id='fixture-test', mode='ralph', root=str(root)))
            started = bridge.state['started_at']
            self.assertGreater(started, 0)
            self.assertGreater(bridge.state['updated_at'], 0)
            bridge.status('running', phase='evaluating', cycle=1)
            state = b.read(root / 'bridge-status.json')
            self.assertEqual(state['phase'], 'evaluating')
            self.assertEqual(state['started_at'], started)
            self.assertGreaterEqual(state['updated_at'], started)
            self.assertEqual(state['cycle'], 1)

    def test_contract_separates_authorized_sources_from_evidence(self):
        for mode in ('goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c = self.config(root, mode)
                source = root / 'project' / 'source.py'
                source.parent.mkdir()
                source.write_text('print("Test source")\n')
                Path(c['task']).write_text(f'Edit only {source}; put the report in work/.')
                bridge = b.Bridge(c)
                bridge.contract()
                contract = (root / 'CONTRACT.md').read_text()
                self.assertIn(f'Checkpoint/evidence directory: {root.resolve() / "work"}', contract)
                self.assertIn('not a source checkout', contract)
                self.assertIn('explicitly authorized source paths outside work/', contract)
                self.assertIn('Without explicit task authorization, write only inside work/', contract)
                self.assertIn('cwd or Git ancestry does not grant write permission', contract)
                self.assertIn('this run\'s config, task specification, reviewer files', contract)
                self.assertIn('do not infer missing access from one module-resolution failure', contract)
                self.assertIn('require(process.env.PPP_PLAYWRIGHT_MODULE)', contract)
                self.assertNotIn('scripts outside work', contract)
                (root / 'work').mkdir()
                (root / 'work/report.md').write_text('Test source edit report')
                checkpoint = dict(run_id=c['run_id'], cycle=1, status='ready',
                                  summary='Test source report', evidence=['report.md'])
                b.atomic(root / 'work/checkpoint.json', checkpoint)
                b.validate_checkpoint(c, 1)
                b.atomic(root / 'work/checkpoint.json', {**checkpoint, 'evidence': ['../project/source.py']})
                with self.assertRaises(ValueError):
                    b.validate_checkpoint(c, 1)

    def test_evidence_limit_is_configurable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=self.config(root);(root/'work').mkdir()
            names=[f'proof-{i}.txt' for i in range(21)]
            for name in names:(root/'work'/name).write_text('Test evidence')
            b.atomic(root/'work/checkpoint.json',dict(run_id=c['run_id'],cycle=1,status='ready',summary='Test package',evidence=names))
            with self.assertRaises(ValueError):b.validate_checkpoint(c,1)
            c['max_evidence_files']=100
            cp,snapshot=b.validate_checkpoint(c,1)
            self.assertEqual(len(snapshot['evidence_sha256']),21)
            b.atomic(root/'config.json',{**c,'max_evidence_files':0})
            with self.assertRaises(ValueError):b.load_config(root/'config.json')

    def test_extension_config_paths_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.config(root); raw = b.read(root / 'config.json')
            for key in ('worker_extensions', 'reviewer_extensions'):
                for bad in ('file.ts', [None], [''], ['  '], ['bad\x00path'], None):
                    b.atomic(root / 'config.json', {**raw, key: bad})
                    with self.assertRaisesRegex(ValueError, key): b.load_config(root / 'config.json')
                b.atomic(root / 'config.json', {**raw, key: ['relative.ts', '/tmp/Test-extension.ts']})
                self.assertEqual(b.load_config(root / 'config.json')[key], [str((root / 'relative.ts').resolve()), str(Path('/tmp/Test-extension.ts').resolve())])

    def test_goal_launch_limit_defaults_and_token_cap_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=self.config(root)
            self.assertEqual(c['goal_max_launches'],10)
            self.assertNotIn('goal_tokens',c)
            raw=b.read(root/'config.json')
            for bad in ({'goal_max_launches':0},{'goal_max_launches':True},{'goal_tokens':0}):
                b.atomic(root/'config.json',{**raw,**bad})
                with self.assertRaises(ValueError):b.load_config(root/'config.json')
            b.atomic(root/'config.json',{**raw,'goal_tokens':5000})
            self.assertEqual(b.load_config(root/'config.json')['goal_tokens'],5000)

    def test_goal_needs_no_cycle_limits_but_ralph_and_ping_pong_do(self):
        import action_protocol as p
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.config(root);raw=b.read(root/'config.json')
            goal={k:v for k,v in raw.items() if k not in ('max_cycles','cycle_seconds')}
            b.atomic(root/'config.json',goal)
            c=b.load_config(root/'config.json')
            self.assertNotIn('max_cycles',c)
            controller=p.Controller(c,p.initial(c,{}))
            self.assertEqual(controller.remaining('main'),10,'Goal budget is goal_max_launches')
            for mode in ('ralph','ping-pong'):
                for missing in ('max_cycles','cycle_seconds'):
                    b.atomic(root/'config.json',{**{k:v for k,v in raw.items() if k!=missing},'mode':mode})
                    with self.assertRaisesRegex(ValueError,'Missing config: '+missing):b.load_config(root/'config.json')
            b.atomic(root/'config.json',{**goal,'max_cycles':0})
            with self.assertRaisesRegex(ValueError,'Invalid limit: max_cycles'):b.load_config(root/'config.json')
            b.atomic(root/'config.json',raw)
            self.assertEqual((b.load_config(root/'config.json')['max_cycles'],b.load_config(root/'config.json')['cycle_seconds']),(3,5))

    def test_pi_transport_binding_and_durable_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            c=self.config(root)
            c.update(review_transport='pi',pi_session_id='launch-session')
            c.pop('thread_id')
            b.atomic(root/'config.json',c)
            c=b.load_config(root/'config.json')
            bridge=b.Bridge(c)
            b.atomic(root/'pi-receiver.json',{'run_id':c['run_id'],'session_id':'launch-session'})
            directory=root/'reviews/001';directory.mkdir(parents=True)
            receipt=directory/'queue-receipt.txt'
            bridge.queue_message('Checkpoint for Sol',receipt)
            messages=list((root/'pi-inbox').glob('*.message.json'))
            self.assertEqual(len(messages),1)
            message=b.read(messages[0])
            self.assertEqual(message['session_id'],'launch-session')
            self.assertEqual(message['kind'],'review')
            self.assertEqual(b.read(receipt)['status'],'queued')
            with self.assertRaises(RuntimeError):bridge.queue_message('duplicate',receipt)
            b.atomic(root/'pi-receiver.json',{'run_id':c['run_id'],'session_id':'different-session'})
            with self.assertRaises(RuntimeError):bridge.queue_message('wrong target',root/'notice.txt')
            self.assertEqual(len(list((root/'pi-inbox').glob('*.message.json'))),1)

    def config(self, root, mode='goal'):
        c = dict(run_id='fixture-test', mode=mode, thread_id='test-thread', worker_model='test-worker', review_model='test-reviewer', task='TASK.md', protocol_version=2, schema_version=1, execution_contract=__import__('test_action_protocol').config()['execution_contract'], max_cycles=3, wall_seconds=20, review_seconds=5, cycle_seconds=5)
        b.atomic(root / 'config.json', c)
        (root / 'TASK.md').write_text('Create result.txt containing PONG.')
        return b.load_config(root / 'config.json')

    def test_browser_runtime_resolves_once_from_project_or_configured_module(self):
        for configured in (False, True):
            with self.subTest(configured=configured), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                project = root / 'Test-project with spaces'
                project.mkdir()
                task = project / 'TASK.md'
                task.write_text('Test browser task using Playwright')
                module = (root / 'Test-configured.cjs') if configured else project / 'node_modules/playwright/index.js'
                module.parent.mkdir(parents=True, exist_ok=True)
                module.write_text('module.exports = {chromium: {launch() {throw Error("Test must not launch browser")}}};')
                env = {'PPP_PLAYWRIGHT_MODULE': str(module) if configured else ''}
                with patch.dict(os.environ, env), patch.object(b.subprocess, 'run', wraps=subprocess.run) as resolve:
                    core = b.Bridge(dict(run_id='Test-browser', mode='goal', root=str(root), task=str(task)))
                    core.prepare_browser_runtime()
                    core.prepare_browser_runtime()
                    self.assertEqual(resolve.call_count, 1)
                self.assertEqual(core.browser_runtime['status'], 'available')
                self.assertEqual(core.browser_env()['PPP_PLAYWRIGHT_MODULE'], str(module.resolve()))
                for mode in ('goal', 'ralph'):
                    core.c['mode'] = mode
                    core.contract()
                    text = (root / 'CONTRACT.md').read_text()
                    self.assertIn(str(module.resolve()), text)
                    self.assertIn('require(process.env.PPP_PLAYWRIGHT_MODULE)', text)

    def test_browser_resolution_failure_is_not_a_launch_gate_or_host_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / 'TASK.md'
            task.write_text('Test browser task')
            core = b.Bridge(dict(run_id='Test-browser', mode='ralph', root=str(root), task=str(task)))
            with patch.object(b.subprocess, 'run', side_effect=subprocess.TimeoutExpired('node', 5)) as resolve:
                core.prepare_browser_runtime()
                core.prepare_browser_runtime()
                self.assertEqual(resolve.call_count, 1)
                self.assertEqual(resolve.call_args.kwargs['timeout'], 5)
            self.assertEqual(core.browser_runtime['status'], 'unavailable')
            self.assertEqual(core.browser_env(), {})
            task.write_text('Test plain code task')
            del core.browser_runtime
            with patch.object(b.subprocess, 'run', side_effect=AssertionError('No browser resolution needed')):
                core.prepare_browser_runtime()
            self.assertEqual(core.browser_runtime['status'], 'not_requested')

    def fake_goal_bridge(self, events, status='active', entries=None):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__('shutil').rmtree, root, ignore_errors=True)
        bridge = b.Bridge(dict(run_id='fixture-test', mode='goal', root=str(root), cycle_seconds=1, wall_seconds=5))
        bridge.state['cycle'] = 1
        bridge.proc = type('Proc', (), {'poll': lambda self: None})()
        bridge.proc.stdin = type('Stdin', (), {'write': lambda self, value: None, 'flush': lambda self: None})()
        bridge.records = __import__('queue').Queue()
        for event in events:
            bridge.records.put(event)
        def send(kind, **values):
            if kind == 'get_entries':
                ident = 'state-query'
                bridge.records.put({'type':'response','id':ident,'success':True,'data':{'entries':entries if entries is not None else [{'type':'custom','customType':'goal-state','data':{'goal':{'status':status,'waiting':None,'safetyPauseCause':None}}}]}})
                return ident
            return 'prompt-id'
        bridge.send = send
        return bridge

    def test_goal_intermediate_settled_then_accepted_wait_is_boundary(self):
        events = [
            {'type':'agent_start'}, {'type':'agent_settled','aborted':False},
            {'type':'agent_start'},
            {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: review'}]}},
            {'type':'agent_settled','aborted':False},
        ]
        bridge = self.fake_goal_bridge(events)
        bridge.goal_cycle()
        self.assertTrue(bridge.records.empty())
        types = [json.loads(line)['type'] for line in (bridge.root/'bridge-events.jsonl').read_text().splitlines()] if bridge.events_file.exists() else []
        self.assertEqual(types.count('pi.agent_settled'), 2)

    def test_goal_correction_in_existing_session_does_not_reread_contract_or_task(self):
        boundary = [{'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: review'}]}},
                    {'type':'agent_settled','aborted':False}]
        prompts = {}
        for name, options in [('fresh', {'fresh_session':True}), ('existing', {'feedback':'Test correction'})]:
            bridge = self.fake_goal_bridge(list(boundary))
            send = bridge.send
            def capture(kind, _send=send, _name=name, **values):
                if kind == 'prompt':
                    prompts[_name] = values['message']
                return _send(kind, **values)
            bridge.send = capture
            bridge.goal_cycle(**options)
            self.assertIn(str(bridge.root / 'work/cycle-context.json'), prompts[name])
        self.assertTrue(prompts['fresh'].startswith('/goal '))
        self.assertRegex(prompts['fresh'], r'Read \S+/CONTRACT\.md, the task and ')
        self.assertFalse(prompts['existing'].startswith('/goal'))
        self.assertNotRegex(prompts['existing'], r'Read \S+/CONTRACT\.md')
        self.assertIn('already delivered in this session', prompts['existing'])
        self.assertIn('Core/Reviewer feedback: Test correction', prompts['existing'])

    def test_goal_budget_replacement_confirms_only_the_expected_dialog(self):
        dialog = {'type':'extension_ui_request','id':'Test-confirm','method':'confirm','title':'Replace goal?'}
        events = [dialog, {'type':'agent_start'},
                  {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: review'}]}},
                  {'type':'agent_settled','aborted':False}]
        bridge = self.fake_goal_bridge(events)
        written = []
        started = []
        def confirm_after_no_start(value):
            self.assertEqual(started, [], 'Worker must not be announced before the replacement dialog')
            written.append(value)
        bridge.proc.stdin.write = confirm_after_no_start
        bridge.goal_cycle(fresh_session=True, replace_budget_limited=True, on_start=lambda: started.append(True))
        self.assertEqual([json.loads(line) for line in written], [{'type':'extension_ui_response','id':'Test-confirm','confirmed':True}])
        self.assertEqual(started, [True])
        for options, request in [({}, dialog), ({'fresh_session':True,'replace_budget_limited':True}, {**dialog, 'title':'Other confirmation'})]:
            bridge = self.fake_goal_bridge([request])
            sent = []
            bridge.proc.stdin.write = sent.append
            with self.assertRaisesRegex(RuntimeError, 'Unexpected Pi Goal dialog'):
                bridge.goal_cycle(**options)
            self.assertEqual(sent, [])

    def test_multiple_intermediate_goal_turns_share_one_cycle(self):
        events = []
        for _ in range(3):
            events.extend([{'type':'agent_start'}, {'type':'agent_settled','aborted':False}])
        events.extend([
            {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: review'}]}},
            {'type':'agent_settled','aborted':False},
        ])
        self.fake_goal_bridge(events).goal_cycle()

    def test_goal_state_query_can_use_current_operation_deadline(self):
        bridge = self.fake_goal_bridge([])
        bridge.cycle_deadline = time.monotonic() - 1
        self.assertEqual(bridge.goal_state(deadline=time.monotonic() + 1)['status'], 'active')
        with self.assertRaisesRegex(TimeoutError, 'Goal state query timeout'):
            bridge.goal_state(deadline=time.monotonic() - 1)

    def test_goal_state_accepts_slow_reply_within_operation(self):
        bridge = self.fake_goal_bridge([])
        clock = [100.0]
        bridge.remaining = lambda: 120.0 - (clock[0] - 100.0)
        records = bridge.records
        original_get = records.get
        def delayed_get(timeout):
            clock[0] += 11
            return original_get(block=False)
        with patch.object(b.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(records, 'get', side_effect=delayed_get):
            self.assertEqual(bridge.goal_state(deadline=130)['status'], 'active')
        self.assertGreater(clock[0], 110)

    def test_goal_state_stops_for_control_or_process_exit(self):
        bridge = self.fake_goal_bridge([])
        bridge.send = lambda *args, **kwargs: 'Test-pending'
        bridge.proc.poll = lambda: 7
        with self.assertRaisesRegex(RuntimeError, 'Pi exited during Goal state query: 7'):
            bridge.goal_state(deadline=time.monotonic() + 1)
        bridge = self.fake_goal_bridge([])
        def cancel():
            raise RuntimeError('Test cancellation')
        bridge.check_control = cancel
        with self.assertRaisesRegex(RuntimeError, 'Test cancellation'):
            bridge.goal_state(deadline=time.monotonic() + 1)

    def test_goal_state_query_preserves_interleaved_events(self):
        bridge = self.fake_goal_bridge([])
        interleaved = [
            {'type':'agent_start'},
            {'type':'agent_settled','aborted':False},
            {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: reviewer'}]}},
        ]
        for event in interleaved:
            bridge.records.put(event)
        bridge.records.put({'type':'response','id':'state-query','success':True,'data':{'entries':[]}})
        self.assertIsNone(bridge.goal_state()['status'])
        self.assertEqual([bridge.next()['type'] for _ in interleaved], [event['type'] for event in interleaved])

    def test_rejected_goal_wait_is_not_boundary(self):
        events = [
            {'type':'tool_execution_end','toolName':'goal_wait','isError':True,'result':{'content':[{'type':'text','text':'Rejected'}]}},
            {'type':'agent_settled','aborted':False},
            {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: reviewer'}]}},
            {'type':'agent_settled','aborted':False},
        ]
        self.fake_goal_bridge(events).goal_cycle()

    def test_native_goal_complete_is_review_boundary_not_acceptance(self):
        events = [
            {'type':'tool_execution_end','toolName':'goal_complete','isError':False,'result':{'content':[{'type':'text','text':'Goal complete: done'}]}},
            {'type':'agent_settled','aborted':False},
        ]
        bridge = self.fake_goal_bridge(events)
        bridge.goal_cycle()
        self.assertEqual(bridge.goal_boundary['status'], 'active')
        self.assertNotEqual(bridge.state.get('status'), 'complete')

    def test_canonical_native_completion_without_tool_event_is_boundary(self):
        bridge = self.fake_goal_bridge([{'type':'agent_settled','aborted':False}], status='complete')
        bridge.goal_cycle()
        self.assertEqual(bridge.goal_boundary['status'], 'complete')
        self.assertNotEqual(bridge.state.get('status'), 'complete')

    def test_goal_rpc_terminal_tombstone_requires_matching_native_completion(self):
        complete = {'type':'custom','customType':'goal-state','data':{'goal':{'id':'Test-owned','status':'complete','tokensUsed':173328,'tokenBudget':400000}}}
        cleared = {'type':'custom','customType':'goal-state','data':{'goal':None}}
        result = {'type':'message','message':{'role':'toolResult','toolName':'goal_complete','isError':False,'details':{'goal_id':'Test-owned'},'content':[{'type':'text','text':'Goal complete: Test result'}]}}
        entries = [complete, cleared, result]
        bridge = self.fake_goal_bridge([{'type':'agent_settled','aborted':False}], entries=entries)
        bridge.goal_cycle()
        self.assertEqual((bridge.goal_boundary['id'], bridge.goal_boundary['status'], bridge.goal_boundary['tokens_used']), ('Test-owned', 'complete', 173328))
        self.assertEqual(json.loads((bridge.root / 'native-goal-state.json').read_text())['tokenBudget'], 400000)
        self.assertNotEqual(bridge.state.get('status'), 'complete')
        for fault in ('active', 'missing_result', 'rejected', 'foreign_result', 'missing_goal', 'extra_null', 'assistant'):
            with self.subTest(fault=fault):
                damaged = json.loads(json.dumps(entries))
                if fault == 'active':
                    damaged[0]['data']['goal']['status'] = 'active'
                elif fault == 'missing_result':
                    damaged.pop()
                elif fault == 'rejected':
                    damaged[-1]['message']['isError'] = True
                elif fault == 'foreign_result':
                    damaged[-1]['message']['details']['goal_id'] = 'Test-foreign'
                elif fault == 'missing_goal':
                    damaged[1]['data'] = {}
                elif fault == 'extra_null':
                    damaged.append(cleared)
                elif fault == 'assistant':
                    damaged.append({'type':'message','message':{'role':'assistant','content':[]}})
                bridge = self.fake_goal_bridge([], entries=damaged)
                self.assertIsNone(bridge.goal_state()['id'])
                self.assertIsNone(bridge.goal_state()['tokens_used'])

    def test_second_goal_completion_with_metered_post_completion_turns_is_boundary(self):
        # Live sequence: first goal completed/cleared, second goal in the same session completes, then Worker answers twice more.
        def goal(ident, status, used):
            return {'type':'custom','customType':'goal-state','data':{'goal':{'id':ident,'status':status,'tokensUsed':used}}}
        def result(ident):
            return {'type':'message','message':{'role':'toolResult','toolName':'goal_complete','isError':False,'details':{'goal_id':ident},'content':[{'type':'text','text':'Goal complete: Test result'}]}}
        def assistant(tokens):
            return {'type':'message','message':{'role':'assistant','content':[],'usage':{'totalTokens':tokens}}}
        cleared = {'type':'custom','customType':'goal-state','data':{'goal':None}}
        entries = [goal('Test-first', 'complete', 553807), cleared, result('Test-first'),
                   goal('Test-second', 'active', 0), assistant(75143), goal('Test-second', 'active', 75143), assistant(76006), goal('Test-second', 'complete', 151149), cleared,
                   {'type':'message','message':{'role':'toolResult','toolName':'bash','isError':True,'content':[]}}, result('Test-second'), assistant(77435),
                   {'type':'message','message':{'role':'toolResult','toolName':'bash','isError':False,'content':[]}}, assistant(77748)]
        bridge = self.fake_goal_bridge([{'type':'agent_settled','aborted':False}], entries=entries)
        bridge.goal_cycle()
        self.assertEqual((bridge.goal_boundary['id'], bridge.goal_boundary['status'], bridge.goal_boundary['tokens_used']), ('Test-second', 'complete', 151149 + 77435 + 77748))
        for fault in ('unmetered', 'foreign_result', 'negative_usage'):
            with self.subTest(fault=fault):
                damaged = json.loads(json.dumps(entries))
                if fault == 'unmetered':
                    del damaged[-1]['message']['usage']
                elif fault == 'foreign_result':
                    damaged[10] = result('Test-first')
                else:
                    damaged[-1]['message']['usage']['totalTokens'] = -1
                bridge = self.fake_goal_bridge([], entries=damaged)
                self.assertIsNone(bridge.goal_state()['id'])
                self.assertIsNone(bridge.goal_state()['tokens_used'])

    def test_goal_without_progress_hits_cycle_deadline(self):
        bridge = self.fake_goal_bridge([])
        bridge.c['cycle_seconds'] = 0.01
        with self.assertRaisesRegex(TimeoutError, 'without a native Goal result'):
            bridge.goal_cycle()

    def test_real_native_goal_stops_and_provider_wait_are_review_boundaries(self):
        for status in ('blocked', 'paused', 'usage_limited', 'complete', 'active'):
            events = [{'type':'agent_settled','aborted':False}]
            bridge = self.fake_goal_bridge(events, status=status)
            if status == 'active':
                bridge.goal_state = lambda: {'status':'active','waiting':'provider retry','safetyPauseCause':None}
            with self.subTest(status=status):
                bridge.goal_cycle()
                self.assertEqual(bridge.goal_boundary['status'], status)
        safety_pause = self.fake_goal_bridge([{'type':'agent_settled','aborted':False}])
        safety_pause.goal_state = lambda: {'status':'active','waiting':None,'safetyPauseCause':'automatic-work-limit'}
        safety_pause.goal_cycle()
        self.assertEqual(safety_pause.goal_boundary['safetyPauseCause'], 'automatic-work-limit')
        with self.assertRaisesRegex(RuntimeError, 'aborted'):
            self.fake_goal_bridge([{'type':'agent_settled','aborted':True}]).goal_cycle()


    def test_checkpoint_hashes_and_path_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = self.config(root)
            (root / 'work').mkdir()
            (root / 'work/result.txt').write_text('PONG')
            cp = dict(run_id=c['run_id'], cycle=1, status='ready', summary='Done', evidence=['result.txt'])
            b.atomic(root / 'work/checkpoint.json', cp)
            _, snap = b.validate_checkpoint(c, 1)
            self.assertTrue(b.unchanged(c, snap))
            (root / 'work/result.txt').write_text('changed')
            self.assertFalse(b.unchanged(c, snap))
            for path in ('../TASK.md', '.env', '/etc/passwd'):
                b.atomic(root / 'work/checkpoint.json', {**cp, 'evidence': [path]})
                with self.subTest(path=path), self.assertRaises(ValueError):
                    b.validate_checkpoint(c, 1)
            b.atomic(root / 'work/checkpoint.json', {**cp, 'cycle': 0})
            with self.assertRaises(ValueError):
                b.validate_checkpoint(c, 1)


if __name__ == '__main__':
    unittest.main()
