# Action-scoped implementation plan

> Evaluator-era design/history: current execution is Worker (ordinary tests) → independent Reviewer (remaining judgments) → Core. Separate evaluator/preflight/repair and old-run resume were removed. Current [protocol](action-scoped-protocol.md) and [migration](evaluator-preparation.md) supersede lifecycle/compatibility instructions below; historical results are not live verification of the new cycle.

Source of truth: [agreed specification](action-scoped-execution.md). This plan is implementation authorization from the current task, not authorization to launch models or mutate external targets.

## Baseline and reusable mechanisms

Inspected `scripts/bridge.py`, `scripts/test_bridge.py`, receiver lifecycle/preparation/status/delivery code, installer/check scripts, SKILL and reviewed-run contract. Legacy has one synchronous cycle loop; run-wide `needs_human`; fresh evaluator subprocess; checkpoint/evidence hashes; independent reviewer; Goal accepted-wait boundary and Ralph iteration boundary; OS bridge lock; single-use launch; atomic JSON status and durable queue attempt receipts. Reuse RPC transport, native boundaries, evaluator invocation pattern, hash checks, queue/receiver identities and receipts. Do not reuse global repeat-failure termination, human-resolution flag, review/wall timeout, or legacy cycle loop for protocol 2.

No general workflow engine: controller selects one eligible action per worker cycle, with dependency validation at review boundaries. Actions are bookkeeping and authorization boundaries, not an arbitrary scheduler.

## Versions and compatibility boundary

- Missing `protocol_version` or explicit `1`: frozen legacy adapter; unchanged task, evaluator, approvals, counters, decisions and deadlines. Unknown versions rejected.
- Explicit `protocol_version: 2`, `schema_version: 1`: action-scoped contract. State, checkpoint, evaluator report, review, human ingress and operation journal carry these identities. Architectural discussion labels are not version identifiers.
- No in-place migration. A launched legacy run cannot resume as protocol 2. Config/task/evaluator fingerprints are pinned on initialization; any mutation halts the new run rather than silently changing its contract.
- Protocol 2 has explicit authorized initial actions, acceptance criteria, execution target identity and closure policy. Main grants are additive; closure defaults to no numeric cap. Worker session IDs are separate from logical run ID.

## Bounded phases and acceptance criteria

### P1 — Durable schemas and authority (spec §§2–4, 8–10, 14)

Implement version dispatch, locked/fsynced transactional snapshot with embedded history, stable action/blocker registries, explicit initial grants/consumption, authenticated-ingress references, closure provenance. Reject malformed identities, duplicate grants, unknown dependencies, cyclic action dependencies and unsupported versions. Preserve legacy state untouched.

Regression gate: schema/identity errors; blocker dedup and retention; atomic rollback; cumulative budget and duplicate authorization; closure default unlimited, missing/invalid causal chain remains main. Run new focused tests plus existing bridge tests.

### P2 — Verified controller transitions (spec §§3, 5–12, 16)

Implement independent evaluator/reviewer judgments, per-action progress/experiments/stall, grouped escalation, partial/invalid resolutions, approval applicability, main/closure selection, halt/cancel/stop/finish precedence, durable concrete wakes and reminder dedup. No worker claim, report validity or exit 0 establishes acceptance.

Regression gate: missing Resend key plus productive footer; multiple blockers; partial/invalid input; technical restoration cannot confer approval; closure-only continuation after exhaustion; unrelated analytics stays main; informative failure versus equivalent retry; action-local stall; grouped budget/blocker questions; finish requires every independent criterion. Waiting/reminders spend no cycles.

### P3 — Shared bridge and receiver integration (spec §§6–7, 11, 13–14)

Route protocol 2 through one shared Goal/Ralph adapter; preserve legacy path. Fresh task-specific evaluator reports and hash-bound reviewer requests drive controller. Human responses/grants/cancellation enter via session-bound explicit receiver commands or confirmed interactive console input (Codex default), not worker flags. Pre-arranged resource publishers can wake independent observation without manufacturing human authority. Responses are queued at safe boundaries; validate before resuming. Wait without worker; local service handles inbox/reminders, no model polling. Initial preparation explicitly declares version and contract requirements. Receiver preserves old commands/session entries/messages.

Regression gate: fake executable/RPC end-to-end in both modes and Pi transport; rejected/mutated reviews; duplicate dispatch; human ingress session binding; notice delivery without model turn; existing receiver and installer suites. No actual installation or paid execution.

### P4 — Recovery, uncertainty and complete regression (spec §§11–17)

Restore same run under exclusive ownership; pin contract, reconcile environment/evidence/approval applicability with fresh independent evidence, preserve session history and cumulative counters. Journal external operations before effects; interrupted operations become uncertain and cannot be replayed until outcome is independently reconciled. Explicit cancellation and halt prohibit automatic restart; stopped runs stay stopped. Persist all final evidence/limitations.

Regression gate: crash windows, unknown external outcome, outcome reconciliation, concurrent controller/worker refusal, stale resolution/review, lost ownership, restoration context, reminder re-entry, global halt precedence, full bridge/receiver/installer/check suites. Inspect exact diff and status.

## Verification records and evidence labels

Per-phase records and exact commands: [verification report](action-scoped-verification.md). Versioned wire/state/CLI design: [protocol 2](action-scoped-protocol.md).

- **Implemented** means source exists.
- **Tested** means named local automated checks passed.
- **Live-verified** requires relevant real model/runtime/external conditions; none authorized here.
- **Planned / unverified** includes missing implementation and insufficient operational evidence, stated separately.

Final source phase status: **P1–P4 implemented and locally tested**. Final gate: 15 legacy bridge + 38 controller + 18 fake-process integration tests, extended receiver suite, ESLint, TypeScript, Ruff and synthetic installer checks pass. See the verification record for intermediate failures/fixes and exact commands. **No live verification** and **no runtime installation** performed; never infer live reliability from fixtures.

## Safety boundaries

Local cooperative host, not a sandbox against same-UID malicious processes. Real authority originates in initial task or authentic human ingress; a worker/reviewer string creates no grant. Semantic scope, independence, provenance, freshness and resolution judgments require fresh independent verification and review. Secret values are never valid ingress/evidence; request secure configuration only. Global unsafe target/authorization/integrity findings halt immediately. Existing unrelated work remains untouched. No installs, live model runs, commits, deploys, KB writes or external mutations.
