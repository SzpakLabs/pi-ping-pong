# Protocol 2: F1–F4 regression audit and deterministic faults

## Verdict and scope

**READY for bounded real Goal/Ralph E2E**, subject to separate explicit authorization, pinned candidate/runtime/contracts, finite task-specific active limits and synthetic local outputs only. This is readiness for an integration experiment, **not** live acceptance, unattended/chat-independent readiness or production approval. No known critical transition/recovery defect remains in the scoped cooperative-host contract after the fixes below and fresh local gates.

No live Goal/Ralph/model calls, real external operations, runtime installation, dependency installation, external-system changes, commit, merge or next-stage launch were performed. No Headless Reviewer, Observer, cross-chat, scheduler, pi-tick or new semantic loop. Unlimited closure and progress-based work admission remain unchanged; no new retry cap was introduced. The existing correction-experiment bound was preserved, including across crash recovery.

Baseline observed during startup: initially staged prior work, then externally updated HEAD `1b618b9c50bff4c98460cdfc1cbc659db97bdbb0` with a clean tree (`3b11735` contains F1/F2; `1b618b9` contains F3/F4). This audit issued no Git mutation commands and did not revert that update. All audit changes are unstaged on that stable HEAD; previous fixes are preserved.

Sources read: [agreed execution architecture](action-scoped-execution.md), [current protocol](action-scoped-protocol.md), [historical independent audit](action-scoped-independent-audit.md), [F1/F2 record](protocol-2-f1-f2-hardening.md), [F3/F4 record](protocol-2-f3-f4-hardening.md), [integration order](autonomous-run-integration-plan.md), root skill and `references/reviewed-runs.md`. Prior reports' PASS claims were not used as evidence. Controller, shared bridge, action bridge, correction/recovery paths and test assertions were inspected directly; all gates below were executed afresh. No separate paid reviewer/subagent was launched.

## Method and evidence boundary

For each matrix row: inspect invariant and existing assertions, reuse sufficient tests, add negative coverage where missing, reproduce defects before changing production, then rerun targeted tests and the full gate. New tests live in `scripts/test_action_faults.py`; no production fault-injection switches were added.

- Actual bridge/CLI subprocesses use private temporary TASK/config/evaluator and synthetic `pi`/`codex` executables placed first in that subprocess's PATH. They cannot fall through to paid tools.
- Crash drivers inject `os._exit(91)` immediately before/after the real fsynced state write, after assessment/correction commit, or after callback recording but before application. Other tests kill the current fixture Core while a recorded synthetic effect/lease is pending.
- Owned-child tests include a TERM-ignoring descendant, unexpected leader exit and Goal native-query exit. Delayed effect markers must remain absent; test cleanup uses a cooperative stop file rather than signalling potentially reused child PIDs.
- Locked-boundary races inject authentic fixture receipts on entry to the real transaction, after earlier control checks. Assertions verify committed halt/cancellation, no review apply/correction/finish/reservation, and no transport call. These tests exercise actual state locks/checksums/fsync, not mocked transition outcomes.
- Some wire-gate tests inject a controlled evaluator report/reviewer response in process; they test identity/acceptance rules, not evaluator semantic quality. Semantic replan and crash/effect journeys use real fixture executables.
- Explicit waits use readiness files/durable state and finite failure deadlines; the 1.5-second cancellation assertion and 2.1-second delayed-effect observation are local-host timing evidence, not a universal scheduling SLA.

The first harness invocation accidentally discovered imported legacy TestCase classes and hit its 60-second limit before the new cases. Importing the fixture module instead of its TestCase fixed discovery; no defect claim derives from that timeout. An initial stale-request fixture did not create its second request; it was corrected before the meaningful RED reproduction. Neither adjustment weakened production checks.

## Findings, root causes and RED → GREEN

| ID | Defect / root cause | Negative evidence before fix | Minimal correction / final result |
| --- | --- | --- | --- |
| R1 — high | Controls were consumed before, but not inside, state-changing transactions. A receipt arriving on locked entry was invisible to review apply/correction/finish. Raising after ingestion inside a transaction would also roll back the control itself. | Initial RED: finish returned 0 instead of 2; endorse and correct both failed to raise termination. | One `ActionBridge.boundary()` ingests controls under the existing state lock, commits terminal controls before refusing entry, and guards reservation, dispatch, callback recording, apply, correction and final selection. Tests also cover pending cancel before operation admission. GREEN. |
| R2 — high | Resume treated a queued/recorded review as permission to start fresh review, without checking durable delivery/disposition history. A first repair that skipped all `verification` metadata also missed in-flight corrective reviews. | Initial RED: `review_seq` grew 1 → 2 after crash. Additional F1/F3 recovery RED: crash in corrective review returned finish/0 on resume instead of blocked/1, renewing review allowance. | Scan attempted reviews against durable applied/verification dispositions before restoration. An unresolved attempt blocks as reviewer-unavailable, even with a response file or `verification: retry`; already-blocked metadata remains blocked. Committed correction not yet dispatched may resume its existing experiment. GREEN. |
| R3 — high | Evaluator had an owned group but no inherited execution lease. Core death released controller ownership while its evaluator remained live. | RED: replacement evaluator started alongside an infinite orphan; resume did not refuse within 3 seconds. | Evaluator also holds the existing `worker.lock` lease through inherited FD; startup refuses overlap without killing saved/discovered PIDs. GREEN. |
| R4 — high | Protocol-2 Worker inherited cleanup that could stop at leader exit, never kill a TERM-ignoring child, and reap group identity through ordinary/Goal polling. | Initial RED: delayed child effect marker existed after cancellation. Additional Goal-query RED reproduced the leak after native-query leader exit. | Protocol-2 polling uses `waitid(WNOWAIT)` until owned group cleanup; shared polling has a default-preserving hook. Worker/evaluator use TERM → KILL → reap, including normal/unexpected leader exit. GREEN. |
| R5 — medium | Grant deduplication bound only request ID. Different retained requests from one budget generation could both authorize main extension after generation changed. | RED: stale distinct request was accepted; original expected rejection did not occur. | Validate existing `main_grant_count` at ingress and again at locked grant application. Stale authentic ingress is processed/rejected without new authority or terminal halt; two pending same-generation grants roll back rather than double-spend. A temporary hard-error ingress fix was itself rejected by a new negative test before the nonterminal disposition. GREEN. |
| R6 — medium | Goal `get_entries` waits bypassed `ActionBridge.next()`, and therefore controls. | RED: cancel during native query produced attention/exit 1 rather than cancellation/exit 2. | Shared no-op-by-default control hook also runs in Goal query waits; Protocol 2 supplies its existing control checks. Cancellation settles below the asserted 1.5-second bound; legacy behavior unchanged. GREEN. |
| R7 — high at integrity boundary | Callback request hash was compared with the current file, but Core did not compare that file with its original in-memory request. Reviewer could sign a rewritten failing report while Core applied the original passing observation. | RED: altered request was accepted; expected integrity refusal was not raised. | Each guarded request check compares the on-disk request with the Core-owned/read request object, in addition to all prior state/eval/checkpoint/evidence/hash checks. No mismatched observation can apply. GREEN. This is integrity hardening, not a same-UID sandbox claim. |

Private logs, not committed release artifacts:

- `/tmp/ppp-regression-red.log`: **5 methods, 6 assertion failures** for R1–R4 before implementation.
- `/tmp/ppp-regression-grant-red.log`: **1 method, 1 failure** for R5.
- `/tmp/ppp-regression-stale-ingress-red.log`: **1 method, 1 error** demonstrating that stale authentic input must not halt the running task.
- `/tmp/ppp-regression-goal-red.log`: **2 methods, 2 failures** for R6 and R4's Goal-query path.
- `/tmp/ppp-regression-request-red.log`: **1 method, 1 failure** for R7.
- `/tmp/ppp-regression-correction-recovery-red.log`: **1 method, 1 failure** for R2's corrective-review restoration path.
- `/tmp/ppp-regression-final-gate.log`: fresh full GREEN gate, including all 25 new fault methods.

These logs are ephemeral diagnostics; the durable deliverables are the committed-source-compatible tests, observed results recorded here, and the exact code diff. No old report's test count substitutes for the new assertions.

## Invariant → tests → results matrix

Prefixes: **P** = `scripts/test_action_protocol.py`; **B** = `scripts/test_action_bridge.py`; **F** = new `scripts/test_action_faults.py`; **L** = `scripts/test_bridge.py`; **R** = `scripts/test_pi_receiver.mjs`; **I** = `scripts/test_install.py`. Names below are exact test methods. Every referenced test was rerun in the final gate; installer is a separate CLI gate. Existing tests were sufficient unless **new** is stated. All rows **PASS** within the stated local boundary.

### Worker / progress

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Crash before durable reservation: no invented consumption or reset | **new F** `test_crash_before_after_durable_cycle_reservation`, before-write branch | PASS: zero before recovery, two genuine final cycles |
| Crash after durable reservation: spent cycle and owner survive, no invisible retry | Same **new F**, after-write branch | PASS: interrupted row receives `none`, action stalls; no acceptance |
| Interrupted Worker still requires an independent assessment after clearing active | P `test_interrupted_cycle_requires_assessment_even_after_active_is_cleared`; **new F** reservation/effect crashes | PASS |
| Missing assessment cannot admit another Worker | P `test_completed_cycle_cannot_repeat_pending_null_in_unlimited_closure`; B `test_missing_selected_cycle_assessment_halts_before_a_second_worker` (both modes) | PASS |
| Duplicate assessment cannot mutate persisted state twice | P `test_assessment_survives_durable_restore_and_cannot_be_assigned_twice`; **new F** `test_missing_duplicate_stale_contradictory_assessments_roll_back` | PASS: exact snapshot rollback |
| Stale assessment cannot bind another state/cycle | P `test_stale_eval_cycle_sequence_and_state_hash_are_refused`; same **new F** rollback matrix | PASS |
| Contradictory assessment cannot mark informative/none progress as action PASS | Same **new F** rollback matrix; P `test_selected_verified_status_also_requires_attempt_disposition` | PASS |
| Informative failure → rejected observation → fresh verification → material replan | **new F** `test_informative_failure_correction_then_material_replan` | PASS: 3 Workers, 5 reviews; dispositions informative/verified/verified, no correction Worker |
| Unlimited closure cannot skip progress or renew equivalent experiments | P `test_completed_cycle_cannot_repeat_pending_null_in_unlimited_closure`, `test_informative_failure_alone_stalls_and_peer_null_cannot_revive_it`, `test_equivalent_experiment_cannot_evade_loop_detection` | PASS |
| Unlimited closure remains numerically unlimited for actual progress | P `test_unlimited_closure_allows_verified_progress_without_numeric_cap` | PASS: eight productive sample cycles, then duplicate fingerprint stalls; eight is not a cap |

### Evaluator / Reviewer

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Malformed evaluator output is technical verification failure, not success | B `test_transient_or_repeated_malformed_evaluator_observation` | PASS: transient recovers; repeated blocks worker-free |
| Unsupported semantic observation may be corrected without applying it | B `test_observation_correction_rechecks_without_repeating_worker`; **new F** informative replan journey | PASS |
| Repeated correction without information cannot renew allowance | B `test_repeated_or_contract_correction_blocks_nonterminal_without_work` | PASS: persisted fingerprint/retries; plain resume spends nothing |
| Correction and assessment commits survive crash exactly once | **new F** `test_crash_after_correction_or_assessment_preserves_exactly_once_cycle` | PASS: same run/grants, two Workers, one assessment per selected cycle |
| Crash during corrective review cannot spend another verification after restoration | **new F** `test_crash_during_corrective_review_does_not_renew_retry_allowance` | PASS: blocked at review 3, pending F1 obligation retained |
| Reviewer crash/failed enqueue never becomes PASS | B `test_reviewer_unavailable_is_not_observation_or_safety_failure` | PASS |
| Reviewer timeout cannot trigger blind paid polling | B `test_reviewer_timeout_does_not_blindly_dispatch_again` | PASS: one dispatch |
| Ambiguous delivery remains blocked even with a valid callback file | **new F** `test_ambiguous_queue_ack_even_with_valid_response_never_accepts_or_retries` | PASS: one dispatch, zero Workers, resume blocked |
| Core crash after attempted delivery cannot silently resend | **new F** `test_crash_after_review_dispatch_never_blindly_redispatches` | PASS |
| Core crash after callback but before apply cannot infer acceptance | **new F** `test_crash_after_response_before_apply_requires_delivery_investigation` | PASS |
| Stale callback after new state revision is rejected | B `test_v2_review_state_and_evidence_hashes_and_duplicate_decisions` | PASS for endorse and correct |
| Duplicate callback / replay correction cannot bind a new review | Same B; **new F** `test_replayed_correction_cannot_apply_to_new_review` | PASS: no changed allowance/consumption |
| Reviewer PASS cannot override nonzero mandatory evaluator exit or fail/blocked/not_tested/unknown | **new F** `test_reviewer_endorse_cannot_override_failed_mandatory_check`; P `test_schema_boolean_and_failed_final_states_never_pass` | PASS |
| Request mutation cannot substitute a different observation under a valid callback hash | **new F** `test_modified_request_cannot_rebind_review_to_different_core_observation` | PASS |
| Evaluator timeout cannot dispatch or overlap another evaluation | B `test_evaluator_timeout_is_bounded_technical_failure_without_dispatch`; **new F** orphan lease test | PASS |

### Cancellation

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Cancel during Worker stops execution and retains uncertain operation | B `test_cancel_active_worker_stops_process_and_preserves_uncertain_effect` | PASS |
| Cancel during Goal native-state query is timely and not lost | **new F** `test_cancel_during_goal_state_query_is_not_delayed_or_lost` | PASS: <1.5 seconds locally |
| Cancel during evaluator cleans only owned group; no review | B `test_cancel_during_eval_kills_owned_descendants_without_review` | PASS: owned TERM-ignoring descendant stops; unrelated session survives |
| Cancel immediately before dispatch prevents transport call | B `test_cancel_at_eval_completion_prevents_dispatch`; **new F** `test_cancel_immediately_before_dispatch_transaction` | PASS |
| Cancel after dispatch/before response refuses late callback | B `test_cancel_during_review_rejects_late_callback`, `test_cancel_while_waiting_pi_review_rejects_callback_after_exit` | PASS for Codex-like and Pi waits |
| Cancel between response receipt and application wins | B `test_synchronous_review_callback_cannot_apply_after_cancel`; **new F** `test_cancel_halt_receipts_at_locked_apply_boundary_win` | PASS for endorse and correct |
| Cancel at callback recording cannot leave a usable review file | **new F** `test_cancel_at_locked_callback_recording_boundary` | PASS |
| Simultaneous cancel/halt/finish respects halt priority, commits controls | P `test_global_halt_precedes_cancellation_regardless_of_ingress_order`; **new F** `test_cancel_halt_finish_race_at_transition_transaction` | PASS: no finish event |
| Owned Worker children cannot survive cancellation or unexpected leader exit | **new F** `test_cancel_worker_cleans_term_ignoring_child_even_after_leader_exit`, `test_unexpected_worker_exit_retains_group_identity_for_child_cleanup`, `test_goal_query_exit_retains_group_identity_for_child_cleanup` | PASS: no delayed effect in all three paths |
| Pending cancel forbids operation reservation before next Worker poll | **new F** `test_pending_cancel_prevents_operation_reservation_before_worker_poll` | PASS: no journal start, no effect |

### Recovery / operations

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Crash after operation reservation/before effect must independently establish no effect | **new F** `test_crash_before_after_synthetic_effect_reconciles_without_replay`, pre-effect branch | PASS: not_performed, one reservation, original owner/cycle retained |
| Crash after effect/before reconciliation cannot replay effect | Same **new F**, effect branch; B `test_orphan_worker_lock_and_uncertain_effect_reconciliation` | PASS: succeeded retained, no second effect |
| uncertain → not_performed needs evidence, then may authorize a fresh reservation | P `test_uncertain_no_effect_requires_independent_evidence`, `test_uncertain_not_performed_preserves_provenance_and_allows_safe_reservation` | PASS: unsupported claim rolls back; safe prior chain retained |
| succeeded/failed cannot be downgraded or repeated | P `test_confirmed_outcomes_cannot_change_or_unlock_replay`, `test_outcome_transition_matrix` | PASS: all 20 outcome combinations exercised |
| Contradictory reconciliation after restoration halts without erasing journal | **new F** effect-crash matrix, contradictory second-resume branch; B `test_contradictory_operation_evidence_halts_durably_without_replay` | PASS: established journal unchanged, one conflict, no replay |
| Repeated resume/duplicate controller/worker cannot overlap | B `test_explicit_extension_same_identity_and_duplicate_controller_refused`, `test_orphan_worker_lock_and_uncertain_effect_reconciliation`; **new F** wait recovery | PASS: wake is no-op under owner; resume refuses duplicates/terminal |
| Orphan evaluator also excludes replacement execution | **new F** `test_orphan_evaluator_lease_refuses_duplicate_evaluation` | PASS: sequence stays 1, no Worker |
| Run/cycles/grants/blockers/evidence survive restoration | **new F** `test_wait_recovery_duplicate_receipt_preserves_blocker_ledger_and_evidence`, correction/assessment and effect-crash matrices | PASS: preserved identities/checksums/content-addressed bytes; no backfill |

### Human / budget

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Duplicate receipt ID cannot repeat resolution or spend cycles | **new F** `test_wait_recovery_duplicate_receipt_preserves_blocker_ledger_and_evidence`; P `test_grouped_blocker_and_distinct_budget_request` | PASS: duplicate physical receipt ingested once |
| Duplicate grant for same request cannot double-spend | P `test_duplicate_budget_authorization_and_later_extension_requests`; R native duplicate grant regressions | PASS |
| Different stale request cannot reuse an old budget generation | **new F** `test_stale_different_request_cannot_reuse_budget_generation`, `test_two_pending_requests_same_budget_generation_cannot_double_grant` | PASS: benign stale ingress rejected; invalid double application rolls back |
| Partial/invalid response resolves only evidenced blockers | P `test_partial_invalid_resolution_and_closure_after_exhaustion`; B `test_wait_invalid_input_then_closure_automatic_without_main_extension` | PASS |
| Closure after main exhaustion requires no additional main grant | Same B; **new F** restored wait/duplicate receipt journey | PASS: ledger main → closure, original grants retained |
| Unrelated main work cannot be relabelled closure | P `test_closure_unlimited_but_causally_bounded`, `test_dynamic_required_repairs_need_causal_evidence_unrelated_stays_main`, `test_causal_reparenting_cannot_form_cycle` | PASS |
| Human response after cancel/halt cannot resume | P `test_cancellation_halt_and_stop_precede_late_resolution`; B `test_durable_wait_recovery_and_cancellation_no_late_restart`; R terminal input regressions | PASS |
| Technical restoration cannot manufacture approval; existing applicable approval survives | P `test_technical_restoration_cannot_manufacture_approval`, `test_applicable_real_approval_is_retained_not_requested_again` | PASS |

### Compatibility

| Scenario / invariant | Test evidence | Result |
| --- | --- | --- |
| Protocol 1 retains original completion/decision/eval/Goal/Ralph behavior | Entire L suite, including `test_goal_and_ralph_revise_then_complete`, `test_invalid_or_stale_decisions_fail_closed`; B `test_version_dispatch_preserves_frozen_legacy_and_refuses_migration` | PASS: 15 legacy tests; default hooks no-op/original poll |
| Protocol 2/schema 1 advertises review extension explicitly; old endorse still valid | B `test_correction_extension_requires_version_evidence_and_explicit_advertisement`, `test_pi_transport_versioned_review_and_passive_final_notice`, old-request fixture in B review/hash test | PASS: no evaluator/config/checkpoint schema change |
| Historical missing assessments are not automatically backfilled | P `test_old_multiple_unassessed_cycles_fail_closed_without_backfill`, `test_assessment_survives_durable_restore_and_cannot_be_assigned_twice` | PASS: one current obligation may be freshly assessed; multiple fail closed |
| CLI/session/receiver envelopes remain compatible | B version/transport/console tests; full R suite | PASS; no receiver source or command enum change in this audit |
| Installer ships check tooling/new suite without private artifacts | I; new suite added to REQUIRED | PASS: source allowlist, modes and privacy exclusions |
| Documentation describes implemented source, not autonomous/live acceptance | Changed link/anchor checks and exact diff inspection | PASS: F5 stale status corrected; historical evidence retained |

## Fresh final verification

Existing dependencies only; no network dependency resolution. Host: Darwin, Python `3.15.0a1`, Node `v26.6.0`. `scripts/check.sh` now includes the new fault suite. Documentation validation resolved all changed local links/anchors and 73 referenced test-method names.

| Command | Exact observed result |
| --- | --- |
| `UV_OFFLINE=1 npm run check` | Exit 0: ESLint, TypeScript, locked Ruff, all four Python unit suites and receiver |
| `python3 -B scripts/test_bridge.py` (within gate) | **15 passed** |
| `python3 -B scripts/test_action_protocol.py` (within gate) | **56 passed** |
| `python3 -B scripts/test_action_bridge.py` (within gate) | **33 passed** |
| `python3 -B scripts/test_action_faults.py` (within gate) | **25 passed**, including subtest matrices |
| `node scripts/test_pi_receiver.mjs` (within gate) | **PASS**, no numeric test count emitted |
| `python3 -B scripts/test_install.py --fixture-root <new temporary directory>/fixture` | **PASS**; temporary synthetic installation only |
| `.venv/bin/ruff check .` | **PASS** |
| `git diff --check` | **PASS** |
| Changed Markdown links/anchors and matrix test-method references | **PASS** |

Total: **129 Python unittest executions**, plus receiver and installer gates. Counts include inherited existing tests and subtests are not counted as extra methods; count alone is not coverage or acceptance.

## Compatibility and residual risks

No protocol/schema migration, frozen TASK/evaluator/config edit, automatic historical assessment backfill, change to main/closure authority, or retry-budget reset. Existing `main_grant_count` and controller-owned history support the new recovery/grant checks; stale-human rejection metadata is additive. CLI, receiver session entries and installer allowlist semantics remain unchanged. Older snapshots with missing generation data fail closed for new budget authority instead of inventing it. Active new-Core correction should not be downgraded to an older Core.

A crash with an unresolved queued review is now deliberately stricter: plain resume blocks instead of resending, even if a callback file exists. There is still no general delivery-investigation/unblock/amend API; do not clear metadata manually. A committed correction whose fresh review has not been attempted remains recoverable; committed assessments never repeat.

Remaining unverified/out-of-scope:

- Real Goal/Ralph/model/provider/transport reliability, evaluator/reviewer semantic quality, visual correctness and real provider truth. Reviewer endorsement cannot replace required deterministic checks, but Core cannot derive real-world truth from an evidence filename.
- Only this local POSIX host/toolchain was exercised, not a cross-platform/Python-version CI matrix or physical power-loss filesystem test.
- Cancellation linearizes when authentic receipts are consumed at guarded boundaries; writes after a boundary's control snapshot belong to the next boundary. Remote enqueue is not atomic with local state. Already-started reviewer work is not recalled/refunded, and the inherited Codex queue call can block up to its existing finite timeout.
- Group cleanup/identity protection assumes cooperative descendants stay in the owned session/group and do not discard/escape the relevant lease or change privilege. A Core crash is not automatic orphan cleanup; a live inherited lease refuses overlap. Orphan descendants after both Core and lease-holder loss, detached processes, host reboot, malicious same-UID modifications and external-resource isolation are not guaranteed. Quiescence and no-effect truth must be independently established before replay; absence of a local marker alone is not a general provider guarantee.
- Worktree/source drift outside retained evidence requires task-specific independent verification. No new external-source pinning/worktree manager, process registry, scheduler or permanent supervisor was introduced.
- Installed runtime was not synchronized. A future authorized E2E must identify and pin the exact candidate source/runtime and safe task limits; passing these tests is not permission to use an older installed copy.

These limits prohibit a production/autonomous-baseline verdict, but do not block a separately authorized bounded integration experiment with local outputs, available review transport, controlled processes and no real external effects.

## Changed files and final repository state

- `scripts/action_bridge.py`: locked control boundaries, owned group supervision/lease, delivery-aware restoration and original-request binding.
- `scripts/action_protocol.py`: budget-generation validation and nonterminal stale-human disposition.
- `scripts/bridge.py`: shared control/result hooks; legacy defaults retained.
- `scripts/test_action_faults.py`: 25 new deterministic negative/recovery methods.
- `scripts/check.sh`: runs the fault suite.
- `scripts/test_install.py`: requires the newly referenced suite in installer output.
- `docs/action-scoped-protocol.md`: clarified locking, leases, recovery, request integrity and budget generations.
- `docs/action-scoped-execution.md`: scoped implementation status correction (historical F5), no architecture rewrite.
- `docs/action-scoped-independent-audit.md`, `docs/README.md`: links to this evidence without replacing historical verdicts.
- `docs/protocol-2-regression-audit.md`: this record.

Final `git status --short`:

```text
 M docs/README.md
 M docs/action-scoped-execution.md
 M docs/action-scoped-independent-audit.md
 M docs/action-scoped-protocol.md
 M scripts/action_bridge.py
 M scripts/action_protocol.py
 M scripts/bridge.py
 M scripts/check.sh
 M scripts/test_install.py
?? docs/protocol-2-regression-audit.md
?? scripts/test_action_faults.py
```

HEAD remains `1b618b9c50bff4c98460cdfc1cbc659db97bdbb0`; no staging, commit, merge, runtime sync or live launch by this audit.

KB read: `02_PROJECTS/Pi_Ping_Pong/README.md`, `_SYSTEM/Knowledge_Read_Rules.md`, `_SYSTEM/Source_Of_Truth.md`, `07_PROMPTS_AGENTS/Global_Agent_Instructions.md`. Project Architecture/Tech_Decisions/Next_Actions files are absent. Older KB overview does not supersede current task/repository implementation evidence; KB not modified because writes outside this worktree are out of scope.

**Stop here.** Real E2E remains a separately authorized next task, not an automatic continuation of READY.
