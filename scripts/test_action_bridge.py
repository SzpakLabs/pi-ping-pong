#!/usr/bin/env python3
"""Real bridge subprocess + synthetic Pi/queue/Reviewer; no paid/live operations."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import action_protocol as p
import bridge as b
import action_bridge as ab
from test_action_protocol import config

HERE = Path(__file__).resolve().parent

FAKE = r'''#!/usr/bin/env python3
import fcntl, hashlib, json, os, re, shlex, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

def assessment(req, path):
 ctx=json.loads(path.with_name('context.json').read_text()); s=ctx['state']; contract=ctx['contract']
 if os.environ.get('PPP_TEST_ASSERT_WRITER_SEPARATION'):
  with (path.parents[2]/'writer.lock').open('a') as lease: fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 proof=list(req['evidence_sha256'])+(['launch-diff'] if os.environ.get('PPP_TEST_HEADLESS_READ_LAUNCH_DIFF') and req['launch_diff'].get('path') else [])
 report=dict(source_state='Test independently inspected fixture '+str(s['cycle']),safe=True,halt_reason=None,actions=[],blockers=[],resolutions=[],grants=[],criteria={},reconciliation=dict(fresh=True,approvals_applicable=True,evidence_refs=proof,operations=[]))
 verified={}
 for aid,a in s['actions'].items():
  output=Path(aid+'.txt')
  verified[aid]=output.is_file() and output.read_text()=='Test independently inspectable '+aid
  selected=next((r for r in s['consumption'] if aid in r.get('action_ids',[r['action_id']]) and not r.get('assessment') and not r.get('not_started')),None)
  attempt=None; experiment=None
  if selected and not os.environ.get('PPP_TEST_OMIT_ASSESSMENT'):
   attempt=dict(strategy='Test inspect source and retained ordinary tests',state_before='Test cycle '+str(selected['cycle']),outcome='Test observed result',fingerprint='Test-cycle-'+str(selected['cycle']),assessment='verified' if verified[aid] else 'informative',evidence_refs=proof)
   if os.environ.get('PPP_TEST_CORRECTIONS') and selected['cycle']<=int(os.environ['PPP_TEST_CORRECTIONS']):
    verified[aid]=False
    attempt['assessment']='informative'
    experiment=dict(hypothesis='Test concrete requested output defect',material_difference='Test distinct fix '+str(selected['cycle']),expected_evidence='Test corrected output',next_step='Test repair actual output defect',fingerprint='Test-fix-'+str(selected['cycle']),evidence_refs=proof)
   removed=[name for name,row in (req.get('launch_diff') or {}).get('files',{}).items() if row.get('removed_lines')]
   if os.environ.get('PPP_TEST_LAUNCH_DIFF_FAIL') and removed and selected['cycle']==1:
    verified[aid]=False; attempt['assessment']='informative'
    experiment=dict(hypothesis='Test Worker removed user launch lines in '+removed[0],material_difference='Test restore user lines',expected_evidence='Test launch diff without removed lines',next_step='Test restore removed user lines in '+removed[0],fingerprint='Test-restore-user-lines',evidence_refs=['launch-diff'])
   if os.environ.get('PPP_TEST_GOAL_BUDGET_LIMIT') and not verified[aid]:
    experiment=dict(hypothesis='Test unfinished output before budget boundary',material_difference='Test complete retained partial output',expected_evidence='Test requested output',next_step='Test finish output',fingerprint='Test-budget-'+str(selected['cycle']),evidence_refs=proof)
  judgment=dict(action={k:a[k] for k in ('id','description','depends_on','operations')},status='verified' if verified[aid] else 'pending',eligible=True,scope_authorized=True,dependencies_valid=True,evidence_refs=proof,attempt=attempt,experiment=experiment)
  if selected and os.environ.get('PPP_TEST_UNFINISHED') and selected['cycle']<=int(os.environ['PPP_TEST_UNFINISHED']):
   verified[aid]=False; judgment.update(status='pending',experiment=None,continuation=dict(next_step='Test finish remaining requested content '+str(selected['cycle']),evidence_refs=proof)); attempt['assessment']='informative'
  if s.get('sessions') and s['sessions'][-1].get('action_ids') and selected and not verified[aid] and not judgment.get('continuation') and not judgment['experiment'] and not os.environ.get('PPP_TEST_CLAIM_ONLY') and not os.environ.get('PPP_TEST_WRONG_OUTPUT'):
   judgment['continuation']=dict(next_step='Test finish absent requested output '+aid,evidence_refs=proof)
  report['actions'].append(judgment)
 for cid in contract['criteria']:
  aid=cid.removesuffix('_ok')
  status='pass' if verified.get(aid) else 'fail' if Path(aid+'.txt').exists() else 'not_tested'
  if os.environ.get('PPP_TEST_UNKNOWN'): status='unknown'
  report['criteria'][cid]=dict(status=status,evidence_refs=proof)
 if os.environ.get('PPP_TEST_UNKNOWN'):
  for row in report['actions']:
   if row['attempt']: row.update(status='pending',experiment=None); row.pop('continuation',None); row['attempt']['assessment']='informative'
 if os.environ.get('PPP_TEST_BLOCKER'):
  if not s['blockers']:
   report['blockers']=[dict(blocker=dict(key='Test-runtime',reason='missing_secret',needed='Configure Test runtime securely',blocked_actions=['email']),evidence_refs=proof)]
   if os.environ.get('PPP_TEST_SECOND_BLOCKER'): report['blockers'].append(dict(blocker=dict(key='Test-access',reason='missing_access',needed='Provide Test service access',blocked_actions=['email']),evidence_refs=proof))
  for bid,bl in s['blockers'].items():
   for hid,h in s['human'].items():
    if h['kind']=='resolution' and not h['processed'] and bid in h['blocker_ids']:
     report['resolutions'].append(dict(blocker_id=bid,human_id=hid,valid=Path('Test-secure-configured').exists(),approval_applicable=False,evidence_refs=proof))
 for resolution in report['resolutions']:
  if resolution['valid']:
   for row in report['actions']:
    if row['action']['id'] in s['blockers'][resolution['blocker_id']]['blocked_actions'] and row['status']!='verified':
     row['experiment']=dict(hypothesis='Test finish work after actual access restoration',material_difference='Test validated human resolution '+resolution['human_id'],expected_evidence='Test requested output',next_step='Test complete unblocked work',fingerprint='Test-resolved-'+resolution['human_id'],evidence_refs=proof)
 for hid,h in s['human'].items():
  if h['kind']=='grant' and not h['processed']: report['grants'].append(hid)
 for oid,op in s['operations'].items():
  outcome='succeeded' if Path('Test-effect-performed').exists() else 'not_performed'
  if os.environ.get('PPP_TEST_OUTCOME_CONFLICT'):
   if op['outcome']=='started':
    for row in report['actions']: row['eligible']=False; row['status']='pending' if row['action']['id']=='email' else row['status']
    report['wake']=dict(source='bounded-recheck',reference='Test inspect recorded outcome',at=time.time()+0.1)
   else: outcome='not_performed'
  report['reconciliation']['operations'].append(dict(id=oid,outcome=outcome,evidence_refs=proof))
 if os.environ.get('PPP_TEST_RECHECK') and ctx['phase']=='checkpoint' and s['cycle']==1:
  for row in report['actions']: row['eligible']=False
  report['wake']=dict(source='bounded-recheck',reference='Test one arranged resource recheck',at=time.time()+1)
 if os.environ.get('PPP_TEST_RESOURCE') and not Path('Test-resource-restored').exists():
  for row in report['actions']: row['eligible']=False
  report['wake']=dict(source='resource-signal',reference='Test-arranged-restoration',at=None)
 return report

def request(message):
 match=re.search(r'Read (.+?/reviews/v2-\d+/request.json),',message)
 return Path(match.group(1)) if match else None

def emit(x): print(json.dumps(x),flush=True)
if Path(sys.argv[0]).name=='codex':
 message=sys.argv[sys.argv.index('--message')+1]; path=request(message)
 if path is None:
  with Path('Test-codex-notices.jsonl').open('a') as f: f.write(json.dumps({'Test-message':message})+'\n')
  print('Test queued notification'); sys.exit(1 if os.environ.get('PPP_TEST_FAIL_FINAL') and ': finish;' in message else 0)
 req=json.loads(path.read_text())
 Path(f'Test-review-prompt-{req["review_id"]}.md').write_text(message)
 with Path('Test-dispatch.jsonl').open('a') as f: f.write(json.dumps({'review':req['review_id'],'cycle':req['cycle']})+'\n')
 if os.environ.get('PPP_TEST_REVIEW_UNAVAILABLE') or (os.environ.get('PPP_TEST_REVIEW_UNAVAILABLE_FROM_CYCLE') and req['cycle']>=int(os.environ['PPP_TEST_REVIEW_UNAVAILABLE_FROM_CYCLE'])): sys.exit(2)
 if os.environ.get('PPP_TEST_NO_REVIEW'): sys.exit(0)
 decision='stop' if os.environ.get('PPP_TEST_REVIEW_REJECT') else 'endorse'
 cmd=[sys.executable,os.environ['PPP_TEST_BRIDGE'],'review-v2','--config',str(path.parents[2]/'config.json'),'--decision',decision,'--feedback','Test independent review']
 if decision=='endorse': cmd+=['--assessment',json.dumps(assessment(req,path))]
 subprocess.run(cmd,check=True)
 if os.environ.get('PPP_TEST_MUTATE_REVIEW'):
  target=path.with_name('review.json'); value=json.loads(target.read_text()); value['request_sha256']='Test-forged'; target.write_text(json.dumps(value))
 sys.exit(0)
if '--tools' in sys.argv and sys.argv[sys.argv.index('--tools')+1]=='read':
 if os.environ.get('PPP_TEST_EXTENSIONS'):
  assert [sys.argv[i+1] for i,x in enumerate(sys.argv[:-1]) if x=='-e']==[os.environ['PPP_TEST_REVIEW_EXTENSION']]
 session=sys.argv[sys.argv.index('--session-id')+1]; provider=sys.argv[sys.argv.index('--provider')+1]; model=sys.argv[sys.argv.index('--model')+1]
 turns=0; result=None
 for line in sys.stdin.buffer:
  cmd=json.loads(line); kind=cmd['type']
  if kind=='get_state':
   reviewer_file='Test-reviewer-session.jsonl'
   if os.environ.get('PPP_TEST_WORKER_USAGE'):
    reviewer_file=str(Path(sys.argv[sys.argv.index('--session-dir')+1])/'Test-reviewer.jsonl')
    Path(reviewer_file).write_text(json.dumps(dict(type='session',id=session))+'\n'+json.dumps(dict(type='message',message=dict(role='assistant',usage=dict(totalTokens=7))))+'\n')
   emit(dict(type='response',id=cmd['id'],success=True,data=dict(sessionId=session,sessionFile=reviewer_file,model=dict(provider=provider,id='Test-wrong-model' if os.environ.get('PPP_TEST_HEADLESS_WRONG_MODEL') else model)))); continue
  if kind=='get_last_assistant_text':
   if os.environ.get('PPP_TEST_HEADLESS_ERROR')=='rpc':
    emit(dict(type='response',id=cmd['id'],command=kind,success=False,error='Test-private-provider-detail')); continue
   malformed=os.environ.get('PPP_TEST_HEADLESS_BAD_JSON') or (os.environ.get('PPP_TEST_HEADLESS_REPAIR_MALFORMED') and turns==1) or (os.environ.get('PPP_TEST_HEADLESS_BAD_JSON_AFTER_WORKER') and req['cycle']>0) or (os.environ.get('PPP_TEST_HEADLESS_ERROR')=='malformed_then_error' and turns==1)
   absent=os.environ.get('PPP_TEST_HEADLESS_ERROR') in {'http400','transport','retry_exhausted'} or (os.environ.get('PPP_TEST_HEADLESS_ERROR')=='malformed_then_error' and turns>1)
   emit(dict(type='response',id=cmd['id'],success=True,data={} if absent else dict(text='Test malformed' if malformed else json.dumps(result)))); continue
  emit(dict(type='response',id=cmd['id'],success=True,data=dict(disposition='started')))
  if kind!='prompt': continue
  turns+=1; parsed=request(cmd['message'])
  if parsed: path=parsed; req=json.loads(path.read_text())
  path.with_name(f'Test-reviewer-prompt-{req["review_id"]}.txt').write_text(cmd['message'])
  with path.with_name(f'Test-reviewer-prompts-{req["review_id"]}.jsonl').open('a') as log: log.write(json.dumps(cmd['message'])+'\n')
  result=dict(decision='endorse',feedback='Test independent headless review',assessment=assessment(req,path))
  if not os.environ.get('PPP_TEST_HEADLESS_NO_IDS'): result.update(run_id=req['run_id'],cycle=req['cycle'],review_id=req['review_id'],state_sha256=req['state_sha256'],request_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
  if os.environ.get('PPP_TEST_HEADLESS_WRONG_HASH'): result['request_sha256']='Test-forged'
  if os.environ.get('PPP_TEST_HEADLESS_STOP'): result=dict(decision='stop',feedback='Test explicit stop')
  if os.environ.get('PPP_TEST_HEADLESS_HALT'): result=dict(decision='halt',feedback='Test concrete safety concern')
  if os.environ.get('PPP_TEST_HEADLESS_HOLD'):
   path.with_name('Test-reviewer-prompt-started').write_text('Test accepted prompt'); time.sleep(30)
  selected=os.environ.get('PPP_TEST_HEADLESS_READ_REFERENCE')
  material_reads=os.environ.get('PPP_TEST_HEADLESS_MATERIAL_READS')
  reads=[(value,False) for value in [str(path),str(path.with_name('context.json')),str(path.parents[2]/'TASK.md')]+list(req['evidence_archive'].values()) if not (material_reads and value==req['evidence_archive'][selected])]
  if os.environ.get('PPP_TEST_HEADLESS_READ_LAUNCH_DIFF') and req['launch_diff'].get('path'): reads.append((req['launch_diff']['path'],os.environ['PPP_TEST_HEADLESS_READ_LAUNCH_DIFF']=='error'))
  if material_reads:
   for item in material_reads.split(','):
    if item=='none': continue
    location,outcome=item.split('-')
    value=str((Path.cwd()/selected).resolve()) if location=='original' else req['evidence_archive'][selected]
    reads.append((value,outcome=='error'))
  for index,(value,injected_failure) in enumerate(reads):
   if os.environ.get('PPP_TEST_HEADLESS_SKIP_READS'): continue
   if os.environ.get('PPP_TEST_HEADLESS_AT_READS'): value='@'+(os.path.relpath(value,Path.cwd()) if os.environ['PPP_TEST_HEADLESS_AT_READS']=='relative' else value)
   emit(dict(type='tool_execution_start',toolCallId='Test-read-'+str(index),toolName='read',args=dict(path=value)))
   failed=injected_failure or (os.environ.get('PPP_TEST_HEADLESS_FAIL_CITED_READ') and value.removeprefix('@') in req['evidence_archive'].values()) or (os.environ.get('PPP_TEST_HEADLESS_FAIL_TASK_READ') and Path(value.removeprefix('@')).name=='TASK.md')
   emit(dict(type='tool_execution_end',toolCallId='Test-read-'+str(index),toolName='read',isError=bool(failed),result=dict(content=[dict(type='text',text='Test material read unavailable' if failed else Path(value.removeprefix('@')).read_text())])))
  fault=os.environ.get('PPP_TEST_HEADLESS_ERROR')
  if fault in {'http400','transport','retry_exhausted','retry_recovered'} or (fault=='malformed_then_error' and turns>1):
   error='Test connection terminated' if fault=='transport' else 'HTTP 400 Test-private-provider-detail'
   emit(dict(type='message_end',message=dict(role='assistant',content=[],stopReason='error',errorMessage=error)))
   emit(dict(type='agent_end',messages=[],willRetry=fault in {'retry_exhausted','retry_recovered'}))
   if fault in {'retry_exhausted','retry_recovered'}:
    emit(dict(type='auto_retry_start',attempt=1,maxAttempts=1,delayMs=1,errorMessage=error))
    emit(dict(type='message_end',message=dict(role='assistant',content=[],stopReason='stop' if fault=='retry_recovered' else 'error',errorMessage=error)))
    emit(dict(type='auto_retry_end',success=fault=='retry_recovered',attempt=1,finalError=error))
  else:
   emit(dict(type='message_end',message=dict(role='assistant',content=[dict(type='text',text=json.dumps(result))],stopReason='stop')))
  emit(dict(type='agent_settled',aborted=False))
 sys.exit(0)
initial_cwd=Path.cwd()
if os.environ.get('PPP_RALPH_GUARDS'): Path(os.environ['PPP_RALPH_GUARDS'],'host.json').write_text(json.dumps(dict(pid=os.getpid(),cleanup_supported=True)))
if '--session-dir' in sys.argv: os.chdir(Path(sys.argv[sys.argv.index('--session-dir')+1]).parent/'work')
session_id=sys.argv[sys.argv.index('--session-id')+1] if '--session-id' in sys.argv else 'Test-default-session'
with Path('Test-worker-session-ids.jsonl').open('a') as log: log.write(json.dumps(session_id)+'\n')
goal_token_path=Path('Test-goal-token-'+session_id+'.txt')
goal_tokens_used=int(goal_token_path.read_text()) if goal_token_path.exists() else 0
goal_id_path=Path('Test-goal-id.txt')
goal_id=int(goal_id_path.read_text()) if goal_id_path.exists() else 0
goal_budget_path=Path('Test-goal-budget-limited.txt')
worker_config=json.loads((Path.cwd().parent/'config.json').read_text())
if os.environ.get('PPP_TEST_EXTENSIONS'):
 extensions=[sys.argv[i+1] for i,x in enumerate(sys.argv[:-1]) if x=='-e']
 assert extensions[-1:]==[os.environ['PPP_TEST_WORKER_EXTENSION']]
 assert os.environ['PPP_TEST_REVIEW_EXTENSION'] not in extensions
elif worker_config['mode']=='ping-pong': assert '-e' not in sys.argv
goal_token_budget=worker_config.get('goal_tokens')
goal_status_path=Path('Test-goal-status.txt')
goal_status=goal_status_path.read_text() if goal_status_path.exists() else 'active'
session_path=Path.cwd().parent/'sessions'/('Test-'+session_id+'.jsonl')
if not session_path.exists(): session_path.write_text(json.dumps(dict(type='session',version=3,id=session_id,cwd=str(initial_cwd)))+'\n')
def persist_goal():
 goal_status_path.write_text(goal_status)
 goal=dict(id=f'Test-goal-{goal_id}',status=goal_status,tokensUsed=goal_tokens_used,tokenBudget=goal_token_budget)
 with session_path.open('a') as log:
  log.write(json.dumps(dict(type='custom',customType='goal-state',data=dict(goal=goal)))+'\n')
  if os.environ.get('PPP_TEST_GOAL_TOMBSTONE') and goal_status in {'complete','active'}:
   log.write(json.dumps(dict(type='custom',customType='goal-state',data=dict(goal=None)))+'\n')
   log.write(json.dumps(dict(type='message',message=dict(role='toolResult',toolName='goal_complete',isError=False,details=dict(goal_id=goal['id']),content=[dict(type='text',text='Goal complete: Test native result')])) )+'\n')
   if os.environ.get('PPP_TEST_GOAL_LATE_TURN'):
    # Live Claude Worker answered again after goal_complete; native tokensUsed excludes this turn.
    log.write(json.dumps(dict(type='message',timestamp=datetime.now(timezone.utc).isoformat(),message=dict(role='assistant',content=[dict(type='text',text='Test late answer')],usage=dict(totalTokens=5))))+'\n')
for line in sys.stdin.buffer:
 cmd = json.loads(line)
 if cmd['type'] == 'get_state':
  emit(dict(type='response', id=cmd['id'], success=True, data=dict(sessionFile=str(session_path)))); continue
 if cmd['type'] == 'get_entries':
  goal=dict(id=f'Test-goal-{goal_id}',status=goal_status,tokensUsed=goal_tokens_used,tokenBudget=goal_token_budget,iteration=goal_tokens_used//17)
  entries=[json.loads(line) for line in session_path.read_text().splitlines()] if os.environ.get('PPP_TEST_GOAL_TOMBSTONE') else [dict(type='custom',customType='goal-state',data=dict(goal=goal))]
  emit(dict(type='response', id=cmd['id'], success=True, data=dict(entries=entries))); continue
 emit(dict(type='response', id=cmd['id'], success=True, data=dict(disposition='started')))
 if cmd['type'] != 'prompt': continue
 if cmd['message'].startswith('/goal ') and goal_id and goal_status!='complete':
  emit(dict(type='extension_ui_request',id='Test-replace',method='confirm',title='Replace goal?'))
  answer=json.loads(sys.stdin.buffer.readline())
  if answer != dict(type='extension_ui_response',id='Test-replace',confirmed=True): sys.exit(4)
  Path('Test-goal-replacement-confirmed').write_text('Test confirmed only after budget grant')
 emit(dict(type='agent_start'))
 if cmd['message'].startswith('/goal '):
  goal_id += 1
  goal_id_path.write_text(str(goal_id))
  goal_tokens_used=0
  goal_status='active'
  token_match=re.search(r'--tokens (\d+)',cmd['message'])
  goal_token_budget=int(token_match.group(1)) if token_match else None
  goal_token_path.write_text('0')
 with Path('Test-worker-prompts.jsonl').open('a') as log: log.write(json.dumps(cmd['message'])+'\n')
 if os.environ.get('PPP_TEST_WORKER_USAGE'):
  with session_path.open('a') as log:
   log.write(json.dumps(dict(type='message',message=dict(role='assistant',content=[],usage=dict(input=3,output=4,cacheRead=10,cacheWrite=2,totalTokens=19))))+'\n')
   if os.environ['PPP_TEST_WORKER_USAGE']=='torn': log.write('{"type":"message","message":{"role":"assist\n')
 ctx = json.loads(Path('cycle-context.json').read_text()); aid = ctx['action_id']
 with Path('Test-worker-contexts.jsonl').open('a') as log: log.write(json.dumps(ctx)+'\n')
 repairing = (ctx.get('feedback') or '').startswith('Core rejected your checkpoint:')
 if os.environ.get('PPP_TEST_CHECKPOINT_REPAIR_TRACKING'):
  checkpoint = Path('checkpoint.json')
  if repairing:
   Path('Test-repair-checkpoint-original').write_bytes(checkpoint.read_bytes())
  else:
   count_path = Path('Test-product-test-executions')
   count_path.write_text(str(int(count_path.read_text()) + 1 if count_path.exists() else 1))
   if ctx['cycle'] == 2: Path('Test-next-action-saw-stale-checkpoint').write_text(str(checkpoint.exists()))
 if os.environ.get('PPP_TEST_NATIVE_GOAL'):
  assert 'goal_wait for' not in cmd['message']
  assert 'Never self-call goal_complete' not in Path('../CONTRACT.md').read_text()
  for item in ctx['action_ids']:
   if os.environ.get('PPP_TEST_NATIVE_GOAL_DELAY'): time.sleep(float(os.environ['PPP_TEST_NATIVE_GOAL_DELAY']))
   if not (os.environ.get('PPP_TEST_BLOCKER') and item=='email' and not Path('Test-secure-configured').exists()): Path(item+'.txt').write_text('Test independently inspectable '+item)
   emit(dict(type='agent_settled',aborted=False))
   query=json.loads(sys.stdin.buffer.readline())
   assert query['type']=='get_entries'
   emit(dict(type='response',id=query['id'],success=True,data=dict(entries=[dict(type='custom',customType='goal-state',data=dict(goal=dict(id=f'Test-goal-{goal_id}',status='active',tokensUsed=goal_tokens_used,tokenBudget=goal_token_budget)))])))
   emit(dict(type='agent_start'))
 product_cwd=Path(json.loads((Path.cwd().parent/'execution-state.json').read_text())['worker_cwd'])
 if os.environ.get('PPP_TEST_PROJECT_CWD'):
  work = Path.cwd().resolve()
  assert os.environ['PPP_WORK_DIR'] == str(work)
  assert os.environ['PPP_CHECKPOINT_PATH'] == str(work/'checkpoint.json')
  assert os.environ['PPP_CONTEXT_PATH'] == str(work/'cycle-context.json')
  assert os.environ['PPP_TARGET'] == json.loads((work.parent/'config.json').read_text())['execution_contract']['target']
  (product_cwd/'Test-shell-created.txt').write_text('Test shell-created product, not a tool reference')
  if os.environ.get('PPP_TEST_REWRITE_USER'): (product_cwd/os.environ['PPP_TEST_REWRITE_USER']).write_text('# Test paraphrased user note\ndef f():\n    return 1\n')
 if os.environ.get('PPP_TEST_BROWSER_RUNTIME'):
  assert os.environ['PPP_PLAYWRIGHT_MODULE']==str((Path.cwd().parent/'node_modules/playwright/index.js').resolve())
 if os.environ.get('PPP_TEST_GOAL_TIMEOUT'):
  goal_tokens_used += 148808
  goal_token_path.write_text(str(goal_tokens_used))
  Path(aid+'.txt').write_text('Test independently inspectable '+aid)
  persist_goal()
  time.sleep(30)
 budget_limited = os.environ.get('PPP_TEST_GOAL_BUDGET_LIMIT') in ({'1', aid} | (set(ctx.get('action_ids',[])) if os.environ.get('PPP_TEST_NATIVE_GOAL') else set()))
 if (os.environ.get('PPP_TEST_EFFECT') or os.environ.get('PPP_TEST_JOURNAL')) and aid == 'email':
  operation=subprocess.run([sys.executable, os.environ['PPP_TEST_BRIDGE'], 'operation', '--config', str(Path.cwd().parent/'config.json'), '--action-id', aid, '--operation-id', 'send', '--owner', ctx['owner']], check=False, stdout=sys.stderr)
  if operation.returncode == 0:
   Path('Test-effect-performed').write_text('Test synthetic external sink outcome')
  else:
   Path('Test-operation-replay-refused').write_text('Test stable operation reservation refused a replay')
  if os.environ.get('PPP_TEST_EFFECT'): time.sleep(30)
 if not repairing and not os.environ.get('PPP_TEST_CLAIM_ONLY') and not (os.environ.get('PPP_TEST_BLOCKER') and aid=='email' and not Path('Test-secure-configured').exists()):
  Path(aid+'.txt').write_text('Test wrong product' if os.environ.get('PPP_TEST_WRONG_OUTPUT') else 'Test independently inspectable '+aid)
 if not repairing:
  Path('Test-tests.txt').write_text('Test ordinary assertions: exit=0; inspect requested output')
 Path('Test-worker-claim.txt').write_text('Test worker says ready; not independent proof')
 cp = dict(protocol_version=2,schema_version=1,run_id=ctx['run_id'],cycle=ctx['cycle'],action_id=aid,status='ready',summary='Test worker claim',evidence=['Test-worker-claim.txt'] if os.environ.get('PPP_TEST_CLAIM_ONLY') else ([aid+'.txt'] if Path(aid+'.txt').exists() else [])+['Test-tests.txt'])
 if os.environ.get('PPP_TEST_NATIVE_GOAL'): cp['evidence'] += [item+'.txt' for item in ctx['action_ids'] if item!=aid]
 if os.environ.get('PPP_TEST_PROJECT_CWD'): cp['evidence'].append(str(product_cwd/'Test-shell-created.txt'))
 if os.environ.get('PPP_TEST_HEADLESS_READ_REFERENCE') and Path(os.environ['PPP_TEST_HEADLESS_READ_REFERENCE']).is_absolute(): cp['evidence'].append(os.environ['PPP_TEST_HEADLESS_READ_REFERENCE'])
 if os.environ.get('PPP_TEST_BAD_CHECKPOINT') and ctx['cycle'] == int(os.environ.get('PPP_TEST_BAD_CHECKPOINT_CYCLE', '1')) and (os.environ['PPP_TEST_BAD_CHECKPOINT']=='always' or ctx.get('worker_attempt',1) <= int(os.environ['PPP_TEST_BAD_CHECKPOINT'] if os.environ['PPP_TEST_BAD_CHECKPOINT'].isdigit() else '1')): cp['evidence']=['../TASK.md']
 if os.environ.get('PPP_TEST_BAD_CHECKPOINT_SCHEMA') and ctx.get('worker_attempt',1) == 1: cp.pop('schema_version')
 if os.environ.get('PPP_TEST_WRONG_CHECKPOINT_ID') == 'missing' and ctx.get('worker_attempt',1) == 1: cp = dict(cycle=ctx['cycle'],note='Test worker note without run identity',files=[aid+'.txt'])
 elif os.environ.get('PPP_TEST_WRONG_CHECKPOINT_ID') and os.environ['PPP_TEST_WRONG_CHECKPOINT_ID'] != 'missing' and ctx['cycle'] == 1: cp['run_id']='Test-wrong-run'
 if budget_limited:
  def record_message(message):
   with session_path.open('a') as log: log.write(json.dumps(dict(type='message',timestamp=datetime.now(timezone.utc).isoformat(),message=message))+'\n')
  test_path=Path('Test-budget-check.py')
  test_path.write_text('import unittest\nfrom pathlib import Path\nclass TestOutput(unittest.TestCase):\n def test_exists(self): self.assertTrue(Path('+repr(aid+'.txt')+').is_file())\nunittest.main()\n')
  outputs=[str(Path(aid+'.txt').resolve()),str(test_path.resolve())]
  if os.environ.get('PPP_TEST_TARGET_OUTPUT'):
   target_path=Path(os.environ['PPP_TEST_TARGET_OUTPUT']); target_path.write_text('Test scoped target deliverable'); outputs.append(str(target_path))
  for index,output in enumerate(outputs):
   record_message(dict(role='assistant',content=[dict(type='toolCall',id='Test-write-'+str(index),name='write',arguments=dict(path=output,content='Test omitted from evidence transcript'))]))
   record_message(dict(role='toolResult',toolCallId='Test-write-'+str(index),toolName='write',content=[dict(type='text',text='Test wrote output')],isError=False))
  command=sys.executable+' Test-budget-check.py'
  record_message(dict(role='assistant',content=[dict(type='toolCall',id='Test-ordinary-tests',name='bash',arguments=dict(command=command))]))
  if not os.environ.get('PPP_TEST_INCOMPLETE_COMMAND'):
   checked=subprocess.run([sys.executable,str(test_path)],capture_output=True,text=True)
   Path('Test-tests.txt').write_text(checked.stdout+checked.stderr)
   record_message(dict(role='toolResult',toolCallId='Test-ordinary-tests',toolName='bash',content=[dict(type='text',text=checked.stdout+checked.stderr)],isError=checked.returncode!=0))
 if not budget_limited and os.environ.get('PPP_TEST_CHECKPOINT_HELPER'):
  subprocess.run([sys.executable,os.environ['PPP_CHECKPOINT_CMD'],'--status',cp['status'],'--summary',cp['summary'],'--next-step','Test next']+['work/'+name for name in cp['evidence']],check=True,stdout=sys.stderr)
 elif not budget_limited:
  Path('checkpoint.json').write_text(json.dumps(cp))
  if os.environ.get('PPP_TEST_CHECKPOINT_REPAIR_TRACKING') and not repairing and ctx['cycle'] == 1:
   Path('Test-rejected-checkpoint-expected').write_bytes(Path('checkpoint.json').read_bytes())
 if cmd['message'].startswith('/ralph'):
  directory=(initial_cwd/shlex.split(cmd['message'].split('--path ',1)[1])[0]).resolve(); task=directory/'RALPH.md'
  grant=int(re.search(r'max_iterations: (\d+)',task.read_text()).group(1))
  iterations=min(grant,int(os.environ.get('PPP_TEST_RALPH_ITERATIONS','1')))
  out=directory/'.ralph-runner/status.json'; out.parent.mkdir(parents=True,exist_ok=True)
  state=dict(ralphPath=str(task),taskDir=str(directory),cwd=str(initial_cwd),currentIteration=iterations,maxIterations=grant,status='running',loopToken='Test-token-'+str(ctx['cycle']))
  out.write_text(json.dumps(state))
  if os.environ.get('PPP_TEST_RALPH_TOKENS'):
   usage=Path(os.environ['PPP_RALPH_GUARDS'])/'usage.json'; pending=usage.with_suffix('.tmp')
   pending.write_text(json.dumps(dict(host=os.getpid(),dispatch=os.environ['PPP_RALPH_USAGE_DISPATCH'],loop_token=state['loopToken'],tokens=37)))
   pending.chmod(0o600); pending.replace(usage)
  if os.environ.get('PPP_TEST_RALPH_HOLD'): time.sleep(30)
  for item in ctx.get('action_ids',[aid]):
   if not os.environ.get('PPP_TEST_CLAIM_ONLY') and not (os.environ.get('PPP_TEST_BLOCKER') and item=='email' and not Path('Test-secure-configured').exists()): Path(item+'.txt').write_text('Test wrong product' if os.environ.get('PPP_TEST_WRONG_OUTPUT') else 'Test independently inspectable '+item)
  cp['evidence'] += [item+'.txt' for item in ctx.get('action_ids',[]) if item!=aid and Path(item+'.txt').exists()]
  if not os.environ.get('PPP_TEST_RALPH_NO_CHECKPOINT'): Path('checkpoint.json').write_text(json.dumps(cp))
  else: Path('checkpoint.json').unlink(missing_ok=True)
  if os.environ.get('PPP_TEST_RALPH_EXIT'): sys.exit(7)
  state.update(completedAt='Test-now',status=os.environ.get('PPP_TEST_RALPH_STATUS','complete'))
  temporary=out.with_suffix('.tmp'); temporary.write_text(json.dumps(state)); temporary.replace(out)
 elif cmd['message'].startswith('/goal ') or goal_id:
  goal_tokens_used += goal_token_budget if budget_limited and os.environ.get('PPP_TEST_NATIVE_GOAL') and goal_token_budget else 17
  goal_token_path.write_text(str(goal_tokens_used))
  goal_status=os.environ.get('PPP_TEST_GOAL_NATIVE_STOP') or ('budget_limited' if budget_limited or os.environ.get('PPP_TEST_GOAL_RENEWAL') and goal_token_budget is not None and goal_tokens_used>=goal_token_budget else 'complete')
  persist_goal()
  crash=Path('Test-crashed-'+str(ctx['cycle']))
  if os.environ.get('PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT') and ctx['cycle']==int(os.environ.get('PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT_CYCLE','1')) and not crash.exists():
   crash.touch(); os.kill(os.getppid(),9); break
  if os.environ.get('PPP_TEST_GOAL_COMPACTION'):
   emit(dict(type='compaction_end',tokensBefore=10000,tokensAfter=1000))
  if budget_limited:
   goal_budget_path.write_text('budget_limited')
   emit(dict(type='agent_settled',aborted=True))
   continue
  emit(dict(type='tool_execution_end',toolName='goal_blocked' if goal_status=='blocked' else 'goal_complete',isError=False,result=dict(content=[dict(type='text',text=('Goal blocked: ' if goal_status=='blocked' else 'Goal complete: ')+'Test native result, not acceptance')])) )
 emit(dict(type='agent_settled',aborted=False))
'''

def fixture_assessment(request, path):
    # Execute only the synthetic read-only response builder, never a task evaluator.
    namespace = {}
    exec(FAKE.split("if Path(sys.argv[0]).name=='codex':", 1)[0], namespace)
    cwd = os.getcwd()
    try:
        os.chdir(path.parents[2] / 'work')
        return namespace['assessment'](request, path)
    finally:
        os.chdir(cwd)


def git_project(path, files, dirty):
    """Synthetic committed project with uncommitted user edits; returns read-only Git state probe."""
    path.mkdir(parents=True, exist_ok=True)

    def run(*args):
        subprocess.run(['git', '-c', 'user.name=Test User', '-c', 'user.email=test@example.invalid', *args], cwd=path, check=True, capture_output=True)
    run('init', '-q')
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    run('add', '.')
    run('commit', '-qm', 'Test initial')
    for name, text in dirty.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    return lambda: ((path / '.git/index').read_bytes(), subprocess.run(['git', 'for-each-ref'], cwd=path, capture_output=True).stdout,
                    (path / '.git/HEAD').read_bytes(), sorted(str(f) for f in (path / '.git').rglob('*.lock')))


class Bridge2Tests(unittest.TestCase):
    def fixture(self, root, mode='ping-pong', blocker=False, effect=False, cycles=2):
        tools = root / 'bin'
        tools.mkdir()
        for name in ('pi', 'codex'):
            path = tools / name
            path.write_text(FAKE)
            path.chmod(0o700)
        c = config()
        c.update(mode=mode, thread_id='Test-thread', worker_provider='Test-provider', worker_model='Test-worker', review_model='Test-reviewer', review_transport='codex', human_transport='pi', pi_session_id='Test-human-session', task='TASK.md', cycle_seconds=5, review_seconds=5, wall_seconds=10, max_cycles=cycles)
        c['execution_contract']['actions'] = c['execution_contract']['actions'][:2]
        if effect:
            c['execution_contract']['actions'][1]['operations'] = [dict(id='send', kind='Test-send', target='Test fake sink')]
        (root / 'TASK.md').write_text('Test authorized fixture outputs and synthetic sink; never real mail.')
        (root / 'TASK.md').chmod(0o600)
        p.durable(root / 'config.json', c)
        p.durable(root / 'pi-receiver.json', dict(run_id=c['run_id'], session_id='Test-human-session'))
        env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH'], 'PPP_TEST_BRIDGE': str(HERE / 'bridge.py')}
        if blocker:
            env['PPP_TEST_BLOCKER'] = '1'
        if effect:
            env['PPP_TEST_EFFECT'] = '1'
        return c, env

    def launch(self, root, env, command='run'):
        log = (root / ('Test-' + command + '.log')).open('wb')
        self.addCleanup(log.close)
        proc = subprocess.Popen([sys.executable, '-B', str(HERE / 'bridge.py'), command, '--config', str(root / 'config.json')], env=env, stdout=log, stderr=log)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def test_browser_runtime_is_shared_by_both_workers_and_ordinary_tests(self):
        for mode in ('goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, env = self.fixture(root, mode=mode)
                (root / 'TASK.md').write_text('Test browser task using project-installed Playwright')
                module = root / 'node_modules/playwright/index.js'
                module.parent.mkdir(parents=True)
                module.write_text('module.exports = {chromium: {launch() {throw Error("Test never launch browser")}}};')
                env.update(PPP_TEST_BROWSER_RUNTIME='1', PPP_PLAYWRIGHT_MODULE='')
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                self.assertIn(str(module), (root / 'CONTRACT.md').read_text())
                self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'finish')

    def test_native_ralph_multi_iteration_full_scope_has_one_post_loop_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ralph', cycles=4)
            env.update(PPP_TEST_RALPH_ITERATIONS='3', PPP_TEST_ASSERT_WRITER_SEPARATION='1', PPP_TEST_RALPH_TOKENS='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
            self.assertEqual(state['consumption'][0]['action_ids'], ['email', 'footer'])
            self.assertEqual(state['consumption'][0]['worker_iterations'], 3)
            self.assertEqual(len(state['consumption'][0]['worker_iteration_grants']), 3)
            self.assertEqual(state['sessions'][0]['ralph_max_iterations'], 4)
            self.assertEqual(state['sessions'][0]['ralph_usage_status'], 'known')
            status = b.read(root / 'bridge-status.json')
            self.assertEqual((status['worker_tokens'], status['worker_tokens_status']), (37, 'partial'))
            self.assertEqual(status['worker_tokens_by_action'], {state['sessions'][0]['action_id']: 37})
            self.assertEqual(state['worker_tokens'], 0, 'Does not charge the Goal ledger')
            self.assertEqual(set(state['acceptance'].values()), {'pass'})
            self.assertEqual(len((root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()), 1)
            native_task = (root / 'ralph/001/RALPH.md').read_text()
            self.assertIn('max_iterations: 4', native_task)
            promise = native_task.split('completion_promise: ')[1].splitlines()[0]
            self.assertIn('output <promise>' + promise + '</promise>', native_task)
            self.assertNotIn('End this one native Ralph iteration', (root / 'CONTRACT.md').read_text())
            self.assertIn('Save the actual results of explicitly requested tests', (root / 'CONTRACT.md').read_text())

    def test_native_ralph_usage_recovery_is_idempotent_and_identity_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ralph', cycles=5)
            env['PPP_TEST_RALPH_ITERATIONS'] = '3'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            core.reconcile_ralph_usage()
            core.reconcile_ralph_usage()
            state = core.store.read()
            self.assertEqual(state['consumption'][0]['worker_iterations'], 3)
            status = Path(state['sessions'][0]['ralph_path']).parent / '.ralph-runner/status.json'
            native = b.read(status)
            native['loopToken'] = 'Test-foreign-loop'
            p.durable(status, native)
            core.reconcile_ralph_usage()
            state = core.store.read()
            self.assertEqual(state['consumption'][0]['worker_iterations'], 3)
            self.assertIn('identity changed', state['sessions'][0]['ralph_usage_error'])

    def test_ralph_token_recovery_replaces_snapshot_and_rejects_foreign_or_broken_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, mode='ralph')
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            sessions = []
            for cycle, aid in enumerate(('email', 'footer', 'email'), 1):
                directory = root / f'Test-guard-{cycle}'
                directory.mkdir(mode=0o700)
                sessions.append(dict(action_id=aid, pid=42, ralph_usage_dispatch=f'Test-dispatch-{cycle}',
                                     ralph_loop_token=f'Test-loop-{cycle}', ralph_guards=str(directory)))
            with core.store.transaction(create=p.initial(core.c, {})) as state:
                state['sessions'] = sessions
            original = core.store.path.read_bytes()

            def record(session, tokens):
                return dict(dispatch=session['ralph_usage_dispatch'], loop_token=session['ralph_loop_token'], host=session['pid'], tokens=tokens)

            def project(tokens, status, actions):
                recovered = ab.ActionBridge(b.load_config(root / 'config.json'))
                recovered.project()
                result = b.read(root / 'bridge-status.json')
                self.assertEqual((result['worker_tokens'], result['worker_tokens_status'], result['worker_tokens_by_action']), (tokens, status, actions))
                self.assertEqual(recovered.store.path.read_bytes(), original, 'Recovery cannot mutate review-bound execution state')

            project(None, 'not_measured', {'email': None, 'footer': None})
            paths = [Path(row['ralph_guards']) / 'usage.json' for row in sessions]
            p.durable(paths[0], record(sessions[0], 11))
            p.durable(paths[0].with_suffix('.tmp'), record(sessions[0], 999))  # Unpublished crash residue.
            p.durable(paths[2], record(sessions[2], 20))
            for bad in ({'dispatch': 'Test-foreign'}, {'loop_token': 'Test-foreign'}, {'host': 41}, {'tokens': True}, {'tokens': -1}):
                p.durable(paths[1], {**record(sessions[1], 9), **bad})
                project(31, 'partial', {'email': 31, 'footer': None})
            paths[1].write_text('{')
            project(31, 'partial', {'email': 31, 'footer': None})
            paths[1].unlink()
            paths[1].symlink_to(paths[0])
            project(31, 'partial', {'email': 31, 'footer': None})
            p.durable(paths[0], record(sessions[0], 25))
            p.durable(paths[1], record(sessions[1], 0))
            self.assertEqual(ab.ralph_token_projection(root, [sessions[0], *sessions])['worker_tokens'], 45)
            project(45, 'partial', {'email': 45, 'footer': 0})
            project(45, 'partial', {'email': 45, 'footer': 0})

    def test_native_ralph_mixed_scope_window_and_release_use_both_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, _ = self.fixture(root, mode='ralph', cycles=5)
            c['execution_contract']['closure']['max_cycles'] = 2
            p.durable(root / 'config.json', c)
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            core.worker_cwd = root
            with core.store.transaction(create=p.initial(core.c, ab.pins(core.c))) as state:
                state['reconciled'] = True
                for action in state['actions'].values():
                    action['eligible'] = True
                controller = p.Controller(core.c, state)
                bid = controller.blocker(dict(key='Test-access', reason='missing_access', needed='Test restored access', blocked_actions=['email']), ['test-proof'])
                state['blockers'][bid]['status'] = 'resolved'
                controller.closure(state['actions']['email'], dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test restored access', evidence_refs=['test-proof']), ['test-proof'])
                controller.consume('footer', 'Test-owner')
                state['sessions'].append(dict(id='Test-native-session', cycle=1, action_id='footer', pid=None))
            core.prepare_ralph(dict(cycle=1, action_id='footer', feedback=None))
            state = core.store.read()
            session = state['sessions'][-1]
            self.assertEqual(session['ralph_max_iterations'], 2)
            self.assertEqual(state['consumption'][0]['worker_scope_grants'], {'closure': ['initial-closure'] * 2, 'main': ['initial-main'] * 2})
            task = Path(session['ralph_path'])
            p.durable(task.parent / '.ralph-runner/status.json', dict(ralphPath=str(task), taskDir=str(task.parent), cwd=session['ralph_cwd'], maxIterations=2, currentIteration=1, loopToken='Test-loop', completedAt='Test-now', status='complete'))
            core.reconcile_ralph_usage()
            core.reconcile_ralph_usage()
            state = core.store.read()
            controller = p.Controller(core.c, state)
            self.assertEqual((controller.remaining('main'), controller.remaining('closure')), (4, 1))
            self.assertEqual(state['consumption'][0]['worker_scope_grants'], {'closure': ['initial-closure'], 'main': ['initial-main']})

    def test_native_ralph_large_grant_respects_vendor_window_limit_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ralph', cycles=55)
            env['PPP_TEST_RALPH_ITERATIONS'] = '50'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['sessions'][0]['ralph_max_iterations'], 50)
            self.assertEqual(state['consumption'][0]['worker_iterations'], 50)
            self.assertEqual(p.Controller(b.load_config(root / 'config.json'), state).remaining('main'), 5)

    def test_native_ralph_corrections_use_only_remaining_cumulative_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='ralph', cycles=5)
            target = root.resolve() / 'Test-project'
            target.mkdir()
            c['execution_contract']['target'] = str(target)
            p.durable(root / 'config.json', c)
            env['PPP_TEST_UNFINISHED'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (3, 3))
            self.assertEqual([row['ralph_max_iterations'] for row in state['sessions']], [5, 4, 3])
            self.assertEqual(Path(state['sessions'][0]['ralph_path']), target / 'RALPH.md')
            self.assertEqual(b.digest(target / 'RALPH.md'), state['sessions'][-1]['ralph_task_sha256'])
            self.assertEqual(b.read(target / '.ralph-runner/status.json')['loopToken'], 'Test-token-3')
            self.assertTrue(all(Path(row['ralph_path']) == target / 'RALPH.md' for row in state['sessions']))
            for row in state['sessions'][:-1]:
                archive = Path(row['ralph_cwd'])
                self.assertEqual(b.digest(archive / 'native-task.md'), row['ralph_task_sha256'])
                self.assertEqual(b.read(archive / 'native-result.json')['loopToken'], row['ralph_loop_token'])
            self.assertEqual(sum(row['worker_iterations'] for row in state['consumption']), 3)
            self.assertFalse(any(row['type'] == 'worker.checkpoint_repair' for row in state['history']))
            self.assertIn('remaining requested content', b.read(root / 'work/cycle-context.json')['actions']['email']['continuation']['next_step'])

    def test_native_ralph_target_snapshot_storage_is_exclusive_and_dirty_work_preserved(self):
        for conflict in ('none', 'task', 'runner', 'symlink', 'quoted', 'unrepresentable'):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as tmp:
                label = "Test project 'quote'" if conflict == 'quoted' else "Test project 'both\"quotes'" if conflict == 'unrepresentable' else 'Test-project'
                project = Path(tmp).resolve() / label
                project.mkdir()
                (project / 'Test-dirty.txt').write_text('Test existing dirty work')
                task, runner = project / 'RALPH.md', project / '.ralph-runner'
                if conflict == 'task':
                    task.write_text('Test user native task')
                elif conflict == 'runner':
                    runner.mkdir()
                    (runner / 'status.json').write_text('Test preserve existing user runner')
                elif conflict == 'symlink':
                    (project / 'Test-user-task.md').write_text('Test symlink target')
                    task.symlink_to(project / 'Test-user-task.md')
                root = Path(tmp).resolve() / 'run'
                root.mkdir(mode=0o700)
                c, env = self.fixture(root, mode='ralph')
                c['execution_contract']['target'] = str(project)
                p.durable(root / 'config.json', c)
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                session = b.read(root / 'execution-state.json')['sessions'][0]
                self.assertEqual(Path(session['ralph_path']).parent, project if conflict in {'none', 'quoted'} else root / 'ralph/001')
                self.assertEqual(session['ralph_cwd'], str(root / 'ralph/001'))
                self.assertEqual((project / 'Test-dirty.txt').read_text(), 'Test existing dirty work')
                if conflict in {'none', 'quoted'}:
                    self.assertEqual(runner.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(task.stat().st_mode & 0o777, 0o600)
                    self.assertIn('.pi/ping-pong and .pi-ping-pong', session['ralph_snapshot_limitation'])
                elif conflict == 'task':
                    self.assertEqual(task.read_text(), 'Test user native task')
                    self.assertFalse(runner.exists())
                elif conflict == 'runner':
                    self.assertEqual((runner / 'status.json').read_text(), 'Test preserve existing user runner')
                    self.assertFalse(task.exists())
                elif conflict == 'symlink':
                    self.assertTrue(task.is_symlink())
                    self.assertEqual(task.read_text(), 'Test symlink target')
                    self.assertFalse(runner.exists())
                else:
                    self.assertFalse(task.exists())
                    self.assertFalse(runner.exists())

    def test_native_ralph_storage_is_locally_excluded_from_user_git_status(self):
        from contextlib import contextmanager
        state = p.initial(config(), {})

        class Store:
            @contextmanager
            def transaction(self):
                yield state
        host = SimpleNamespace(c=config(), store=Store())

        def exclude(target):
            ab.ActionBridge.exclude_ralph_artifacts(host, target)

        def events(kind):
            return [row for row in state['history'] if row['type'] == kind]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            plain = base / 'Test-plain'
            plain.mkdir()
            exclude(plain)
            self.assertFalse(events('ralph.storage_excluded') + events('ralph.storage_exclude_unavailable'), 'non-Git target is skipped silently')
            project = base / 'Test-project'
            git_project(project, {'a.py': 'a = 1\n', '.gitignore': '/.ralph-runner/\n'}, {'a.py': 'a = 2\n'})
            info = project / '.git/info'
            for child in info.iterdir():
                child.unlink()
            info.rmdir()
            gitignore = (project / '.gitignore').read_bytes()
            exclude(project)
            exclude(project)
            self.assertEqual((info / 'exclude').read_text().splitlines().count('/RALPH.md'), 1, 'idempotent; info/ created')
            self.assertNotIn('ralph-runner', (info / 'exclude').read_text(), 'already ignored path untouched')
            self.assertEqual((project / '.gitignore').read_bytes(), gitignore)
            (project / 'RALPH.md').write_text('Test native task')
            (project / '.ralph-runner').mkdir()
            (project / '.ralph-runner/status.json').write_text('{}')
            status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=project, capture_output=True, text=True).stdout
            self.assertEqual(status.strip(), 'M a.py')
            nested = base / 'Test-nested'
            git_project(nested, {'pkg/RALPH.md': 'Test tracked user file\n'}, {})
            (nested / '.git/info/exclude').write_text('# Test user rule without newline')
            exclude(nested / 'pkg')
            text = (nested / '.git/info/exclude').read_text()
            self.assertTrue(text.startswith('# Test user rule without newline\n'))
            self.assertIn('/pkg/.ralph-runner/', text.splitlines())
            self.assertNotIn('/pkg/RALPH.md', text, 'tracked user RALPH.md stays visible')
            broken = base / 'Test-broken'
            git_project(broken, {'a.py': 'a\n'}, {})
            (broken / '.git/info/exclude').unlink()
            (broken / '.git/info/exclude').mkdir()
            exclude(broken)
            self.assertEqual(len(events('ralph.storage_exclude_unavailable')), 1, 'write failure is an event, not a blocker')

    def test_native_ralph_in_git_target_leaves_user_status_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve() / 'Test-project'
            git_project(project, {'a.py': 'a = 1\n'}, {'a.py': 'a = 2  # Test user edit\n'})
            root = Path(tmp).resolve() / 'run'
            root.mkdir(mode=0o700)
            c, env = self.fixture(root, mode='ralph')
            c['execution_contract']['target'] = str(project)
            p.durable(root / 'config.json', c)
            self.assertEqual(self.launch(root, env).wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            self.assertTrue((project / 'RALPH.md').exists() and (project / '.ralph-runner').is_dir())
            status = subprocess.run(['git', 'status', '--porcelain'], cwd=project, capture_output=True, text=True).stdout
            self.assertNotIn('RALPH', status)
            self.assertNotIn('ralph-runner', status)
            self.assertIn('a.py', status)

    def test_native_ralph_reuse_refuses_foreign_or_modified_storage(self):
        for conflict in ('task-edit', 'task-replaced', 'runner-replaced', 'foreign-token', 'active-result', 'leased'):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, mode='ralph')
                target = root.resolve() / 'Test-project'
                target.mkdir()
                c['execution_contract']['target'] = str(target)
                p.durable(root / 'config.json', c)
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                task, runner = target / 'RALPH.md', target / '.ralph-runner'
                if conflict == 'task-edit':
                    task.write_text('Test user changed the task')
                elif conflict == 'task-replaced':
                    task.rename(target / 'Test-original-task')
                    task.write_text((target / 'Test-original-task').read_text())
                elif conflict == 'runner-replaced':
                    runner.rename(target / 'Test-original-runner')
                    runner.mkdir()
                    (runner / 'status.json').write_text((target / 'Test-original-runner/status.json').read_text())
                elif conflict in {'foreign-token', 'active-result'}:
                    native = b.read(runner / 'status.json')
                    if conflict == 'foreign-token':
                        native['loopToken'] = 'Test-other-run'
                    else:
                        native.pop('completedAt')
                    p.durable(runner / 'status.json', native)
                original = task.read_bytes(), (runner / 'status.json').read_bytes()
                core = ab.ActionBridge(b.load_config(root / 'config.json'))
                with core.store.transaction() as state:
                    state['sessions'].append(dict(id='Test-next-session'))
                lease = None
                try:
                    if conflict == 'leased':
                        lease = os.open(runner, os.O_RDONLY | os.O_DIRECTORY)
                        ab.fcntl.flock(lease, ab.fcntl.LOCK_EX | ab.fcntl.LOCK_NB)
                    self.assertIsNone(core.reuse_ralph_storage(task, runner))
                    self.assertEqual((task.read_bytes(), (runner / 'status.json').read_bytes()), original)
                finally:
                    if lease is not None:
                        os.close(lease)

    def test_native_ralph_real_blockers_leave_independent_work_and_one_grouped_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='ralph', blocker=True)
            env['PPP_TEST_SECOND_BLOCKER'] = '1'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'wait' and bool(value['requests']), proc)
            self.assertTrue((root / 'work/footer.txt').is_file())
            self.assertEqual((state['cycle'], state['review_seq'], len(state['requests']), len(state['blockers'])), (1, 1, 1, 2))
            self.human(root, c, kind='cancel')
            self.assertEqual(proc.wait(timeout=10), 2)

    def test_native_ralph_unknown_or_unavailable_review_delivers_without_synthetic_replay(self):
        for flag in ('PPP_TEST_UNKNOWN', 'PPP_TEST_REVIEW_UNAVAILABLE', 'PPP_TEST_RALPH_NO_CHECKPOINT'):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, env = self.fixture(root, mode='ralph')
                env[flag] = '1'
                if flag == 'PPP_TEST_RALPH_NO_CHECKPOINT':
                    env['PPP_TEST_UNKNOWN'] = '1'
                proc = self.launch(root, env)
                self.assertIn(proc.wait(timeout=20), (1, 2), (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual((state['cycle'], len(state['sessions'])), (1, 1))
                self.assertNotEqual(set(state['acceptance'].values()), {'pass'})
                self.assertTrue(state['available_results'])
                self.assertTrue((root / 'work/footer.txt').is_file())
                self.assertFalse(any(row['type'] == 'worker.checkpoint_repair' for row in state['history']))

    def test_native_ralph_host_failure_still_reviews_and_delivers_available_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ralph', cycles=4)
            env.update(PPP_TEST_RALPH_EXIT='1', PPP_TEST_UNKNOWN='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
            self.assertEqual(state['consumption'][0]['worker_iterations'], 4)
            self.assertTrue(state['available_results'])
            self.assertIn('Pi exited unexpectedly: 7', state['sessions'][0]['ralph_host_error'])
            self.assertNotEqual(set(state['acceptance'].values()), {'pass'})

    def test_native_ralph_time_boundary_keeps_unconfirmed_iteration_reservations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='ralph', cycles=4)
            c['wall_seconds'] = 1
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_RALPH_HOLD='1', PPP_TEST_UNKNOWN='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['consumption'][0]['worker_iterations']), (1, 4))
            self.assertEqual(state['sessions'][0]['ralph_usage_status'], 'reserved')
            self.assertTrue(state['available_results'])
            self.assertGreaterEqual(state['worker_seconds'], 1)

    def test_native_goal_runs_full_objective_before_one_independent_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=1)
            c['cycle_seconds'] = 1
            c['execution_contract']['actions'][0]['depends_on'] = ['email']
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_NATIVE_GOAL_DELAY='1.1', PPP_TEST_ASSERT_WRITER_SEPARATION='1', PPP_TEST_GOAL_TOMBSTONE='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('finish', 1, 1))
            self.assertEqual(state['consumption'][0]['action_ids'], ['email', 'footer'])
            self.assertEqual(state['sessions'][0]['goal_status'], 'complete')
            self.assertEqual(len((root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()), 1)
            self.assertEqual(set(state['acceptance'].values()), {'pass'})
            contract = (root / 'CONTRACT.md').read_text()
            self.assertNotIn('One authorized selected action per cycle', contract)
            self.assertNotIn('After checkpoint call goal_wait', contract)

    def test_native_goal_runs_without_cycle_limits_in_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal')
            for key in ('max_cycles', 'cycle_seconds'):
                c.pop(key)
            p.durable(root / 'config.json', c)
            env['PPP_TEST_NATIVE_GOAL'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            status = b.read(root / 'bridge-status.json')
            self.assertGreater(status['worker_tokens'], 0)
            self.assertEqual(status['main_remaining'], 9, 'one native Goal launch of the default 10 spent')
            self.assertIsNone(b.read(root / 'work/cycle-context.json')['budget']['cycle_seconds'])

    def test_native_goal_repeated_concrete_corrections_share_history_and_remaining_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='goal', cycles=1)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_UNFINISHED='2', PPP_TEST_GOAL_TOMBSTONE='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('finish', 3, 3))
            self.assertEqual(state['worker_tokens'], 51)
            self.assertEqual(len({row['id'] for row in state['sessions']}), 1)
            self.assertEqual(len({row['goal_window_id'] for row in state['sessions']}), 3)
            self.assertEqual([row['goal_native_id'] for row in state['sessions']], ['Test-goal-1', 'Test-goal-2', 'Test-goal-3'])
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            # Without configured goal_tokens each native Goal starts uncapped by tokens; three launches is the default limit.
            self.assertEqual([message.startswith('/goal ') and '--tokens' not in message for message in prompts], [True, True, True])
            self.assertTrue(all(row['assessment']['attempt']['assessment'] == 'informative' for row in state['consumption'][:2]))
            self.assertTrue(all(row['goal_status'] == 'complete' for row in state['sessions']))

    def test_native_goal_later_window_completion_with_late_turn_reaches_review(self):
        # Live regression: second native Goal completed, Worker answered after goal_complete; Core halted with usage unavailable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='goal', cycles=1)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_UNFINISHED='1', PPP_TEST_GOAL_TOMBSTONE='1', PPP_TEST_GOAL_LATE_TURN='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('finish', 2, 2))
            self.assertEqual((state['worker_tokens'], state['goal_usage_status']), (2 * (17 + 5), 'known'))
            self.assertEqual([row['goal_native_id'] for row in state['sessions']], ['Test-goal-1', 'Test-goal-2'])
            self.assertFalse(any(event['type'] == 'attention.required' for event in state['history']))

    def test_native_goal_real_blocker_does_not_prevent_independent_work_or_reset_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', blocker=True)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_GOAL_NATIVE_STOP='blocked')
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'wait' and bool(value['requests']), proc)
            self.assertTrue((root / 'work/footer.txt').is_file())
            self.assertFalse((root / 'work/email.txt').exists())
            self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
            self.assertEqual(state['sessions'][0]['goal_status'], 'blocked')
            self.assertEqual(len(state['requests']), 1)
            (root / 'work/Test-secure-configured').write_text('Test actual local access restoration')
            self.human(root, c, 'resolution', blocker_ids=list(state['blockers']))
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['worker_tokens'], 34)
            self.assertEqual(state['execution'], 'finish')
            self.assertTrue((root / 'work/Test-goal-replacement-confirmed').is_file())
            self.assertEqual(state['sessions'][1]['action_ids'], ['email'])

    def test_native_goal_unknown_result_does_not_manufacture_a_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='goal')
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_UNKNOWN='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('stop', 1, 1))
            self.assertEqual(state['sessions'][0]['goal_status'], 'complete')
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            request = b.read(root / 'reviews/v2-000001/request.json')
            self.assertTrue(all(Path(path).is_file() for path in request['evidence_archive'].values()))
            self.assertIn('footer.txt', request['evidence_archive'])
            self.assertFalse(state['requests'])

    def test_ping_pong_ordinary_worker_reviews_each_result_and_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ping-pong', cycles=4)
            env['PPP_TEST_CORRECTIONS'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['cycle'], 4)
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertEqual(len(prompts), 4)
            self.assertTrue(all(not prompt.startswith(('/goal', '/ralph')) for prompt in prompts))
            self.assertGreaterEqual(sum(event['type'] == 'review.applied' for event in state['history']), 4)

    def test_ping_pong_worker_tokens_are_reported_per_session_without_budget_effect(self):
        for usage, status in (('1', 'known'), ('torn', 'partial')):
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env['PPP_TEST_WORKER_USAGE'] = usage
                self.assertEqual(self.launch(root, env).wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                rows = state['sessions']
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(row['tokens'] == 19 and row['tokens_status'] == status for row in rows))
                self.assertEqual(rows[0]['usage'], dict(input=3, output=4, cacheRead=10, cacheWrite=2, totalTokens=19))
                status_file = b.read(root / 'bridge-status.json')
                self.assertEqual((status_file['worker_tokens'], status_file['worker_tokens_status']), (38, status))
                self.assertEqual(state['worker_tokens'], 0, 'report only; Goal token ledger untouched')
                self.assertEqual((status_file['reviewer_tokens'], status_file['reviewer_tokens_status']), (14, 'known'))
                self.assertEqual(b.read(root / 'reviews/v2-000001/reviewer.json')['tokens'], 7)
                self.assertEqual(state['execution'], 'finish')

    def test_session_usage_parsing_is_idempotent_identity_bound_and_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            path = base / 'Test-session.jsonl'
            lines = [dict(type='session', id='Test-id'),
                     dict(type='message', message=dict(role='user', content='Test')),
                     dict(type='message', message=dict(role='assistant', usage=dict(input=1, output=2, cacheRead=3, cacheWrite=4, totalTokens=10))),
                     dict(type='message', message=dict(role='assistant', usage=dict(input=5, totalTokens=5)))]
            path.write_text(''.join(json.dumps(line) + '\n' for line in lines))
            first = ab.session_usage(path, 'Test-id', base)
            self.assertEqual(first, ab.session_usage(path, 'Test-id', base), 'recomputed whole, never accumulated')
            self.assertEqual((first['tokens'], first['tokens_status'], first['usage']['input']), (15, 'known', 6))
            with path.open('a') as stream:
                stream.write('not json\n' + json.dumps(dict(type='message', message=dict(role='assistant', content=[]))) + '\n')
            self.assertEqual((ab.session_usage(path, 'Test-id', base)['tokens'], ab.session_usage(path, 'Test-id', base)['tokens_status']), (15, 'partial'))
            self.assertEqual(ab.session_usage(path, 'Test-other', base)['tokens_status'], 'not_measured')
            self.assertEqual(ab.session_usage(path, 'Test-id', base / 'Test-elsewhere')['tokens_status'], 'not_measured')
            self.assertEqual(ab.session_usage(None, 'Test-id', base)['tokens'], None)
            self.assertEqual(ab.usage_total([]), (None, 'not_measured'))
            self.assertEqual(ab.usage_total([dict(id='a', tokens=1, tokens_status='known'), dict(id='a', tokens=4, tokens_status='known')]), (4, 'known'), 'resume row replaces, never adds')
            self.assertEqual(ab.usage_total([dict(id='a', tokens=4, tokens_status='known'), dict(id='b', tokens=None, tokens_status='not_measured')]), (4, 'partial'))

    def test_worker_checkpoint_helper_writes_checkpoint_core_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ping-pong')
            env['PPP_TEST_CHECKPOINT_HELPER'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertFalse(any(event['type'] == 'worker.checkpoint_invalid' for event in state['history']))
            self.assertIn('PPP_CHECKPOINT_CMD', (root / 'CONTRACT.md').read_text())

    def test_ping_pong_continues_unfinished_work_without_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ping-pong', cycles=4)
            env['PPP_TEST_UNFINISHED'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['cycle'], 4)
            self.assertEqual(sum(event['type'] == 'action.continued' for event in state['history']), 2)
            self.assertFalse(any(event['type'] == 'experiment.planned' for event in state['history']))

    def test_worker_wall_budget_uses_durable_active_time_after_restart(self):
        core = object.__new__(ab.ActionBridge)
        core.c = {'wall_seconds': 20}
        core.store = SimpleNamespace(read=lambda: {'worker_seconds': 7})
        core.worker_started_at = time.monotonic() - 2
        self.assertAlmostEqual(core.wall_remaining(), 11, delta=0.1)

    def test_goal_resume_reuses_durable_session_and_only_remaining_token_budget(self):
        core = object.__new__(ab.ActionBridge)
        core.c = {**config(), 'mode': 'goal', 'goal_tokens': 100}
        state = p.initial(core.c, {})
        state['worker_tokens'] = 62
        state['sessions'] = [dict(id='Test-persistent-goal', status='checkpoint', goal_started=True, tokens_used=62, goal_token_budget=100)]
        core.store = SimpleNamespace(read=lambda: state)
        core.goal_session_id = None
        core.goal_started = False
        self.assertTrue(core.prepare_goal_session())
        self.assertEqual(core.goal_session_id, 'Test-persistent-goal')
        self.assertTrue(core.goal_started)
        self.assertEqual(core.c['worker_session_id'], 'Test-persistent-goal')
        self.assertEqual(core.c['goal_session_tokens'], 38)
        self.assertTrue(core.prepare_goal_session(), 'A stopped RPC process must revalidate the restored native identity')

    def test_native_goal_explicit_token_cap_is_cumulative_and_passed_to_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=1)
            c['goal_tokens'] = 100000
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_UNFINISHED='2', PPP_TEST_GOAL_TOMBSTONE='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertEqual([int(message.split('--tokens ')[1].split()[0]) for message in prompts], [100000, 99983, 99966])

    def test_native_goal_launch_limit_pauses_with_available_result_and_no_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=1)
            c['goal_max_launches'] = 2
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_UNFINISHED='2', PPP_TEST_GOAL_TOMBSTONE='1')
            proc = self.launch(root, env)
            try:
                for _ in range(200):
                    state = b.read(root / 'execution-state.json') if (root / 'execution-state.json').exists() else None
                    if state and state['execution'] == 'paused_budget':
                        break
                    self.assertIsNone(proc.poll(), (root / 'Test-run.log').read_text())
                    time.sleep(0.1)
                else:
                    self.fail('Launch-limited Goal did not pause for an explicit grant')
                self.assertEqual(len({row['goal_window_id'] for row in state['sessions']}), 2)
                self.assertEqual(len((root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()), 2)
                self.assertNotEqual(set(state['acceptance'].values()), {'pass'})
                self.assertEqual(p.Controller(c, state).remaining('main'), 0)
                self.assertEqual(state['review_seq'], 2)
            finally:
                self.human(root, c, kind='cancel')
                proc.wait(timeout=10)

    def test_goal_resume_after_controller_crash_keeps_session_and_token_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='goal', cycles=2)
            env.update(PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT='1', PPP_TEST_GOAL_TOMBSTONE='1')
            crashed = self.launch(root, env)
            self.assertEqual(crashed.wait(timeout=20), -9, (root / 'Test-run.log').read_text())
            before = b.read(root / 'execution-state.json')
            session_id = before['sessions'][0]['id']
            self.assertIn(before['worker_tokens'], (0, 17))
            worker_pid = before['sessions'][0]['pid']
            for _ in range(100):
                try:
                    os.kill(worker_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail('Synthetic Goal RPC process did not release its inherited worker lease')
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=30), 0, (root / 'Test-resume.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['worker_tokens'], 34)
            self.assertTrue(all(row['id'] == session_id for row in state['sessions']))
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertTrue(prompts[0].startswith('/goal ') and '--tokens' not in prompts[0])
            self.assertTrue(prompts[1].startswith('/goal ') and '--tokens' not in prompts[1])

    def test_goal_time_limit_retains_usage_and_independently_reviews_available_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal')
            c.update(goal_tokens=300000, cycle_seconds=1, review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_GOAL_TIMEOUT='1', PPP_TEST_UNKNOWN='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            status = b.read(root / 'bridge-status.json')
            self.assertEqual(state['execution'], 'stop')
            self.assertTrue(any(event['type'] == 'worker.goal_time_limited' for event in state['history']))
            self.assertEqual(state['review_seq'], 1)
            self.assertGreaterEqual(state['worker_seconds'], c['wall_seconds'])
            self.assertEqual((state['worker_tokens'], status['worker_tokens'], status['main_remaining']), (148808, 148808, 151192))
            self.assertIsNone(status['worker_tokens_status'])
            self.assertEqual(state['goal_usage_status'], 'known')
            session = state['sessions'][-1]
            self.assertTrue(session['goal_started'])
            self.assertEqual(session['goal_native_id'], 'Test-goal-1')
            native_entries = [json.loads(line) for line in Path(session['session_file']).read_text().splitlines()]
            self.assertEqual(native_entries[-1]['data']['goal']['tokenBudget'], 300000)
            self.assertGreaterEqual(state['worker_seconds'], 1)
            result = state['available_results'][0]
            self.assertIn('email.txt', result['available_files'])
            self.assertEqual(result['status'], 'unverified')
            self.assertTrue(any('time budget exhausted' in item for item in result['limitations']))
            reports = [b.read(path)['message'] for path in (root / 'pi-inbox').glob('*.message.json')]
            self.assertTrue(any('Worker time limit' in message and '10 seconds exhausted' in message for message in reports))
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            window, identity = session['goal_window_id'], session['id']
            # Reproduce an older controller's lost accounting, without altering the native file.
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            with core.store.transaction() as legacy:
                legacy['worker_tokens'] = 0
                for key in ('tokens_used', 'goal_native_id'):
                    legacy['sessions'][-1].pop(key)
                legacy['sessions'][-1]['goal_started'] = False
            core.reconcile_goal_usage()
            core.reconcile_goal_usage()
            saved = core.store.read()
            self.assertEqual(saved['sessions'][-1]['goal_window_id'], window)
            self.assertEqual(saved['sessions'][-1]['id'], identity)
            with self.assertRaisesRegex(ValueError, 'cannot automatically resume'):
                core.run(resume=True)
            self.assertEqual(saved['worker_tokens'], 148808)
            self.assertEqual(saved['grants'], state['grants'])
            self.assertEqual(core.c['cycle_seconds'], 1)
            self.assertEqual(core.c['wall_seconds'], c['wall_seconds'])
            core.prepare_goal_session()
            self.assertTrue(core.goal_started)
            self.assertEqual(core.c['goal_session_tokens'], 151192)

    def test_goal_durable_usage_rejects_foreign_session_and_window_and_keeps_high_water(self):
        for fault in ('none', 'startup', 'missing', 'ambiguous', 'session', 'cwd', 'window', 'previous', 'truncated', 'assistant'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, _ = self.fixture(root, mode='goal')
                core = ab.ActionBridge(b.load_config(root / 'config.json'))
                (root / 'sessions').mkdir()
                path = root / 'sessions/Test-native.jsonl'
                session = dict(id='Test-session', goal_window_id='Test-window', goal_native_id='Test-owned', goal_started=True, pid=123, session_file=str(path), tokens_used=20)
                state = p.initial(core.c, {})
                state.update(worker_tokens=20, sessions=[session])
                if fault in {'startup', 'missing', 'ambiguous'}:
                    session.update(pid=None, session_file=None, goal_started=False, goal_dispatch_attempted=True)
                if fault == 'previous':
                    session.update(goal_native_id=None, goal_previous_native_id='Test-old', goal_started=False)
                with core.store.transaction(create=state):
                    pass
                native = 'Test-other' if fault == 'window' else 'Test-old' if fault == 'previous' else 'Test-owned'
                entries = [dict(type='session', version=3, id='Test-foreign' if fault == 'session' else 'Test-session', cwd=str(root / ('Test-foreign-cwd' if fault == 'cwd' else 'work'))),
                           dict(type='custom', customType='goal-state', data=dict(goal=dict(id=native, tokensUsed=42, tokenBudget=100))),
                           dict(type='custom', customType='goal-state', data=dict(goal=dict(id=native, tokensUsed=31, tokenBudget=100)))]
                if fault == 'assistant':
                    entries.append(dict(type='message', message=dict(role='assistant', usage=dict(totalTokens=7))))
                path.write_text(''.join(json.dumps(entry)+'\n' for entry in entries) + ('{"type":' if fault == 'truncated' else ''))
                if fault == 'missing':
                    path.unlink()
                if fault == 'ambiguous':
                    path.with_name('Test-duplicate.jsonl').write_text(path.read_text())
                core.cycle_deadline = core.operation_deadline = time.monotonic() - 100
                with patch.object(core, 'goal_state', side_effect=AssertionError('Expired RPC must not be used')):
                    core.reconcile_goal_usage()
                    core.reconcile_goal_usage()
                saved = core.store.read()
                self.assertEqual(saved['worker_tokens'], 20 if fault in {'session', 'cwd', 'window', 'previous', 'missing', 'ambiguous'} else 42)
                self.assertEqual(saved['sessions'][-1]['goal_window_id'], 'Test-window')
                self.assertEqual(saved['goal_usage_status'], 'known' if fault in {'none', 'startup'} else 'unknown')
                core.project()
                projected = b.read(root / 'bridge-status.json')
                if fault not in {'none', 'startup'}:
                    self.assertIsNone(projected['main_remaining'])
                    with self.assertRaisesRegex(RuntimeError, 'usage is unknown'):
                        core.prepare_goal_session()

    def test_goal_terminal_tombstone_reconciliation_preserves_identity_and_high_water(self):
        for fault in ('none', 'active', 'missing_result', 'rejected', 'foreign_result', 'foreign_window', 'previous', 'assistant', 'truncated', 'extra_null'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, _ = self.fixture(root, mode='goal')
                core = ab.ActionBridge(b.load_config(root / 'config.json'))
                (root / 'sessions').mkdir()
                path = root / 'sessions/Test-native.jsonl'
                session = dict(id='Test-session', goal_window_id='Test-window', goal_native_id='Test-owned', goal_started=True, pid=123, session_file=str(path), tokens_used=20)
                state = p.initial(core.c, {})
                state.update(worker_tokens=20, sessions=[session])
                if fault == 'previous':
                    session.update(goal_native_id=None, goal_previous_native_id='Test-owned')
                with core.store.transaction(create=state):
                    pass
                native_id = 'Test-foreign' if fault == 'foreign_window' else 'Test-owned'
                entries = [dict(type='session', version=3, id='Test-session', cwd=str(root / 'work')),
                           dict(type='custom', customType='goal-state', data=dict(goal=dict(id=native_id, status='active', tokensUsed=42))),
                           dict(type='custom', customType='goal-state', data=dict(goal=dict(id=native_id, status='active' if fault == 'active' else 'complete', tokensUsed=31))),
                           dict(type='custom', customType='goal-state', data=dict(goal=None)),
                           dict(type='message', message=dict(role='toolResult', toolName='goal_complete', isError=fault == 'rejected', details=dict(goal_id='Test-foreign' if fault == 'foreign_result' else native_id), content=[dict(type='text', text='Goal complete: Test result')]))]
                if fault == 'missing_result':
                    entries.pop()
                elif fault == 'assistant':
                    entries.append(dict(type='message', message=dict(role='assistant', usage=dict(totalTokens=7))))
                elif fault == 'extra_null':
                    entries.append(dict(type='custom', customType='goal-state', data=dict(goal=None)))
                path.write_text(''.join(json.dumps(entry)+'\n' for entry in entries) + ('{"type":' if fault == 'truncated' else ''))
                with patch.object(core, 'goal_state', side_effect=AssertionError('Recovery must use durable entries, not RPC')):
                    core.reconcile_goal_usage()
                    core.reconcile_goal_usage()
                saved = core.store.read()
                # A metered post-completion assistant turn is added to the high-water, not treated as unknown.
                self.assertEqual(saved['worker_tokens'], 20 if fault in {'foreign_window', 'previous'} else 49 if fault == 'assistant' else 42)
                self.assertEqual(saved['goal_usage_status'], 'known' if fault in {'none', 'assistant'} else 'unknown')
                self.assertEqual(saved['sessions'][-1]['goal_window_id'], 'Test-window')
                self.assertEqual(saved['sessions'][-1]['id'], 'Test-session')
                self.assertEqual((saved['grants'], saved['consumption'], saved['acceptance']), (state['grants'], state['consumption'], state['acceptance']))
                if fault not in {'none', 'assistant'}:
                    with self.assertRaisesRegex(RuntimeError, 'usage is unknown'):
                        core.prepare_goal_session()

    def test_second_goal_window_post_completion_turns_are_metered_not_unknown(self):
        for fault in ('none', 'unmetered'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, mode='goal')
                core = ab.ActionBridge(b.load_config(root / 'config.json'))
                (root / 'sessions').mkdir()
                path = root / 'sessions/Test-native.jsonl'
                first = dict(id='Test-session', goal_window_id='Test-window-1', goal_native_id='Test-first', goal_started=True, goal_status='complete', pid=1, session_file=str(path), tokens_used=100)
                second = dict(id='Test-session', goal_window_id='Test-window-2', goal_native_id='Test-second', goal_previous_native_id='Test-first', goal_started=True, pid=2, session_file=str(path), tokens_used=30)
                state = p.initial(core.c, {})
                state.update(worker_tokens=130, sessions=[first, second])
                with core.store.transaction(create=state):
                    pass
                def goal(ident, status, used):
                    return dict(type='custom', customType='goal-state', data=dict(goal=dict(id=ident, status=status, tokensUsed=used)))
                def done(ident):
                    return dict(type='message', message=dict(role='toolResult', toolName='goal_complete', isError=False, details=dict(goal_id=ident), content=[dict(type='text', text='Goal complete: Test result')]))
                cleared = dict(type='custom', customType='goal-state', data=dict(goal=None))
                late = dict(type='message', message=dict(role='assistant', content=[], **({} if fault == 'unmetered' else {'usage': dict(totalTokens=7)})))
                entries = [dict(type='session', version=3, id='Test-session', cwd=str(root / 'work')), goal('Test-first', 'complete', 100), cleared, done('Test-first'),
                           goal('Test-second', 'active', 0), goal('Test-second', 'complete', 30), cleared, done('Test-second'), late]
                path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
                core.reconcile_goal_usage()
                core.reconcile_goal_usage()
                saved = core.store.read()
                if fault == 'none':
                    self.assertEqual((saved['worker_tokens'], saved['goal_usage_status'], saved['sessions'][-1]['tokens_used']), (137, 'known', 37))
                else:
                    self.assertEqual((saved['worker_tokens'], saved['goal_usage_status']), (130, 'unknown'))
                    with self.assertRaisesRegex(RuntimeError, 'usage is unknown'):
                        core.prepare_goal_session()

    def test_premature_goal_tombstone_does_not_allow_worker_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='goal')
            env.update(PPP_TEST_GOAL_TOMBSTONE='1', PPP_TEST_GOAL_NATIVE_STOP='active')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 1, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('halt', 1, 0))
            self.assertEqual((state['worker_tokens'], state['goal_usage_status']), (17, 'unknown'))
            self.assertIsNone(b.read(root / 'bridge-status.json')['main_remaining'])
            self.assertNotEqual(set(state['acceptance'].values()), {'pass'})
            self.assertEqual(len((root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()), 1)

    def test_goal_resume_migrates_cycle_caps_without_resetting_token_usage(self):
        c = {**config(), 'mode': 'goal', 'goal_tokens': 100}
        state = p.initial(c, {})
        state['grants'][0]['max_cycles'] = c['max_cycles']
        state['grants'].append(dict(id='G1', scope='main', max_cycles=2, authority='Test-human-grant'))
        state['grants'].append(dict(id='G2', scope='main', max_cycles=None, authority='Test-previously-migrated-grant'))
        state['history'].append(dict(type='grant.added', authority='Test-previously-migrated-grant', cycles=1))
        state['worker_tokens'] = 62
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, c['run_id'])
            with store.transaction(create=state):
                pass
            core = object.__new__(ab.ActionBridge)
            core.c = c
            core.store = store
            core.migrate_goal_cycle_grants()
            saved = store.read()
            self.assertTrue(all(grant['max_cycles'] is None for grant in saved['grants']))
            self.assertEqual(next(grant for grant in saved['grants'] if grant['authority'] == 'Test-human-grant')['goal_token_windows'], 2)
            self.assertEqual(next(grant for grant in saved['grants'] if grant['authority'] == 'Test-previously-migrated-grant')['goal_token_windows'], 1)
            self.assertEqual(saved['worker_tokens'], 62)
            self.assertEqual(p.Controller(c, saved).goal_token_budget(), 400)
            self.assertEqual(p.Controller(c, saved).remaining('main'), 338)
            self.assertTrue(any(event['type'] == 'goal.checkpoint_caps_removed' for event in saved['history']))

    def test_goal_cycle_grant_renews_token_window_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=2)
            c['goal_tokens'] = 17
            c['cycle_seconds'] = 3
            p.durable(root / 'config.json', c)
            env['PPP_TEST_GOAL_RENEWAL'] = '1'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'paused_budget', proc)
            self.assertEqual(state['worker_tokens'], 17)
            self.assertEqual(state['cycle'], 1)
            request_id = next(iter(state['requests']))
            time.sleep(c['cycle_seconds'] + 0.2)
            self.human(root, c, 'grant', request_id=request_id, cycles=1)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['worker_tokens'], 34)
            self.assertTrue((root / 'work/Test-goal-replacement-confirmed').is_file())
            self.assertEqual(state['cycle'], 2)
            self.assertEqual(state['sessions'][0]['id'], state['sessions'][1]['id'])
            self.assertNotEqual(state['sessions'][0]['goal_window_id'], state['sessions'][1]['goal_window_id'])
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertTrue(all(prompt.startswith('/goal --tokens 17 ') for prompt in prompts))

    def test_goal_budget_limited_interrupted_turn_without_checkpoint_is_reviewed_truthfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=2)
            c['goal_tokens'] = 17
            p.durable(root / 'config.json', c)
            env['PPP_TEST_GOAL_BUDGET_LIMIT'] = '1'
            env['PPP_TEST_WRONG_OUTPUT'] = '1'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'paused_budget' and b.read(root / 'bridge-status.json')['status'] == 'paused_budget', proc)
            status = b.read(root / 'bridge-status.json')
            request = b.read(root / 'reviews/v2-000001/request.json')
            self.assertEqual(state['worker_tokens'], 17)
            self.assertEqual(state['sessions'][-1]['status'], 'budget_limited')
            self.assertEqual(state['execution'], 'paused_budget')
            self.assertEqual(status['status'], 'paused_budget')
            self.assertIsNone(request['checkpoint'])
            self.assertIsNone(request['checkpoint_sha256'])
            self.assertIn('email.txt', request['evidence_archive'])
            self.assertIn('Test-budget-check.py', request['evidence_archive'])
            facts = b.read(next(path for name, path in request['evidence_archive'].items() if name.startswith('budget-result-')))
            tests = facts['tool_facts']['Test-ordinary-tests']
            self.assertIn('Test-budget-check.py', tests['command'])
            self.assertIn('Ran 1 test', tests['result']['content'][0]['text'])
            self.assertIn('OK', tests['result']['content'][0]['text'])
            self.assertNotIn('exitCode', tests['result'], 'isError=false and OK do not invent numeric exit')
            self.assertNotIn('content', facts['tool_facts']['Test-write-0'])
            self.assertEqual(state['cycle'], 1)
            self.assertEqual(b.read(root / 'reviews/v2-000001/review.json')['assessment']['criteria']['email_ok']['status'], 'fail')
            self.assertNotEqual(state['acceptance']['email_ok'], 'pass')
            self.assertTrue((root / 'work/email.txt').is_file())
            self.assertTrue(any(event['type'] == 'worker.goal_budget_limited' for event in state['history']))
            self.human(root, c, 'cancel')
            self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())

    def test_budget_partial_files_and_real_tests_are_delivered_after_valid_unknown_review(self):
        for transport, incomplete in (('headless', False), ('headless', True), ('chat', False)):
            with self.subTest(transport=transport, incomplete=incomplete), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, mode='goal')
                target = root / 'Test-target'
                target.mkdir()
                target_file = (target / 'Test-result.py').resolve()
                c['execution_contract']['target'] = str(target)
                c['execution_contract']['actions'] = [row for row in c['execution_contract']['actions'] if row['id'] == 'email']
                c['goal_tokens'] = 17
                if transport == 'headless':
                    c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env.update(PPP_TEST_GOAL_BUDGET_LIMIT='1', PPP_TEST_UNKNOWN='1', PPP_TEST_TARGET_OUTPUT=str(target_file))
                if incomplete:
                    env['PPP_TEST_INCOMPLETE_COMMAND'] = '1'
                proc = self.launch(root, env)
                self.await_state(root, lambda value: value['execution'] == 'paused_budget' and any((root / 'notices').glob('Q-*.receipt.json')), proc)
                time.sleep(0.3)
                state = b.read(root / 'execution-state.json')
                self.assertEqual((state['cycle'], state['review_seq'], len(state['sessions'])), (1, 1, 1))
                self.assertEqual(state['execution'], 'paused_budget')
                self.assertEqual(set(state['acceptance'].values()), {'unknown'})
                self.assertNotIn('verification', state, 'valid unknown is not a technical failure')
                self.assertFalse(state['blockers'], 'unknown creates no human verification-repair gate')
                self.assertFalse(any(item['type'] == 'experiment.planned' for item in state['history']))
                self.assertTrue(all(item['main_extension'] for item in state['requests'].values()), 'existing explicit token-grant semantics stay unchanged')
                result = b.read(root / 'unverified-results/cycle-000001/result.json')
                self.assertEqual(state['available_results'], [result])
                self.assertEqual(result['status'], 'unverified')
                self.assertIn(str(target_file), result['available_files'])
                self.assertIn('email.txt', result['available_files'])
                request = b.read(root / 'reviews/v2-000001/request.json')
                self.assertIsNone(request['checkpoint'])
                for name, retained in request['evidence_archive'].items():
                    self.assertEqual(b.digest(retained), request['evidence_sha256'][name])
                facts = b.read(next(path for name, path in request['evidence_archive'].items() if name.startswith('budget-result-')))
                tests = facts['tool_facts']['Test-ordinary-tests']
                if incomplete:
                    self.assertNotIn('result', tests, 'unfinished process has no result or exit')
                else:
                    self.assertIn('Ran 1 test', tests['result']['content'][0]['text'])
                    self.assertNotIn('exitCode', tests['result'])
                if transport == 'headless':
                    messages = [b.read(path)['message'] for path in (root / 'pi-inbox').glob('*.message.json')]
                else:
                    messages = [json.loads(line)['Test-message'] for line in (root / 'work/Test-codex-notices.jsonl').read_text().splitlines()]
                self.assertTrue(any('Available scoped files' in message and str(target_file) in message and 'email.txt' in message for message in messages))
                self.assertTrue(any('unreferenced files may remain' in message for message in messages))
                self.human(root, c, 'cancel')
                self.assertEqual(proc.wait(timeout=20), 2, (root / 'Test-run.log').read_text())

    def test_partial_evidence_is_owned_scoped_and_excludes_private_transcript(self):
        for fault in ('none', 'session', 'window', 'missing', 'truncated'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                self.fixture(root, mode='goal')
                c = b.load_config(root / 'config.json')
                core = ab.ActionBridge(c)
                work = root / 'work'
                work.mkdir()
                (root / 'sessions').mkdir()
                path = root / 'sessions/Test-native.jsonl'
                (work / 'Test-old.py').write_text('Test earlier cycle output')
                (work / '.env').write_text('Test private material')
                (root / 'Test-outside.py').write_text('Test outside authorized output')
                p.durable(root / 'output-baseline.json', ab.outputs.snapshot(c))
                (work / 'Test-current.py').write_text('Test available output')
                entries = [dict(type='session', id='Test-foreign' if fault == 'session' else 'Test-owned', cwd=str(work))]
                def message(role, **fields):
                    return dict(type='message', timestamp='1970-01-01T00:00:15+00:00', message=dict(role=role, **fields))
                calls = [dict(type='toolCall', id='Test-'+name, name=tool, arguments=args) for name, tool, args in (
                    ('current', 'write', dict(path='Test-current.py', content='Test do not copy write arguments')),
                    ('outside', 'write', dict(path=str(root / 'Test-outside.py'))),
                    ('secret', 'write', dict(path='.env')),
                    ('read', 'read', dict(path='.env')),
                    ('bash-secret', 'bash', dict(command='cat .env')),
                    ('bash-value', 'bash', dict(command='printf Test')),
                    ('pending', 'bash', dict(command='python3 -m unittest')))]
                old = message('assistant', content=[dict(type='toolCall', id='Test-old', name='write', arguments=dict(path='Test-old.py'))])
                old['timestamp'] = '1970-01-01T00:00:05+00:00'
                entries += [old, message('assistant', content=calls),
                    message('toolResult', toolCallId='Test-read', content=[dict(type='text', text='Test private read output')]),
                    message('toolResult', toolCallId='Test-bash-secret', content=[dict(type='text', text='Test private shell output')]),
                    message('toolResult', toolCallId='Test-bash-value', content=[dict(type='text', text='api_key=Test-private-value')]),
                    dict(type='custom', customType='goal-state', data=dict(goal=dict(id='Test-foreign' if fault == 'window' else 'Test-goal')))]
                path.write_text(''.join(json.dumps(entry)+'\n' for entry in entries) + ('{"Test-incomplete":' if fault == 'truncated' else ''))
                if fault == 'missing':
                    path.unlink()
                state = p.initial(c, ab.pins(c))
                state['reconciled'] = True
                state['actions']['email']['eligible'] = True
                p.Controller(c, state).consume('email', 'Test-owner')
                state['sessions'] = [dict(id='Test-owned', goal_native_id='Test-goal', cycle=1, action_id='email', status='budget_limited', started_at=10, ended_at=20, session_file=str(path))]
                with core.store.transaction(create=state):
                    pass
                core.preserve_budget_result()
                core.preserve_budget_result()
                results = core.store.read()['available_results']
                self.assertEqual(len(results), 1, 'recovery is idempotent')
                result = results[0]
                facts = b.read(next(path for name, path in result['evidence_archive'].items() if name.startswith('budget-result-')))
                if fault in {'session', 'window', 'missing'}:
                    self.assertEqual(result['available_files'], ['Test-current.py'])
                    self.assertIn(str(work / 'Test-current.py'), result['discovery_candidates'])
                    self.assertFalse(facts['tool_facts'])
                    self.assertTrue(any('unavailable' in item for item in result['limitations']))
                else:
                    self.assertEqual(result['available_files'], ['Test-current.py'])
                    self.assertNotIn('Test-read', facts['tool_facts'])
                    self.assertNotIn('result', facts['tool_facts']['Test-pending'])
                    self.assertIn('omitted', facts['tool_facts']['Test-bash-secret'])
                    self.assertIn('omitted', facts['tool_facts']['Test-bash-value'])
                    serialized = json.dumps(facts)
                    self.assertNotIn('Test private read output', serialized)
                    self.assertNotIn('Test private shell output', serialized)
                    self.assertNotIn('Test-private-value', serialized)
                    self.assertNotIn('Test do not copy write arguments', serialized)

    def test_budget_notices_distinguish_goal_tokens_and_ralph_cycles(self):
        for mode in ('goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, mode=mode)
                c = b.load_config(root / 'config.json')
                core = ab.ActionBridge(c)
                state = p.initial(c, ab.pins(c))
                state['requests']['Test-budget-request'] = dict(main_extension=True, blocker_ids=[], questions=[])
                with core.store.transaction(create=state):
                    pass
                with patch.object(p.Controller, 'remaining', return_value=0), patch.object(core, 'notice') as notice:
                    core.deliver()
                message = notice.call_args.args[1]
                self.assertIn('additional Goal windows' if mode == 'goal' else 'additional main cycles', message)
                if mode == 'goal':
                    self.assertIn('each adds one native Goal launch)', message)
                    self.assertNotIn('additional main cycles', message)

    def test_goal_crash_after_window_persist_before_native_start_does_not_charge_old_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=2)
            c['goal_tokens'] = 17
            p.durable(root / 'config.json', c)
            env['PPP_TEST_GOAL_RENEWAL'] = '1'
            env['PPP_TEST_KILL_AFTER_GOAL_WINDOW_PERSIST'] = '2'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'paused_budget', proc)
            request_id = next(iter(state['requests']))
            self.human(root, c, 'grant', request_id=request_id, cycles=1)
            self.assertEqual(proc.wait(timeout=20), -9, (root / 'Test-run.log').read_text())
            crashed = b.read(root / 'execution-state.json')
            self.assertEqual(crashed['worker_tokens'], 17)
            self.assertFalse(crashed['sessions'][-1]['goal_started'])
            self.assertEqual(crashed['sessions'][-1]['goal_previous_native_id'], 'Test-goal-1')
            self.assertNotIn('goal_native_id', crashed['sessions'][-1])

            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=30), 0, (root / 'Test-resume.log').read_text())
            final = b.read(root / 'execution-state.json')
            self.assertEqual(final['execution'], 'finish')
            self.assertEqual(final['worker_tokens'], 34)
            self.assertEqual(final['sessions'][0]['id'], final['sessions'][1]['id'])
            self.assertEqual(final['sessions'][0]['goal_native_id'], 'Test-goal-1')
            self.assertEqual(final['sessions'][-1]['goal_native_id'], 'Test-goal-2')
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertTrue(all(prompt.startswith('/goal --tokens 17 ') for prompt in prompts))

    def test_goal_grant_survives_resume_and_renewal_recovers_same_pi_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=3)
            c['execution_contract']['actions'].append(dict(id='dns', description='Test dns'))
            c['execution_contract']['criteria']['dns_ok'] = 'Test dns independently passes'
            c['goal_tokens'] = 17
            p.durable(root / 'config.json', c)
            env['PPP_TEST_GOAL_RENEWAL'] = '1'
            env['PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT'] = '1'
            env['PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT_CYCLE'] = '2'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda value: value['execution'] == 'paused_budget' and value['cycle'] == 1, proc)
            request_id = next(iter(state['requests']))
            grant_receipt = self.human(root, c, 'grant', request_id=request_id, cycles=1)
            self.assertEqual(proc.wait(timeout=30), -9, (root / 'Test-run.log').read_text())
            crashed = b.read(root / 'execution-state.json')
            self.assertEqual(crashed['worker_tokens'], 17)  # Native usage is reconciled on resume.
            self.assertEqual(crashed['cycle'], 2)
            old_session_id = crashed['sessions'][0]['id']
            old_worker_pid = crashed['sessions'][-1]['pid']
            for _ in range(100):
                try:
                    os.kill(old_worker_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail('Synthetic Goal RPC process did not release its inherited worker lease')

            resumed = self.launch(root, env, 'resume')
            state = self.await_state(root, lambda value: value['execution'] == 'paused_budget' and value['cycle'] == 2, resumed)
            saved_grant = next(grant for grant in state['grants'] if grant['authority'] == grant_receipt['id'])
            self.assertIsNone(saved_grant['max_cycles'])
            self.assertEqual(saved_grant['goal_token_windows'], 1)
            self.assertEqual(state['worker_tokens'], 34)
            self.assertTrue(all(row['id'] == old_session_id for row in state['sessions']))
            request_id = next(rid for rid, request in state['requests'].items() if request['main_extension'] and request['main_grant_count'] == len(state['grants']))
            self.human(root, c, 'grant', request_id=request_id, cycles=1)
            self.assertEqual(resumed.wait(timeout=30), 0, (root / 'Test-resume.log').read_text())
            final = b.read(root / 'execution-state.json')
            self.assertEqual(final['execution'], 'finish')
            self.assertEqual(final['worker_tokens'], 51)
            self.assertTrue(all(row['id'] == old_session_id for row in final['sessions']))
            self.assertEqual({Path(row['session_file']).name for row in final['sessions']}, {'Test-' + old_session_id + '.jsonl'})
            session_ids = [json.loads(line) for line in (root / 'work/Test-worker-session-ids.jsonl').read_text().splitlines()]
            self.assertGreaterEqual(len(session_ids), 2)
            self.assertEqual(set(session_ids), {old_session_id})

    def test_goal_token_accounting_sums_distinct_persisted_sessions(self):
        c = {**config(), 'mode': 'goal', 'goal_tokens': 100}
        state = p.initial(c, {})
        state['worker_tokens'] = 12
        state['sessions'] = [dict(id='Test-old-goal', tokens_used=12), dict(id='Test-new-goal')]
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, c['run_id'])
            with store.transaction(create=state):
                pass
            core = object.__new__(ab.ActionBridge)
            core.store = store
            core.goal_session_id = 'Test-new-goal'
            core.goal_started = True
            core.record_goal_usage(20)
            saved = store.read()
            self.assertEqual(saved['worker_tokens'], 32)
            self.assertEqual(saved['sessions'][1]['tokens_used'], 20)

    def await_state(self, root, predicate, proc=None):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (root / 'execution-state.json').exists():
                s = b.read(root / 'execution-state.json')
                if predicate(s):
                    return s
            if proc and proc.poll() is not None:
                self.fail('Bridge exited early: ' + (root / 'Test-run.log').read_text() + '\n' + str(b.read(root / 'bridge-status.json')))
            time.sleep(0.02)
        self.fail('Timed out: ' + str(b.read(root / 'bridge-status.json')))

    def human(self, root, c, kind='resolution', **fields):
        raw = {**p.header(c['run_id']), 'id': 'Test-human-' + str(time.time_ns()), 'source': 'pi-command', 'session_id': c['pi_session_id'], 'kind': kind, 'message': 'Test authentic receiver fixture', **fields}
        p.durable(root / 'human-inbox' / (raw['id'] + '.json'), raw)
        return raw

    def test_worker_checkpoint_repairs_repeat_within_cumulative_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, cycles=4)
            env['PPP_TEST_BAD_CHECKPOINT'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['cycle'], 2)
            self.assertEqual(len(state['consumption']), 2)
            self.assertEqual(len(state['sessions']), 4)
            self.assertEqual(sum(row['worker_iterations'] for row in state['consumption']), 2)
            self.assertEqual(sum(row.get('checkpoint_repairs', 0) for row in state['consumption']), 2)
            self.assertEqual(b.read(root / 'bridge-status.json')['checkpoint_repairs'], 2)
            self.assertEqual(sum(event['type'] == 'worker.checkpoint_repair' for event in state['history']), 2)
            self.assertEqual(len(state['actions']['email']['attempts']), 1)

    def test_ping_pong_checkpoint_repairs_do_not_spend_task_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, cycles=2)
            env['PPP_TEST_BAD_CHECKPOINT'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['cycle'], 2)
            self.assertEqual([row['worker_iterations'] for row in state['consumption']], [1, 1])
            self.assertEqual(state['consumption'][0]['checkpoint_repairs'], 2)
            self.assertEqual(state['actions']['footer']['status'], 'verified')

    def test_checkpoint_repair_limit_exhaustion_delivers_unverified_work_without_new_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, cycles=2)
            config = b.read(root / 'config.json')
            config['checkpoint_repair_attempts'] = 1
            p.durable(root / 'config.json', config)
            env['PPP_TEST_BAD_CHECKPOINT'] = 'always'
            proc = self.launch(root, env)
            result = proc.wait(timeout=20)
            state = b.read(root / 'execution-state.json')
            self.assertIn(result, {0, 2}, (root / 'Test-run.log').read_text())
            first = [row for row in state['sessions'] if row['cycle'] == 1]
            self.assertEqual([row['status'] for row in first], ['repair_needed', 'repair_needed'])
            self.assertEqual(state['consumption'][0]['worker_iterations'], 1)
            self.assertEqual(state['consumption'][0]['checkpoint_repairs'], 1)
            self.assertTrue(any(event['type'] == 'worker.repair_budget_exhausted' and 'Checkpoint repair limit exhausted (1/1)' in event['diagnosis'] for event in state['history']))
            self.assertEqual(len(state['grants']), 2)
            exhausted = next(i for i, event in enumerate(state['history']) if event['type'] == 'worker.repair_budget_exhausted')
            self.assertIn('review.applied', [event['type'] for event in state['history'][exhausted:]])
            self.assertIn('worker.partial_result_retained', [event['type'] for event in state['history'][exhausted:]])
            retained = [item for item in state['available_results'] if item['cycle'] == 1]
            self.assertEqual([item['status'] for item in retained], ['unverified'])
            self.assertIn('email.txt', retained[0]['available_files'])
            self.assertTrue((root / 'work/email.txt').is_file())
            self.assertEqual(sum(event['type'] == 'operation.started' for event in state['history']), 0)

    def test_goal_repairs_and_checkpoints_reuse_one_compacting_token_budgeted_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, mode='goal', cycles=1)
            env['PPP_TEST_BAD_CHECKPOINT'] = '1'
            env['PPP_TEST_GOAL_COMPACTION'] = '1'
            env['PPP_TEST_ASSERT_WRITER_SEPARATION'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertEqual(len(prompts), 2)
            self.assertTrue(prompts[0].startswith('/goal ') and '--tokens' not in prompts[0])
            self.assertTrue(prompts[1].startswith('/goal ') and '--tokens' not in prompts[1])
            self.assertNotIn('Core rejected your checkpoint', prompts[1])
            self.assertIn('Core rejected your previous checkpoint (cycle 1)', prompts[1])
            self.assertIn('../TASK.md', prompts[1])
            self.assertIn('../TASK.md', b.read(root / 'work/cycle-context.json')['checkpoint_rejected'])
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['cycle'], 2)
            self.assertEqual(len(state['sessions']), 2)
            self.assertEqual(len({row['id'] for row in state['sessions']}), 1)
            self.assertEqual(state['worker_tokens'], 34)
            self.assertEqual(state['sessions'][0]['status'], 'native_result')
            self.assertTrue(state['available_results'])
            self.assertFalse(any(event['type'] == 'worker.checkpoint_repair' for event in state['history']))
            self.assertGreater(state['worker_seconds'], 0)
            self.assertGreater(state['verification_seconds'], 0)

    def test_invalid_worker_checkpoint_repairs_same_reserved_cycle_without_repeating_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, cycles=3)
            env.update(PPP_TEST_BAD_CHECKPOINT='1', PPP_TEST_CHECKPOINT_REPAIR_TRACKING='1')
            proc = self.launch(root, env)
            result = proc.wait(timeout=15)
            self.assertEqual(result, 0, (root / 'Test-run.log').read_text() + '\n' + str(b.read(root / 'bridge-status.json')) + '\n' + str(b.read(root / 'execution-state.json')))
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['cycle'], 2)
            sessions = [row for row in state['sessions'] if row['action_id'] == 'email' and row['cycle'] == 1]
            self.assertEqual(len(sessions), 2)
            self.assertEqual([row['status'] for row in sessions], ['repair_needed', 'checkpoint'])
            self.assertEqual(sum(event['type'] == 'worker.checkpoint_repair' for event in state['history']), 1)
            self.assertEqual(sum(row['cycle'] == 1 for row in state['consumption']), 1)
            self.assertEqual(state['execution'], 'finish')
            original_bytes = (root / 'work/Test-repair-checkpoint-original').read_bytes()
            self.assertEqual(original_bytes, (root / 'work/Test-rejected-checkpoint-expected').read_bytes())
            original = json.loads(original_bytes)
            self.assertEqual(original['evidence'], ['../TASK.md'])
            self.assertEqual((root / 'work/Test-product-test-executions').read_text(), '2')
            self.assertEqual((root / 'work/Test-next-action-saw-stale-checkpoint').read_text(), 'False')
            self.assertEqual(sum(row['worker_iterations'] for row in state['consumption']), 2)
            self.assertEqual(state['consumption'][0]['checkpoint_repairs'], 1)
            status = b.read(root / 'bridge-status.json')
            self.assertEqual(status['checkpoint_repairs'], 1)
            self.assertEqual((status['worker_tokens'], status['worker_tokens_status']), (None, 'not_measured'))

    def test_missing_checkpoint_schema_is_repaired_instead_of_halted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, cycles=4)
            env['PPP_TEST_BAD_CHECKPOINT_SCHEMA'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['cycle'], 2)
            self.assertEqual([row['status'] for row in state['sessions'][:2]], ['repair_needed', 'checkpoint'])
            self.assertTrue(any(event['type'] == 'worker.checkpoint_repair' for event in state['history']))
            prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
            self.assertEqual(len(prompts), 4)
            self.assertTrue(any('Unsupported protocol/schema' in event.get('diagnosis', '') for event in state['history']))


    def test_checkpoint_repair_does_not_repeat_uncertain_external_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, effect=True, cycles=3)
            env.pop('PPP_TEST_EFFECT')
            env.update(PPP_TEST_JOURNAL='1', PPP_TEST_BAD_CHECKPOINT='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertEqual(state['operations']['email:send']['outcome'], 'succeeded')
            self.assertEqual(sum(event['type'] == 'operation.started' for event in state['history']), 1)
            self.assertTrue((root / 'work/Test-effect-performed').exists())
            self.assertTrue((root / 'work/Test-operation-replay-refused').exists())
            self.assertEqual(sum(row['cycle'] == 1 for row in state['consumption']), 1)

    def test_mvp_worker_ready_claim_is_not_independent_acceptance(self):
        for mode in ('goal', 'ralph'):
            for fault in ('PPP_TEST_CLAIM_ONLY', 'PPP_TEST_WRONG_OUTPUT'):
                with self.subTest(mode=mode, fault=fault), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _, env = self.fixture(root, mode)
                    env[fault] = '1'
                    proc = self.launch(root, env)
                    self.assertEqual(proc.wait(timeout=15), 2)
                    state = b.read(root / 'execution-state.json')
                    self.assertEqual(state['execution'], 'stop')
                    self.assertTrue(all(value != 'pass' for value in state['acceptance'].values()))
                    self.assertEqual(state['cycle'], 1)
                    self.assertEqual(len(state['consumption']), state['cycle'])
                    self.assertTrue(all(action['status'] == 'stalled' for action in state['actions'].values()))
                    requests = [b.read(path) for path in sorted((root / 'reviews').glob('v2-*/request.json'))]
                    self.assertTrue(all(request['checkpoint']['status'] == 'ready' for request in requests[1:]))
                    self.assertTrue(all(row['status'] != 'pass' for request in [b.read(path) for path in (root / 'reviews').glob('*/review.json')] for row in request['assessment']['criteria'].values()))

    def test_project_does_not_call_verification_or_resource_wait_human_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            c = b.load_config(root / 'config.json')
            core = ab.ActionBridge(c)
            with core.store.transaction(create=p.initial(c, ab.pins(c))):
                pass
            for verification, source, expected in [({'status': 'retry'}, None, 'running'), ({'status': 'blocked'}, None, 'attention_required'), (None, 'resource-signal', 'waiting_resource'), (None, 'bounded-recheck', 'waiting_event'), (None, None, 'waiting_event'), (None, 'human-response', 'waiting_human')]:
                with self.subTest(verification=verification, source=source):
                    with core.store.transaction() as state:
                        state.update(execution='wait', verification=verification, wait={'source': source} if source else None)
                    core.project()
                    self.assertEqual(b.read(root / 'bridge-status.json')['status'], expected)


    def test_headless_reviewer_needs_no_identity_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            env['PPP_TEST_HEADLESS_NO_IDS'] = '1'
            p.durable(root / 'config.json', c)
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            result = b.read(root / 'reviews/v2-000001/reviewer-result.json')
            self.assertEqual(set(result), {'decision', 'feedback', 'assessment'})
            self.assertIn('criteria', result['assessment'])
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'finish')

    def test_worker_and_reviewer_extension_flags_are_separate(self):
        for mode in ('ping-pong', 'goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, mode=mode)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider',
                         worker_extensions=['Test-worker.ts'], reviewer_extensions=['Test-review.ts'])
                env.update(PPP_TEST_EXTENSIONS='1', PPP_TEST_WORKER_EXTENSION=str((root / 'Test-worker.ts').resolve()),
                           PPP_TEST_REVIEW_EXTENSION=str((root / 'Test-review.ts').resolve()))
                p.durable(root / 'config.json', c)
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=30), 0, (root / 'Test-run.log').read_text())
                self.assertTrue(list((root / 'reviews').glob('*/reviewer.json')))

    def test_headless_read_path_strips_one_at_before_home_or_relative_resolution(self):
        from headless_reviewer import ReviewerRPC
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            rpc = ReviewerRPC(ab.ActionBridge(b.load_config(root / 'config.json')), root, 'Test-review-session')
            with patch.dict(os.environ, {'HOME': str(root)}):
                for spelling, expected in (('@~/Test-proof', root / 'Test-proof'),
                                           ('@Test-proof', root / 'work/Test-proof'),
                                           ('@@Test-proof', root / 'work/@Test-proof'),
                                           ('Test-proof', root / 'work/Test-proof')):
                    with self.subTest(spelling=spelling):
                        self.assertEqual(rpc.read_path(spelling), str(expected.resolve()))

    def test_headless_at_prefixed_reads_do_not_cause_false_missing_or_retry(self):
        for spelling in ('absolute', 'relative'):
            with self.subTest(spelling=spelling), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env['PPP_TEST_HEADLESS_AT_READS'] = spelling
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('finish', 2, 2))
                self.assertFalse(any(event['type'].startswith('verification.') for event in state['history']))
                for audit in (root / 'reviews').glob('*/reviewer-reads.json'):
                    reads = b.read(audit)
                    self.assertFalse(reads['missing'])
                    self.assertEqual(reads['succeeded'], reads['required'])

    def test_headless_cancellation_stops_owned_reviewer_and_refuses_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_HOLD'] = '1'
            proc = self.launch(root, env)
            deadline = time.monotonic() + 5
            metadata = root / 'reviews/v2-000001/reviewer.json'
            while time.monotonic() < deadline:
                if metadata.exists() and b.read(metadata)['status'] == 'running':
                    break
                time.sleep(0.02)
            self.assertEqual(b.read(metadata)['status'], 'running')
            self.human(root, c, kind='cancel')
            self.assertEqual(proc.wait(timeout=10), 2)
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'cancelled')
            self.assertEqual(b.read(metadata)['status'], 'interrupted')
            with self.assertRaises(ProcessLookupError):
                os.kill(b.read(metadata)['pid'], 0)
            self.assertFalse(metadata.with_name('review.json').exists())
            resumed = self.launch(root, env, 'resume')
            self.assertNotEqual(resumed.wait(timeout=5), 0)
            self.assertEqual(len(list((root / 'reviews').glob('*/queue-receipt.attempt.json'))), 1)

    def test_wrong_worker_checkpoint_identity_is_never_accepted_but_work_is_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, cycles=2)
            c['checkpoint_repair_attempts'] = 1
            p.durable(root / 'config.json', c)
            env['PPP_TEST_WRONG_CHECKPOINT_ID'] = '1'
            proc = self.launch(root, env)
            self.assertIn(proc.wait(timeout=20), {0, 2}, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            first = [row for row in state['sessions'] if row['cycle'] == 1]
            self.assertEqual([row['status'] for row in first], ['repair_needed', 'repair_needed'])
            self.assertTrue(any(event['type'] == 'worker.checkpoint_invalid' and 'Test-wrong-run' in event['diagnosis'] for event in state['history']))
            self.assertTrue(any(event['type'] == 'worker.repair_budget_exhausted' for event in state['history']))
            self.assertNotEqual(state['execution'], 'halt')
            self.assertEqual([item['status'] for item in state['available_results'] if item['cycle'] == 1], ['unverified'])
            self.assertFalse((root / 'unverified-results/cycle-000001/checkpoint.json').exists())

    def test_worker_checkpoint_without_run_identity_is_repaired(self):
        for mode in ('ping-pong', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, env = self.fixture(root, mode=mode, cycles=2 if mode == 'ping-pong' else 1)
                env['PPP_TEST_WRONG_CHECKPOINT_ID'] = 'missing'
                if mode == 'ralph':
                    env['PPP_TEST_UNKNOWN'] = '1'
                proc = self.launch(root, env)
                self.assertIn(proc.wait(timeout=20), {0, 2}, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertNotEqual(state['execution'], 'halt')
                self.assertTrue(any(event['type'] == 'worker.checkpoint_invalid' and 'run_id None' in event['diagnosis'] for event in state['history']))
                self.assertFalse(any(event['type'] == 'attention.required' for event in state['history']))
                self.assertIn('review.applied', [event['type'] for event in state['history']])
                if mode == 'ping-pong':
                    self.assertEqual([row['status'] for row in state['sessions']], ['repair_needed', 'checkpoint'] * 2)
                    self.assertEqual([row['checkpoint_repairs'] for row in state['consumption']], [1, 1])
                    self.assertEqual([row['worker_iterations'] for row in state['consumption']], [1, 1])
                    self.assertEqual(state['execution'], 'finish')
                else:
                    self.assertEqual((state['cycle'], len(state['sessions']), state['sessions'][0]['status']), (1, 1, 'native_result'))
                    self.assertTrue(state['available_results'])
                    self.assertNotEqual(set(state['acceptance'].values()), {'pass'})

    def test_headless_invalid_response_is_repaired_in_the_same_reviewer_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_REPAIR_MALFORMED'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            first = root / 'reviews/v2-000001'
            prompt_history = (first / 'Test-reviewer-prompts-1.jsonl').read_text().splitlines()
            self.assertEqual(len(prompt_history), 2)
            self.assertIn('prior response was not accepted', prompt_history[1])
            self.assertEqual(len(list(first.glob('reviewer-attempt-*.stdout'))), 2)
            self.assertEqual(state['cycle'], 2)
            self.assertEqual(len(list(root.glob('reviews/v2-000001/reviewer.json'))), 1)
            self.assertEqual(b.read(first / 'reviewer-result.json')['decision'], 'endorse')

    def test_headless_transport_errors_do_not_request_response_repairs_and_preserve_work(self):
        for fault in ('http400', 'transport', 'retry_exhausted', 'malformed_then_error', 'rpc'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env['PPP_TEST_HEADLESS_ERROR'] = fault
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=15), 1, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                first = root / 'reviews/v2-000001'
                prompts = (first / 'Test-reviewer-prompts-1.jsonl').read_text().splitlines()
                self.assertEqual(len(prompts), 2 if fault == 'malformed_then_error' else 1)
                self.assertEqual((state['cycle'], state['review_seq']), (2, 1))
                self.assertEqual(state['verification']['kind'], 'reviewer_unavailable')
                self.assertEqual(set(state['acceptance'].values()), {'unknown'})
                self.assertEqual({row['action_id'] for row in state['verification']['unverified_results']}, {'email', 'footer'})
                self.assertEqual(sum(row['worker_iterations'] for row in state['consumption']), 2)
                self.assertEqual(len(state['sessions']), 2)
                self.assertEqual(len(state['grants']), 2)
                self.assertFalse(state['requests'], 'Reviewer transport failure is not a human gate')
                self.assertFalse((first / 'review.json').exists())
                self.assertFalse((first / 'queue-receipt.txt').exists())
                self.assertTrue((first / 'queue-receipt.attempt.json').exists())
                self.assertEqual(b.read(first / 'reviewer.json')['status'], 'interrupted')
                for aid in ('email', 'footer'):
                    self.assertEqual((root / 'work' / (aid + '.txt')).read_text(), 'Test independently inspectable ' + aid)
                for record in state['verification']['unverified_results']:
                    self.assertTrue(Path(record['checkpoint']).is_file())
                    self.assertTrue(record['evidence_archive'])
                    for name, archived in record['evidence_archive'].items():
                        self.assertTrue(Path(archived).is_file(), name)
                reports = [b.read(path)['message'] for path in (root / 'pi-inbox').glob('*.message.json')]
                self.assertTrue(any('Unverified Worker result' in message for message in reports))
                self.assertNotIn('Test-private-provider-detail', json.dumps(state) + ''.join(reports))
                self.assertIn('reviewer.json', state['verification']['diagnosis'])

    def test_headless_native_transport_retry_can_recover_before_settlement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_ERROR'] = 'retry_recovered'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['execution'], state['cycle'], state['review_seq']), ('finish', 2, 2))
            self.assertNotIn('verification', state)
            for first in (root / 'reviews').glob('v2-*'):
                prompts = list(first.glob('Test-reviewer-prompts-*.jsonl'))
                self.assertEqual(len(prompts), 1)
                self.assertEqual(len(prompts[0].read_text().splitlines()), 1)
                self.assertEqual(b.read(first / 'reviewer-result.json')['decision'], 'endorse')

    def test_reviewer_unavailable_is_not_observation_or_safety_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            env['PPP_TEST_REVIEW_UNAVAILABLE'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=10), 1)
            s = b.read(root / 'execution-state.json')
            self.assertNotIn(s['execution'], p.TERMINAL)
            self.assertEqual(s['verification']['kind'], 'reviewer_unavailable')
            self.assertEqual(s['verification']['status'], 'blocked')
            self.assertEqual(s['cycle'], 2)
            self.assertTrue(all(v == 'unknown' for v in s['acceptance'].values()))
            self.assertEqual(len(list((root / 'reviews').glob('*/request.json'))), 1)

    def test_reviewer_timeout_does_not_blindly_dispatch_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c['review_seconds'] = 1
            p.durable(root / 'config.json', c)
            env['PPP_TEST_NO_REVIEW'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=8), 1)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['verification']['kind'], 'reviewer_unavailable')
            self.assertEqual(s['verification']['status'], 'blocked')
            self.assertEqual(s['review_seq'], 1)
            self.assertEqual(len((root / 'work/Test-dispatch.jsonl').read_text().splitlines()), 1)

    def test_cancel_while_waiting_pi_review_rejects_callback_after_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c['review_transport'] = 'pi'
            p.durable(root / 'config.json', c)
            proc = self.launch(root, env)
            self.await_state(root, lambda s: (root / 'reviews/v2-000001/queue-receipt.txt').exists(), proc)
            self.human(root, c, 'cancel')
            self.assertEqual(proc.wait(timeout=5), 2)
            loaded = b.load_config(root / 'config.json')
            with self.assertRaises(ValueError):
                ab.record_review(loaded, SimpleNamespace(review_id=1, decision='endorse', feedback='Test late callback after controller exit'))
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['execution'], 'cancelled')
            self.assertEqual(s['cycle'], 1)
            self.assertEqual(s['review_seq'], 1)
            self.assertIsNone(s.get('last_review'))
            self.assertFalse((root / 'reviews/v2-000001/review.json').exists())

    def test_wait_invalid_input_then_closure_automatic_without_main_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, blocker=True, cycles=2)
            proc = self.launch(root, env)
            s = self.await_state(root, lambda s: s['execution'] == 'wait', proc)
            self.assertEqual(s['actions']['footer']['status'], 'verified')
            self.assertEqual(s['blockers']['B1']['status'], 'open')
            before = s['cycle'], s['review_seq']
            time.sleep(0.5)
            s = b.read(root / 'execution-state.json')
            self.assertEqual((s['cycle'], s['review_seq']), before, 'waiting must not poll models')
            self.human(root, c, blocker_ids=['B1'])
            self.await_state(root, lambda s: len(s['blockers']['B1']['resolutions']) == 1, proc)
            self.assertEqual(b.read(root / 'execution-state.json')['blockers']['B1']['status'], 'open')
            (root / 'work/Test-secure-configured').write_text('Test secure host configuration presence; not a secret')
            self.human(root, c, blocker_ids=['B1'])
            self.assertEqual(proc.wait(timeout=15), 0, (root / 'Test-run.log').read_text())
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['cycle'], 3)
            self.assertEqual([x['scope'] for x in s['consumption']], ['main', 'main', 'closure'])
            self.assertEqual(len(s['grants']), 2)
            self.assertEqual(s['run_id'], c['run_id'])

    def test_explicit_extension_same_identity_and_duplicate_controller_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, cycles=1)
            proc = self.launch(root, env)
            s = self.await_state(root, lambda s: s['execution'] == 'paused_budget', proc)
            duplicate = self.launch(root, env, 'resume')
            self.assertNotEqual(duplicate.wait(timeout=5), 0)
            wake = self.launch(root, env, 'wake')
            self.assertEqual(wake.wait(timeout=5), 0)
            qid = next(iter(s['requests']))
            self.human(root, c, 'grant', request_id=qid, cycles=1)
            self.assertEqual(proc.wait(timeout=15), 0, (root / 'Test-run.log').read_text())
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['run_id'], c['run_id'])
            self.assertEqual(s['cycle'], 2)
            self.assertEqual(len(s['grants']), 3)
            self.assertEqual(len(s['consumption']), 2)

    def test_durable_wait_recovery_and_cancellation_no_late_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, blocker=True, cycles=2)
            proc = self.launch(root, env)
            before = self.await_state(root, lambda s: s['execution'] == 'wait', proc)
            proc.terminate()
            proc.wait(timeout=5)
            self.human(root, c, 'cancel')
            resumed = self.launch(root, env, 'wake')
            self.assertEqual(resumed.wait(timeout=10), 2)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['execution'], 'cancelled')
            self.assertEqual(s['cycle'], before['cycle'])
            again = self.launch(root, env, 'resume')
            self.assertNotEqual(again.wait(timeout=5), 0)
            self.assertEqual(b.read(root / 'execution-state.json')['cycle'], before['cycle'])

    def test_governing_integrity_change_halts_not_silent_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, blocker=True, cycles=2)
            proc = self.launch(root, env)
            self.await_state(root, lambda s: s['execution'] == 'wait', proc)
            (root / 'TASK.md').write_text('Test unauthorized contract replacement')
            self.assertEqual(proc.wait(timeout=5), 2)
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'halt')

    def test_orphan_worker_lock_and_uncertain_effect_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, effect=True)
            proc = self.launch(root, env)
            s = self.await_state(root, lambda s: bool(s['operations']), proc)
            pid = s['sessions'][-1]['pid']
            self.addCleanup(lambda: self.kill_group(pid))
            deadline = time.monotonic() + 3
            while not (root / 'work/Test-effect-performed').exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            proc.kill()
            proc.wait(timeout=5)
            duplicate = self.launch(root, env, 'resume')
            self.assertEqual(duplicate.wait(timeout=5), 1)
            self.assertIn('ownership still held', b.read(root / 'bridge-status.json')['reason'])
            self.kill_group(pid)
            time.sleep(0.1)
            env.pop('PPP_TEST_EFFECT')
            resumed = self.launch(root, env, 'resume')
            # Main budget was spent before interrupted effect; authenticated extension is separate.
            self.assertEqual(resumed.wait(timeout=10), 2)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['operations']['email:send']['outcome'], 'succeeded')
            self.assertEqual(s['cycle'], 2)

    def test_corrupted_independent_review_hash_halts_without_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            env['PPP_TEST_MUTATE_REVIEW'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=5), 1)
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'halt')
            self.assertEqual(b.read(root / 'execution-state.json')['cycle'], 1)


    def test_pi_transport_versioned_review_and_passive_final_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, 'goal')
            c['review_transport'] = 'pi'
            c.pop('thread_id')
            p.durable(root / 'config.json', c)
            bound = b.load_config(root / 'config.json')
            proc = self.launch(root, env)
            seen = set()
            notices = []
            deadline = time.monotonic() + 15
            while proc.poll() is None and time.monotonic() < deadline:
                for message in sorted((root / 'pi-inbox').glob('*.message.json')):
                    if message.name in seen:
                        continue
                    seen.add(message.name)
                    envelope = b.read(message)
                    self.assertEqual(envelope['protocol_version'], 2)
                    self.assertEqual(envelope['schema_version'], 1)
                    self.assertEqual(envelope['session_id'], c['pi_session_id'])
                    if envelope['kind'] == 'review':
                        import re
                        request_path = Path(re.search(r'Read (.+?/request.json),', envelope['message']).group(1))
                        req = b.read(request_path)
                        ab.record_review(bound, SimpleNamespace(review_id=req['review_id'], decision='endorse', feedback='Test independent Pi transport reviewer', assessment=json.dumps(fixture_assessment(req, request_path))))
                    else:
                        notices.append(envelope)
                        self.assertFalse(envelope['trigger_turn'])
                time.sleep(0.02)
            self.assertEqual(proc.wait(timeout=5), 0, (root / 'Test-run.log').read_text())
            terminal = [b.read(x) for x in (root / 'pi-inbox').glob('*.message.json') if b.read(x).get('notice_type') == 'terminal']
            self.assertEqual(len(terminal), 1)
            self.assertFalse(terminal[0]['trigger_turn'])
            self.assertEqual(b.read(root / 'execution-state.json')['execution'], 'finish')

    def test_cancel_active_worker_stops_process_and_preserves_uncertain_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, effect=True)
            proc = self.launch(root, env)
            s = self.await_state(root, lambda s: bool(s['operations']), proc)
            pid = s['sessions'][-1]['pid']
            self.human(root, c, 'cancel')
            self.assertEqual(proc.wait(timeout=10), 2)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['execution'], 'cancelled')
            self.assertEqual(s['operations']['email:send']['outcome'], 'uncertain')
            self.assertIsNone(s['active'])
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_external_resource_signal_wakes_only_arranged_observation_without_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            env['PPP_TEST_RESOURCE'] = '1'
            proc = self.launch(root, env)
            s = self.await_state(root, lambda s: s['execution'] == 'wait', proc)
            self.assertEqual(s['cycle'], 1)
            before = s['review_seq']
            time.sleep(0.3)
            self.assertEqual(b.read(root / 'execution-state.json')['review_seq'], before)
            wrong = subprocess.run([sys.executable, str(HERE / 'bridge.py'), 'signal', '--config', str(root / 'config.json'), '--event-id', 'Test-wrong', '--wake-ref', 'Test-unarranged'], env=env, capture_output=True)
            self.assertNotEqual(wrong.returncode, 0)
            self.assertEqual(b.read(root / 'execution-state.json')['review_seq'], before)
            (root / 'work/Test-resource-restored').write_text('Test actual independently observed restoration')
            signal_proc = subprocess.run([sys.executable, str(HERE / 'bridge.py'), 'signal', '--config', str(root / 'config.json'), '--event-id', 'Test-restored', '--wake-ref', 'Test-arranged-restoration'], env=env, capture_output=True)
            self.assertEqual(signal_proc.returncode, 0, signal_proc.stderr.decode())
            self.assertEqual(proc.wait(timeout=15), 0)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['run_id'], c['run_id'])
            self.assertEqual(s['cycle'], 2)
            self.assertEqual(s['review_seq'], 3)
            self.assertEqual(len(s['grants']), 2)
            self.assertFalse(s['human'])
            self.assertTrue(s['signals']['Test-restored']['processed'])

    def test_console_human_authority_requires_real_interactive_boundary_not_pipe_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c['human_transport'] = 'console'
            p.durable(root / 'config.json', c)
            loaded = b.load_config(root / 'config.json')
            store = p.Store(root, c['run_id'])
            with store.transaction(create=p.initial(loaded, ab.pins(loaded))):
                pass
            noninteractive = subprocess.run([sys.executable, str(HERE / 'bridge.py'), 'human', '--config', str(root / 'config.json')], input=b'{"kind":"cancel","message":"Test pipe cannot approve"}', env=env, capture_output=True)
            self.assertNotEqual(noninteractive.returncode, 0)
            self.assertFalse((root / 'human-inbox').exists())
            # Synthetic console confirmation fixture; not a claim of real human approval.
            with patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=['{"kind":"cancel","message":"Test authentic console fixture"}', 'AUTHORIZE ' + c['run_id']]), patch.object(ab.ActionBridge, 'run', return_value=0):
                self.assertEqual(ab.console_human(loaded), 0)
            receipts = list((root / 'human-inbox').glob('*.json'))
            self.assertEqual(len(receipts), 1)
            raw = b.read(receipts[0])
            self.assertEqual(raw['source'], 'console-command')
            self.assertEqual(store.read()['execution'], 'continue', 'receipt alone has not changed controller state')
            action_bridge = ab.ActionBridge(loaded)
            action_bridge.ingress()
            self.assertEqual(store.read()['execution'], 'cancelled')

    def test_final_delivery_failure_does_not_erase_independent_acceptance_or_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            env['PPP_TEST_FAIL_FINAL'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=15), 1)
            s = b.read(root / 'execution-state.json')
            self.assertEqual(s['execution'], 'finish')
            self.assertTrue(all(v == 'pass' for v in s['acceptance'].values()))
            self.assertEqual(s['cycle'], 2)
            self.assertTrue((root / 'notices/terminal-finish.receipt.attempt.json').exists())
            again = self.launch(root, env, 'resume')
            self.assertNotEqual(again.wait(timeout=5), 0)
            self.assertEqual(len((root / 'work/Test-codex-notices.jsonl').read_text().splitlines()), 1)

    def test_completed_evidence_is_retained_immutably_not_only_as_live_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'work').mkdir()
            source = root / 'work/Test-proof'
            source.write_text('Test completed action evidence')
            hashes = {'Test-proof': b.digest(source)}
            archived = ab.retain_evidence({'root': str(root)}, hashes, time.monotonic() + 5)
            source.write_text('Test later repair evidence')
            target = Path(archived['Test-proof'])
            self.assertEqual(target.read_text(), 'Test completed action evidence')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            target.write_text('Test corrupted retained evidence')
            with self.assertRaisesRegex(ValueError, 'Retained evidence integrity'):
                ab.retain_evidence({'root': str(root)}, hashes, time.monotonic() + 5)

    def test_project_target_evidence_is_directly_accepted_and_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'run'
            root.mkdir()
            c, _ = self.fixture(root)
            c['root'] = str(root)
            work = root / 'work'
            work.mkdir()
            target = Path(tmp) / 'project' / 'site'
            target.mkdir(parents=True)
            source = target / 'index.html'
            source.write_text('Test output')
            c['execution_contract']['target'] = str(target)
            name = os.path.relpath(source, work)
            checkpoint = dict(run_id=c['run_id'], cycle=1, status='progress', summary='Test output', evidence=[name, str(source)])
            p.durable(work / 'checkpoint.json', checkpoint)
            _, snap = b.validate_checkpoint(c, 1)
            self.assertTrue(b.unchanged(c, snap))
            archived = ab.retain_evidence(c, snap['evidence_sha256'], time.monotonic() + 5)
            self.assertEqual(Path(archived[name]).read_text(), 'Test output')
            checkpoint['evidence'] = ['work/Test-missing.txt']
            p.durable(work / 'checkpoint.json', checkpoint)
            with self.assertRaises(ValueError) as error:
                b.validate_checkpoint(c, 1)
            self.assertIn(repr('work/Test-missing.txt'), str(error.exception))
            self.assertIn(str(work / 'work/Test-missing.txt'), str(error.exception))
            self.assertIn(str(work), str(error.exception))
            outside = Path(tmp) / 'outside'
            outside.write_text('Test outside')
            (target / 'escape').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'Evidence escapes') as error:
                b.evidence_path(c, str(target / 'escape'))
            for value in (str(target / 'escape'), str(outside), str(work), str(target)):
                self.assertIn(value, str(error.exception))
            checkpoint['evidence'] = [name, str(source)]
            p.durable(work / 'checkpoint.json', checkpoint)
            source.write_text('Test changed')
            self.assertFalse(b.unchanged(c, snap))
            c['execution_contract']['target'] = str(source)
            self.assertEqual(b.evidence_path(c, str(source)), source.resolve())
            c['execution_contract']['target'] = 'Test descriptive target'
            with self.assertRaisesRegex(ValueError, 'Evidence escapes'):
                b.evidence_path(c, str(source))

    def test_both_modes_work_in_current_absolute_product_target(self):
        for mode in ('goal', 'ralph'):
            for kind in ('root', 'subdirectory', 'file'):
                with self.subTest(mode=mode, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve() / 'run'
                    root.mkdir(mode=0o700)
                    c, env = self.fixture(root, mode=mode)
                    project = Path(tmp).resolve() / 'Test-project'
                    project.mkdir()
                    target = project
                    if kind == 'subdirectory':
                        target = project / 'Test-site'
                        target.mkdir()
                    elif kind == 'file':
                        target = project / 'Test-shell-created.txt'
                        target.write_text('Test old user file')
                    untouched = project / 'Test-user.txt'
                    untouched.write_text('Test preserve existing user changes')
                    c['execution_contract']['target'] = str(target)
                    p.durable(root / 'config.json', c)
                    env['PPP_TEST_PROJECT_CWD'] = '1'
                    proc = self.launch(root, env)
                    self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                    cwd = target if target.is_dir() else target.parent
                    state = b.read(root / 'execution-state.json')
                    self.assertEqual(state['worker_cwd'], str(cwd))
                    for session in state['sessions']:
                        expected_cwd = root / 'ralph' / f'{session["cycle"]:03}' if mode == 'ralph' else cwd
                        self.assertEqual(session['cwd'], str(expected_cwd))
                        header = json.loads(Path(session['session_file']).read_text().splitlines()[0])
                        self.assertEqual(header['cwd'], str(expected_cwd))
                    self.assertTrue((cwd / 'Test-shell-created.txt').is_file())
                    self.assertTrue((root / 'work/checkpoint.json').is_file())
                    self.assertFalse((cwd / 'cycle-context.json').exists())
                    self.assertEqual(untouched.read_text(), 'Test preserve existing user changes')
                    baseline = b.read(root / 'output-baseline.json')
                    self.assertEqual(baseline['roots'], [str(root / 'work'), str(target)])
                    self.assertIn(str(root / 'work/cycle-context.json'), (root / 'CONTRACT.md').read_text())
                    if mode == 'ralph':
                        self.assertNotIn('Shared outputs:', Path(state['sessions'][0]['ralph_path']).read_text())

    def test_goal_target_cwd_and_baseline_survive_native_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'run'
            root.mkdir(mode=0o700)
            c, env = self.fixture(root, mode='goal')
            target = Path(tmp).resolve() / 'Test-existing-project'
            git_project(target, {'a.py': 'a = 1\n'}, {'a.py': 'a = 2  # Test user\n'})
            c['execution_contract']['target'] = str(target)
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_PROJECT_CWD='1', PPP_TEST_KILL_CONTROLLER_AFTER_GOAL_CHECKPOINT='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), -9)
            baseline = (root / 'output-baseline.json').read_bytes()
            launch_record = (root / 'launch-git.json').read_bytes()
            (target / 'Test-user-after-launch.txt').write_text('Test concurrent user file')
            crashed = b.read(root / 'execution-state.json')
            session_id = crashed['sessions'][-1]['id']
            for _ in range(100):
                try:
                    os.kill(crashed['sessions'][-1]['pid'], 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            resumed = self.launch(root, env, 'resume')
            self.assertEqual(resumed.wait(timeout=20), 0, (root / 'Test-resume.log').read_text())
            final = b.read(root / 'execution-state.json')
            self.assertEqual(final['worker_tokens'], 34)
            self.assertEqual(final['worker_cwd'], str(target))
            self.assertTrue(all(session['id'] == session_id and session['cwd'] == str(target) for session in final['sessions']))
            self.assertEqual((root / 'output-baseline.json').read_bytes(), baseline)
            self.assertEqual((root / 'launch-git.json').read_bytes(), launch_record, 'resume never recreates the launch record')
            self.assertNotIn('available_results', final, 'a valid recovered checkpoint must not trigger fallback scanning')
            request = b.read(root / 'reviews/v2-000001/request.json')
            self.assertIsNotNone(request['checkpoint'], 'recovery uses the actual matching checkpoint')

    def test_shell_only_results_survive_real_interrupt_without_session_claims(self):
        for mode in ('goal', 'ralph'):
            for baseline_state in ('complete', 'missing', 'partial'):
                with self.subTest(mode=mode, baseline=baseline_state), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve() / 'run'
                    root.mkdir(mode=0o700)
                    self.fixture(root, mode=mode)
                    c = b.load_config(root / 'config.json')
                    target = Path(tmp).resolve() / 'Test-target'
                    target.mkdir()
                    c['execution_contract']['target'] = str(target)
                    (root / 'work').mkdir()
                    old = target / 'Test-old-user.txt'
                    old.write_text('Test original unrelated user work')
                    baseline = ab.outputs.snapshot(c)
                    if baseline_state == 'partial':
                        baseline['limitations'] = ['Test baseline partial; visibility unknown.']
                    if baseline_state != 'missing':
                        p.durable(root / 'output-baseline.json', baseline)
                    shell = target / 'Test-shell-created.html'
                    shell.write_text('Test shell-only result')
                    secret = target / '.env'
                    secret.write_text('Test never copy private config')
                    state = p.initial(c, ab.pins(c))
                    state['sessions'] = [dict(id='Test-owned', cycle=1, action_id='email', status='interrupted', pid=123, cwd=str(target), session_file=None, started_at=10, ended_at=20)]
                    core = ab.ActionBridge(c)
                    with core.store.transaction(create=state):
                        pass
                    core.preserve_budget_result()
                    core.preserve_budget_result()
                    results = core.store.read()['available_results']
                    self.assertEqual(len(results), 1)
                    result = results[0]
                    self.assertIn(str(shell), result['available_files'])
                    self.assertEqual(Path(result['evidence_archive'][str(shell)]).read_text(), shell.read_text())
                    self.assertNotIn(str(secret), result['discovery_candidates'])
                    self.assertEqual(result['status'], 'unverified')
                    self.assertEqual(set(core.store.read()['acceptance'].values()), {'unknown'})
                    facts = b.read(next(path for name, path in result['evidence_archive'].items() if name.startswith('budget-result-')))
                    self.assertFalse(facts['tool_facts'], 'filesystem discovery must not fabricate owned-session facts')
                    if baseline_state != 'missing':
                        self.assertNotIn(str(old), result['available_files'])
                    else:
                        self.assertIn('unknown origin', ' '.join(result['limitations']))
                    self.assertEqual(old.read_text(), 'Test original unrelated user work')

    def test_launch_diff_shows_removed_user_lines_without_touching_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'run'
            root.mkdir(mode=0o700)
            c, env = self.fixture(root, mode='goal')
            target = Path(tmp).resolve() / 'Test-project'
            probe = git_project(target, {'report.py': 'def f():\n    return 1\n', 'app.config.py': 'K = 1\n', 'clean.py': 'x = 1\n'},
                                {'report.py': '# TODO(user): Test keep idea A\n# Test second user line\ndef f():\n    return 1\n',
                                 'app.config.py': 'K = 2  # Test private\n', 'notes.md': 'Test untracked user note\n'})
            for private_dir in ('.pi/ping-pong/manual-e2e', '.pi-ping-pong/runs/Test-legacy'):
                private = target / private_dir / 'Test-private-report.md'
                private.parent.mkdir(parents=True)
                private.write_text('Test private service contents')
            before = probe()
            c['execution_contract']['target'] = str(target)
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_PROJECT_CWD='1', PPP_TEST_REWRITE_USER='report.py')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            self.assertEqual(probe(), before, 'HEAD, refs and index stay untouched; no lock files')
            record = b.read(root / 'launch-git.json')
            self.assertEqual(set(record['files']), {'report.py', 'notes.md'})
            self.assertEqual(set(record['omitted']), {'app.config.py'}, 'service paths are not launch-evidence rows')
            self.assertNotIn('Test-private-report.md', json.dumps(b.read(root / 'output-baseline.json')))
            self.assertNotIn('Test private', json.dumps(record))
            request = b.read(root / 'reviews/v2-000001/request.json')
            diff = request['launch_diff']
            self.assertEqual(diff['sha256'], b.digest(diff['path']))
            self.assertEqual(diff['files']['report.py'], dict(status='changed', removed_lines=2))
            self.assertEqual(diff['files']['notes.md'], dict(status='unchanged'))
            self.assertEqual(diff['files']['app.config.py']['status'], 'unknown')
            self.assertEqual(diff['coverage'], 'partial')
            self.assertNotIn('clean.py', diff['files'])
            text = Path(diff['path']).read_text()
            self.assertIn('-# TODO(user): Test keep idea A', text)
            self.assertIn('not a verdict', text)
            self.assertNotIn('Test private', text)
            self.assertNotIn(diff['path'], request['evidence_archive'].values())
            prompt = next(root.rglob('Test-review-prompt-1.md')).read_text()
            self.assertIn('Launch diff (evidence ref "launch-diff")', prompt)
            self.assertIn('never a synthetic correction', prompt)

    def test_headless_launch_diff_read_is_audited_and_citable_but_not_required(self):
        for read in ('success', 'error', ''):
            with self.subTest(read=read), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve() / 'run'
                root.mkdir(mode=0o700)
                c, env = self.fixture(root, mode='goal')
                target = Path(tmp).resolve() / 'Test-project'
                git_project(target, {'a.py': 'a = 1\n'}, {'a.py': 'a = 2  # Test user edit\n'})
                c['execution_contract']['target'] = str(target)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env.update(PPP_TEST_PROJECT_CWD='1', PPP_TEST_HEADLESS_READ_LAUNCH_DIFF=read)
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 1 if read == 'error' else 0, (root / 'Test-run.log').read_text())
                directory = root / 'reviews/v2-000001'
                diff = str(Path(b.read(directory / 'request.json')['launch_diff']['path']).resolve())
                reads = b.read(directory / 'reviewer-reads.json')
                self.assertEqual(reads['optional'], [diff])
                self.assertNotIn(diff, reads['required'] + reads['missing'])
                self.assertEqual(diff in reads['succeeded'], read == 'success')
                self.assertEqual(diff in reads['errors'], read == 'error')
                state = b.read(root / 'execution-state.json')
                if read == 'error':
                    self.assertIn('could not access cited material', state['verification']['diagnosis'])
                    self.assertIn('launch-diff', state['verification']['diagnosis'])
                else:
                    self.assertEqual(state['execution'], 'finish')
                    if read:
                        self.assertIn('launch-diff', json.dumps(b.read(directory / 'review.json')['assessment']))

    def test_launch_diff_removed_user_line_fail_sends_correction_to_worker(self):
        # PPP path only: deterministic Worker overwrite + scripted Reviewer fail; no model judgment involved.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'run'
            root.mkdir(mode=0o700)
            c, env = self.fixture(root, mode='ping-pong', cycles=4)
            target = Path(tmp).resolve() / 'Test-project'
            git_project(target, {'report.py': 'def f():\n    return 1\n'},
                        {'report.py': '# TODO(user): Test keep idea A\ndef f():\n    return 1\n'})
            c['execution_contract']['target'] = str(target)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env.update(PPP_TEST_PROJECT_CWD='1', PPP_TEST_REWRITE_USER='report.py', PPP_TEST_LAUNCH_DIFF_FAIL='1')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=30), 0, (root / 'Test-run.log').read_text())
            request = b.read(root / 'reviews/v2-000001/request.json')
            diff = request['launch_diff']
            self.assertEqual(diff['files']['report.py'], dict(status='changed', removed_lines=1))
            self.assertEqual(diff['sha256'], b.digest(diff['path']))
            self.assertIn('-# TODO(user): Test keep idea A', Path(diff['path']).read_text())
            self.assertIn('launch-diff', json.dumps(b.read(root / 'reviews/v2-000001/review.json')['assessment']))
            state = b.read(root / 'execution-state.json')
            planned = [row for row in state['history'] if row['type'] == 'experiment.planned']
            self.assertEqual([row['fingerprint'] for row in planned], ['Test-restore-user-lines'])
            self.assertEqual([row['action_id'] for row in state['consumption']][:2], ['email', 'email'], 'correction goes back to Worker')
            contexts = [json.loads(line) for line in (root / 'work/Test-worker-contexts.jsonl').read_text().splitlines()]
            self.assertEqual((contexts[1]['cycle'], contexts[1]['action_id']), (2, 'email'))
            self.assertEqual(contexts[1]['action']['experiment']['next_step'], 'Test restore removed user lines in report.py')
            self.assertEqual(contexts[1]['action']['experiment']['evidence_refs'], ['launch-diff'])
            self.assertEqual(state['execution'], 'finish')

    def test_launch_record_degrades_for_non_git_errors_and_file_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            plain = base / 'Test-plain'
            plain.mkdir()
            c = dict(run_id='Test-run', execution_contract=dict(target=str(plain)))
            self.assertEqual(ab.launch_diff.record(c)['status'], 'not_git')
            self.assertIsNone(ab.launch_diff.record(dict(run_id='Test-run', execution_contract=dict(target='Test descriptive target'))))
            (base / 'run/reviews/v2-000001').mkdir(parents=True)
            meta = ab.launch_diff.build(c, base / 'run', base / 'run/reviews/v2-000001')
            self.assertEqual(meta['coverage'], 'unknown')
            self.assertNotIn('path', meta)
            project = base / 'Test-project'
            git_project(project, {'one.py': 'a = 1\n', 'two.py': 'b = 1\n'}, {'one.py': 'a = 2\n', 'two.py': 'b = 2\n', 'three.py': 'c\n'})
            only = ab.launch_diff.record(dict(run_id='Test-run', execution_contract=dict(target=str(project / 'one.py'))))
            self.assertEqual((set(only['files']), only['omitted']), ({'one.py'}, {}))
            with patch.object(ab.launch_diff.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 5)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    ab.launch_diff.record(dict(run_id='Test-run', execution_contract=dict(target=str(project))))

    def test_launch_git_failure_does_not_block_and_resume_does_not_recreate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'run'
            root.mkdir(mode=0o700)
            c, env = self.fixture(root, mode='goal')
            target = Path(tmp).resolve() / 'Test-project'
            git_project(target, {'a.py': 'a = 1\n'}, {'a.py': 'a = 2\n'})
            c['execution_contract']['target'] = str(target)
            p.durable(root / 'config.json', c)
            (root / 'launch-git.json').mkdir()  # Simulate unavailable launch record storage.
            env.update(PPP_TEST_PROJECT_CWD='1')
            self.assertEqual(self.launch(root, env).wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['execution'], 'finish')
            self.assertTrue(any(event['type'] == 'outputs.launch_git_unavailable' for event in state['history']))
            self.assertEqual(b.read(root / 'reviews/v2-000001/request.json')['launch_diff']['coverage'], 'unknown')

    def test_missing_launch_baseline_does_not_block_both_modes(self):
        for mode in ('goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, env = self.fixture(root, mode=mode)
                (root / 'output-baseline.json').mkdir()  # Simulate unavailable snapshot storage.
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual(state['execution'], 'finish')
                self.assertTrue(any(event['type'] == 'outputs.baseline_unavailable' for event in state['history']))

    def test_worker_contract_uses_exact_run_paths_and_distinguishes_local_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            bridge = ab.ActionBridge(b.load_config(root / 'config.json'))
            bridge.contract()
            contract = (root / 'CONTRACT.md').read_text()
            self.assertIn(str(root / 'work/checkpoint.json'), contract)
            self.assertIn(str(root / 'work/cycle-context.json'), contract)
            self.assertIn('Ordinary local edits and tests', contract)
            self.assertIn('Evidence may directly reference files inside the absolute filesystem execution_contract.target', contract)


    @staticmethod
    def kill_group(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


    def test_worker_tests_then_one_direct_review_per_result_both_modes(self):
        for mode in ('goal', 'ralph'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, mode)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-independent-provider')
                p.durable(root / 'config.json', c)
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                expected = 1 if mode == 'ralph' else 2
                self.assertEqual((state['cycle'], state['review_seq']), (expected, expected))
                status = b.read(root / 'bridge-status.json')
                if mode == 'ralph':
                    self.assertEqual((status['worker_tokens'], status['worker_tokens_status']), (None, 'not_measured'))
                    self.assertIn('--no-session', status['worker_tokens_reason'])
                self.assertEqual(state['execution'], 'finish')
                self.assertFalse((root / 'eval.py').exists())
                self.assertFalse(list(root.rglob('eval.stdout')))
                self.assertFalse((root / 'evaluator-revisions').exists())
                reviewers = []
                for directory in sorted((root / 'reviews').glob('v2-*')):
                    request = b.read(directory / 'request.json')
                    self.assertGreater(request['cycle'], 0, 'no paid pre-work review')
                    self.assertNotIn('eval', request)
                    self.assertNotIn('report', request, 'Worker supplies evidence, never acceptance judgments')
                    self.assertIn('Test-tests.txt', request['evidence_archive'])
                    self.assertIn('exit=0', Path(request['evidence_archive']['Test-tests.txt']).read_text())
                    review = b.read(directory / 'review.json')
                    self.assertIn('criteria', review['assessment'])
                    reviewers.append(b.read(directory / 'reviewer.json')['session_id'])
                    prompt = (directory / f'Test-reviewer-prompt-{request["review_id"]}.txt').read_text()
                    self.assertIn('do not rerun or re-prove deterministic checks', prompt)
                self.assertEqual(len(set(reviewers)), expected)
                self.assertTrue(set(reviewers).isdisjoint({row['id'] for row in state['sessions']} | {c['pi_session_id']}))
                notices = [b.read(path) for path in (root / 'pi-inbox').glob('*.message.json')]
                self.assertFalse(any('Evaluator started' in row['message'] for row in notices))
                self.assertTrue(all(row['kind'] == 'notice' for row in notices))

    def test_unknown_assessment_never_synthesizes_worker_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, mode='ping-pong', cycles=6)
            env['PPP_TEST_UNKNOWN'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 2)
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (2, 2))
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            self.assertFalse(any(row['type'] == 'experiment.planned' for row in state['history']))
            self.assertTrue(all((root / 'work' / (aid + '.txt')).is_file() for aid in ('email', 'footer')))
            self.assertEqual(len(state['sessions']), 2, 'continue independent work, not fake corrections')

    def test_missing_headless_response_delivers_work_and_continues_independent_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-independent-provider', review_seconds=1)
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_BAD_JSON'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 1)
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (2, 1))
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            self.assertEqual({row['action_id'] for row in state['verification']['unverified_results']}, {'email', 'footer'})
            self.assertEqual(len(list((root / 'reviews').glob('*/reviewer.json'))), 1)
            notices = [b.read(path) for path in (root / 'pi-inbox').glob('*.message.json')]
            self.assertTrue(any(row.get('notice_type') == 'reporter' and 'Unverified Worker result' in row['message'] for row in notices))
            self.assertFalse(state['requests'], 'internal role failure is not a human approval request')

    def test_repeated_concrete_worker_corrections_use_existing_budget_and_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, cycles=4)
            env['PPP_TEST_CORRECTIONS'] = '2'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual([row['action_id'] for row in state['consumption']], ['email', 'email', 'email', 'footer'])
            self.assertEqual(state['review_seq'], 4)
            self.assertEqual(sum(row['type'] == 'experiment.planned' for row in state['history']), 2)
            self.assertEqual(p.Controller(b.load_config(root / 'config.json'), state).remaining('main'), 0)
            self.assertEqual(state['execution'], 'finish')

    def test_old_evaluator_config_and_run_are_rejected_without_mutating_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, _ = self.fixture(root)
            c['eval_argv'] = [sys.executable, str(root / 'eval.py')]
            p.durable(root / 'config.json', c)
            (root / 'eval.py').write_text('raise AssertionError("Test never executed")')
            before = {str(path.relative_to(root)): b.digest(path) for path in root.rglob('*') if path.is_file()}
            with self.assertRaisesRegex(ValueError, 'eval_argv is obsolete'):
                b.load_config(root / 'config.json')
            self.assertEqual(before, {str(path.relative_to(root)): b.digest(path) for path in root.rglob('*') if path.is_file()})
            del c['eval_argv']
            p.durable(root / 'config.json', c)
            core = ab.ActionBridge(b.load_config(root / 'config.json'))
            with core.store.transaction(create=p.initial(core.c, ab.pins(core.c))) as state:
                del state['lifecycle']
            before = {str(path.relative_to(root)): b.digest(path) for path in root.rglob('*') if path.is_file()}
            with self.assertRaisesRegex(ValueError, 'Evaluator-era runs cannot resume'):
                core.run(resume=True)
            self.assertEqual(before, {str(path.relative_to(root)): b.digest(path) for path in root.rglob('*') if path.is_file()})
            self.assertFalse((root / 'reviews').exists())

    def test_missing_review_does_not_release_dependent_or_uncertain_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c['execution_contract']['actions'][0]['depends_on'] = ['email']
            p.durable(root / 'config.json', c)
            env['PPP_TEST_REVIEW_UNAVAILABLE'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=15), 1)
            state = b.read(root / 'execution-state.json')
            self.assertEqual(state['cycle'], 1)
            self.assertTrue((root / 'work/email.txt').is_file())
            self.assertFalse((root / 'work/footer.txt').exists())
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})

    def test_inline_task_and_contract_do_not_require_read_event_ceremony(self):
        for missing_reads in ('PPP_TEST_HEADLESS_SKIP_READS', 'PPP_TEST_HEADLESS_FAIL_TASK_READ'):
            with self.subTest(missing_reads=missing_reads), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root)
                task = 'Test unique actual requirement: preserve the blue Test widget; no external send.'
                (root / 'TASK.md').write_text(task)
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                p.durable(root / 'config.json', c)
                env[missing_reads] = '1'
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 0, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual((state['execution'], state['review_seq']), ('finish', 2))
                for seq in (1, 2):
                    directory = root / 'reviews' / f'v2-{seq:06}'
                    prompt = (directory / f'Test-reviewer-prompt-{seq}.txt').read_text()
                    self.assertIn(task, prompt)
                    inline = json.loads(next(line for line in prompt.splitlines() if line.startswith('{"task":')))
                    self.assertEqual(inline['contract'], c['execution_contract'])
                    self.assertEqual(inline['task'], task)
                    self.assertIn('delivered inline; no read-tool prerequisite', prompt)
                    reads = b.read(directory / 'reviewer-reads.json')
                    self.assertTrue(reads['missing'] if missing_reads == 'PPP_TEST_HEADLESS_SKIP_READS' else not reads['missing'])
                    self.assertNotIn(str((root / 'TASK.md').resolve()), reads['required'] + reads['missing'])
                    self.assertEqual(reads['inline'], [str((root / 'TASK.md').resolve())])
                    self.assertEqual(len(list(directory.glob('reviewer-attempt-*.stdout'))), 1)

    def test_failed_access_to_cited_material_cannot_establish_pass_or_force_worker_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root)
            c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
            p.durable(root / 'config.json', c)
            env['PPP_TEST_HEADLESS_FAIL_CITED_READ'] = '1'
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 1, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (2, 1))
            self.assertIn('could not access cited material', state['verification']['diagnosis'])
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            self.assertEqual(len(state['verification']['unverified_results']), 2)
            self.assertFalse(state['requests'])
            self.assertFalse(any(row['type'] == 'experiment.planned' for row in state['history']))
            directory = root / 'reviews/v2-000001'
            self.assertFalse((directory / 'review.json').exists())
            self.assertEqual(len(list(directory.glob('reviewer-attempt-*.stdout'))), 1)
            self.assertTrue(b.read(directory / 'reviewer-reads.json')['errors'])

    def test_cited_material_access_matches_original_archive_and_successful_aliases(self):
        cases = [('original-error', False), ('archive-error', False),
                 ('original-error,archive-success', True), ('archive-error,original-success', True),
                 ('none', True)]
        for target in ('work', 'authorized-target'):
            for material_reads, accepted in cases:
                with self.subTest(target=target, reads=material_reads), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    c, env = self.fixture(root)
                    c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider')
                    reference = 'email.txt'
                    if target == 'authorized-target':
                        project = root / 'Test-authorized-project'
                        project.mkdir()
                        material = project / 'Test-material.txt'
                        material.write_text('Test retained authorized-target material')
                        c['execution_contract']['target'] = str(project.resolve())
                        reference = str(material.resolve())
                    p.durable(root / 'config.json', c)
                    env.update(PPP_TEST_HEADLESS_READ_REFERENCE=reference, PPP_TEST_HEADLESS_MATERIAL_READS=material_reads)
                    proc = self.launch(root, env)
                    self.assertEqual(proc.wait(timeout=20), 0 if accepted else 1, (root / 'Test-run.log').read_text())
                    state = b.read(root / 'execution-state.json')
                    directory = root / 'reviews/v2-000001'
                    reads = b.read(directory / 'reviewer-reads.json')
                    if material_reads != 'none':
                        self.assertTrue(reads['errors'])
                    self.assertEqual(len(list(directory.glob('reviewer-attempt-*.stdout'))), 1)
                    if accepted:
                        self.assertEqual((state['execution'], state['review_seq']), ('finish', 2))
                        self.assertEqual(set(state['acceptance'].values()), {'pass'})
                    else:
                        self.assertEqual((state['cycle'], state['review_seq']), (2, 1))
                        self.assertIn('could not access cited material', state['verification']['diagnosis'])
                        self.assertEqual(set(state['acceptance'].values()), {'unknown'})
                        self.assertEqual(len(state['verification']['unverified_results']), 2)
                        self.assertFalse((directory / 'review.json').exists())
                        self.assertFalse(state['requests'])
                        self.assertFalse(any(row['type']=='experiment.planned' for row in state['history']))

    def test_existing_human_gaps_are_grouped_and_delivered_when_later_reviewer_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root, blocker=True)
            env.update(PPP_TEST_SECOND_BLOCKER='1', PPP_TEST_REVIEW_UNAVAILABLE_FROM_CYCLE='2')
            proc = self.launch(root, env)
            self.assertEqual(proc.wait(timeout=20), 1, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (2, 2))
            self.assertEqual(state['verification']['kind'], 'reviewer_unavailable')
            self.assertEqual(set(state['acceptance'].values()), {'unknown'})
            self.assertTrue((root / 'work/footer.txt').is_file())
            self.assertEqual(len(state['requests']), 1)
            request = next(iter(state['requests'].values()))
            self.assertEqual(request['blocker_ids'], ['B1', 'B2'])
            self.assertFalse(request['main_extension'], 'Reviewer failure creates no new human or budget gate')
            self.assertEqual({b['reason'] for b in state['blockers'].values()}, {'missing_secret', 'missing_access'})
            notices = [json.loads(line)['Test-message'] for line in (root / 'work/Test-codex-notices.jsonl').read_text().splitlines()]
            questions = [message for message in notices if 'grouped request' in message]
            self.assertEqual(len(questions), 1)
            self.assertIn('B1: Configure Test runtime securely', questions[0])
            self.assertIn('B2: Provide Test service access', questions[0])
            self.assertIn('/ppp-respond', questions[0])
            self.assertIn('these inputs address task blockers, not the unavailable Reviewer', questions[0])
            self.assertTrue(any('Existing results remain available; acceptance is unknown' in message for message in notices))

    def test_goal_budget_limited_full_result_is_preserved_on_reviewer_failure(self):
        for budget_action, fault in (('email', 'malformed'), ('footer', 'malformed'), ('footer', 'http400')):
            with self.subTest(budget_action=budget_action, fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c, env = self.fixture(root, mode='goal')
                c.update(review_transport='pi', review_execution='headless', review_provider='Test-review-provider',
                         review_seconds=1, goal_tokens=17 if budget_action=='email' else 34)
                p.durable(root / 'config.json', c)
                env.update(PPP_TEST_NATIVE_GOAL='1', PPP_TEST_GOAL_BUDGET_LIMIT=budget_action)
                env['PPP_TEST_HEADLESS_BAD_JSON' if fault == 'malformed' else 'PPP_TEST_HEADLESS_ERROR'] = '1' if fault == 'malformed' else fault
                proc = self.launch(root, env)
                self.assertEqual(proc.wait(timeout=20), 1, (root / 'Test-run.log').read_text())
                state = b.read(root / 'execution-state.json')
                self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
                if fault == 'http400':
                    first = root / 'reviews/v2-000001'
                    self.assertEqual(len((first / 'Test-reviewer-prompts-1.jsonl').read_text().splitlines()), 1)
                    self.assertEqual(state['verification']['kind'], 'reviewer_unavailable')
                self.assertEqual(set(state['verification']['blocked_action_ids']), {'email', 'footer'})
                self.assertIsNone(state['active'])
                self.assertEqual(state['worker_tokens'], c['goal_tokens'])
                self.assertEqual(set(state['acceptance'].values()), {'unknown'})
                records = state['verification']['unverified_results']
                record = records[0]
                self.assertIn(budget_action, state['sessions'][0]['action_ids'])
                self.assertIsNone(record['checkpoint'])
                self.assertEqual(record['workspace'], str((root / 'work').resolve()))
                self.assertEqual(record['worker_tokens_total'], c['goal_tokens'])
                self.assertTrue((root / 'work' / (budget_action+'.txt')).is_file())
                self.assertEqual(len({item['cycle'] for item in records}), len(records))
                prompts = [json.loads(line) for line in (root / 'work/Test-worker-prompts.jsonl').read_text().splitlines()]
                self.assertTrue(all(not message.startswith('/goal ') for message in prompts[1:]), 'missing Reviewer feedback never starts a replacement Goal')
                reports = [b.read(path) for path in (root / 'pi-inbox').glob('*.message.json')]
                self.assertTrue(any(row.get('notice_type')=='reporter' and 'Unverified Worker result' in row['message'] and budget_action in row['message'] for row in reports))

    def test_bounded_arranged_wait_is_one_wake_not_model_polling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, env = self.fixture(root)
            env['PPP_TEST_RECHECK'] = '1'
            proc = self.launch(root, env)
            state = self.await_state(root, lambda s: (s.get('wait') or {}).get('source')=='bounded-recheck', proc)
            self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
            self.assertIsNone(state['active'])
            time.sleep(0.25)
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (1, 1))
            self.assertEqual(proc.wait(timeout=15), 0, (root / 'Test-run.log').read_text())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), (2, 3))
            self.assertEqual(len(state['wake_history']), 1)
            self.assertEqual(len((root / 'work/Test-dispatch.jsonl').read_text().splitlines()), 3)

    def test_human_wait_outlives_worker_wall_budget_and_reminders_do_not_poll_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, env = self.fixture(root, blocker=True)
            c['wall_seconds'] = 2
            c['execution_contract']['reminder_seconds'] = 1
            p.durable(root / 'config.json', c)
            proc = self.launch(root, env)
            state = self.await_state(root, lambda s: (s.get('wait') or {}).get('source')=='human-response', proc)
            before = state['cycle'], state['review_seq']
            dispatches = (root / 'work/Test-dispatch.jsonl').read_text().splitlines()
            self.assertIsNone(state['active'])
            time.sleep(2.5)
            self.assertIsNone(proc.poll())
            state = b.read(root / 'execution-state.json')
            self.assertEqual((state['cycle'], state['review_seq']), before)
            self.assertGreaterEqual(sum(row['type']=='wait.reminder' for row in state['history']), 2)
            self.assertEqual((root / 'work/Test-dispatch.jsonl').read_text().splitlines(), dispatches)
            self.assertEqual(len((root / 'work/Test-codex-notices.jsonl').read_text().splitlines()), 1)
            self.human(root, c, 'cancel')
            self.assertEqual(proc.wait(timeout=10), 2)

if __name__ == '__main__':
    unittest.main()
