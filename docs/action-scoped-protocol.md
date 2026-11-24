# Protocol 2 / schema 1 — direct independent review

## Version and compatibility

Current execution uses integer protocol_version=2, schema_version=1 and execution_contract. No eval_argv or task-specific evaluator. Protocol 1 and evaluator-era runs are unsupported; old files are not rewritten or migrated. The existing action/criterion report schema, CLI run/resume/wake/human/signal/operation paths, Pi receiver message envelopes, aliases and session entries remain. `review-v2 --assessment` now submits Reviewer judgments directly; old correct/correction/human-needs and legacy decide semantics are not supported. See [migration](evaluator-preparation.md).

## Contract and initial work

execution_contract contains target, actions, criteria, closure and reminder_seconds. Actions have stable id, description, depends_on and pre-authorized operations. Dependencies must exist and be acyclic. Config/TASK are private run-owned regular files outside work/; both hashes and paths remain pinned. Run state has lifecycle=worker-reviewer, used to refuse evaluator-era restoration, not another user setup requirement.

Fresh initial actions are eligible from recorded task authority; Core selects dependency-ready work without an initial model call. Scope/authorization, explicit external operations and approval requirements still apply. Cwd/Git ancestry does not grant scope. Worker journals a pre-authorized external operation through bridge.py operation with the current owner token before performing it. Existing identity/ownership, lease, operation-state and authentic approval checks remain. No repeated external effect on uncertain, failed or succeeded outcomes.

Worker runs ordinary targeted tests and retains commands, exit status, output, source and relevant artifacts in its checkpoint evidence. Browser tasks use the same resolved Playwright route for Goal and Ralph. A missing/broken check is a verification limitation, not proof of a product defect.

## Native Goal execution

Goal receives the full authorized task scope in `cycle-context.action_ids`/`actions`, not one model turn or external effect. The existing `action_id` anchors its cycle/checkpoint identity. Dispatched dependencies can be completed within that same native Goal; blocked, ineligible, previously unassessed or out-of-scope work stays excluded. Stable pre-authorized operation IDs can be reserved across the dispatch under its exclusive owner; successful, failed or uncertain effects never replay.

Native continuation runs until native completion or a real stopped/waiting/token/time limitation. Progress checkpoints do not force `goal_wait` or review. Core stops its Worker process before independent result review so native wake timers cannot write concurrently. A completed/stopped native Goal can receive concrete corrections through a new native ID in the same Pi history, limited to remaining cumulative tokens/time; an active waiting window keeps its ID. Native completion is not acceptance and acceptance needs no additional Worker turn. Ralph runs its native multi-iteration loop over the full dispatched objective, with result review after completion or a real limitation, not each progress checkpoint. Concrete corrections/remaining authorized work stay within cumulative native iterations/time; unknown alone never creates a correction. See [native task storage and snapshot limits](project-workspace.md).

## Independent Reviewer boundary

After an actual Worker result (or a concrete recovery/human/resource event), Core archives evidence, writes context.json/request.json and starts one independent Reviewer. No pre-work evaluator, post-work evaluator, source patch or evaluator retry exists. Headless execution uses a separate fresh read-only Pi session with explicit actual model/provider/session validation and a finite independent review deadline. Chat/Codex review transport remains available for new configs.

Core includes the full TASK and current contract/checkpoint inline, not just paths; other context and retained material remain available to the read tool. Reviewer uses ordinary test results for what they establish, without rerunning or re-proving deterministic checks. It judges residual requirement fit, semantic/visual quality, omissions and concrete contradictions. Do not invent scenarios, selectors, names, incidental representations, approvals or acceptance gates. Missing evidence is unknown, never fabricated pass. Further Worker experiments need a specific defect/unfinished authorized action and materially different next step; Core never converts unknown into an experiment.

Headless output:

```json
{"decision":"endorse", "feedback":"Concrete independent finding", "assessment":{}}
```

The assessment placeholder above must be filled with the existing report fields below. `endorse` submits judgments, not acceptance. halt requires a concrete global safety/integrity risk; stop means explicit abandonment. Those decisions need no assessment. Optional complete response identities must match exactly; normally omit them. Core binds run/protocol/schema, cycle, review_id, state_sha256 and target from its immutable request.

Required assessment fields:

- source_state: specific inspected state; safe: boolean; halt_reason: null unless unsafe.
- criteria: EVERY criterion ID -> {status: pass|fail|blocked|not_tested|unknown, evidence_refs: retained names}. Pass requires relevant retained evidence.
- actions: EVERY current action, with action={id,description,depends_on,operations}, status=pending|verified|stalled, eligible:boolean, scope_authorized:true, dependencies_valid:true, evidence_refs, attempt, experiment. Existing contracts are immutable. New in-scope actions/decompositions use the same scope/dependency/provenance checks.
- attempt: the outstanding selected cycle requires {strategy,state_before,outcome,fingerprint,assessment:verified|informative|none,evidence_refs} on its anchor action; other dispatched Goal actions may optionally carry an attempt from that same whole-result review, while non-dispatched peers use null. Verified progress requires retained proof. Unknown/nonprogress can be recorded without inventing evidence or repetition. Duplicate fingerprints cannot establish progress.
- experiment: null or {hypothesis,material_difference,expected_evidence,next_step,fingerprint,evidence_refs}. Evidence-backed, materially different, nonduplicate; no experiment is generated from generic Reviewer feedback or unknown criteria.
- continuation: optional {next_step,evidence_refs} on an eligible pending action in the outstanding dispatch, with an informative nonduplicate attempt on that action or the Goal anchor and retained evidence. It identifies specific unfinished authorized work or a concrete defect to fix, without imposing an experiment. Generic uncertainty is not remaining work.
- blockers: [{blocker:{key,reason,needed,blocked_actions},evidence_refs}], only missing_secret|missing_access|approval_required|user_choice|external_blocker. Stable deduplication keys retain history.
- resolutions: [{blocker_id,human_id,valid,approval_applicable,evidence_refs}], using authentic addressed input; technical success never manufactures human approval/choice.
- grants: unprocessed authentic grant IDs, additive and single-use.
- reconciliation: {fresh:true,approvals_applicable:true,evidence_refs,operations:[{id,outcome:succeeded|not_performed|failed|uncertain,evidence_refs}]}. Every uncertain effect remains held until actually reconciled; contradictory stable outcomes halt without replacing the journal.
- Optional decompositions=[{parent_id,child_ids,complete:true}] and wake={source,reference,at}, using existing validated action and arranged-wake contracts.

Chat submission:

```sh
python3 scripts/bridge.py review-v2 --config /absolute/run/config.json \
  --decision endorse --feedback 'Concrete finding' --assessment '<JSON assessment>'
```

review-id may be supplied or resolved from the active request. Core validates a copy before durable recording, then revalidates before application under its control boundary. Request/state/checkpoint/evidence hashes and duplicate refusal remain; Worker ready/exit0 is never acceptance. evidence_archive values are complete immutable file paths, not directories. Successful correlated read events remain audit evidence, not mandatory blanket rereads or a new review loop. A missing read event alone is not a failure. An observed failed access to material cited for verified claims, without later successful access, cannot establish endorsement; work is delivered unverified without forced reads/review repeats or a Worker defect. Missing relevant evidence must remain unknown. Invalid response formatting may be corrected within the SAME Reviewer session/deadline, not by repeating valid negative findings or launching another evaluator/Reviewer.

## Decisions and delivery

Core finish still requires reconciled state, no unassessed cycles, all criteria pass, every action complete and all blockers resolved. Delivery alone never sets finish. A stop after an applied no-defect review with every action complete, no uncertain operation, open blocker, wait or fail/blocked criterion, and only unknown/not_tested criteria left records `delivery.status=delivered_unverified` (bridge `outcome`): delivered, not verified, not acceptance; grants/usage are unchanged. Informative/nonprogress attempts stall that action unless the selected cycle has an evidenced specific continuation or justified experiment; peer observation cannot erase the restriction. Independent eligible actions continue around scoped blockers or blocked review, but not through unresolved dependencies or uncertain operations. A failed Goal result review holds every dispatched action, not just its accounting anchor. Unknown review cannot reuse an earlier dispatched correction/experiment to replay Worker work.

A failed/unavailable Reviewer records the limitation, preserves checkpoint/evidence under unverified-results/, continues independent authorized work, then delivers the available result with unverified items. No blind review redispatch, forced evaluator repair, fake pass or extra Worker iteration merely to obtain missing review. Already identified genuine human gaps are grouped and delivered even when the Reviewer later fails; the failure itself creates no human or budget gate. Human questions are grouped only after independent work is exhausted and only for real human-dependent gaps. A Goal budget-limited result without a checkpoint remains in the unverified-result ledger when review fails; preserving it atomically clears its active reservation.

## Budgets, waits and recovery

Goal uses one Pi session/history, cumulative wall_seconds, goal_max_launches (default 10 new native Goal windows) and an optional cumulative goal_tokens cap (unset = no native --tokens), native-window identity and high-water accounting across checkpoints, grants and recovery. Checkpoints do not spend max_cycles. Explicit main grants add configured token windows; previous native Goal IDs cannot be charged as new windows. A persisted but undispatched window can be retried after reconciliation. Missing native telemetry leaves a lower bound/unknown remaining allowance, not more Worker budget; delivery/review can continue. See [full Goal accounting](../references/reviewed-runs.md#budgets-and-goal-accounting).

Mixed Goal/Ralph dispatches keep the full authorized objective but record `worker_scope_grants` for every participating scope; existing anchor `scope`/`grant_id`/`worker_iteration_grants` remain compatible. Goal still shares one cumulative token/time allowance. Ralph reserves the smallest participating scope's finite native iteration window before spawn, including corrections, charging and releasing each scope consistently; only a matching ordinary terminal native result releases unused reservations. Missing/interrupted/error/cancelled telemetry keeps the reserved bound. Non-identity malformed/missing native checkpoints use available-output review, not task replay to repair metadata. Its cycle_seconds bounds individual native iterations, not the whole loop. Goal uses cumulative active Worker wall_seconds and tokens, not a per-action cycle_seconds cutoff. Actual time exhaustion reconciles usage and reviews/delivers retained outputs without another Worker allowance. Completed Goal corrections create fresh native windows bounded by the remaining allowance, not a fresh run budget. Missing/malformed non-identity Goal checkpoints use output discovery and review rather than a metadata-only product replay. Missing/wrong checkpoint run/cycle/action identities are never accepted, but are Worker checkpoint errors handled by the same repair/available-output path, not a halt. Other checkpoint schema/evidence repairs use the same action/cycle, cumulative wall time and existing outputs, never task/effect replay. Ping-pong checkpoint format/schema repairs (`worker.checkpoint_invalid` → same reserved action/cycle redispatch) do not spend `max_cycles`; they have their own bound `checkpoint_repair_attempts` (optional config, default 3 per reserved action/cycle; 0 disables repair) and still spend cumulative `wall_seconds`. Used repairs are recorded as `checkpoint_repairs` on the consumption row and in `bridge-status.json`, separate from `worker_iterations`. At the limit Core records `worker.repair_budget_exhausted`, retains scoped outputs as an unverified result for independent review, and grants no new budget, replay or acceptance. Worker budgets remain separate from finite review_seconds and verification_seconds. Unknown verification is not a checkpoint-repair request.

Ralph's `worker_tokens`, `worker_tokens_status` and `worker_tokens_by_action` in `bridge-status.json` are [report-only observations](../references/reviewed-runs.md#native-ralph-accounting-and-storage). They never change the reserved iteration window, grants, execution-state hash, or acceptance. A partial count is an observed lower bound; missing measurements are null, not zero.

Human waits/reminders spend no Worker/model turns. `/ppp-respond` normal text/native confirmation and advanced JSON remain; console human ingress is interactive. Grants/resolutions are authenticated/addressed, never model-generated approval. Resource signals wake only the arranged source; bounded rechecks are one-shot, not model polling.

resume/wake preserve run identity, counters, grants, session/native Goal accounting, blockers and operations. No migration of evaluator-era runs. Live inherited Worker/Reviewer leases forbid overlap. Durable attempted review without disposition blocks, even if a callback exists; no blind redispatch/replay. Reconciled idle/applied-review state does not need mandatory repeated review on resume; unresolved results/effects do. Terminal runs cannot restart.

Cancellation/halt is ingested at guarded locked boundaries before review recording/application, dispatch, Worker/operation reservation and finish selection; terminal controls commit before refusal. RPC waits check controls. Owned POSIX process-group cleanup retains unreaped PID identity with waitid(WNOWAIT), TERM/KILL and bounded Darwin EPERM exit observation. Never signal unrelated processes or claim containment of escaped native child groups from an outer lease alone. Host locks are cooperative, not a malicious-code sandbox.

## Evidence limits

Hash-bound synthetic tests establish protocol behavior, not live model correctness, browser visuals, billing, authentication or UI-close autonomy. Review read events prove access, not comprehension. Existing historical implementation/audit/E2E docs describe the removed evaluator lifecycle; current rules above supersede those instructions. New live tests need separate authorization; no global runtime update is implied by source changes.
