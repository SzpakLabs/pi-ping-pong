"""Protocol 2 / schema 1. Cooperative host controller, not a security sandbox."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

PROTOCOL = 2
SCHEMA = 1
TERMINAL = {'halt', 'stop', 'finish', 'cancelled'}
REASONS = {'missing_secret', 'missing_access', 'approval_required', 'user_choice', 'external_blocker'}
OPERATION_TRANSITIONS = {
    'started': {'uncertain', 'not_performed', 'succeeded', 'failed'},
    'uncertain': {'uncertain', 'not_performed', 'succeeded', 'failed'},
    'not_performed': {'not_performed'},
    'succeeded': {'succeeded'},
    'failed': {'failed'},
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, 'Expected nonempty bounded text')
    require(not re.search(r'(?:\bsk-[\w-]{16,}|\bgh[pousr]_[\w]{12,}|\bbearer\s+\S+|(?:api[_-]?key|secret|token)\s*[:=]\s*\S+)', value, re.I), 'Secret values are forbidden; configure securely')
    return value


def ident(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}', value), 'Invalid identity')
    return value


def positive(value):
    require(type(value) is int and value > 0, 'Expected positive integer')
    return value


def envelope(value, run_id):
    require(type(value.get('protocol_version')) is int and type(value.get('schema_version')) is int and value['protocol_version'] == PROTOCOL and value['schema_version'] == SCHEMA, 'Unsupported protocol/schema')
    require(value.get('run_id') == run_id, 'Wrong run identity')


def header(run_id):
    return dict(protocol_version=PROTOCOL, schema_version=SCHEMA, run_id=run_id)


def action(raw):
    ident(raw['id'])
    text(raw['description'])
    require(set(raw) <= {'id', 'description', 'depends_on', 'operations', 'provenance'}, 'Unknown action fields')
    deps = raw.get('depends_on', [])
    require(isinstance(deps, list) and len(deps) == len(set(deps)), 'Invalid action dependencies')
    for dep in deps:
        ident(dep)
    ops = raw.get('operations', [])
    require(isinstance(ops, list), 'Invalid operations')
    for op in ops:
        require(set(op) <= {'id', 'target', 'kind', 'approval_blocker'}, 'Unknown operation fields')
        ident(op['id'])
        text(op['target'])
        text(op['kind'])
        if op.get('approval_blocker'):
            ident(op['approval_blocker'])
    require(len({o['id'] for o in ops}) == len(ops), 'Duplicate operation ID')
    return {**deepcopy(raw), 'depends_on': deps, 'operations': ops, 'blocked_by': [], 'status': 'pending', 'scope': 'main', 'evidence': [], 'attempts': [], 'experiment': None, 'eligible': False}


def dependencies(actions):
    def visit(aid, trail):
        require(aid in actions, 'Unknown dependency')
        require(aid not in trail, 'Cyclic action dependency')
        for dep in actions[aid]['depends_on']:
            visit(dep, trail | {aid})
    for aid in actions:
        visit(aid, set())


def validate_decompositions(actions):
    def visit(aid, trail):
        require(aid not in trail, 'Cyclic action decomposition')
        children = actions[aid].get('decomposed_into', [])
        require(isinstance(children, list) and len(children) == len(set(children)), 'Invalid action decomposition')
        require(actions[aid]['status'] != 'decomposed' or bool(children), 'Decomposed action has no parts')
        for child in children + actions[aid]['depends_on']:
            require(child in actions and child != aid, 'Unknown or self-referential decomposition part')
            visit(child, trail | {aid})
    for aid in actions:
        visit(aid, set())


def action_complete(actions, aid):
    action = actions[aid]
    return action['status'] == 'verified' or action['status'] == 'decomposed' and all(action_complete(actions, child) for child in action.get('decomposed_into', []))


def human_channel(c):
    return c.get('human_transport', 'pi' if c.get('review_transport', 'pi') == 'pi' else 'console')


def validate_contract(c):
    envelope(c, c['run_id'])
    require(human_channel(c) in {'pi', 'console'}, 'Unsupported human_transport')
    ident(c['run_id'])
    contract = c['execution_contract']
    require(set(contract) == {'target', 'actions', 'criteria', 'closure', 'reminder_seconds'}, 'Execution contract fields differ from schema 1')
    text(contract['target'])
    positive(contract['reminder_seconds'])
    require(isinstance(contract['actions'], list) and contract['actions'], 'Initial authorized actions required')
    actions = {a['id']: action(a) for a in contract['actions']}
    require(len(actions) == len(contract['actions']), 'Duplicate action identity')
    dependencies(actions)
    criteria = contract['criteria']
    require(isinstance(criteria, dict) and criteria, 'Acceptance criteria required')
    for cid, description in criteria.items():
        ident(cid)
        text(description)
    closure = contract['closure']
    require(set(closure) == {'authorized', 'max_cycles'} and type(closure['authorized']) is bool, 'Explicit initial closure authority required')
    if closure['max_cycles'] is not None:
        positive(closure['max_cycles'])
    if c.get('mode') != 'goal' or 'max_cycles' in c:
        positive(c['max_cycles'])
    return actions


def initial(c, pins):
    actions = validate_contract(c)
    now = time.time()
    goal_mode = c.get('mode') == 'goal'
    cycle_limit = None if goal_mode else c['max_cycles']
    closure_limit = None if goal_mode else c['execution_contract']['closure']['max_cycles']
    return {**header(c['run_id']), 'revision': 0, 'execution': 'continue', 'acceptance': {cid: 'unknown' for cid in c['execution_contract']['criteria']},
            'actions': actions, 'blockers': {}, 'grants': [dict(id='initial-main', scope='main', max_cycles=cycle_limit, authority='initial-contract'), dict(id='initial-closure', scope='closure', max_cycles=closure_limit, authority='initial-contract')],
            'consumption': [], 'human': {}, 'signals': {}, 'operations': {}, 'sessions': [], 'active': None, 'wait': None, 'wake_history': [], 'requests': {}, 'history': [], 'pins': pins,
            'lifecycle': 'worker-reviewer', 'cycle': 0, 'review_seq': 0, 'reconciled': False, 'created_at': now, 'updated_at': now, 'active_seconds': 0.0, 'worker_seconds': 0.0, 'worker_tokens': 0, 'verification_seconds': 0.0}


def durable(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(canonical(value) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


class Store:
    def __init__(self, root, run_id):
        self.root, self.run_id = Path(root), run_id
        self.path = self.root / 'execution-state.json'

    def read(self):
        state = json.loads(self.path.read_text())
        envelope(state, self.run_id)
        require(state.get('integrity_sha256') == sha({k: v for k, v in state.items() if k != 'integrity_sha256'}), 'Durable state checksum mismatch; investigate before recovery')
        require(type(state['cycle']) is int and state['cycle'] == len(state['consumption']), 'Corrupt cumulative cycle accounting')
        require(len({g['id'] for g in state['grants']}) == len(state['grants']), 'Duplicate durable grant identity')
        grants = {g['id']: g for g in state['grants']}
        used = {gid: 0 for gid in grants}
        legacy = []
        for row in state['consumption']:
            count = row.get('worker_iterations', 1)
            require(type(count) is int and count >= 1, 'Corrupt worker iteration count')
            assigned = row.get('worker_iteration_grants')
            if assigned is None:
                require(row['grant_id'] in grants, 'Unknown budget grant identity')
                row['worker_iteration_grants'] = [row['grant_id']]
                used[row['grant_id']] += 1
                legacy.append((row, count - 1))
            else:
                require(isinstance(assigned, list) and len(assigned) == count and all(gid in grants for gid in assigned), 'Corrupt worker iteration grant ledger')
                scoped = row.get('worker_scope_grants', {row['scope']: assigned})
                require(isinstance(scoped, dict) and scoped.get(row['scope']) == assigned, 'Corrupt worker scope grant ledger')
                require(set(scoped) <= {'main', 'closure'}, 'Corrupt dispatched budget scopes')
                for scope, identities in scoped.items():
                    require(isinstance(identities, list) and len(identities) == count and all(gid in grants and grants[gid]['scope'] == scope for gid in identities), 'Corrupt worker scope grant ledger')
                    for gid in identities:
                        used[gid] += 1
        for row, extras in legacy:
            for _ in range(extras):
                grant = next((g for g in state['grants'] if g['scope'] == row['scope'] and (g['max_cycles'] is None or used[g['id']] < g['max_cycles'])), None)
                require(grant is not None, 'Corrupt budget consumption')
                row['worker_iteration_grants'].append(grant['id'])
                used[grant['id']] += 1
        for g in state['grants']:
            require(g['max_cycles'] is None or used[g['id']] <= g['max_cycles'], 'Corrupt budget consumption')
        require([x['cycle'] for x in state['consumption']] == list(range(1, state['cycle'] + 1)), 'Nonmonotonic durable cycles')
        dependencies(state['actions'])
        validate_decompositions(state['actions'])
        return state

    @contextmanager
    def transaction(self, create=None):
        with (self.root / 'execution.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if create is not None:
                require(not self.path.exists(), 'Run already initialized; no migration or replay')
                state = deepcopy(create)
            else:
                state = self.read()
            before = deepcopy(state) if create is None else None
            yield state
            if state == before:
                return
            envelope(state, self.run_id)
            state['revision'] += 1
            state['updated_at'] = time.time()
            state['integrity_sha256'] = sha({k: v for k, v in state.items() if k != 'integrity_sha256'})
            durable(self.path, state)


class Controller:
    def __init__(self, c, state):
        self.c, self.s = c, state
        envelope(state, c['run_id'])

    def event(self, kind, **fields):
        self.s['history'].append(dict(type=kind, at=time.time(), **deepcopy(fields)))

    def blocker(self, raw, evidence):
        require(set(raw) <= {'key', 'reason', 'needed', 'blocked_actions', 'deadline'}, 'Unknown blocker fields')
        key = text(raw['key'])
        require(raw['reason'] in REASONS, 'Technical failure is not a human blocker')
        text(raw['needed'])
        require(raw['blocked_actions'] and all(a in self.s['actions'] for a in raw['blocked_actions']), 'Unknown blocked action')
        if raw.get('deadline') is not None:
            require(type(raw['deadline']) in {int, float}, 'Invalid blocker deadline')
        existing = next((b for b in self.s['blockers'].values() if b['key'] == key), None)
        if existing:
            require(existing['reason'] == raw['reason'], 'Blocker identity changed reason')
            existing['blocked_actions'] = sorted(set(existing['blocked_actions'] + raw['blocked_actions']))
            existing['evidence'].extend(evidence)
            existing['last_seen_cycle'] = self.s['cycle']
            # Rediscovery of a resolved condition reopens that identity, retaining resolution history.
            existing['status'] = 'open'
            existing['needed'] = raw['needed']
            if raw.get('deadline') is not None:
                existing['deadline'] = raw['deadline']
            b = existing
        else:
            bid = 'B' + str(len(self.s['blockers']) + 1)
            b = dict(id=bid, **deepcopy(raw), status='open', escalation='deferred', found_cycle=self.s['cycle'], last_seen_cycle=self.s['cycle'], evidence=list(evidence), resolutions=[])
            self.s['blockers'][bid] = b
        for aid in b['blocked_actions']:
            a = self.s['actions'][aid]
            if b['id'] not in a['blocked_by']:
                a['blocked_by'].append(b['id'])
        self.event('blocker.observed', blocker_id=b['id'])
        return b['id']

    def goal_granted_windows(self):
        return sum(g.get('goal_token_windows', g['max_cycles'] or 0) for g in self.s['grants'] if g['scope'] == 'main' and g['authority'] != 'initial-contract')

    def goal_token_budget(self):
        return None if self.c.get('goal_tokens') is None else self.c['goal_tokens'] * (1 + self.goal_granted_windows())

    def goal_tokens_remaining(self):
        budget = self.goal_token_budget()
        return None if budget is None else max(0, budget - self.s.get('worker_tokens', 0))

    def goal_launch_limit(self):
        # Each explicitly granted window may start one more native Goal.
        return self.c.get('goal_max_launches', 10) + self.goal_granted_windows()

    def goal_launches_used(self):
        # A window is reserved durably with its session row before dispatch; recovery reuses its id.
        return len({row.get('goal_window_id', row.get('id')) for row in self.s['sessions']})

    def goal_needs_new_window(self):
        if not self.s['sessions']:
            return True
        prior = self.s['sessions'][-1]
        if not prior.get('goal_started', prior.get('status') != 'starting'):
            return False
        budget = prior.get('goal_token_budget', self.c.get('goal_tokens'))
        usage = max(0, self.s.get('worker_tokens', 0) - prior.get('goal_token_baseline', 0))
        return (budget is not None and usage >= budget) or prior.get('goal_status') in {'complete', 'blocked', 'paused', 'usage_limited'}

    def remaining(self, scope):
        grants = [g for g in self.s['grants'] if g['scope'] == scope]
        if scope == 'closure' and not self.c['execution_contract']['closure']['authorized']:
            return 0
        if self.c.get('mode') == 'goal':
            tokens = self.goal_tokens_remaining()
            new_window = self.goal_needs_new_window()
            # Continuing the current window (waiting Goal, recovery, undispatched reservation) spends no launch.
            launches = max(0, self.goal_launch_limit() - self.goal_launches_used()) + (0 if new_window else 1)
            if tokens == 0 or launches == 0:
                return 0
            return launches if tokens is None else tokens
        if any(g['max_cycles'] is None for g in grants):
            return float('inf')
        return sum(g['max_cycles'] for g in grants) - sum(self.grant_used(g['id']) for g in grants)

    def grant(self, human_id):
        h = self.s['human'][human_id]
        require(h['kind'] == 'grant' and h.get('validated') is True, 'Grant needs verified authentic human authority')
        require(not any(g['authority'] == human_id for g in self.s['grants']), 'Authorization already spent')
        positive(h['cycles'])
        request_id = h.get('request_id')
        require(request_id is None or not any(g.get('request_id') == request_id for g in self.s['grants']), 'Budget request authorization already applied')
        if request_id is not None:
            require(self.s['requests'][request_id].get('main_grant_count') == len(self.s['grants']), 'Stale budget request generation')
        self.s['grants'].append(dict(id='G' + str(len(self.s['grants']) + 1), scope='main', max_cycles=h['cycles'], authority=human_id, request_id=request_id))
        self.event('grant.added', authority=human_id, cycles=h['cycles'], goal_token_budget=self.goal_token_budget() if self.c.get('mode') == 'goal' else None, goal_launch_limit=self.goal_launch_limit() if self.c.get('mode') == 'goal' else None)

    def closure(self, a, p, evidence):
        require(self.c['execution_contract']['closure']['authorized'], 'Closure not initially authorized')
        require(set(p) == {'blocker_id', 'unblocked_action_id', 'parent_action_id', 'reason', 'evidence_refs'}, 'Incomplete closure provenance')
        text(p['reason'])
        require(p['evidence_refs'] and set(p['evidence_refs']) <= set(evidence), 'Unverified causal evidence')
        b = self.s['blockers'].get(p['blocker_id'])
        require(b is not None and b['status'] == 'resolved', 'Closure requires resolved blocker')
        root = p['unblocked_action_id']
        require(root in b['blocked_actions'], 'Action was not unblocked by this blocker')
        parent = p['parent_action_id']
        if a['id'] == root:
            require(parent is None, 'Unblocked root cannot invent a parent')
        else:
            require(parent in self.s['actions'] and parent != a['id'], 'Missing closure parent')
            ancestor = self.s['actions'][parent]
            origin = ancestor.get('provenance', {})
            require(ancestor['scope'] == 'closure' and origin.get('blocker_id') == b['id'] and origin.get('unblocked_action_id') == root, 'Broken closure causal chain')
            visited = {a['id']}
            cursor = parent
            while cursor is not None:
                require(cursor not in visited and cursor in self.s['actions'], 'Cyclic or missing closure ancestry')
                visited.add(cursor)
                link = self.s['actions'][cursor].get('provenance', {})
                require(link.get('blocker_id') == b['id'] and link.get('unblocked_action_id') == root, 'Unverified closure ancestry')
                if cursor == root:
                    require(link.get('parent_action_id') is None, 'Invalid closure root')
                    break
                cursor = link.get('parent_action_id')
            require(root in visited, 'Closure ancestry does not reach unblocked root')
        a.update(scope='closure', provenance=deepcopy(p))
        self.event('closure.validated', action_id=a['id'], provenance=p)

    def grant_used(self, grant_id):
        return sum(identities.count(grant_id) for row in self.s['consumption']
                   for identities in row.get('worker_scope_grants', {row['scope']: row.get('worker_iteration_grants', [row['grant_id']] * row.get('worker_iterations', 1))}).values())

    def consume(self, aid, owner):
        require(self.s['execution'] not in TERMINAL and self.s['active'] is None, 'No concurrent or terminal worker')
        a = self.s['actions'][aid]
        require(a in self.available(), 'Action not independently eligible or still blocked')
        scope = a['scope']
        require(self.remaining(scope) > 0, 'Execution budget exhausted')
        dispatch = {'action_ids': self.goal_actions()} if self.c.get('mode') in {'goal', 'ralph'} else {}
        scopes = {self.s['actions'][item]['scope'] for item in dispatch.get('action_ids', [aid])}
        assigned = {item: [next(g['id'] for g in self.s['grants'] if g['scope'] == item and (g['max_cycles'] is None or self.grant_used(g['id']) < g['max_cycles']))] for item in sorted(scopes)}
        self.s['cycle'] += 1
        self.s['consumption'].append(dict(cycle=self.s['cycle'], action_id=aid, scope=scope, grant_id=assigned[scope][0], owner=owner, worker_iterations=1, worker_iteration_grants=list(assigned[scope]), **({'worker_scope_grants': assigned} if dispatch else {}), **dispatch))
        self.s['active'] = dict(action_id=aid, owner=owner, cycle=self.s['cycle'], **dispatch)
        self.event('cycle.reserved', **self.s['active'], scope=scope)

    def goal_actions(self):
        # Goal/Ralph pursue one native objective; action IDs remain accounting/safety identities, not turn boundaries.
        scoped = []
        blocked = set((self.s.get('verification') or {}).get('blocked_action_ids', []))
        blocked.update(item for row in self.unassessed() for item in row.get('action_ids', [row['action_id']]))
        pending = [a for a in self.s['actions'].values() if a['status'] == 'pending' and a['eligible']
                   and self.remaining(a['scope']) > 0 and a['id'] not in blocked
                   and all(self.s['blockers'][b]['status'] == 'resolved' for b in a['blocked_by'])]
        while True:
            added = [a['id'] for a in pending if a['id'] not in scoped
                     and all(action_complete(self.s['actions'], dep) or dep in scoped for dep in a['depends_on'])]
            if not added:
                return scoped
            scoped.extend(added)

    def abandon_worker_repair(self, diagnosis):
        active = self.s['active']
        require(active is not None, 'No active Worker reservation to abandon')
        row = next((item for item in self.s['consumption'] if item['cycle'] == active['cycle']), None)
        require(row is not None, 'Active Worker reservation has no budget record')
        self.s['actions'][active['action_id']]['status'] = 'stalled'
        self.s['active'] = None
        self.event('worker.repair_budget_exhausted', action_id=active['action_id'], cycle=active['cycle'], diagnosis=diagnosis)

    def reserve_checkpoint_repair(self, aid):
        # Checkpoint format repair is bounded separately; it never spends task iterations (max_cycles).
        active = self.s['active']
        require(active is not None and active['action_id'] == aid, 'Checkpoint repair requires the reserved action')
        row = next((item for item in self.s['consumption'] if item['cycle'] == active['cycle']), None)
        require(row is not None, 'Checkpoint repair has no cumulative budget reservation')
        used = row.get('checkpoint_repairs', 0)
        limit = self.c.get('checkpoint_repair_attempts', 3)
        if used >= limit:
            raise ValueError(f'Checkpoint repair limit exhausted ({used}/{limit})')
        row['checkpoint_repairs'] = used + 1
        return row['checkpoint_repairs']

    def reserve_worker_iteration(self, aid):
        active = self.s['active']
        require(active is not None and active['action_id'] == aid, 'Worker iteration requires the reserved action')
        row = next((item for item in self.s['consumption'] if item['cycle'] == active['cycle']), None)
        require(row is not None, 'Worker iteration has no cumulative budget reservation')
        scoped = row.get('worker_scope_grants', {row['scope']: row.setdefault('worker_iteration_grants', [row['grant_id']])})
        grants = {}
        for scope in scoped:
            require(self.remaining(scope) > 0, 'Worker iteration budget exhausted')
            grant = next((g for g in self.s['grants'] if g['scope'] == scope and (g['max_cycles'] is None or self.grant_used(g['id']) < g['max_cycles'])), None)
            require(grant is not None, 'Worker iteration budget exhausted')
            grants[scope] = grant['id']
        for scope, identities in scoped.items():
            identities.append(grants[scope])
        row['worker_iteration_grants'] = list(scoped[row['scope']])
        row['worker_iterations'] = row.get('worker_iterations', 1) + 1
        self.event('worker.iteration_reserved', cycle=active['cycle'], action_id=aid, iteration=row['worker_iterations'], scope=row['scope'], grant_id=grants[row['scope']])

    def ingress(self, raw, session_id):
        envelope(raw, self.c['run_id'])
        channel = human_channel(self.c)
        expected_session = self.c.get('pi_session_id') if channel == 'pi' else 'console:' + self.c['run_id']
        require(raw.get('session_id') == session_id == expected_session, 'Human ingress requires bound receiver/console session')
        hid = ident(raw['id'])
        require(hid not in self.s['human'], 'Duplicate human response')
        require(raw.get('kind') in {'resolution', 'grant', 'cancel', 'halt', 'signal'}, 'Unknown human ingress kind')
        require(set(raw) <= {'protocol_version', 'schema_version', 'run_id', 'session_id', 'id', 'kind', 'blocker_ids', 'message', 'cycles', 'request_id', 'source'}, 'Unknown human ingress fields')
        text(raw['message'])
        require(raw.get('source') == ('pi-command' if channel == 'pi' else 'console-command'), 'Only explicit confirmed human commands create human authority')
        if raw['kind'] == 'resolution':
            require(raw.get('blocker_ids') and all(b in self.s['blockers'] for b in raw['blocker_ids']), 'Response must address known blocker IDs')
        if raw['kind'] == 'grant':
            positive(raw['cycles'])
            require(raw.get('request_id') in self.s['requests'] and self.s['requests'][raw['request_id']]['main_extension'], 'Grant must address a budget request')
            prior = next((h for h in self.s['human'].values() if h['kind'] == 'grant' and h.get('request_id') == raw['request_id']), None)
            if prior is not None:
                self.s['human'][hid] = {**deepcopy(raw), 'validated': False, 'processed': True, 'duplicate_of': prior['id'], 'received_at': time.time()}
                self.event('human.duplicate_authorization', human_id=hid, prior_id=prior['id'])
                return
            if self.s['requests'][raw['request_id']].get('main_grant_count') != len(self.s['grants']):
                self.s['human'][hid] = {**deepcopy(raw), 'validated': False, 'processed': True, 'rejected': 'stale_budget_request', 'received_at': time.time()}
                self.event('human.stale_authorization', human_id=hid, request_id=raw['request_id'])
                return
        self.s['human'][hid] = {**deepcopy(raw), 'validated': False, 'processed': False, 'received_at': time.time()}
        self.event('human.received', human_id=hid, ingress_kind=raw['kind'])
        if raw['kind'] in {'cancel', 'halt'}:
            if raw['kind'] == 'halt' or self.s['execution'] != 'halt':
                self.s['execution'] = 'cancelled' if raw['kind'] == 'cancel' else 'halt'
            self.s['wait'] = None
            self.event('execution.' + self.s['execution'], reason=raw['message'])
        # Input never resolves blockers or restarts terminal work; a global halt has highest precedence.

    def apply(self, report, evidence, review_ref):
        """Only the bridge calls this after independent hash-bound Reviewer assessment."""
        envelope(report, self.c['run_id'])
        fields = {'protocol_version', 'schema_version', 'run_id', 'cycle', 'review_id', 'state_sha256', 'target', 'source_state', 'safe', 'halt_reason', 'actions', 'blockers', 'resolutions', 'grants', 'criteria', 'reconciliation'}
        require(set(report) - {'wake'} in (fields, fields | {'decompositions'}), 'Reviewer report fields differ from schema 1')
        require(report['target'] == self.c['execution_contract']['target'], 'Unverified target identity')
        text(report['source_state'])
        require(type(report['safe']) is bool, 'Safety judgment required')
        if not report['safe']:
            text(report['halt_reason'])
            self.s['execution'] = 'halt'
            self.s['wait'] = None
            self.event('execution.halt', reason=report['halt_reason'], review=review_ref)
            return
        if self.s['execution'] in TERMINAL:
            return
        require(type(report['cycle']) is int and report['cycle'] == self.s['cycle'] and type(report['review_id']) is int and report['review_id'] == self.s['review_seq'] and report['state_sha256'] == sha(self.s), 'Stale reviewer cycle/review/state identity')
        require(set(report['criteria']) == set(self.s['acceptance']), 'Every acceptance criterion must be assessed')
        for cid, result in report['criteria'].items():
            require(set(result) == {'status', 'evidence_refs'}, 'Invalid criterion report')
            require(result['status'] in {'pass', 'fail', 'blocked', 'not_tested', 'unknown'}, 'Invalid acceptance state')
            self.proof(result['evidence_refs'], evidence, required=result['status'] == 'pass')
        pending = self.unassessed()
        require(len(pending) <= 1 and all(row['cycle'] == self.s['cycle'] for row in pending), 'Historical worker cycles lack independent assessment; investigate before recovery')
        selected = pending[0] if pending else None
        dispatched = selected.get('action_ids', [selected['action_id']]) if selected else []
        primary_attempt = deepcopy(next((r['attempt'] for r in report['actions'] if selected and r['action']['id'] == selected['action_id']), None))
        if primary_attempt and any(a['fingerprint'] == primary_attempt['fingerprint'] for a in self.s['actions'][selected['action_id']]['attempts']):
            primary_attempt['assessment'] = 'none'
        for result in report['actions']:
            aid = result['action']['id']
            if selected is not None and aid == selected['action_id']:
                require(result['attempt'] is not None, 'Selected worker cycle requires independent assessment')
            elif result['attempt'] is not None and aid not in dispatched:
                raise ValueError('Attempt requires an unassessed selected cycle, not initial/peer observation')
        if selected is not None:
            require(any(r['action']['id'] == selected['action_id'] for r in report['actions']), 'Selected worker cycle requires independent assessment')
        rec = report['reconciliation']
        require(set(rec) == {'fresh', 'approvals_applicable', 'evidence_refs', 'operations'}, 'Invalid reconciliation report')
        self.proof(rec['evidence_refs'], evidence, required=bool(rec['operations']))
        require(rec['fresh'] is True and rec['approvals_applicable'] is True, 'Environment/evidence/approvals need reconciliation')
        seen_operations = set()
        conflicts = []
        for result in rec['operations']:
            require(set(result) == {'id', 'outcome', 'evidence_refs'}, 'Invalid operation reconciliation')
            require(result['id'] not in seen_operations, 'Duplicate operation reconciliation')
            seen_operations.add(result['id'])
            self.proof(result['evidence_refs'], evidence)
            op = self.s['operations'][result['id']]
            require(result['outcome'] in {'succeeded', 'not_performed', 'failed', 'uncertain'}, 'Unknown operation outcome')
            if result['outcome'] not in OPERATION_TRANSITIONS[op['outcome']]:
                conflicts.append((op, result))
        if conflicts:
            for op, result in conflicts:
                self.event('operation.conflict', id=op['id'], previous=op, observed=result, review=review_ref)
            self.s.update(execution='halt', wait=None, active=None, reconciled=False)
            self.s['acceptance'] = {cid: 'unknown' for cid in self.s['acceptance']}
            self.event('execution.halt', reason='Contradictory operation evidence; investigate without replay', review=review_ref)
            return
        # Apply resolutions before closure provenance, so a verified resolution activates closure now.
        for resolution in report['resolutions']:
            require(set(resolution) == {'blocker_id', 'human_id', 'valid', 'approval_applicable', 'evidence_refs'}, 'Invalid resolution judgment')
            b = self.s['blockers'][resolution['blocker_id']]
            require(type(resolution['valid']) is bool and type(resolution['approval_applicable']) is bool, 'Resolution needs actual validation')
            self.proof(resolution['evidence_refs'], evidence)
            h = self.s['human'].get(resolution['human_id'])
            if resolution['human_id'] is not None:
                require(h is not None and h['kind'] == 'resolution' and b['id'] in h['blocker_ids'], 'Resolution not addressed by human response')
                h['processed'] = True
            if resolution['valid'] and b['reason'] in {'approval_required', 'user_choice'}:
                require(h is not None and resolution['approval_applicable'], 'Technical success cannot manufacture human approval or choice')
            b['resolutions'].append({**deepcopy(resolution), 'review': review_ref})
            if resolution['valid']:
                b['status'] = 'resolved'
                b['escalation'] = 'resolved'
                self.event('blocker.resolved', blocker_id=b['id'], review=review_ref)
                # Initial authority plus independently validated resolution establishes root provenance.
                if self.c['execution_contract']['closure']['authorized']:
                    for aid in b['blocked_actions']:
                        a = self.s['actions'][aid]
                        if a['status'] != 'verified' and a['scope'] == 'main':
                            self.closure(a, dict(blocker_id=b['id'], unblocked_action_id=aid, parent_action_id=None, reason='Independently validated blocker resolution', evidence_refs=resolution['evidence_refs']), evidence)
            else:
                b['status'] = 'open'
        for hid in report['grants']:
            h = self.s['human'][hid]
            require(not h['processed'] and 'duplicate_of' not in h, 'Grant authorization replay')
            h['validated'] = True
            self.grant(hid)
            h['processed'] = True
        seen = set()
        for result in report['actions']:
            require(set(result) in ({'action', 'status', 'eligible', 'scope_authorized', 'dependencies_valid', 'evidence_refs', 'attempt', 'experiment'}, {'action', 'status', 'eligible', 'scope_authorized', 'dependencies_valid', 'evidence_refs', 'attempt', 'experiment', 'continuation'}), 'Invalid action judgment')
            raw = result['action']
            validated_action = action(raw)
            aid = ident(raw['id'])
            require(aid not in seen, 'Duplicate action judgment')
            seen.add(aid)
            require(result['scope_authorized'] is True and result['dependencies_valid'] is True, 'Action scope/independence must be independently validated')
            require(type(result['eligible']) is bool, 'Action eligibility must be verified')
            self.proof(result['evidence_refs'], evidence, required=result['status'] == 'verified' or result['experiment'] is not None or aid not in self.s['actions'] or bool(raw.get('operations')))
            if aid not in self.s['actions']:
                self.s['actions'][aid] = validated_action
                self.event('action.added', action_id=aid, review=review_ref)
            a = self.s['actions'][aid]
            require(raw['description'] == a['description'] and raw.get('depends_on', []) == a['depends_on'] and raw.get('operations', []) == a['operations'], 'Existing action contract is immutable')
            if raw.get('provenance'):
                self.closure(a, raw['provenance'], evidence)
            require(result['status'] in {'pending', 'verified', 'stalled'}, 'Invalid verified action state')
            a['eligible'] = result['eligible']
            a['status'] = result['status']
            if a.get('decomposed_into'):
                require(result['status'] != 'verified', 'Decomposed parent must be verified through its parts')
                a['status'] = 'decomposed'
            a['evidence'] = list(result['evidence_refs'])
            a['verification'] = dict(review=review_ref, source_state=report['source_state'])
            if result['attempt'] is not None:
                self.attempt(a, result['attempt'], result['experiment'], evidence)
                if selected['action_id'] == aid:
                    selected['assessment'] = dict(cycle=selected['cycle'], review=review_ref, attempt=deepcopy(a['attempts'][-1]))
                    self.event('cycle.assessed', cycle=selected['cycle'], action_id=aid, review=review_ref)
            elif result['experiment'] is not None:
                self.experiment(a, result['experiment'], evidence)
            elif aid in dispatched:
                a['experiment'] = None
            if aid in dispatched:
                a['budget_interrupted_cycle'] = (selected['cycle'] if self.c.get('mode') == 'goal'
                    and self.remaining(a['scope']) <= 0 and any(
                        session.get('cycle') == selected['cycle'] and aid in session.get('action_ids', [session.get('action_id')])
                        and session.get('status') == 'budget_limited' for session in self.s.get('sessions', [])) else None)
            continuation = result.get('continuation')
            if continuation is not None:
                require(aid in dispatched and result['status'] == 'pending' and result['eligible'] and result['experiment'] is None, 'Continuation requires the selected eligible unfinished action')
                require(isinstance(continuation, dict) and set(continuation) == {'next_step', 'evidence_refs'}, 'Invalid unfinished work continuation')
                text(continuation['next_step'])
                self.proof(continuation['evidence_refs'], evidence)
                assessment = a['attempts'][-1] if result['attempt'] is not None else primary_attempt
                require(assessment is not None and assessment['assessment'] == 'informative', 'Continuation requires independently identified progress or remaining work, not unknown')
                a['continuation'] = deepcopy(continuation)
                a['status'] = 'pending'
                self.event('action.continued', action_id=aid, cycle=selected['cycle'], next_step=continuation['next_step'])
            elif aid in dispatched or result['attempt'] is not None or result['status'] != 'pending':
                a.pop('continuation', None)
            if (a['status'] == 'pending' and (a['attempts'] and a['attempts'][-1]['assessment'] != 'verified' or aid in dispatched and aid != selected['action_id'])
                    and a['experiment'] is None and a.get('continuation') is None and a.get('budget_interrupted_cycle') is None):
                a['status'] = 'stalled'
            elif a['status'] == 'stalled' and result['status'] == 'pending' and a.get('budget_interrupted_cycle') is not None:
                a['status'] = 'pending'
        require(seen == set(self.s['actions']), 'Every action needs a fresh eligibility/dependency judgment')
        dependencies(self.s['actions'])
        decompositions = report.get('decompositions', [])
        require(isinstance(decompositions, list), 'Invalid action decompositions')
        used_parents = set()
        for item in decompositions:
            require(set(item) == {'parent_id', 'child_ids', 'complete'} and item['complete'] is True, 'A decomposition must name all parts and be independently complete')
            parent_id = ident(item['parent_id'])
            child_ids = item['child_ids']
            require(parent_id in self.s['actions'] and parent_id not in used_parents, 'Unknown or duplicate decomposition parent')
            require(isinstance(child_ids, list) and child_ids and len(child_ids) == len(set(child_ids)), 'Decomposition needs distinct child actions')
            require(all(ident(child_id) in seen and child_id != parent_id for child_id in child_ids), 'Every decomposition part needs a fresh independent action judgment')
            parent = self.s['actions'][parent_id]
            previous = parent.get('decomposed_into')
            require(previous is None or previous == child_ids, 'Action decomposition contract is immutable')
            parent['decomposed_into'] = deepcopy(child_ids)
            parent['status'] = 'decomposed'
            used_parents.add(parent_id)
            self.event('action.decomposed', parent_id=parent_id, child_ids=child_ids, review=review_ref)
        validate_decompositions(self.s['actions'])
        # Apply blockers after action reconciliation so a single review boundary can split a compound action and block only the dependent part.
        for raw in report['blockers']:
            require(set(raw) == {'blocker', 'evidence_refs'}, 'Invalid blocker judgment')
            self.proof(raw['evidence_refs'], evidence)
            self.blocker(raw['blocker'], raw['evidence_refs'])
        for result in rec['operations']:
            op = self.s['operations'][result['id']]
            self.event('operation.reconciled', id=op['id'], previous_outcome=op['outcome'], previous_evidence_refs=op.get('evidence_refs', []), previous_review=op.get('review'), outcome=result['outcome'], evidence_refs=result['evidence_refs'], review=review_ref, owner=op['owner'], cycle=op['cycle'])
            op.update(outcome=result['outcome'], evidence_refs=deepcopy(result['evidence_refs']), review=review_ref)
        self.s['reconciled'] = not any(op['outcome'] in {'started', 'uncertain'} for op in self.s['operations'].values())
        self.s['acceptance'] = {cid: r['status'] for cid, r in report['criteria'].items()}
        self.s['acceptance_evidence'] = dict(criteria=deepcopy(report['criteria']), source_state=report['source_state'], review=review_ref)
        self.s['active'] = None
        self.s['execution'] = 'continue'
        if not self.s['reconciled']:
            self.arrange_wait('resource-signal', 'Reconcile uncertain operations: ' + ', '.join(k for k, op in self.s['operations'].items() if op['outcome'] in {'started', 'uncertain'}))
        elif self.s['wait'] and self.s['wait']['source'] != 'human-response':
            self.s['wait'] = None
        if report.get('wake') is not None:
            wake = report['wake']
            require(set(wake) == {'source', 'reference', 'at'}, 'Invalid arranged wake')
            self.arrange_wait(wake['source'], wake['reference'], wake['at'])
        self.s['last_review'] = review_ref
        self.event('review.applied', review=review_ref, source_state=report['source_state'])

    @staticmethod
    def proof(refs, evidence, required=True):
        require(isinstance(refs, list) and (not required or bool(refs)) and all(isinstance(r, str) and r in evidence for r in refs), 'Missing independently snapshotted evidence')

    def experiment(self, a, experiment, evidence):
        require(set(experiment) == {'hypothesis', 'material_difference', 'expected_evidence', 'next_step', 'fingerprint', 'evidence_refs'}, 'Incomplete justified experiment')
        for key in ('hypothesis', 'material_difference', 'expected_evidence', 'next_step', 'fingerprint'):
            text(experiment[key])
        self.proof(experiment['evidence_refs'], evidence)
        require(not any(x['fingerprint'] == experiment['fingerprint'] for x in a['attempts']) and
                not any(event['type'] == 'experiment.planned' and event.get('action_id') == a['id'] and event.get('fingerprint') == experiment['fingerprint'] for event in self.s['history']),
                'Equivalent experiment already attempted; changed conditions required')
        a['experiment'] = deepcopy(experiment)
        a['status'] = 'pending'
        self.event('experiment.planned', action_id=a['id'], fingerprint=experiment['fingerprint'])

    def attempt(self, a, attempt, experiment, evidence):
        require(set(attempt) == {'strategy', 'state_before', 'outcome', 'fingerprint', 'assessment', 'evidence_refs'}, 'Invalid action attempt')
        for key in ('strategy', 'state_before', 'outcome', 'fingerprint'):
            text(attempt[key])
        self.proof(attempt['evidence_refs'], evidence, required=attempt['assessment'] == 'verified')
        require(attempt['assessment'] in {'verified', 'informative', 'none'}, 'Invalid progress assessment')
        value = deepcopy(attempt)
        if any(x['fingerprint'] == value['fingerprint'] for x in a['attempts']):
            value['assessment'] = 'none'
        a['attempts'].append(value)
        a['experiment'] = None
        if a['status'] == 'verified':
            require(value['assessment'] == 'verified', 'Action PASS requires verified progress')
        elif experiment is not None:
            self.experiment(a, experiment, evidence)
        elif value['assessment'] != 'verified':
            a['status'] = 'stalled'
        self.event('attempt.assessed', action_id=a['id'], attempt=value)

    def unassessed(self):
        return [row for row in self.s['consumption'] if not row.get('assessment') and not row.get('not_started')]

    def available(self):
        verification = self.s.get('verification') or {}
        if (verification and verification.get('status') != 'blocked') or not self.s['reconciled']:
            return []
        unassessed = self.unassessed()
        if unassessed and not verification:
            return []
        blocked = set(verification.get('blocked_action_ids', [])) | {aid for row in unassessed for aid in row.get('action_ids', [row['action_id']])}
        def depends_on_blocked(aid, seen=None):
            seen = set() if seen is None else seen
            if aid in seen:
                return False
            seen.add(aid)
            return aid in blocked or any(depends_on_blocked(dep, seen) for dep in self.s['actions'][aid]['depends_on'])
        return [a for a in self.s['actions'].values() if a['status'] == 'pending' and a['eligible'] and not depends_on_blocked(a['id']) and all(self.s['blockers'][b]['status'] == 'resolved' for b in a['blocked_by']) and all(action_complete(self.s['actions'], d) for d in a['depends_on'])]

    def transition(self, now=None):
        now = time.time() if now is None else now
        if self.s['execution'] in TERMINAL:
            return self.s['execution'], None
        if self.s.get('verification') and self.s['verification'].get('status') != 'blocked':
            return 'wait', None
        if self.s['active'] is not None:
            return 'continue', None
        if not self.s.get('verification') and self.s['reconciled'] and not self.unassessed() and all(v == 'pass' for v in self.s['acceptance'].values()) and all(action_complete(self.s['actions'], aid) for aid in self.s['actions']) and all(b['status'] == 'resolved' for b in self.s['blockers'].values()):
            self.s['execution'] = 'finish'
            self.s['wait'] = None
            self.event('execution.finish', review=self.s['last_review'])
            return 'finish', None
        available = self.available()
        worker_limited = ((self.c.get('mode') == 'goal' and self.s.get('goal_usage_status') == 'unknown')
                          or (self.c.get('mode') in {'goal', 'ralph'} and self.s.get('worker_seconds', 0) >= self.c.get('wall_seconds', float('inf'))))
        permitted = [a for a in available if self.remaining(a['scope']) > 0 and not worker_limited]
        open_blockers = [b for b in self.s['blockers'].values() if b['status'] == 'open']
        extension = (any(a['scope'] == 'main' for a in available) and self.remaining('main') <= 0
                     and not (self.c.get('mode') == 'ralph' and worker_limited))
        if permitted:
            self.s['execution'] = 'replan' if permitted[0]['experiment'] else 'continue'
            self.s['wait'] = None
            return self.s['execution'], permitted[0]['id']
        if (self.s.get('verification') or {}).get('status') == 'blocked':
            if open_blockers:
                self.request(open_blockers, False, now)
            self.s['execution'] = 'wait'
            self.s['wait'] = None
            return 'verification_blocked', None
        if open_blockers or extension:
            rid = self.request(open_blockers, extension, now)
            state = 'wait' if open_blockers else 'paused_budget'
            self.s['execution'] = state
            if self.s['wait'] is None:
                self.s['wait'] = dict(source='human-response', reference=rid, since=now, next_reminder=now + self.c['execution_contract']['reminder_seconds'], reminder_seq=0)
            elif self.s['wait']['source'] == 'human-response':
                self.s['wait']['reference'] = rid
            return state, None
        if self.s['wait'] is not None:
            self.s['execution'] = 'wait'
            return 'wait', None
        self.s['execution'] = 'stop'
        unverified = self.delivered_unverified()
        if unverified:
            # Delivery, not acceptance: budgets, grants and the no-synthetic-correction rule are unchanged.
            self.s['delivery'] = dict(status='delivered_unverified', unverified_criteria=unverified, review=self.s['last_review'])
            self.event('execution.stop', outcome='delivered_unverified', unverified_criteria=unverified, review=self.s['last_review'],
                       reason='Delivered, not verified: every action is complete and the independent review found no defect, uncertain operation, blocker or wait; only unverified criteria remain')
            return 'stop', None
        self.event('execution.stop', reason='No authorized productive action, justified experiment or concrete wake source remains')
        return 'stop', None

    def delivered_unverified(self):
        """Criteria left unknown/not_tested after an applied review found no defect and every action complete; empty means an ordinary stop."""
        statuses = self.s['acceptance'].values()
        if (not self.s.get('last_review') or self.s.get('verification') or not self.s['reconciled'] or self.unassessed()
                or any(op['outcome'] in {'started', 'uncertain'} for op in self.s['operations'].values())
                or any(b['status'] == 'open' for b in self.s['blockers'].values())
                or any(status in {'fail', 'blocked'} for status in statuses)
                or not all(action_complete(self.s['actions'], aid) for aid in self.s['actions'])):
            return []
        return sorted(cid for cid, status in self.s['acceptance'].items() if status in {'unknown', 'not_tested'})

    def request(self, blockers, extension, now):
        payload = dict(blocker_ids=sorted(b['id'] for b in blockers), main_extension=extension, main_grant_count=len(self.s['grants']) if extension else None, blocker_versions={b['id']: len(b['resolutions']) for b in blockers})
        rid = 'Q-' + sha(payload)[:16]
        if rid not in self.s['requests']:
            self.s['requests'][rid] = dict(id=rid, **payload, questions=[dict(blocker_id=b['id'], needed=b['needed']) for b in blockers], created_at=now)
            self.event('escalation.grouped', request_id=rid)
        for b in blockers:
            b['escalation'] = 'requested'
        return rid

    def arrange_wait(self, source, reference, at=None):
        require(source in {'human-response', 'resource-signal', 'bounded-recheck'}, 'A specific wake source is mandatory')
        text(reference)
        if source == 'bounded-recheck':
            require(type(at) in {int, float} and at > 0, 'Recheck needs an absolute scheduled deadline')
            require(not any(w['source'] == source and w['reference'] == reference for w in self.s['wake_history']), 'Bounded wake is one-shot; no recurring paid model polling')
        require(self.s['execution'] not in TERMINAL, 'Terminal run cannot wait')
        self.s['wait'] = dict(source=source, reference=reference, at=at, since=time.time(), next_reminder=time.time() + self.c['execution_contract']['reminder_seconds'], reminder_seq=0)
        self.s['wake_history'].append(dict(source=source, reference=reference, at=at))

    def reminder(self, now=None):
        now = time.time() if now is None else now
        wait = self.s['wait']
        if self.s['execution'] in TERMINAL or not wait or now < wait['next_reminder']:
            return None
        wait['reminder_seq'] += 1
        wait['next_reminder'] = now + self.c['execution_contract']['reminder_seconds']
        rid = 'reminder-' + str(len(self.s['history'])) + '-' + str(wait['reminder_seq'])
        self.event('wait.reminder', id=rid)
        return rid

    def resource_signal(self, raw):
        envelope(raw, self.c['run_id'])
        require(set(raw) == {'protocol_version', 'schema_version', 'run_id', 'id', 'reference'}, 'Invalid resource event schema')
        eid = ident(raw['id'])
        text(raw['reference'])
        require(eid not in self.s['signals'], 'Duplicate resource event')
        require(self.s['execution'] not in TERMINAL and self.s['active'] is None, 'Resource event applies only at a safe nonterminal boundary')
        wait = self.s['wait']
        if wait is None or wait['source'] != 'resource-signal' or wait['reference'] != raw['reference']:
            self.s['signals'][eid] = {**deepcopy(raw), 'processed': True, 'ignored': True}
            self.event('resource.ignored', id=eid, reason='No matching arranged wake')
            return
        self.s['signals'][eid] = {**deepcopy(raw), 'processed': False}
        self.s['wait'] = None
        self.s['execution'] = 'replan'
        self.s['reconciled'] = False
        self.s['acceptance'] = {cid: 'unknown' for cid in self.s['acceptance']}
        self.event('resource.signal', id=eid, reference=raw['reference'])
        # A signal schedules fresh independent observation only; it grants no approval, scope or budget.

    def operation(self, aid, oid, owner):
        require(self.s['execution'] not in TERMINAL and self.s['reconciled'], 'Run not safe for effects')
        active = self.s['active']
        require(active is not None and active['owner'] == owner and aid in active.get('action_ids', [active['action_id']]), 'Operation requires current exclusive worker ownership')
        require(self.s['sessions'] and self.s['sessions'][-1]['owner'] == owner and self.s['sessions'][-1]['status'] == 'running' and 'ended_at' not in self.s['sessions'][-1], 'Retired worker session cannot perform external effects')
        a = self.s['actions'][aid]
        plan = next((op for op in a['operations'] if op['id'] == oid), None)
        require(plan is not None, 'External operation not authorized by action contract')
        require(all(self.s['blockers'][b]['status'] == 'resolved' for b in a['blocked_by']), 'Action remains blocked')
        if plan.get('approval_blocker'):
            b = self.s['blockers'][plan['approval_blocker']]
            require(b['reason'] == 'approval_required' and b['status'] == 'resolved' and any(r['valid'] and r['human_id'] is not None and r['approval_applicable'] for r in b['resolutions']), 'External operation needs applicable authentic approval')
        key = aid + ':' + oid
        old = self.s['operations'].get(key)
        require(old is None or old['outcome'] == 'not_performed', 'External operation must not replay an uncertain, failed or completed outcome')
        self.s['operations'][key] = dict(id=key, action_id=aid, operation=deepcopy(plan), outcome='started', owner=owner, cycle=self.s['cycle'], prior=deepcopy(old))
        self.event('operation.started', id=key, owner=owner)
        return key

    def interrupted(self):
        if self.s['active'] is not None:
            self.event('worker.interrupted', active=self.s['active'])
        for session in self.s['sessions']:
            if session['status'] in {'starting', 'running'}:
                session['status'] = 'interrupted'
        for op in self.s['operations'].values():
            if op['outcome'] == 'started':
                self.event('operation.interrupted', id=op['id'], previous_outcome='started', outcome='uncertain', owner=op['owner'], cycle=op['cycle'])
                op['outcome'] = 'uncertain'
        self.s['active'] = None
        self.s['reconciled'] = False
        self.s['acceptance'] = {cid: 'unknown' for cid in self.s['acceptance']}
        for a in self.s['actions'].values():
            a['eligible'] = False
        self.event('reconciliation.required')
