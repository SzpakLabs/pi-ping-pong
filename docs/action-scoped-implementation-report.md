# Action-scoped execution — implementation report

> Evaluator-era design/history: current execution is Worker (ordinary tests) → independent Reviewer (remaining judgments) → Core. Separate evaluator/preflight/repair and old-run resume were removed. Current [protocol](action-scoped-protocol.md) and [migration](evaluator-preparation.md) supersede lifecycle/compatibility instructions below; historical results are not live verification of the new cycle.

Authoritative requirements: [agreed architecture](action-scoped-execution.md). Design and phase gates: [plan](action-scoped-implementation-plan.md). Wire/CLI contract: [protocol 2 / schema 1](action-scoped-protocol.md). Exact commands, failures investigated and final results: [verification record](action-scoped-verification.md).

## Delivered architecture

- `scripts/action_protocol.py`: executable schema validation, fsynced/sealed transactional registry/history, deterministic verified transitions, action/blocker/provenance/progress/authority accounting.
- `scripts/action_bridge.py`: controller service over the existing shared Goal/Ralph bridge, independent evaluator/reviewer boundaries, human/resource event ingress, worker-free waiting, reminders, ownership and reconciled restoration.
- `scripts/bridge.py`: explicit version adapter and v2 CLI; existing legacy cycle/review implementation remains in place. New sessions and durable queue behavior are conditional on protocol 2.
- `extensions/pi-reviewed.ts`: explicit native human confirmation, addressed private receipts, automatic race-safe wake, v2 status/blocker visibility and model-free passive notices; legacy aliases, session entries and old envelopes retained.
- Focused controller and subprocess regressions; receiver regressions extended; development gate and synthetic installer coverage include new modules.

No workflow engine, general DAG scheduler, vendor patch, global Goal/Ralph setting change, runtime install, live model run, commit, deployment or external target mutation.

## Requirement/invariant coverage

All rows describe source implementation; local test evidence is distinguished from operational proof.

| Agreed requirement | Implemented mechanism | Automated regression evidence |
| --- | --- | --- |
| Execution/blockers/acceptance separate (§2) | Independent state domains; worker checkpoint is a claim; controller alone chooses finish | `test_independent_acceptance_required_not_exit_or_worker_claim`, non-PASS criteria tests |
| Stable actions, dependencies, completed evidence (§3) | Immutable authorized contracts; fresh scope/independence checks; dependency validation, retained verification and immutable evidence archive | Schema/dependency/cycle tests; material dependency refusal; completed-evidence retention/corruption tests |
| Persistent deduplicated blockers (§4) | Stable B identities by semantic key, retained observations/resolutions, reopening without deletion | Rediscovery across cycles; multiple Resend/DNS blockers |
| Deferred/grouped and early escalation (§5) | Continue eligible independent work, grouped questions plus distinct grant request, concrete early deadline | Footer despite Resend; grouped blockers/budget; early-deadline test |
| Validated addressed human input (§6) | Native Pi or interactive console receipt, source/session binding, fresh independent resolution judgment, safe-boundary application | Partial/invalid resolutions; authentic approval retention; wrong session/RPC/pipe refusal |
| Independent roles/controller transitions (§7) | Worker absent during fresh eval/review; run/cycle/state/report/evidence/request hashes; structured endorsement not acceptance | Both runtimes; Pi/Codex transport; stale/corrupt hashes and report identity tests |
| Main versus causal closure (§8–9) | Initial closure authority, mandatory validated ancestry/evidence, main default for unsupported labels | Exhausted main then closure; unrelated work refusal; dynamic necessary repairs; cyclic ancestry refusal; new blocker grants nothing |
| Additive budgets in same run (§10) | Grant/consumption ledger, reserve before spawn, request/receipt replay protection, preserved counters | Same-run extension and later request identities; duplicate grant/controller refusal |
| Indefinite durable wait/reminders (§11) | Specific request/resource/one-shot recheck reference, no worker, fsynced local service state/receipts, cancellation suppression | Wait outlives active wall bound; no model/worker polling; passive reminders/reload; arranged recheck and resource event tests |
| Meaningful progress and local stall (§12) | Independently assessed attempts/fingerprints; justified materially different experiments; equivalent retries cannot count as progress | Informative failure versus futile retry; no-work stop; stalled action does not stop productive peers/concrete wake |
| Same-run sessions/reconciliation (§13) | Separate worker session UUIDs, exclusive controller + inherited worker lock, pinned governing files, fresh environment/approval/effect reconciliation, restored context | Multiple sessions/same run; durable wait recovery; orphan refusal; interrupted fake side effect investigated, not blindly replayed |
| Independent final acceptance (§14) | Every required criterion PASS, all required actions independently verified, no open blocker/uncertain operation, fresh valid review; failed eval cannot finish; delivery failure cannot erase acceptance | Both fake native routes reach independently reviewed finish; non-PASS/stale review refusal; final callback-failure/no-replay regression |
| Halt/stop/finish/cancel distinctions (§7, §10–11) | Terminal transitions retain distinct states; negative safety signals halt before further work; late input cannot restart | Unsafe eval before spawn/review; contract mutation halt; active-worker cancellation and uncertain journal retention |
| Versioned compatibility (§14) | Missing version/explicit 1 frozen legacy adapter; explicit 2/schema 1; no migration | Existing bridge/receiver suites plus explicit frozen-state/version-dispatch regression |

## Evidence labels

- **Implemented:** mechanisms and CLI/receiver changes above exist in this worktree.
- **Tested:** **71 Python tests** (15 legacy, 38 controller, 18 fake-process integration), receiver API/real-loader regressions, ESLint, TypeScript, Ruff and synthetic installation checks listed in the verification record. They exercise actual controller/bridge source without real providers.
- **Live-verified:** **none in this task**. No real Goal/Ralph campaign, real Resend/DNS credential probe, paid model review, host-reboot restoration, external side effect or visual TUI validation was authorized or performed.
- **Planned / unverified:** live pilots, real provider-specific reconciliation/evaluator quality, host supervision/notification availability and malicious-process isolation. These are not claimed as operational acceptance or production readiness.
- **Blocked implementation work:** none identified at the recorded source/regression gate. Deployment/install/live evidence remains outside this task's authorization, not silently completed.

## Compatibility assessment

Legacy TASK/evaluator/state/approval/budget semantics are not rewritten. Original `decide` decisions, passing-eval requirement for legacy continue/complete, finite legacy wall/human deadlines and duplicate-start refusal remain. Explicit legacy protocol selection is accepted; unknown versions fail closed. Protocol-2 commands cannot implicitly upgrade a legacy run. New native preparation explicitly declares version 2; existing drafts are not silently migrated. Existing receiver custom entries, aliases and legacy message delivery remain compatible. New human metadata uses a separate session entry type.

Protocol 2 intentionally has a different evaluator JSON contract and controller-owned decisions; this is an opt-in/new-contract boundary, not an in-place migration. Its governing files must be private within the run and outside worker outputs. Task-specific independent evaluators must implement the documented judgments against actual authorized source/runtime state. An illustrative/static always-PASS evaluator is not valid verification.

## Operational limitations and safety boundaries

1. Cooperative local-host system, not an OS sandbox or cryptographic proof of human identity. Same-UID malicious code can forge files or access terminals; independent review, protected run contracts and honest workers remain necessary. Integrity seals detect accidental corruption, not deliberate resealing.
2. Scope, independence, meaningful information, fingerprint equivalence, approval applicability and causal necessity are semantic judgments. The controller requires independently evidenced/reviewed judgments; it does not make them true by checking JSON. Provider-specific truth must be established by the task evaluator/reviewer, never inferred from report validity.
3. No real secret values or test recipients are supplied by this implementation. Credential validation must use authorized secure checks against the actual runtime; external effects need actual task authorization and real reconciliation evidence.
4. Timer/reminder delivery needs the host/controller running. After a crash, explicit resume or authentic human/resource wake restores it under reconciliation. No launch daemon or external push/email notification service is installed. Codex recurring reminders remain local to avoid paid polling; one logical escalation/final callback can use the existing queue.
5. An orphan holding the inherited worker lock prevents restoration. The controller does not kill a PID it cannot safely own, reset budgets, or assume an uncertain effect failed. Operator investigation may be required; no new run is silently created to bypass it.
6. Already-enqueued reviewer messages cannot safely be removed from unrelated Pi queues. New stale review/reminder dispatch is suppressed on terminal state, and controller checks refuse stale decisions/continuation regardless.
7. Runtime copies were deliberately **not installed**: current task prohibits installation changes. This worktree is the implementation source; operational use requires separately authorized installation and live verification.
8. KB project README/global agent instructions were read; project Architecture/Tech_Decisions/Next_Actions files were absent. No KB files changed: requested write scope is this repository.
