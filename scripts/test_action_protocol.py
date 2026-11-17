#!/usr/bin/env python3
"""Synthetic protocol 2 regressions; never invokes models or external targets."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import action_protocol as p


def config():
    return dict(protocol_version=2, schema_version=1, run_id='action-test', max_cycles=2,
                execution_contract=dict(target='Test local fixture', reminder_seconds=3600,
                    actions=[dict(id=a, description='Test ' + a) for a in ('footer', 'email', 'dns', 'analytics')],
                    criteria={'footer_ok': 'Test footer independently passes', 'email_ok': 'Test delivery independently passes'},
                    closure=dict(authorized=True, max_cycles=None)))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.s = p.initial(self.c, {'test': 'pinned'})
        self.e = p.Controller(self.c, self.s)
        self.s['reconciled'] = True
        for a in self.s['actions'].values():
            a['eligible'] = True

    def blocker(self, key='resend', actions=None, reason='missing_secret'):
        return self.e.blocker(dict(key=key, reason=reason, needed='Configure Test runtime securely', blocked_actions=actions or ['email']), ['test-proof'])

    def test_explicit_versions_schema_and_dependencies(self):
        for change in ({'protocol_version': 3}, {'schema_version': 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.initial({**self.c, **change}, {})
        c = deepcopy(self.c)
        c['execution_contract']['actions'][0]['depends_on'] = ['unknown']
        with self.assertRaises(ValueError):
            p.initial(c, {})
        c['execution_contract']['actions'][0]['depends_on'] = ['footer']
        with self.assertRaises(ValueError):
            p.initial(c, {})

    def test_blocker_identity_survives_cycles_and_rediscovery(self):
        b = self.blocker()
        self.s['cycle'] = 4
        self.assertEqual(self.blocker(actions=['email', 'dns']), b)
        b2 = self.blocker('dns-access', ['dns'], 'missing_access')
        self.assertNotEqual(b, b2)
        self.assertEqual(len(self.s['blockers']), 2)
        self.assertEqual(self.s['blockers'][b]['found_cycle'], 0)
        self.assertEqual(self.s['blockers'][b]['last_seen_cycle'], 4)
        self.assertEqual(self.s['actions']['footer']['blocked_by'], [])
        self.s['blockers'][b]['status'] = 'resolved'
        self.blocker()
        self.assertEqual(self.s['blockers'][b]['status'], 'open')

    def test_grants_are_additive_and_authority_single_use(self):
        self.e.consume('footer', 'owner-test')
        assess_cycle(self.c, self.s)
        self.e.consume('analytics', 'owner-test')
        assess_cycle(self.c, self.s)
        self.assertEqual(self.e.remaining('main'), 0)
        self.s['human']['H1'] = dict(kind='grant', cycles=3)
        with self.assertRaises(ValueError):
            self.e.grant('H1')
        self.s['human']['H1']['validated'] = True
        self.e.grant('H1')
        self.assertEqual(self.e.remaining('main'), 3)
        self.assertEqual(self.s['cycle'], 2)
        self.assertEqual(len(self.s['consumption']), 2)
        with self.assertRaises(ValueError):
            self.e.grant('H1')

    def test_closure_unlimited_but_causally_bounded(self):
        bid = self.blocker()
        self.s['blockers'][bid]['status'] = 'resolved'
        provenance = dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test validated resolution', evidence_refs=['test-proof'])
        email = self.s['actions']['email']
        self.e.closure(email, provenance, ['test-proof'])
        self.assertEqual(self.e.remaining('closure'), float('inf'))
        self.assertEqual(self.s['actions']['analytics']['scope'], 'main')
        with self.assertRaises(ValueError):
            self.e.closure(self.s['actions']['analytics'], provenance, ['test-proof'])
        repair = p.action(dict(id='repair', description='Test required error-handling repair'))
        self.e.closure(repair, {**provenance, 'parent_action_id': 'email'}, ['test-proof'])
        self.assertEqual(repair['scope'], 'closure')
        for bad in ({**provenance, 'evidence_refs': []}, {**provenance, 'blocker_id': 'B9'}, {k: v for k, v in provenance.items() if k != 'reason'}):
            with self.assertRaises(ValueError):
                self.e.closure(email, bad, ['test-proof'])

    def test_transaction_rollback_and_durable_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            with self.assertRaises(ValueError):
                with store.transaction() as s:
                    s['cycle'] = 99
                    raise ValueError('Test interrupted transaction')
            self.assertEqual(store.read()['cycle'], 0)
            with self.assertRaises(ValueError):
                with store.transaction(create=self.s):
                    pass
            self.assertEqual((Path(tmp) / 'execution-state.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((Path(tmp) / 'execution-state.json').read_text())['run_id'], self.c['run_id'])

    def test_secret_values_rejected(self):
        with self.assertRaises(ValueError):
            self.e.blocker(dict(key='test', reason='missing_secret', needed='RESEND_API_KEY=private-test-value', blocked_actions=['email']), [])


def report(c, state):
    actions = []
    for a in state['actions'].values():
        raw = {k: deepcopy(a[k]) for k in ('id', 'description', 'depends_on', 'operations')}
        actions.append(dict(action=raw, status='stalled' if a['status'] == 'decomposed' else a['status'], eligible=True, scope_authorized=True, dependencies_valid=True, evidence_refs=['test-proof'], attempt=None, experiment=None))
    return {**p.header(c['run_id']), 'cycle': state['cycle'], 'review_id': state['review_seq'], 'state_sha256': p.sha(state), 'target': c['execution_contract']['target'], 'source_state': 'Test independent source digest', 'safe': True, 'halt_reason': None,
            'actions': actions, 'blockers': [], 'resolutions': [], 'grants': [], 'criteria': {cid: dict(status='unknown', evidence_refs=[]) for cid in state['acceptance']},
            'reconciliation': dict(fresh=True, approvals_applicable=True, evidence_refs=['test-proof'], operations=[])}


def experiment(fingerprint='different-test'):
    return dict(hypothesis='Test provider configuration', material_difference='Test different verified environment', expected_evidence='Test diagnostic output', next_step='Test select branch from diagnostic', fingerprint=fingerprint, evidence_refs=['test-proof'])


def attempt(fingerprint='same-test', assessment='none'):
    return dict(strategy='Test rejection diagnosis', state_before='Test state digest', outcome='Test provider rejection', fingerprint=fingerprint, assessment=assessment, evidence_refs=['test-proof'])


def assess_cycle(c, state):
    r = report(c, state)
    selected = state['consumption'][-1]
    result = next(x for x in r['actions'] if x['action']['id'] == selected['action_id'])
    result['attempt'] = attempt('Test-verified-cycle-' + str(selected['cycle']), 'verified')
    p.Controller(c, state).apply(r, {'test-proof'}, 'Test independently verified fixture progress')


class TransitionTests(RegistryTests):
    def test_native_goal_dispatch_keeps_real_dependencies_and_scoped_operation_identity(self):
        self.c.update(mode='goal', goal_tokens=100)
        self.s['actions']['dns']['depends_on'] = ['email']
        self.blocker(actions=['email'])
        self.s['actions']['footer']['operations'] = [dict(id='publish', kind='Test effect', target='Test sink')]
        self.s['actions']['analytics']['operations'] = [dict(id='send', kind='Test effect', target='Test other sink')]
        self.e.consume('footer', 'Test-owner')
        self.assertEqual(self.s['active']['action_ids'], ['footer', 'analytics'])
        self.assertEqual(self.s['consumption'][0]['action_ids'], ['footer', 'analytics'])
        self.s['sessions'] = [dict(owner='Test-owner', status='running')]
        self.assertEqual(self.e.operation('footer', 'publish', 'Test-owner'), 'footer:publish')
        self.assertEqual(self.e.operation('analytics', 'send', 'Test-owner'), 'analytics:send')
        self.assertEqual(self.s['cycle'], 1)
        with self.assertRaisesRegex(ValueError, 'must not replay'):
            self.e.operation('analytics', 'send', 'Test-owner')
        with self.assertRaisesRegex(ValueError, 'exclusive worker ownership'):
            self.e.operation('email', 'send', 'Test-owner')

    def test_goal_launch_limit_counts_only_new_native_windows(self):
        self.c.update(mode='goal', goal_max_launches=2)
        self.c.pop('goal_tokens', None)
        e = self.e
        self.assertIsNone(e.goal_token_budget())
        self.assertEqual(e.remaining('main'), 2)
        # Durable reservation of window W1 before dispatch, then a recovered row of the same window.
        self.s['sessions'] = [dict(id='Test-s', goal_window_id='W1', status='starting', goal_started=False)]
        self.assertEqual(e.remaining('main'), 2)
        self.s['sessions'].append(dict(id='Test-s', goal_window_id='W1', status='interrupted', goal_started=True, goal_status='active'))
        self.assertEqual(e.remaining('main'), 2, 'Recovery/continuation of the same window spends no launch')
        self.s['sessions'][-1]['goal_status'] = 'complete'
        self.assertEqual(e.remaining('main'), 1)
        self.s['sessions'].append(dict(id='Test-s', goal_window_id='W2', status='checkpoint', goal_started=True, goal_status='complete'))
        self.assertEqual(e.remaining('main'), 0)
        self.s['grants'].append(dict(id='G3', scope='main', max_cycles=None, goal_token_windows=1, authority='Test-human'))
        self.assertEqual(e.remaining('main'), 1)
        self.c['goal_tokens'] = 10
        self.s['worker_tokens'] = 20
        self.assertEqual(e.remaining('main'), 0, 'An explicit cumulative token cap still bounds Goal')

    def test_native_mixed_scope_dispatch_charges_each_scope_without_splitting_objective(self):
        for mode in ('goal', 'ralph'):
            for anchor in ('footer', 'email'):
                with self.subTest(mode=mode, anchor=anchor):
                    c = {**config(), 'mode': mode, 'goal_tokens': 100}
                    c['max_cycles'] = 4
                    c['execution_contract']['closure']['max_cycles'] = 2
                    state = p.initial(c, {})
                    state['reconciled'] = True
                    for action in state['actions'].values():
                        action['eligible'] = True
                    core = p.Controller(c, state)
                    bid = core.blocker(dict(key='Test-resolved', reason='missing_access', needed='Test access', blocked_actions=['email']), ['test-proof'])
                    state['blockers'][bid]['status'] = 'resolved'
                    core.closure(state['actions']['email'], dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test restored access', evidence_refs=['test-proof']), ['test-proof'])
                    state['actions']['dns']['depends_on'] = ['email']
                    core.consume(anchor, 'Test-owner')
                    self.assertEqual(set(state['active']['action_ids']), set(state['actions']))
                    core.reserve_worker_iteration(anchor)
                    row = state['consumption'][0]
                    self.assertEqual(row['worker_scope_grants'], {'closure': ['initial-closure'] * 2, 'main': ['initial-main'] * 2})
                    self.assertEqual(core.grant_used('initial-main'), 2)
                    self.assertEqual(core.grant_used('initial-closure'), 2)
                    if mode == 'ralph':
                        self.assertEqual((core.remaining('main'), core.remaining('closure')), (2, 0))
                        before = deepcopy(row)
                        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                            core.reserve_worker_iteration(anchor)
                        self.assertEqual(row, before, 'Failed mixed-scope reservation is atomic even before transaction rollback')
                    else:
                        state['worker_tokens'] = 37
                        self.assertEqual((core.remaining('main'), core.remaining('closure')), (63, 63))
                    with tempfile.TemporaryDirectory() as tmp:
                        store = p.Store(tmp, c['run_id'])
                        with store.transaction(create=state):
                            pass
                        self.assertEqual(store.read()['consumption'], state['consumption'])
                        with store.transaction() as corrupt:
                            corrupt['consumption'][0]['worker_scope_grants']['closure'].pop()
                        with self.assertRaisesRegex(ValueError, 'scope grant ledger'):
                            store.read()

    def test_native_goal_unknown_cannot_reuse_a_previous_peer_correction(self):
        self.c.update(mode='goal', goal_tokens=100)
        self.s['actions']['email']['continuation'] = dict(next_step='Test previous remaining work', evidence_refs=['test-proof'])
        self.s['actions']['dns']['experiment'] = experiment('Test previous correction')
        self.e.consume('footer', 'Test-owner')
        r = report(self.c, self.s)
        r['actions'][0]['attempt'] = attempt('Test unknown whole result', 'informative')
        self.apply(r)
        self.assertFalse(self.e.available())
        self.assertNotIn('continuation', self.s['actions']['email'])
        self.assertIsNone(self.s['actions']['dns']['experiment'])
        self.assertEqual(set(self.s['acceptance'].values()), {'unknown'})

    def test_goal_budget_interruption_remains_eligible_for_explicit_grant(self):
        self.c.update(mode='goal', goal_tokens=100)
        self.e.consume('footer', 'owner-test')
        self.s['worker_tokens'] = 118
        self.s['sessions'].append(dict(cycle=self.s['cycle'], action_id='footer', action_ids=self.s['active']['action_ids'], status='budget_limited'))
        r = report(self.c, self.s)
        next(x for x in r['actions'] if x['action']['id'] == 'footer')['attempt'] = attempt('Test-budget-interruption', 'informative')
        self.apply(r)
        self.assertEqual(self.s['actions']['footer']['status'], 'pending')
        self.assertEqual(self.e.transition(), ('paused_budget', None))
        self.assertEqual(self.s['worker_tokens'], 118)
        self.s['human']['Test-grant'] = dict(kind='grant', cycles=1, validated=True)
        self.e.grant('Test-grant')
        self.apply(report(self.c, self.s))
        self.assertEqual(self.s['actions']['footer']['status'], 'pending')
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.e.consume('email', 'owner-test')
        assess_cycle(self.c, self.s)
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        self.assertNotIn('footer', [a['id'] for a in self.e.available()], 'Another native result needs concrete remaining work, not a synthetic replay')

    def apply(self, r):
        self.e.apply(r, {'test-proof'}, 'Test independent review')

    def test_compound_action_decomposition_can_finish_after_blocker_resolution(self):
        composite_spec = dict(id='compound', description='Test compound work with independent and access-gated parts')
        self.s['actions']['compound'] = p.action(composite_spec)
        self.c['execution_contract']['actions'].append(composite_spec)
        dependent = dict(id='after-compound', description='Test action depending on all compound parts', depends_on=['compound'])
        self.c['execution_contract']['actions'].append(dependent)
        self.s['actions']['after-compound'] = p.action(dependent)
        result = report(self.c, self.s)
        for item in result['actions']:
            item.update(status='verified', eligible=False)
        next(item for item in result['actions'] if item['action']['id'] == 'compound').update(status='stalled', eligible=False)
        next(item for item in result['actions'] if item['action']['id'] == 'after-compound').update(status='pending', eligible=True)
        independent = dict(id='independent-part', description='Test locally available part', depends_on=[], operations=[])
        blocked = dict(id='access-part', description='Test access-gated part', depends_on=[], operations=[])
        for raw, eligible in ((independent, True), (blocked, True)):
            result['actions'].append(dict(action=raw, status='pending', eligible=eligible, scope_authorized=True,
                                          dependencies_valid=True, evidence_refs=['test-proof'], attempt=None, experiment=None))
        result['decompositions'] = [dict(parent_id='compound', child_ids=['independent-part', 'access-part'], complete=True)]
        result['blockers'] = [dict(blocker=dict(key='Test-access', reason='missing_access', needed='Test restore access',
                                                  blocked_actions=['access-part']), evidence_refs=['test-proof'])]
        self.apply(result)
        self.assertEqual(self.s['actions']['compound']['status'], 'decomposed')
        self.assertEqual(self.e.transition(), ('continue', 'independent-part'))
        self.assertEqual(self.s['actions']['access-part']['blocked_by'], ['B1'])

        self.e.consume('independent-part', 'Test-independent-owner')
        result = report(self.c, self.s)
        result['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        independent_result = next(row for row in result['actions'] if row['action']['id'] == 'independent-part')
        independent_result.update(status='verified', attempt=attempt('Test-independent-part', 'verified'))
        self.apply(result)
        self.assertEqual(self.e.transition(), ('wait', None))
        blocker_id = self.s['actions']['access-part']['blocked_by'][0]
        request_id = self.s['wait']['reference']
        self.s['human']['H1'] = dict(id='H1', kind='resolution', request_id=request_id,
                                    blocker_ids=[blocker_id], source='Test addressed response', message='Test access restored', processed=False)
        self.s['blockers'][blocker_id]['status'] = 'open'

        result = report(self.c, self.s)
        result['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        result['resolutions'] = [dict(blocker_id=blocker_id, human_id='H1', valid=True,
                                      approval_applicable=False, evidence_refs=['test-proof'])]
        access_result = next(row for row in result['actions'] if row['action']['id'] == 'access-part')
        access_result.update(status='pending', eligible=True)
        self.apply(result)
        self.assertEqual(self.s['blockers'][blocker_id]['status'], 'resolved')
        self.assertEqual(self.e.transition(), ('continue', 'access-part'))

        self.e.consume('access-part', 'Test-access-owner')
        result = report(self.c, self.s)
        result['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        access_result = next(row for row in result['actions'] if row['action']['id'] == 'access-part')
        access_result.update(status='verified', attempt=attempt('Test-access-part', 'verified'))
        self.apply(result)
        self.assertEqual(self.s['actions']['compound']['status'], 'decomposed')
        self.assertEqual(self.e.transition(), ('continue', 'after-compound'))
        self.e.consume('after-compound', 'Test-dependent-owner')
        result = report(self.c, self.s)
        result['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        dependent_result = next(row for row in result['actions'] if row['action']['id'] == 'after-compound')
        dependent_result.update(status='verified', attempt=attempt('Test-after-compound', 'verified'))
        self.apply(result)
        self.assertEqual(self.e.transition(), ('finish', None))

    def test_decomposition_cycle_is_rejected_and_cannot_false_finish(self):
        left = dict(id='left', description='Test left compound action', depends_on=[], operations=[])
        right = dict(id='right', description='Test right compound action', depends_on=[], operations=[])
        self.c['execution_contract']['actions'].extend([left, right])
        self.s['actions'].update({row['id']: p.action(row) for row in (left, right)})
        result = report(self.c, self.s)
        result['decompositions'] = [
            dict(parent_id='left', child_ids=['right'], complete=True),
            dict(parent_id='right', child_ids=['left'], complete=True),
        ]
        with self.assertRaisesRegex(ValueError, 'Cyclic action decomposition'):
            self.apply(result)

    def test_blocked_dependency_chain_unblocks_in_order_while_independent_action_runs(self):
        dependent = dict(id='verify-email', description='Test dependent verification', depends_on=['email'])
        self.c['execution_contract']['actions'].append(dependent)
        self.s['actions']['verify-email'] = p.action(dependent)
        self.s['actions']['verify-email']['eligible'] = True
        self.s['actions']['dns']['status'] = self.s['actions']['analytics']['status'] = 'verified'
        bid = self.blocker()
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.assertNotIn('verify-email', {a['id'] for a in self.e.available()})
        self.s['actions']['footer']['status'] = 'verified'
        self.s['blockers'][bid]['status'] = 'resolved'
        root = dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test verified access restoration', evidence_refs=['test-proof'])
        self.e.closure(self.s['actions']['email'], root, {'test-proof'})
        self.assertEqual([a['id'] for a in self.e.available()], ['email'])
        self.s['actions']['email']['status'] = 'verified'
        self.assertIn('verify-email', {a['id'] for a in self.e.available()})

    def test_missing_resend_does_not_block_footer_and_groups_multiple_blockers(self):
        b1 = self.blocker()
        b2 = self.blocker('dns', ['dns'], 'missing_access')
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.assertFalse(self.s['requests'])
        self.s['actions']['footer']['status'] = 'verified'
        self.s['actions']['analytics']['status'] = 'verified'
        self.assertEqual(self.e.transition(), ('wait', None))
        q = next(iter(self.s['requests'].values()))
        self.assertEqual(q['blocker_ids'], [b1, b2])
        self.assertEqual(self.s['wait']['source'], 'human-response')

    def test_partial_invalid_resolution_and_closure_after_exhaustion(self):
        b1 = self.blocker()
        b2 = self.blocker('dns', ['dns'], 'missing_access')
        self.s['actions']['footer']['status'] = 'verified'
        self.e.consume('analytics', 'Test-owner')
        assess_cycle(self.c, self.s)
        self.e.consume('analytics', 'Test-owner')
        assess_cycle(self.c, self.s)
        self.c['pi_session_id'] = 'Test-session'
        human = {**p.header(self.c['run_id']), 'id': 'H1', 'session_id': 'Test-session', 'kind': 'resolution', 'source': 'pi-command', 'blocker_ids': [b1, b2], 'message': 'Test configured both resources'}
        self.e.ingress(human, 'Test-session')
        self.assertEqual(self.s['blockers'][b1]['status'], 'open')
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=b, human_id='H1', valid=b == b2, approval_applicable=False, evidence_refs=['test-proof']) for b in (b1, b2)]
        self.apply(r)
        self.assertEqual(self.s['blockers'][b1]['status'], 'open')
        self.assertEqual(self.s['blockers'][b2]['status'], 'resolved')
        self.assertEqual(self.e.transition(), ('continue', 'dns'))
        self.assertEqual(self.s['actions']['dns']['scope'], 'closure')
        self.assertEqual(self.s['actions']['analytics']['scope'], 'main')
        self.assertEqual(self.e.remaining('main'), 0)
        self.assertEqual(self.s['cycle'], 2)

    def test_technical_restoration_cannot_manufacture_approval(self):
        bid = self.blocker('approval', ['email'], 'approval_required')
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=bid, human_id=None, valid=True, approval_applicable=False, evidence_refs=['test-proof'])]
        with self.assertRaisesRegex(ValueError, 'manufacture'):
            self.apply(r)
        r['resolutions'][0]['valid'] = False
        self.apply(r)
        self.assertEqual(self.s['blockers'][bid]['status'], 'open')

    def test_grouped_blocker_and_distinct_budget_request(self):
        self.blocker()
        for _ in range(2):
            self.e.consume('footer', 'Test-owner')
            assess_cycle(self.c, self.s)
        self.assertEqual(self.e.transition(), ('wait', None))
        q = next(iter(self.s['requests'].values()))
        self.assertTrue(q['main_extension'])
        self.c['pi_session_id'] = 'Test-session'
        h = {**p.header(self.c['run_id']), 'id': 'H2', 'kind': 'grant', 'session_id': 'Test-session', 'source': 'pi-command', 'request_id': q['id'], 'cycles': 2, 'message': 'Test explicitly authorize two extra main cycles'}
        self.e.ingress(h, 'Test-session')
        r = report(self.c, self.s)
        r['grants'] = ['H2']
        self.apply(r)
        self.assertEqual(self.e.remaining('main'), 2)
        self.assertEqual(self.s['cycle'], 2)
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        with self.assertRaises(ValueError):
            self.e.ingress(h, 'Test-session')
        with self.assertRaises(ValueError):
            self.apply(r)

    def test_budget_pause_not_stopped_and_no_counter_reset(self):
        for _ in range(2):
            self.e.consume('footer', 'Test-owner')
            assess_cycle(self.c, self.s)
        self.assertEqual(self.e.transition(), ('paused_budget', None))
        self.assertEqual(len(self.s['consumption']), 2)

    def test_goal_budget_grant_adds_one_configured_token_window_per_cycle(self):
        c = {**self.c, 'mode': 'goal', 'goal_tokens': 50}
        state = p.initial(c, {})
        state['worker_tokens'] = 50
        state['human']['H1'] = dict(kind='grant', cycles=2, validated=True)
        controller = p.Controller(c, state)
        self.assertEqual(controller.remaining('main'), 0)
        controller.grant('H1')
        self.assertEqual(controller.goal_token_budget(), 150)
        self.assertEqual(controller.remaining('main'), 100)

    def test_abandon_exhausted_worker_repair_releases_active_action(self):
        self.c['max_cycles'] = self.s['grants'][0]['max_cycles'] = 1
        self.e.consume('footer', 'Test-owner')
        self.e.abandon_worker_repair('Test iteration budget exhausted')
        self.assertIsNone(self.s['active'])
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        self.assertEqual(self.e.transition(), ('stop', None))
        self.assertTrue(any(event['type'] == 'worker.repair_budget_exhausted' for event in self.s['history']))

    def test_checkpoint_repairs_have_own_limit_and_spend_no_task_iterations(self):
        self.c['max_cycles'] = self.s['grants'][0]['max_cycles'] = 1
        self.c['checkpoint_repair_attempts'] = 2
        self.e.consume('footer', 'Test-owner')
        self.assertEqual([self.e.reserve_checkpoint_repair('footer') for _ in range(2)], [1, 2])
        with self.assertRaisesRegex(ValueError, 'Checkpoint repair limit exhausted'):
            self.e.reserve_checkpoint_repair('footer')
        self.assertEqual(self.s['consumption'][0]['worker_iterations'], 1)
        self.assertEqual(self.s['consumption'][0]['checkpoint_repairs'], 2)
        self.assertEqual(self.e.remaining('main'), 0)

    def test_worker_iteration_budget_counts_ralph_repairs_without_changing_logical_cycle(self):
        self.c['max_cycles'] = self.s['grants'][0]['max_cycles'] = 2
        self.e.consume('footer', 'Test-owner')
        self.e.reserve_worker_iteration('footer')
        self.assertEqual(self.s['cycle'], 1)
        self.assertEqual(self.s['consumption'][0]['worker_iterations'], 2)
        self.assertEqual(self.e.remaining('main'), 0)
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.e.reserve_worker_iteration('footer')

    def test_goal_checkpoints_do_not_consume_iteration_budget(self):
        c = {**self.c, 'mode': 'goal', 'goal_tokens': 50, 'max_cycles': 1}
        state = p.initial(c, {})
        controller = p.Controller(c, state)
        state['reconciled'] = True
        for action in state['actions'].values():
            action['eligible'] = True
        self.assertTrue(all(grant['max_cycles'] is None for grant in state['grants']))
        controller.consume('footer', 'Test-goal-owner')
        state['consumption'][0]['assessment'] = {'attempt': {'assessment': 'verified'}}
        state['active'] = None
        controller.consume('email', 'Test-goal-owner')
        self.assertEqual(state['cycle'], 2)
        self.assertEqual(controller.remaining('main'), 50)

    def test_repair_iteration_after_budget_grant_uses_new_grant(self):
        self.c['max_cycles'] = 1
        self.s['grants'][0]['max_cycles'] = 1
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            with store.transaction() as state:
                controller = p.Controller(self.c, state)
                controller.consume('footer', 'Test-owner')
                state['grants'].append(dict(id='G1', scope='main', max_cycles=1, authority='Test-human-grant'))
                controller.reserve_worker_iteration('footer')
            saved = store.read()
            self.assertEqual(saved['consumption'][0]['worker_iteration_grants'], ['initial-main', 'G1'])
            self.assertEqual(p.Controller(self.c, saved).remaining('main'), 0)
            with store.transaction() as state:
                state['consumption'][0].pop('worker_iteration_grants')
            recovered = store.read()
            self.assertEqual(recovered['consumption'][0]['worker_iteration_grants'], ['initial-main', 'G1'])

    def test_blocked_verification_holds_failed_action_but_keeps_independent_work(self):
        self.s['actions']['analytics']['depends_on'] = ['email']
        p.dependencies(self.s['actions'])
        self.e.consume('email', 'Test-owner')
        self.s['active'] = None
        self.s['verification'] = {'status': 'blocked', 'blocked_action_ids': ['email']}
        self.s['execution'] = 'wait'
        self.assertEqual({row['id'] for row in self.e.available()}, {'footer', 'dns'})
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.e.consume('footer', 'Test-independent-owner')
        self.assertEqual(self.s['acceptance'], {'footer_ok': 'unknown', 'email_ok': 'unknown'})

    def test_informative_failure_experiment_and_action_local_stall(self):
        self.c['max_cycles'] = self.s['grants'][0]['max_cycles'] = 3
        self.e.consume('footer', 'Test-owner')
        r = report(self.c, self.s)
        r['actions'][0].update(attempt=attempt(assessment='informative'), experiment=experiment())
        self.apply(r)
        self.assertEqual(self.e.transition(), ('replan', 'footer'))
        self.e.consume('footer', 'Test-owner-2')
        r = report(self.c, self.s)
        r['actions'][0]['attempt'] = attempt(assessment='informative')
        self.apply(r)
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        self.assertEqual(self.e.transition(), ('continue', 'email'))
        for a in self.s['actions'].values():
            a['status'] = 'stalled'
        self.assertEqual(self.e.transition(), ('stop', None))
        self.assertNotEqual(set(self.s['acceptance'].values()), {'pass'})

    def test_equivalent_experiment_cannot_evade_loop_detection(self):
        a = self.s['actions']['email']
        self.e.attempt(a, attempt(), None, {'test-proof'})
        with self.assertRaisesRegex(ValueError, 'Equivalent'):
            self.e.experiment(a, experiment('same-test'), {'test-proof'})

    def test_blocked_review_still_groups_real_blockers_after_independent_work(self):
        self.e.blocker(dict(key='Test-access', reason='missing_access', needed='Test actual service access', blocked_actions=['email']), ['test-proof'])
        self.s['verification'] = dict(status='blocked', blocked_action_ids=[])
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.assertFalse(self.s['requests'])
        for value in self.s['actions'].values():
            if value['id'] != 'email':
                value['status'] = 'verified'
        self.assertEqual(self.e.transition(), ('verification_blocked', None))
        request = next(iter(self.s['requests'].values()))
        self.assertEqual(request['blocker_ids'], ['B1'])
        self.assertFalse(request['main_extension'])
        self.assertEqual(self.s['blockers']['B1']['escalation'], 'requested')
        self.assertEqual(self.e.transition(), ('verification_blocked', None))
        self.assertEqual(len(self.s['requests']), 1)
        self.assertIsNone(self.s['wait'], 'unavailable Reviewer is not itself a human-response gate')

    def test_wait_reminders_are_local_deduplicated_and_spend_nothing(self):
        for a in self.s['actions'].values():
            a['status'] = 'stalled'
        self.blocker()
        self.e.transition(now=1000)
        before = deepcopy(self.s['consumption'])
        self.assertIsNone(self.e.reminder(1001))
        rid = self.e.reminder(5000)
        self.assertIsNotNone(rid)
        self.assertIsNone(self.e.reminder(5000))
        self.assertEqual(self.s['consumption'], before)
        self.assertEqual(self.e.transition(now=9000000), ('wait', None))
        with self.assertRaises(ValueError):
            self.e.arrange_wait('model-poll', 'Test invalid')

    def test_cancellation_halt_and_stop_precede_late_resolution(self):
        for terminal in ('cancelled', 'halt', 'stop'):
            self.s['execution'] = terminal
            r = report(self.c, self.s)
            r['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
            self.apply(r)
            self.assertEqual(self.e.transition(), (terminal, None))
        self.s['execution'] = 'continue'
        r['safe'] = False
        r['halt_reason'] = 'Test authorization revoked'
        self.apply(r)
        self.assertEqual(self.e.transition(), ('halt', None))

    def unknown_only_review(self, criterion='unknown'):
        self.c['max_cycles'] = self.s['grants'][0]['max_cycles'] = 1
        self.e.consume('footer', 'Test-owner')
        r = report(self.c, self.s)
        for row in r['actions']:
            row['status'] = 'verified'
        r['actions'][0]['attempt'] = attempt('Test-cycle-1', 'verified')
        r['criteria'] = {cid: dict(status=criterion, evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        r['criteria']['footer_ok']['status'] = 'pass'
        return r

    def test_unknown_without_defect_is_delivered_unverified_not_acceptance(self):
        self.apply(self.unknown_only_review())
        grants, consumption = deepcopy(self.s['grants']), deepcopy(self.s['consumption'])
        self.assertEqual(self.e.transition(), ('stop', None))
        self.assertEqual(self.s['delivery'], dict(status='delivered_unverified', unverified_criteria=['email_ok'], review='Test independent review'))
        self.assertEqual(self.s['history'][-1]['outcome'], 'delivered_unverified')
        self.assertNotIn('No authorized productive action', self.s['history'][-1]['reason'])
        self.assertNotEqual(self.s['execution'], 'finish')
        self.assertEqual(self.s['acceptance'], {'footer_ok': 'pass', 'email_ok': 'unknown'})
        self.assertEqual((self.s['grants'], self.s['consumption']), (grants, consumption), 'Delivery never resets budgets')
        self.assertEqual(self.e.remaining('main'), 0)
        state = deepcopy(self.s)
        self.assertEqual(p.Controller(self.c, self.s).transition(), ('stop', None))
        self.assertEqual(self.s, state, 'Replaying a delivered stop is idempotent')

    def test_defect_blocker_or_uncertain_effect_keeps_ordinary_stop_or_wait(self):
        for case in ('fail', 'blocked', 'pending', 'stalled'):
            with self.subTest(case=case):
                self.setUp()
                r = self.unknown_only_review('fail' if case == 'fail' else 'unknown')
                if case == 'blocked':
                    r['blockers'] = [dict(blocker=dict(key='Test-access', reason='missing_access', needed='Provide Test access', blocked_actions=['email']), evidence_refs=['test-proof'])]
                if case in {'pending', 'stalled'}:
                    r['actions'][1].update(status=case, eligible=False)
                self.apply(r)
                decision = self.e.transition()
                self.assertNotIn('delivery', self.s)
                if case == 'blocked':
                    self.assertEqual(decision, ('wait', None))
                else:
                    self.assertEqual(decision, ('stop', None))
                    self.assertIn('No authorized productive action', self.s['history'][-1]['reason'])
        self.setUp()
        self.s['operations']['email:send'] = dict(id='email:send', outcome='uncertain')
        self.s['actions']['footer']['status'] = 'verified'
        self.s['last_review'] = 'Test prior review'
        self.assertEqual(self.e.delivered_unverified(), [])

    def test_independent_acceptance_required_not_exit_or_worker_claim(self):
        for a in self.s['actions'].values():
            a['status'] = 'verified'
        self.assertEqual(self.e.transition(), ('stop', None))
        self.s['execution'] = 'continue'
        r = report(self.c, self.s)
        r['criteria'] = {cid: dict(status='pass', evidence_refs=['test-proof']) for cid in self.s['acceptance']}
        self.apply(r)
        self.assertEqual(self.e.transition(), ('finish', None))

    def test_material_dependency_judgments_are_not_worker_permission(self):
        r = report(self.c, self.s)
        r['actions'][0]['dependencies_valid'] = False
        with self.assertRaisesRegex(ValueError, 'independently'):
            self.apply(r)

    def test_wrong_session_and_forged_authority_rejected(self):
        self.c['pi_session_id'] = 'Test-session'
        h = {**p.header(self.c['run_id']), 'id': 'H1', 'kind': 'cancel', 'session_id': 'Test-wrong', 'source': 'pi-command', 'message': 'Test cancel'}
        with self.assertRaises(ValueError):
            self.e.ingress(h, 'Test-session')
        h['session_id'] = 'Test-session'
        h['source'] = 'worker'
        with self.assertRaises(ValueError):
            self.e.ingress(h, 'Test-session')

    def test_interrupted_effect_cannot_be_replayed_and_duplicate_worker_refused(self):
        self.s['actions']['email']['operations'] = [dict(id='send', target='Test authorized sink', kind='Test-send')]
        self.e.consume('email', 'Test-owner')
        self.s['sessions'].append(dict(owner='Test-owner', status='running'))
        key = self.e.operation('email', 'send', 'Test-owner')
        with self.assertRaises(ValueError):
            self.e.consume('footer', 'Test-other-owner')
        self.e.interrupted()
        self.assertEqual(self.s['operations'][key]['outcome'], 'uncertain')
        self.assertFalse(self.s['reconciled'])
        r = report(self.c, self.s)
        r['actions'][1]['attempt'] = attempt('Test-interrupted-email', 'verified')
        r['reconciliation']['operations'] = [dict(id=key, outcome='uncertain', evidence_refs=['test-proof'])]
        self.apply(r)
        self.assertEqual(self.e.transition(), ('wait', None))
        r = report(self.c, self.s)
        r['reconciliation']['operations'] = [dict(id=key, outcome='not_performed', evidence_refs=['test-proof'])]
        self.apply(r)
        self.e.consume('email', 'Test-owner-2')
        self.s['sessions'].append(dict(owner='Test-owner-2', status='running'))
        with self.assertRaises(ValueError):
            self.e.operation('email', 'send', 'Test-wrong-owner')
        self.assertEqual(self.e.operation('email', 'send', 'Test-owner-2'), key)
        r = report(self.c, self.s)
        r['actions'][1]['attempt'] = attempt('Test-reconciled-email', 'verified')
        r['reconciliation']['operations'] = [dict(id=key, outcome='succeeded', evidence_refs=['test-proof'])]
        self.apply(r)
        self.s['active'] = dict(owner='Test-owner-2', action_id='email')
        with self.assertRaises(ValueError):
            self.e.operation('email', 'send', 'Test-owner-2')


class RecoveryAndAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.c['pi_session_id'] = 'Test-session'
        self.s = p.initial(self.c, {})
        self.e = p.Controller(self.c, self.s)
        self.e.apply(report(self.c, self.s), {'test-proof'}, 'Test review')

    def blocker(self, aid='email', reason='missing_secret'):
        return self.e.blocker(dict(key='Test-' + aid, reason=reason, needed='Test configure securely', blocked_actions=[aid]), ['test-proof'])

    def human(self, kind, hid, **fields):
        value = {**p.header(self.c['run_id']), 'id': hid, 'session_id': 'Test-session', 'source': 'pi-command', 'kind': kind, 'message': 'Test authentic addressed input', **fields}
        self.e.ingress(value, 'Test-session')

    def test_applicable_real_approval_is_retained_not_requested_again(self):
        bid = self.blocker(reason='approval_required')
        self.human('resolution', 'H1', blocker_ids=[bid])
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=bid, human_id='H1', valid=True, approval_applicable=True, evidence_refs=['test-proof'])]
        self.e.apply(r, {'test-proof'}, 'Test approval review')
        self.e.apply(report(self.c, self.s), {'test-proof'}, 'Test later review')
        self.assertEqual(self.s['blockers'][bid]['status'], 'resolved')
        self.assertEqual(len(self.s['blockers'][bid]['resolutions']), 1)
        self.assertFalse(self.s['requests'])

    def test_new_blocker_during_closure_grants_no_scope_or_budget(self):
        bid = self.blocker()
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=bid, human_id=None, valid=True, approval_applicable=False, evidence_refs=['test-proof'])]
        self.e.apply(r, {'test-proof'}, 'Test restoration review')
        self.assertEqual(self.s['actions']['email']['scope'], 'closure')
        second = self.e.blocker(dict(key='Test-provider', reason='missing_access', needed='Test restore provider access', blocked_actions=['email']), ['test-proof'])
        self.assertNotEqual(bid, second)
        self.assertEqual(self.s['actions']['email']['provenance']['blocker_id'], bid)
        self.assertEqual(self.s['actions']['analytics']['scope'], 'main')
        self.assertEqual(len(self.s['grants']), 2)
        self.assertEqual(self.e.remaining('main'), 2)
        self.assertEqual(self.e.transition(), ('continue', 'footer'))

    def test_dynamic_required_repairs_need_causal_evidence_unrelated_stays_main(self):
        bid = self.blocker()
        r = report(self.c, self.s)
        r['resolutions'] = [dict(blocker_id=bid, human_id=None, valid=True, approval_applicable=False, evidence_refs=['test-proof'])]
        self.e.apply(r, {'test-proof'}, 'Test resolution')
        r = report(self.c, self.s)
        root = self.s['actions']['email']['provenance']
        for aid, provenance in [('repair', {**root, 'parent_action_id': 'email', 'reason': 'Test unblocked verification exposed necessary repair'}), ('unrelated', None)]:
            raw = dict(id=aid, description='Test ' + aid, depends_on=[], operations=[])
            if provenance:
                raw['provenance'] = provenance
            r['actions'].append(dict(action=raw, status='pending', eligible=True, scope_authorized=True, dependencies_valid=True, evidence_refs=['test-proof'], attempt=None, experiment=None))
        self.e.apply(r, {'test-proof'}, 'Test causal necessity review')
        self.assertEqual(self.s['actions']['repair']['scope'], 'closure')
        self.assertEqual(self.s['actions']['unrelated']['scope'], 'main')
        self.e.consume('footer', 'Test-owner')
        assess_cycle(self.c, self.s)
        self.e.consume('footer', 'Test-owner')
        assess_cycle(self.c, self.s)
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.e.consume('unrelated', 'Test-owner')
        self.e.consume('repair', 'Test-owner')
        self.assertEqual(self.s['consumption'][-1]['scope'], 'closure')
        self.assertEqual(self.e.remaining('main'), 0)

    def test_causal_reparenting_cannot_form_cycle(self):
        bid = self.blocker()
        self.s['blockers'][bid]['status'] = 'resolved'
        root = dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test root', evidence_refs=['test-proof'])
        self.e.closure(self.s['actions']['email'], root, {'test-proof'})
        for aid, parent in [('repair', 'email'), ('verify', 'repair')]:
            a = p.action(dict(id=aid, description='Test ' + aid))
            self.e.closure(a, {**root, 'parent_action_id': parent}, {'test-proof'})
            self.s['actions'][aid] = a
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            self.e.closure(self.s['actions']['repair'], {**root, 'parent_action_id': 'verify'}, {'test-proof'})

    def test_duplicate_budget_authorization_and_later_extension_requests(self):
        for _ in range(2):
            self.e.consume('footer', 'Test-owner')
            assess_cycle(self.c, self.s)
        self.e.transition()
        qid = next(iter(self.s['requests']))
        self.human('grant', 'H1', request_id=qid, cycles=1)
        self.human('grant', 'H2', request_id=qid, cycles=1)
        self.assertEqual(self.s['human']['H2']['duplicate_of'], 'H1')
        r = report(self.c, self.s)
        r['grants'] = ['H1']
        self.e.apply(r, {'test-proof'}, 'Test real grant review')
        self.assertEqual(self.e.remaining('main'), 1)
        self.e.consume('footer', 'Test-owner-2')
        assess_cycle(self.c, self.s)
        self.e.transition()
        self.assertEqual(len(self.s['requests']), 2)
        newer = next(q for q in self.s['requests'] if q != qid)
        self.human('grant', 'H3', request_id=newer, cycles=2)
        r = report(self.c, self.s)
        r['grants'] = ['H3']
        self.e.apply(r, {'test-proof'}, 'Test second extension review')
        self.assertEqual(self.e.remaining('main'), 2)
        self.assertEqual(self.s['cycle'], 3)

    def test_deadline_does_not_request_blockers_before_independent_work_finishes(self):
        bid = self.e.blocker(dict(key='Test-deadline', reason='missing_access', needed='Test access before concrete deadline', blocked_actions=['email'], deadline=1010), ['test-proof'])
        self.assertEqual(self.e.transition(now=1000), ('continue', 'footer'))
        self.assertFalse(self.s['requests'])
        for aid in ('footer', 'dns', 'analytics'):
            self.s['actions'][aid]['status'] = 'verified'
        self.assertEqual(self.e.transition(now=1000), ('wait', None))
        self.assertEqual(next(iter(self.s['requests'].values()))['blocker_ids'], [bid])

    def test_concrete_resource_wake_preserves_action_local_stall(self):
        for a in self.s['actions'].values():
            a['status'] = 'stalled'
        self.e.arrange_wait('resource-signal', 'Test host resource-restoration signal')
        self.assertEqual(self.e.transition(), ('wait', None))
        self.assertEqual(self.s['cycle'], 0)
        self.assertTrue(all(a['status'] == 'stalled' for a in self.s['actions'].values()))

    def test_corrupt_snapshot_cannot_recover_or_reset_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            damaged = json.loads(store.path.read_text())
            damaged['cycle'] = 99
            p.durable(store.path, damaged)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                store.read()
            with self.assertRaises(ValueError):
                with store.transaction():
                    pass

    def test_retired_session_owner_cannot_start_external_operation(self):
        self.s['actions']['email']['operations'] = [dict(id='send', target='Test fake sink', kind='Test-send')]
        self.e.consume('email', 'Test-owner')
        self.s['sessions'].append(dict(owner='Test-owner', status='checkpoint', ended_at=1))
        with self.assertRaisesRegex(ValueError, 'Retired worker'):
            self.e.operation('email', 'send', 'Test-owner')
        self.assertFalse(self.s['operations'])

    def test_global_halt_precedes_cancellation_regardless_of_ingress_order(self):
        for order in (('halt', 'cancel'), ('cancel', 'halt')):
            self.s['execution'] = 'continue'
            self.s['human'] = {}
            for index, kind in enumerate(order):
                self.human(kind, 'H' + str(index))
            self.assertEqual(self.e.transition(), ('halt', None))

    def test_stale_review_cycle_sequence_and_state_hash_are_refused(self):
        r = report(self.c, self.s)
        for change in ({'cycle': 99}, {'review_id': 99}, {'state_sha256': 'Test-forged-state'}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Stale reviewer'):
                self.e.apply({**r, **change}, {'test-proof'}, 'Test stale eval')

    def test_bounded_wake_cannot_be_renewed_as_model_polling(self):
        self.e.arrange_wait('bounded-recheck', 'Test one-shot resource observation', at=1)
        self.s['wait'] = None
        with self.assertRaisesRegex(ValueError, 'one-shot'):
            self.e.arrange_wait('bounded-recheck', 'Test one-shot resource observation', at=999999999999)
        self.assertEqual(self.s['cycle'], 0)

    def test_schema_boolean_and_failed_final_states_never_pass(self):
        with self.assertRaises(ValueError):
            p.envelope({**p.header(self.c['run_id']), 'schema_version': True}, self.c['run_id'])
        for status in ('blocked', 'not_tested', 'unknown', 'fail'):
            s = deepcopy(self.s)
            e = p.Controller(self.c, s)
            r = report(self.c, s)
            for a in r['actions']:
                a['status'] = 'verified'
            for criterion in r['criteria'].values():
                criterion.update(status=status, evidence_refs=['test-proof'])
            e.apply(r, {'test-proof'}, 'Test independent non-PASS')
            self.assertEqual(e.transition(), ('stop', None))


class CycleAssessmentRegressionTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.s = p.initial(self.c, {})
        self.e = p.Controller(self.c, self.s)
        self.apply(report(self.c, self.s))

    def apply(self, r):
        self.e.apply(r, {'test-proof'}, 'Test cycle-bound independent review')

    def selected_report(self, assessment='verified', fingerprint=None, next_experiment=None):
        r = report(self.c, self.s)
        row = self.s['consumption'][-1]
        result = next(x for x in r['actions'] if x['action']['id'] == row['action_id'])
        result.update(attempt=attempt(fingerprint or 'Test-cycle-' + str(row['cycle']), assessment), experiment=next_experiment)
        return r

    def test_completed_cycle_cannot_repeat_pending_null_in_unlimited_closure(self):
        bid = self.e.blocker(dict(key='Test-input', reason='missing_access', needed='Test restored access', blocked_actions=['email']), ['test-proof'])
        self.s['blockers'][bid]['status'] = 'resolved'
        self.e.closure(self.s['actions']['email'], dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test causal restoration', evidence_refs=['test-proof']), {'test-proof'})
        for aid, a in self.s['actions'].items():
            if aid != 'email':
                a['status'] = 'verified'
        self.e.consume('email', 'Test-owner')
        self.assertEqual(self.e.remaining('closure'), float('inf'))
        for index in range(5):
            before = deepcopy(self.s)
            r = report(self.c, self.s)
            if index % 2:
                next(x for x in r['actions'] if x['action']['id'] == 'email')['experiment'] = experiment('Test-no-disposition')
            with self.assertRaisesRegex(ValueError, 'assessment'):
                self.apply(r)
            self.assertEqual(self.s, before, 'Missing selected assessment must be rejected before mutations')
        self.s['active'] = None
        self.assertEqual(self.e.available(), [])
        with self.assertRaises(ValueError):
            self.e.consume('email', 'Test-replay-owner')
        self.assertEqual(self.s['cycle'], 1)

    def test_interrupted_cycle_requires_assessment_even_after_active_is_cleared(self):
        self.e.consume('footer', 'Test-owner')
        self.e.interrupted()
        self.assertIsNone(self.s['active'])
        with self.assertRaisesRegex(ValueError, 'assessment'):
            self.apply(report(self.c, self.s))
        self.apply(self.selected_report(assessment='none'))
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        self.assertEqual(self.e.transition(), ('continue', 'email'))
        self.assertEqual(self.s['consumption'][0]['assessment']['review'], 'Test cycle-bound independent review')

    def test_selected_verified_status_also_requires_attempt_disposition(self):
        self.e.consume('footer', 'Test-owner')
        r = report(self.c, self.s)
        r['actions'][0]['status'] = 'verified'
        with self.assertRaisesRegex(ValueError, 'assessment'):
            self.apply(r)

    def test_informative_failure_alone_stalls_and_peer_null_cannot_revive_it(self):
        self.e.consume('footer', 'Test-owner')
        self.apply(self.selected_report(assessment='informative'))
        a = self.s['actions']['footer']
        self.assertEqual(a['attempts'][-1]['assessment'], 'informative')
        self.assertEqual(a['status'], 'stalled')
        r = report(self.c, self.s)
        r['actions'][0]['status'] = 'pending'
        self.apply(r)
        self.assertEqual(a['status'], 'stalled')
        self.assertEqual(len(a['attempts']), 1)
        self.assertEqual(self.e.transition(), ('continue', 'email'))

    def test_specific_unfinished_work_continues_without_experiment(self):
        self.e.consume('footer', 'Test-owner')
        r = self.selected_report(assessment='informative')
        r['actions'][0]['continuation'] = dict(next_step='Test finish remaining footer content', evidence_refs=['test-proof'])
        self.apply(r)
        self.assertEqual(self.e.transition(), ('continue', 'footer'))
        self.assertIsNone(self.s['actions']['footer']['experiment'])
        self.e.consume('footer', 'Test-next-owner')
        self.apply(self.selected_report(assessment='informative', fingerprint='Test-cycle-1'))
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')

    def test_continuation_survives_review_of_a_peer_action(self):
        self.e.consume('footer', 'Test-owner')
        r = self.selected_report(assessment='informative')
        r['actions'][0]['continuation'] = dict(next_step='Test finish footer', evidence_refs=['test-proof'])
        self.apply(r)
        self.e.consume('email', 'Test-peer-owner')
        r = self.selected_report(assessment='verified')
        r['actions'][1]['status'] = 'verified'
        self.apply(r)
        self.assertEqual(self.s['actions']['footer']['status'], 'pending')
        self.assertEqual(self.s['actions']['footer']['continuation']['next_step'], 'Test finish footer')

    def test_continuation_requires_selected_informative_evidenced_work(self):
        self.e.consume('footer', 'Test-owner')
        for assessment, refs in [('none', ['test-proof']), ('informative', [])]:
            state = deepcopy(self.s)
            r = self.selected_report(assessment=assessment)
            r['actions'][0]['continuation'] = dict(next_step='Test remaining work', evidence_refs=refs)
            with self.assertRaises(ValueError):
                p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test review')

    def test_missing_evidence_can_record_unknown_but_cannot_verify_work(self):
        self.e.consume('footer', 'Test-owner')
        r = self.selected_report(assessment='informative')
        for value in r['criteria'].values():
            value.update(status='unknown', evidence_refs=[])
        for value in r['actions']:
            value['evidence_refs'] = []
            if value['attempt']:
                value['attempt']['evidence_refs'] = []
        r['reconciliation']['evidence_refs'] = []
        self.e.apply(r, set(), 'Test missing review evidence')
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        self.assertEqual(set(self.s['acceptance'].values()), {'unknown'})
        self.assertEqual(self.e.transition(), ('continue', 'email'))
        r = report(self.c, self.s)
        r['criteria']['footer_ok'].update(status='pass', evidence_refs=[])
        with self.assertRaisesRegex(ValueError, 'Missing independently snapshotted evidence'):
            self.e.apply(r, set(), 'Test unsupported pass')

    def test_initial_and_peer_observation_do_not_invent_attempts(self):
        self.assertTrue(all(not a['attempts'] for a in self.s['actions'].values()))
        self.e.consume('footer', 'Test-owner')
        self.apply(self.selected_report())
        self.apply(report(self.c, self.s))
        self.assertEqual(len(self.s['actions']['footer']['attempts']), 1)
        self.assertTrue(all(not a['attempts'] for aid, a in self.s['actions'].items() if aid != 'footer'))
        self.assertEqual(self.s['consumption'][0]['assessment']['cycle'], 1)

    def test_initial_or_peer_attempt_is_not_a_real_selected_cycle(self):
        r = report(self.c, self.s)
        r['actions'][0]['attempt'] = attempt(assessment='verified')
        with self.assertRaisesRegex(ValueError, 'selected cycle'):
            self.apply(r)
        self.e.consume('footer', 'Test-owner')
        r = self.selected_report()
        r['actions'][1]['attempt'] = attempt(assessment='verified')
        with self.assertRaisesRegex(ValueError, 'selected cycle'):
            self.apply(r)

    def test_informative_failure_can_run_materially_different_experiment_once(self):
        self.e.consume('footer', 'Test-owner')
        self.apply(self.selected_report('informative', 'Test-first', experiment('Test-second')))
        self.assertEqual(self.e.transition(), ('replan', 'footer'))
        self.e.consume('footer', 'Test-owner-2')
        self.apply(self.selected_report('informative', 'Test-second'))
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        r = report(self.c, self.s)
        r['actions'][0].update(status='pending', experiment=experiment('Test-second'))
        with self.assertRaisesRegex(ValueError, 'Equivalent'):
            self.apply(r)

    def test_unlimited_closure_allows_verified_progress_without_numeric_cap(self):
        bid = self.e.blocker(dict(key='Test-input', reason='missing_access', needed='Test restored access', blocked_actions=['email']), ['test-proof'])
        self.s['blockers'][bid]['status'] = 'resolved'
        self.e.closure(self.s['actions']['email'], dict(blocker_id=bid, unblocked_action_id='email', parent_action_id=None, reason='Test causal restoration', evidence_refs=['test-proof']), {'test-proof'})
        for aid, a in self.s['actions'].items():
            if aid != 'email':
                a['status'] = 'verified'
        for _ in range(8):
            self.assertEqual(self.e.transition(), ('continue', 'email'))
            self.e.consume('email', 'Test-owner')
            self.apply(self.selected_report())
        self.assertEqual(self.e.remaining('closure'), float('inf'))
        self.assertEqual(self.e.remaining('main'), 2)
        self.assertEqual(len(self.s['actions']['email']['attempts']), 8)
        self.assertTrue(all(row.get('assessment') for row in self.s['consumption']))
        self.e.consume('email', 'Test-owner')
        self.apply(self.selected_report('verified', 'Test-cycle-8'))
        self.assertEqual(self.s['actions']['email']['status'], 'stalled', 'Equivalent fingerprints are not verified new progress')

    def test_assessment_survives_durable_restore_and_cannot_be_assigned_twice(self):
        self.e.consume('footer', 'Test-owner')
        self.e.interrupted()
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            with self.assertRaisesRegex(ValueError, 'assessment'):
                with store.transaction() as state:
                    p.Controller(self.c, state).apply(report(self.c, state), {'test-proof'}, 'Test invalid recovery')
            self.assertFalse(store.read()['consumption'][0].get('assessment'))
            self.s = store.read()
            self.e = p.Controller(self.c, self.s)
            r = self.selected_report()
            with store.transaction() as state:
                p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test durable recovery')
            state = store.read()
            self.assertEqual(state['consumption'][0]['assessment']['cycle'], 1)
            self.assertEqual(state['cycle'], 1)
            r = report(self.c, state)
            r['actions'][0]['attempt'] = attempt('Test-duplicate-disposition', 'verified')
            with self.assertRaisesRegex(ValueError, 'selected cycle'):
                with store.transaction() as state:
                    p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test duplicate recovery')
            self.assertEqual(len(store.read()['actions']['footer']['attempts']), 1)

    def test_old_multiple_unassessed_cycles_fail_closed_without_backfill(self):
        self.e.consume('footer', 'Test-owner')
        old = deepcopy(self.s['consumption'][0])
        old['cycle'] = 2
        self.s['consumption'].append(old)
        self.s['cycle'] = 2
        self.s['active'] = None
        before = deepcopy(self.s)
        with self.assertRaisesRegex(ValueError, 'Historical worker cycles'):
            self.apply(self.selected_report())
        self.assertEqual(self.s, before)
        self.assertFalse(self.e.available())
        self.s['acceptance'] = {cid: 'pass' for cid in self.s['acceptance']}
        for a in self.s['actions'].values():
            a['status'] = 'verified'
        self.assertEqual(self.e.transition(), ('stop', None), 'Missing assessments must not permit finish either')

    def test_external_wake_is_observation_not_a_worker_attempt_or_retry_grant(self):
        for a in self.s['actions'].values():
            a['eligible'] = False
        self.e.arrange_wait('resource-signal', 'Test-restoration')
        self.e.resource_signal({**p.header(self.c['run_id']), 'id': 'Test-wake', 'reference': 'Test-restoration'})
        self.apply(report(self.c, self.s))
        self.assertEqual(self.s['cycle'], 0)
        self.assertTrue(all(not a['attempts'] for a in self.s['actions'].values()))
        self.e.consume('footer', 'Test-owner')
        self.apply(self.selected_report('informative'))
        self.e.arrange_wait('resource-signal', 'Test-next-restoration')
        self.e.resource_signal({**p.header(self.c['run_id']), 'id': 'Test-wake-2', 'reference': 'Test-next-restoration'})
        r = report(self.c, self.s)
        r['actions'][0]['status'] = 'pending'
        self.apply(r)
        self.assertEqual(self.s['actions']['footer']['status'], 'stalled')
        r = report(self.c, self.s)
        r['actions'][0].update(status='pending', experiment=experiment('Test-restored-conditions'))
        self.apply(r)
        self.assertEqual(self.e.transition(), ('replan', 'footer'))
        self.assertEqual(len(self.s['actions']['footer']['attempts']), 1)


class OperationReconciliationRegressionTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.s = p.initial(self.c, {})
        self.e = p.Controller(self.c, self.s)
        self.e.apply(report(self.c, self.s), {'test-proof'}, 'Test initial observation')
        self.s['actions']['email']['operations'] = [dict(id='send', target='Test local sink', kind='Test-send')]
        self.e.consume('email', 'Test-owner')
        self.s['sessions'].append(dict(owner='Test-owner', status='running'))
        self.key = self.e.operation('email', 'send', 'Test-owner')
        self.e.interrupted()

    def reconcile(self, outcome, extra=None):
        r = report(self.c, self.s)
        if not self.s['consumption'][0].get('assessment'):
            next(x for x in r['actions'] if x['action']['id'] == 'email').update(attempt=attempt('Test-interrupted-cycle', 'verified'))
        r['reconciliation']['operations'] = [dict(id=self.key, outcome=outcome, evidence_refs=['test-proof'])]
        if extra:
            r['reconciliation']['operations'].append(extra)
        self.e.apply(r, {'test-proof'}, 'Test outcome ' + outcome)

    def test_confirmed_outcomes_cannot_change_or_unlock_replay(self):
        for old in ('succeeded', 'failed'):
            for new in ('not_performed', 'uncertain', 'failed' if old == 'succeeded' else 'succeeded'):
                with self.subTest(old=old, new=new):
                    self.setUp()
                    self.reconcile(old)
                    before = deepcopy(self.s['operations'][self.key])
                    self.reconcile(new)
                    self.assertEqual(self.s['execution'], 'halt')
                    self.assertEqual(self.s['operations'][self.key], before)
                    self.assertTrue(any(x['type'] == 'operation.conflict' for x in self.s['history']))
                    self.s['active'] = dict(owner='Test-owner', action_id='email')
                    self.s['sessions'][-1]['status'] = 'running'
                    with self.assertRaises(ValueError):
                        self.e.operation('email', 'send', 'Test-owner')
                    self.assertEqual(self.s['operations'][self.key], before)
                    self.s.update(execution='continue', reconciled=True)
                    with self.assertRaisesRegex(ValueError, 'must not replay'):
                        self.e.operation('email', 'send', 'Test-owner')

    def test_outcome_transition_matrix(self):
        allowed = {
            'started': {'uncertain', 'not_performed', 'succeeded', 'failed'},
            'uncertain': {'uncertain', 'not_performed', 'succeeded', 'failed'},
            'not_performed': {'not_performed'},
            'succeeded': {'succeeded'},
            'failed': {'failed'},
        }
        for old, permitted in allowed.items():
            for new in ('uncertain', 'not_performed', 'succeeded', 'failed'):
                with self.subTest(old=old, new=new):
                    self.setUp()
                    self.s['operations'][self.key]['outcome'] = old
                    self.reconcile(new)
                    self.assertEqual(self.s['operations'][self.key]['outcome'], new if new in permitted else old)
                    self.assertEqual(self.s['execution'], 'continue' if new in permitted else 'halt')

    def test_uncertain_no_effect_requires_independent_evidence(self):
        r = report(self.c, self.s)
        r['actions'][1]['attempt'] = attempt('Test-interrupted-cycle', 'verified')
        r['reconciliation']['operations'] = [dict(id=self.key, outcome='not_performed', evidence_refs=[])]
        with tempfile.TemporaryDirectory() as tmp:
            store = p.Store(tmp, self.c['run_id'])
            with store.transaction(create=self.s):
                pass
            before = store.read()
            r['state_sha256'] = p.sha(before)
            with self.assertRaisesRegex(ValueError, 'Missing independently'):
                with store.transaction() as state:
                    p.Controller(self.c, state).apply(r, {'test-proof'}, 'Test unsupported no-effect claim')
            self.assertEqual(store.read(), before)
            self.assertEqual(store.read()['operations'][self.key]['outcome'], 'uncertain')

    def test_uncertain_not_performed_preserves_provenance_and_allows_safe_reservation(self):
        self.reconcile('not_performed')
        old = deepcopy(self.s['operations'][self.key])
        self.assertEqual(old['outcome'], 'not_performed')
        self.assertEqual(old['owner'], 'Test-owner')
        self.assertEqual(old['cycle'], 1)
        self.assertTrue(any(x['type'] == 'operation.reconciled' and x['previous_outcome'] == 'uncertain' and x['outcome'] == 'not_performed' for x in self.s['history']))
        self.e.consume('email', 'Test-owner-2')
        self.s['sessions'].append(dict(owner='Test-owner-2', status='running'))
        self.assertEqual(self.e.operation('email', 'send', 'Test-owner-2'), self.key)
        self.assertEqual(self.s['operations'][self.key]['prior'], old)
        self.assertEqual(self.s['operations'][self.key]['cycle'], 2)

    def test_confirmed_no_effect_cannot_change_without_a_new_reservation(self):
        self.reconcile('not_performed')
        self.reconcile('succeeded')
        self.assertEqual(self.s['execution'], 'halt')
        self.assertEqual(self.s['operations'][self.key]['outcome'], 'not_performed')

    def test_duplicate_operation_observations_are_not_order_dependent(self):
        for first, second in (('uncertain', 'not_performed'), ('not_performed', 'succeeded')):
            with self.subTest(first=first, second=second):
                self.setUp()
                with self.assertRaisesRegex(ValueError, 'Duplicate operation'):
                    self.reconcile(first, dict(id=self.key, outcome=second, evidence_refs=['test-proof']))
                self.assertEqual(self.s['operations'][self.key]['outcome'], 'uncertain')

    def test_same_confirmed_outcome_revalidation_retains_evidence_history(self):
        self.reconcile('succeeded')
        self.reconcile('succeeded')
        self.assertEqual(self.s['operations'][self.key]['outcome'], 'succeeded')
        observations = [x for x in self.s['history'] if x['type'] == 'operation.reconciled']
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0]['previous_outcome'], 'uncertain')
        self.assertEqual(observations[1]['previous_outcome'], 'succeeded')
        self.assertTrue(all(x['evidence_refs'] == ['test-proof'] and x['review'] for x in observations))


if __name__ == '__main__':
    unittest.main()
