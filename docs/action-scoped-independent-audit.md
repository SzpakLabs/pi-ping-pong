# Independent audit: action-scoped protocol 2

## Scope and verdict

Reviewed commits `b4a2091`, `48b939d`, and `81b9229` against the agreed [architecture](action-scoped-execution.md), including controller, bridge, receiver changes, tests, and protocol/implementation reports. Baseline: HEAD `81b9229`; working tree was clean before this audit. The parallel-chat review supplied by the user was treated as hypotheses, not verification evidence.

**Verdict: do not merge as the accepted autonomous baseline yet.** Existing tests pass, but source inspection and synthetic in-memory reproductions expose missing transition safeguards. Fix these before live integration. No production claim, live model run, runtime installation, external operation, old-run mutation, or implementation change was made during this audit.

## Follow-up: F1/F2 hardening

The subsequent [F1/F2 hardening record](protocol-2-f1-f2-hardening.md) documents negative-test reproduction, controller fixes, compatibility and local verification against baseline `6f3adc2`. This audit's original reproductions and verdict below describe its original baseline. The later [F3/F4 hardening record](protocol-2-f3-f4-hardening.md) documents correction/cancellation fixes and targeted synthetic faults. The subsequent [F1–F4 regression audit](protocol-2-regression-audit.md) records the comprehensive local fault matrix and additional boundary fixes. Live integration remains a separate gate. Passing local hardening is not acceptance of the autonomous baseline.

## Findings (priority order)

### F1 — High: unlimited closure can bypass progress assessment completely

Locations: `scripts/action_protocol.py:389-397,439-461`.

`apply()` accepts `status=pending, eligible=true, attempt=null, experiment=null` after a consumed worker cycle. It neither requires an assessment of that cycle nor marks the action stalled. `available()` then selects it again. The `attempt()` safeguards only execute when the evaluator elects to provide an attempt. An informative attempt also leaves a pending action runnable without requiring a justified next experiment.

**Reproduced:** initialized a resolved-blocker closure root, marked other actions verified, and repeated `transition -> consume -> apply` using the existing synthetic report helper with both fields null. Five closure cycles were consumed, zero attempts recorded, and the next transition was still `continue` for the same action. This is not a semantic-equivalence ambiguity: the structural assessment can be omitted entirely. The current integration evaluator fixture itself uses null attempts for all actions, so existing green tests do not protect this boundary.

Impact: the agreed no-default-numerical-cap policy can become an unbounded paid loop without exercising loop detection. Initial reconciliation and unchanged peer actions legitimately need no attempt, so a blanket prohibition on null is not appropriate.

Minimal fix: bind each completed/interrupted selected worker cycle to exactly one independent disposition for that action. Distinguish initial observation, peer revalidation, actual attempt, and validated external wake. Require verified progress or an evidenced productive next step before repeating unfinished work; keep informative failure valid without requiring success. Reject omission as an invalid observation or request a bounded corrected verification, not a fabricated human blocker.

Regression: repeated pending/null judgments after a selected cycle cannot consume unlimited closure; informative failure needs a justified next step; initial eligibility and peer revalidation remain possible without fictitious attempts.

### F2 — High: reconciliation can erase a completed operation's replay protection

Locations: `scripts/action_protocol.py:404-409,563-566`.

Operation reconciliation overwrites any existing outcome with any allowed outcome. A previously `succeeded` or `failed` operation can therefore become `not_performed`. `operation()` explicitly permits a new reservation for `not_performed`, reopening the same stable operation ID to execution. There is no previous-outcome transition guard.

**Reproduced:** placed a successful journal entry into controller state, applied a valid-shaped independently endorsed reconciliation reporting `not_performed`, and observed the persisted outcome change to `not_performed`. The replay admission predicate subsequently accepts that outcome. No actual email, DNS operation, or external effect was performed.

Impact: the controller does not enforce its documented rule that completed/failed operations cannot simply replay. Although a trustworthy verifier should not contradict established evidence, the controller is responsible for rejecting invalid state transitions rather than merely trusting a valid enum.

Minimal fix: define legal operation-outcome transitions. Preserve established completed outcomes; contradictory new evidence must enter explicit investigation/halt handling rather than silently grant replay. Allow recovery from uncertain effects only through the documented evidence-backed resolution path. Preserve outcome history and operation identity.

Regression: succeeded/failed -> not_performed cannot unlock the same operation; legitimate uncertain -> not_performed can, under validated reconciliation; contradictory evidence cannot silently overwrite established truth.

### F3 — Medium: an incorrect evaluator judgment has no nonterminal correction path

Locations: `scripts/action_bridge.py:373-376,395-402`; terminal-state rules in `scripts/action_protocol.py:15` and `scripts/action_bridge.py:457`.

The independent reviewer has only `endorse|halt|stop`, and its prompt explicitly says to stop if report judgments are incorrect. A technical verification defect or wrong dependency/progress judgment therefore forces a terminal run stop instead of an observation correction or replan. Terminal runs cannot resume. This recreates the audited permission-friction failure mode at a new boundary: a correct reviewer detecting a repairable verification error can terminate otherwise productive work.

This is source-confirmed, not a live-model reproduction. It does not imply the reviewer should endorse a bad report or edit protected evaluator code.

Minimal fix: specify a nonterminal verifier/reviewer correction or diagnostic path owned by the controller, retaining fresh identity/evidence checks and no-progress protection. Distinguish an incorrect observation from governing-evaluator corruption or a true global safety failure. Protected evaluator mutation remains prohibited; if a genuinely broken frozen evaluator cannot be repaired under the contract, report that boundary honestly rather than pretending it is routine worker work.

Regression: reviewer rejects a repairable unsupported judgment; acceptance remains pending, no worker executes under that judgment, and independent work or corrected verification can proceed without a new logical run. Repeated unproductive observation repair still stalls/stops honestly.

### F4 — Medium: cancellation during evaluation is not consumed before reviewer dispatch

Locations: `scripts/action_bridge.py:343-380`.

The evaluator is a blocking `subprocess.run()` with a timeout up to 120 seconds. Human controls are checked before it and while waiting for review, but not between evaluator completion and `queue_message()`. A durable cancellation arriving during evaluation can therefore still cause a new paid/model-triggering reviewer request. If the reviewer response is already recorded synchronously, the review-wait loop can be skipped altogether; cancellation is then consumed on the next controller-loop iteration.

This is source-confirmed; no real model cancellation test was performed. Worker execution is absent during this interval, so this finding is about control latency and avoidable post-cancellation work, not a demonstrated extra external write.

Minimal fix: check cancellation/halt before creating/dispatching new review work and before application, including the already-recorded-review case. For prompt cancellation of active evaluation, supervise its owned process group instead of relying only on a blocking call. Do not kill unrelated processes or treat an inbox flag as final acceptance authority.

Regression: cancel during a deliberately delayed fake evaluator; no subsequent review is enqueued, no worker resumes, terminal state wins, and owned evaluator execution settles within the declared cancellation policy.

### F5 — Low: agreed-specification status contradicts the implementation record

Location: `docs/action-scoped-execution.md:3`.

The specification still says “not implemented,” while implementation/verification documents claim delivery. Replace this with a dated, scoped status linking implementation and independent audit evidence: source implementation exists; identified audit gaps remain; live acceptance is unverified. Do not replace it with a blanket production-ready claim.

## Independently executed checks

- `python3 -B scripts/test_action_protocol.py`: **38 passed**.
- `python3 -B scripts/test_action_bridge.py`: **18 passed** (fake Pi/queue processes).
- `python3 -B scripts/test_bridge.py`: **15 passed**.
- `node scripts/test_pi_receiver.mjs`: **passed**.
- `npm run lint`: **passed**.
- `npm run typecheck`: **passed**.
- `.venv/bin/ruff check .`: **passed**.
- Synthetic installer: `python3 -B scripts/test_install.py --fixture-root <new temporary directory>/fixture`: **passed**. The initial invocation without `--fixture-root` failed argument parsing; it was corrected after reading the test interface. No installed runtime was changed.
- Additional isolated controller reproductions confirmed F1 and F2. No repository implementation/test files were modified to run them.

Thus the reported **71 Python tests** are independently confirmed, but test count is not acceptance of missing negative transitions. No dependency installation was necessary. `.venv` tooling was already available; lint/typecheck resolved available tools.

## Assessment of the parallel discussion

Agree with its emphasis on independent evidence, a single authority, cooperative-host limitations, and a live integration gate. Disagree that the remaining main uncertainty is necessarily a future Observer or lack of real E2E: F1 and F2 are already reproducible controller gaps and should be fixed first.

The implementation already owns the autonomous execution loop: `ActionBridge.run()` selects work, runs Goal/Ralph, evaluates, reviews, waits, consumes responses, and resumes. A separate loop for “automatic continuation after worker completion” would duplicate functionality. A future Observer should be limited to host/process supervision, service availability, timers, and delivering reconciled recovery requests to the existing controller. It must not own acceptance, budgets, action selection, or run transitions.

A worker can bypass the external-operation journal using ordinary same-UID tools. The docs acknowledge cooperative execution rather than an OS security sandbox; this is an operational threat-model limitation, not a newly demonstrated enforced-sandbox regression. Live tests cannot prove malicious-process isolation. Likewise, schema tests cannot establish evaluator/reviewer semantic quality or real provider outcome truth.

## Proposed next steps

1. **Close F1/F2 with negative tests first**, then minimal controller fixes. Preserve unlimited default closure; do not substitute an arbitrary retry cap for the agreed progress policy.
2. **Define and implement F3/F4 behavior**, including correction authority, nonterminal dispositions, and cancellation boundaries. Update protocol docs and status F5; record remaining limits.
3. **Run deterministic integration/fault regressions** using existing fake-process infrastructure: omitted attempts, contradictory operation reconciliation, rejected observation repair, cancellation during eval, stale decisions, grant replay, and crash at durable reservation/application boundaries. Re-run existing suites, receiver checks, installer fixture, and development gate. This is controller hardening, not a new autonomous-loop project.
4. **Seek separate authorization for a bounded live E2E matrix**, using isolated local outputs and no real external side effects: real Goal and Ralph finish; missing synthetic input while footer work completes; addressed invalid/valid response; exhausted main then closure; same-run main grant; interrupted worker/reconciled replacement. Pin source, runtime dependency versions, evaluator, budgets and evidence. Keep the supervisor stable and candidate implementation separate. Passing fake tests is not live acceptance.
5. **Accept an explicitly scoped baseline** only after critical findings and required integration evidence are closed. Production/host-reboot claims remain separate from local protocol acceptance.
6. **Only then specify the host Observer** if unattended restart/reminder availability is needed: one authority remains in the controller; Observer acquires no new execution/approval rights. Add host-restart fault tests and passive reminder-delivery checks for that feature.

No additional full rewrite or general-purpose workflow engine is indicated by this audit. The immediate work is targeted correctness and integration proof.

## Knowledge-base scope

The earlier task context consulted `Artem_KB/02_PROJECTS/Pi_Ping_Pong/README.md`, `_SYSTEM/Knowledge_Read_Rules.md`, and `_SYSTEM/Source_Of_Truth.md`. The audit derives implementation conclusions from the current repository, not stale KB status. No KB changes were made; this deliverable is scoped to repository documentation.
