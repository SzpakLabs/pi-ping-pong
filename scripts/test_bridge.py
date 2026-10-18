#!/usr/bin/env python3
"""Protocol tests use fake executables; no paid providers or real queue calls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bridge', HERE / 'bridge.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

FAKE = r'''#!/usr/bin/env python3
import json,sys,os,re
from pathlib import Path
def emit(x): print(json.dumps(x),flush=True)
if Path(sys.argv[0]).name=='codex':
 msg=sys.argv[sys.argv.index('--message')+1]
 if 'reviewed run ' in msg and ' is complete.' in msg:
  Path('final-callback-prompt.txt').write_text(msg);print('Queued final report');sys.exit(0)
 if 'stopped and needs attention.' in msg:
  Path('attention-callback-prompt.txt').write_text(msg);print('Queued attention report');sys.exit(0)
 Path('review-callback-prompt.txt').write_text(msg)
 match=re.search(r'Read (.+?/reviews/\d+/request.json),',msg)
 if match:
  path=Path(match.group(1)); req=json.loads(path.read_text())
  result={k:req[k] for k in ('run_id','cycle','checkpoint_sha256')}
  result.update(decision='revise' if req['eval']['exit_code'] else 'complete',feedback='Change result to PONG' if req['eval']['exit_code'] else 'Verified PONG')
  if os.environ.get('PI_FAKE_HUMAN') and req['cycle']==1:
   result.update(decision='wait_human',feedback='Need Test choice')
   import subprocess
   code="import sys,json,time;from pathlib import Path;time.sleep(0.7);p=Path(sys.argv[1]);r=json.loads(p.read_text());s=json.loads((p.parents[2]/'bridge-status.json').read_text());assert s['status']=='waiting_human';r.update(decision='revise',human_resolved=True,feedback='User supplied Test choice; write PONG');p.write_text(json.dumps(r))"
   subprocess.Popen([sys.executable,'-c',code,str(path.with_name('review.json'))],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  path.with_name('review.json').write_text(json.dumps(result))
 print('Queued fake receipt')
 sys.exit(0)
for line in sys.stdin.buffer:
 cmd=json.loads(line)
 if cmd['type']=='get_state':
  emit({'type':'response','id':cmd['id'],'success':True,'data':{'sessionFile':'fake-session.jsonl'}});continue
 emit({'type':'response','id':cmd['id'],'success':True,'data':{'disposition':'started'}})
 if cmd['type']!='prompt':continue
 message=cmd['message']
 if 'Final independent review ACCEPTED' in message:
  emit({'type':'tool_execution_end','toolName':'goal_complete','result':{'content':[{'type':'text','text':'Goal complete: verified'}]},'isError':False})
  emit({'type':'agent_settled','aborted':False});continue
 ctx=json.loads(Path('cycle-context.json').read_text()); n=ctx['cycle']
 Path('result.txt').write_text('PING' if n==1 or os.environ.get('PI_FAKE_STUCK') else 'PONG')
 cp={'run_id':ctx['run_id'],'cycle':n,'status':'ready','summary':'Candidate result','evidence':['result.txt'],'next_step':'review'}
 if os.environ.get('PI_FAKE_HUMAN') and n==1:cp.update(status='needs_human',reason_code='user_choice')
 Path('checkpoint.json').write_text(json.dumps(cp))
 if message.startswith('/ralph'):
  directory=Path(message.split('--path ',1)[1]);p=directory/'.ralph-runner/status.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'completedAt':'now','status':'max-iterations','loopToken':f'fake-{n}'}))
 else:
  emit({'type':'tool_execution_end','toolName':'goal_wait','result':{'content':[{'type':'text','text':'Goal waiting: reviewer'}]},'isError':False})
 emit({'type':'agent_settled','aborted':False})
'''


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
                self.assertIn('this run\'s config, task specification, reviewer files, evaluator', contract)
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
        c = dict(run_id='fixture-test', mode=mode, thread_id='test-thread', worker_model='test-worker', review_model='test-reviewer', task='TASK.md', eval_argv=[sys.executable, str(root / 'eval.py')], max_cycles=3, wall_seconds=20, review_seconds=5, cycle_seconds=5)
        b.atomic(root / 'config.json', c)
        (root / 'TASK.md').write_text('Create result.txt containing PONG.')
        (root / 'eval.py').write_text("from pathlib import Path\nassert Path('result.txt').read_text()=='PONG'\n")
        return b.load_config(root / 'config.json')

    def test_goal_and_ralph_revise_then_complete(self):
        for mode, scenario in [('goal','normal'), ('ralph','normal'), ('goal','human'), ('goal','stuck')]:
            with self.subTest(mode=mode,scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                tools = root / 'bin'
                tools.mkdir()
                for name in ('pi', 'codex'):
                    p = tools / name
                    p.write_text(FAKE)
                    p.chmod(0o755)
                self.config(root, mode)
                env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH']}
                if scenario=='human':env['PI_FAKE_HUMAN']='1'
                if scenario=='stuck':env['PI_FAKE_STUCK']='1'
                p = subprocess.run([sys.executable, str(HERE / 'bridge.py'), 'run', '--config', str(root / 'config.json')], env=env, capture_output=True, timeout=20)
                if scenario=='stuck':
                    self.assertEqual(p.returncode,1,p.stderr.decode())
                    self.assertIn('Repeated identical',b.read(root/'bridge-status.json')['reason'])
                    attention = (root / 'work/attention-callback-prompt.txt').read_text()
                    self.assertIn('what is verified versus unknown', attention)
                    self.assertIn('Escalation', attention)
                    continue
                self.assertEqual(p.returncode, 0, p.stderr.decode())
                self.assertEqual(b.read(root / 'bridge-status.json')['status'], 'complete')
                self.assertEqual((root / 'work/result.txt').read_text(), 'PONG')
                self.assertEqual(b.read(root / 'reviews/001/request.json')['eval']['exit_code'], 1)
                self.assertEqual(b.read(root / 'reviews/002/request.json')['eval']['exit_code'], 0)
                callback = (root / 'work/review-callback-prompt.txt').read_text()
                final_callback = (root / 'work/final-callback-prompt.txt').read_text()
                for heading in ('Run summary', 'Steps', 'Verification and errors', 'Escalation', 'Completion', 'Next action'):
                    self.assertIn(heading, callback)
                    self.assertIn(heading, final_callback)
                self.assertIn('briefly state each option\'s main benefit and cost/risk', callback)
                self.assertIn('Do not end by asking a vague question', callback)
                self.assertIn('reviews/002/request.json', final_callback)
                self.assertIn('reviews/002/review.json', final_callback)
                events = [json.loads(x) for x in (root / 'bridge-events.jsonl').read_text().splitlines()]
                self.assertEqual([x['decision'] for x in events if x['type'] == 'review.applied'], ['revise', 'complete'])
                if scenario=='human':
                    self.assertTrue(any(x.get('status')=='waiting_human' for x in events))
                # Single-use run identity: no silent duplicate work or queue.
                duplicate = subprocess.run([sys.executable, str(HERE / 'bridge.py'), 'run', '--config', str(root / 'config.json')], env=env, capture_output=True)
                self.assertNotEqual(duplicate.returncode, 0)

    def fake_goal_bridge(self, events, status='active'):
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
                bridge.records.put({'type':'response','id':ident,'success':True,'data':{'entries':[{'type':'custom','customType':'goal-state','data':{'goal':{'status':status,'waiting':None,'safetyPauseCause':None}}}]}})
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

    def test_multiple_intermediate_goal_turns_share_one_cycle(self):
        events = []
        for _ in range(3):
            events.extend([{'type':'agent_start'}, {'type':'agent_settled','aborted':False}])
        events.extend([
            {'type':'tool_execution_end','toolName':'goal_wait','isError':False,'result':{'content':[{'type':'text','text':'Goal waiting: review'}]}},
            {'type':'agent_settled','aborted':False},
        ])
        self.fake_goal_bridge(events).goal_cycle()

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

    def test_premature_goal_complete_rejected(self):
        events = [
            {'type':'tool_execution_end','toolName':'goal_complete','isError':False,'result':{'content':[{'type':'text','text':'Goal complete: done'}]}},
            {'type':'agent_settled','aborted':False},
        ]
        with self.assertRaisesRegex(RuntimeError, 'before independent review'):
            self.fake_goal_bridge(events).goal_cycle()

    def test_accepted_final_goal_complete(self):
        events = [
            {'type':'tool_execution_end','toolName':'goal_complete','isError':False,'result':{'content':[{'type':'text','text':'Goal complete: done'}]}},
            {'type':'agent_settled','aborted':False},
        ]
        self.fake_goal_bridge(events).goal_cycle(final=True)

    def test_goal_without_progress_hits_cycle_deadline(self):
        bridge = self.fake_goal_bridge([])
        bridge.c['cycle_seconds'] = 0.01
        with self.assertRaisesRegex(TimeoutError, 'without an accepted Goal boundary'):
            bridge.goal_cycle()

    def test_goal_stopped_or_provider_wait_is_diagnosed(self):
        for status, reason in [('blocked', 'stopped or entered'), ('active', 'stopped or entered')]:
            events = [{'type':'agent_settled','aborted':False}]
            bridge = self.fake_goal_bridge(events, status=status)
            if status == 'active':
                bridge.goal_state = lambda: {'status':'active','waiting':'provider retry','safetyPauseCause':None}
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, reason):
                bridge.goal_cycle()
        safety_pause = self.fake_goal_bridge([{'type':'agent_settled','aborted':False}])
        safety_pause.goal_state = lambda: {'status':'active','waiting':None,'safetyPauseCause':'automatic-work-limit'}
        with self.assertRaisesRegex(RuntimeError, 'stopped or entered'):
            safety_pause.goal_cycle()
        with self.assertRaisesRegex(RuntimeError, 'aborted'):
            self.fake_goal_bridge([{'type':'agent_settled','aborted':True}]).goal_cycle()

    def test_invalid_or_stale_decisions_fail_closed(self):
        c = {}
        request = dict(run_id='a', cycle=1, checkpoint_sha256='hash', checkpoint={'status': 'ready'}, eval={'exit_code': 1})
        base = dict(run_id='a', cycle=1, checkpoint_sha256='hash', decision='revise', feedback='Fix failed check')
        self.assertEqual(b.validate_review(c, request, base), 'revise')
        for change in ({'cycle': 2}, {'run_id': 'b'}, {'checkpoint_sha256': 'wrong'}, {'decision': 'complete'}, {'decision': 'continue'}, {'feedback': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                b.validate_review(c, request, {**base, **change})
        request['eval']['exit_code'] = 0
        request['checkpoint']['status'] = 'needs_human'
        with self.assertRaises(ValueError):
            b.validate_review(c, request, {**base, 'decision': 'continue'})
        self.assertEqual(b.validate_review(c, request, {**base, 'decision': 'wait_human'}), 'wait_human')
        self.assertEqual(b.validate_review(c, request, {**base, 'decision': 'continue', 'human_resolved': True}), 'continue')
        with self.assertRaises(ValueError):
            b.validate_review(c, request, {**base, 'decision': 'complete', 'human_resolved': True})

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
