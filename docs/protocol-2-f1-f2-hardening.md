# Protocol 2: F1/F2 hardening evidence

Scope: correctness fixes and synthetic regression protection only. Baseline HEAD: `6f3adc224495c083207f684ebe56e86783066007`; worktree was clean at task start. No F3/F4 implementation, new orchestration loop, headless reviewer, Observer, cross-chat, scheduler, runtime installation, commit, merge, paid model run, or real external effect.

Requirements: [independent audit](action-scoped-independent-audit.md), [agreed architecture](action-scoped-execution.md), [protocol](action-scoped-protocol.md), [integration plan](autonomous-run-integration-plan.md).

## Root causes

- **F1:** progress checks ran only when the evaluator supplied an optional `attempt`. No durable association connected a consumed/completed/interrupted cycle with its selected action's independent disposition. `pending/eligible` plus null attempt/experiment could therefore run again. An informative failure without a next experiment also remained runnable.
- **F2:** reconciliation validated the outcome enum but not the transition from the previous journal outcome. Overwriting `succeeded`/`failed` with `not_performed` satisfied the existing replay admission predicate.

## Test-first evidence

Before changes, the existing suites passed: 38 protocol tests, 18 bridge-v2 tests, 15 legacy tests.

First added 14 protocol regression test methods, then ran:

```sh
python3 -B -m unittest discover -s scripts -p test_action_protocol.py
```

Observed **52 tests, exit 1: 19 assertion failures and 1 error** (subtests account for multiple failures). Failures included:

- `test_completed_cycle_cannot_repeat_pending_null_in_unlimited_closure`: missing selected assessment was accepted.
- `test_interrupted_cycle_requires_assessment_even_after_active_is_cleared`: interrupted cycle lost its assessment obligation.
- `test_selected_verified_status_also_requires_attempt_disposition`: marking selected work verified bypassed assessment.
- `test_informative_failure_alone_stalls_and_peer_null_cannot_revive_it`: informative failure stayed pending.
- `test_informative_failure_can_run_materially_different_experiment_once`: informative failure without another experiment stayed runnable.
- `test_external_wake_is_observation_not_a_worker_attempt_or_retry_grant`: an observation could revive a stalled attempt without a justified new experiment.
- `test_initial_or_peer_attempt_is_not_a_real_selected_cycle`: fictitious initial/peer attempts were accepted.
- `test_initial_and_peer_observation_do_not_invent_attempts`: required durable cycle-assessment metadata was absent (`KeyError: assessment`).
- `test_unlimited_closure_allows_verified_progress_without_numeric_cap`: productive cycles had no durable dispositions.
- `test_confirmed_outcomes_cannot_change_or_unlock_replay`: six contradictory transitions did not halt.
- `test_confirmed_no_effect_cannot_change_without_a_new_reservation`: outcome could change without an execution reservation.
- `test_duplicate_operation_observations_are_not_order_dependent`: contradictory duplicate IDs were accepted.
- Outcome history/provenance tests found no reconciliation history events.

Subsequently added four protocol tests for durable restoration/exactly-once disposition, historical missing assessments, the complete outcome matrix, and evidence-required no-effect recovery; plus two real-bridge synthetic regressions. Ran the latter against an isolated archive of baseline HEAD with the updated fixture tests: **2 test methods, 3 assertion failures, exit 1**. Both Goal and Ralph incorrectly finished after omitted selected assessments (exit 0 instead of fail-closed exit 1); contradictory completed-operation evidence incorrectly finished (exit 0 instead of halt exit 2). No working source or installed runtime was replaced for this baseline comparison.

## Changes

### Cycle-bound assessment

- `consumption` is the durable assessment obligation, surviving `active` clearing and interruption. Each selected cycle gets exactly one independent attempt disposition and review reference in its consumption row, plus a `cycle.assessed` event.
- Reject missing selected assessments before applying report mutations. Reject an attempt on initial/peer/external-wake observations without an outstanding selected cycle. Experiment alone cannot substitute for a missing cycle disposition.
- Block new workers and final acceptance while any reserved cycle remains unassessed.
- Retain informative failures, but mark unfinished actions stalled without verified nonduplicate progress or a justified next experiment. Null peer/wake observations cannot erase this restriction. New independently justified experiments can reactivate work without inventing attempts.
- Retain unlimited closure. Regression executes eight productive closure cycles without consuming main budget, then confirms an equivalent fingerprint stalls the action. Eight is a finite test sample, not an implementation cap.

### Outcome transition guards

- Explicit transition matrix allows `started/uncertain` to reconcile to independently established outcomes. `succeeded`, `failed`, and `not_performed` permit only same-outcome revalidation until a legitimate new reservation from `not_performed`.
- Contradiction preserves the journal entry, records both observations in `operation.conflict`, clears acceptance to unknown, and halts for investigation before applying the report's grants/resolutions/actions.
- Duplicate operation IDs are rejected before mutation; missing independent evidence cannot establish no effect.
- Append outcome/review/evidence history on reconciliation and interruption. New safe reservations retain prior journal entries, identities, plans, owners and originating cycles.

Existing protocol fixtures now assess actual synthetic cycles instead of directly clearing `active` or reporting null for every selected action. The bridge fixture measures local output/effect markers for its assessments; all provider/worker/reviewer processes remain fake. The action-local-stall test now explicitly budgets three main cycles because its two attempts are genuinely consumed before checking independent continuation; production budgets are unchanged.

## Contract and compatibility

No evaluator fields/enums, CLI, config, receiver entries, protocol number or schema number changed. The protocol documents the stricter conditional validation of existing fields and additive controller-owned consumption metadata. This is enforcement of the agreed schema-1 progress/replay invariants, not the future semantic-responsibility schema redesign.

No existing runs or governing files were modified. Missing historical metadata is not guessed: one unassessed current cycle can receive fresh review; multiple historical unassessed cycles fail closed for investigation. A frozen evaluator omitting required assessments is rejected, not silently repaired. Protocol 1 implementation and tests are unchanged; dispatch and legacy semantics remain covered.

## Final verification

All commands use existing dependencies; `UV_OFFLINE=1` prevents network dependency resolution during the development gate.

| Command | Result |
| --- | --- |
| `python3 -B scripts/test_action_protocol.py` | 56 passed |
| `python3 -B scripts/test_action_bridge.py` | 20 passed |
| `python3 -B scripts/test_bridge.py` | 15 passed |
| `node scripts/test_pi_receiver.mjs` | PASS |
| `UV_OFFLINE=1 npm run check` | PASS: ESLint, TypeScript, locked Ruff, all three Python suites and receiver suite |
| `python3 -B scripts/test_install.py --fixture-root <new temporary directory>/fixture` | PASS: synthetic allowlist, required tooling, executable modes, privacy exclusions |
| `git diff --check` | PASS |

Total: **91 Python tests**; the receiver suite reports PASS without a numeric count. Exact changed source/test/documentation diffs and final Git status were inspected. No live acceptance is claimed.

## Remaining limits and stop boundary

Historical stage boundary below is retained. Subsequently authorized [F3/F4 hardening](protocol-2-f3-f4-hardening.md) records its own changes and local evidence; it does not retroactively establish live acceptance.

F1/F2 are covered locally; F3/F4 remain separate open work. Missing/incorrect mandatory observations still fail closed through the current halt path, not a newly implemented correction loop. The historical audit's broader merge/autonomous-baseline warning remains applicable.

Independent evaluator/reviewer quality still determines semantic progress, materially different experiments, and provider truth. The cooperative local-host journal is not an OS sandbox or protection against workers bypassing it. Synthetic tests establish the guarded transitions, not real Goal/Ralph/model reliability.

KB consulted: `02_PROJECTS/Pi_Ping_Pong/README.md`, `_SYSTEM/Knowledge_Read_Rules.md`, `_SYSTEM/Source_Of_Truth.md`. KB status is older than the current repository requirements; no KB writes were in scope. Installed runtime was deliberately not synchronized. Stop here; no F3/F4 or live E2E work is authorized by completing these gates.
