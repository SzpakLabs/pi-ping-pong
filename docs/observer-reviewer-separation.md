# Chat A UI and the Observer/Reviewer separation gap

> Evaluator-era design/history: current execution is Worker (ordinary tests) → independent Reviewer (remaining judgments) → Core. Separate evaluator/preflight/repair and old-run resume were removed. Current [protocol](action-scoped-protocol.md) and [migration](evaluator-preparation.md) supersede lifecycle/compatibility instructions below; historical results are not live verification of the new cycle.

**Status: corrected MVP boundary.** A separate Headless Reviewer is required for MVP; only cross-chat access and the extended UI-disconnect/catch-up target are Post-MVP / Deferred. Earlier wording incorrectly treated separate Reviewer execution as deferred. See [the headless adapter](headless-reviewer.md) for code/config boundaries and evidence; this note does not authorize a live run or migration.

## Final PPP MVP boundary

Execution autonomy does not require independence from the user session at this stage. Chat A remains an explicit infrastructure dependency and must be available during MVP E2E. Autonomous continuation after A closes is not claimed.

**Worker executes. Evaluator measures. Reviewer assesses. Core decides.** Goal/Ralph are executors. Chat A is human-operated: it sends confirmed commands to Core and receives Core reports. Reviewer executes in a separate Core-owned headless Pi session; it may use the same model ID as A, but never the same conversational session. Chat A gains no Core authority. Core alone owns orchestration, execution transitions, budgets and acceptance. Existing DAG, FSM, budgets, scoped blockers and operation journal remain the management logic; durable execution means persisted state and the supported reconciled recovery after failures, not an always-on or automatic-restart guarantee.

The principal MVP criterion is reproducible real Goal/Ralph E2E with independent acceptance, correct continuation, budget compliance and safe blocker handling while Chat A is available. PPP performs authorized work, repeats only justified attempts, continues independent eligible work around local blockers, and requests human input only when genuinely needed. No successful MVP E2E is claimed by this scope decision.

Required in MVP: separate Worker/Evaluator/Headless Reviewer execution coordinated by Core, with passive reports to the human-operated Chat A. Deferred from MVP: access/control from arbitrary other chats; Core lifecycle independence from A; Observer, durable outbox and missed-message catch-up; and close/reopen-A tests. The future acceptance scenario below is not an MVP gate. Do not expand architecture without demonstrated necessity. Existing restrictions on paid E2E remain in force until separate explicit authorization.

## Extended Post-MVP product behavior

Chat A remains the user's interface for starting a run, seeing status/reports, and providing confirmed human input. The automated execution and review plane must not depend on Chat A staying open or on its model taking Observer/Reviewer turns. A run should continue with the existing Core, Worker, fresh Evaluator, and a separate headless semantic Reviewer. Chat A can close and later reopen the same persisted session to read durable reports/catch-up and address actual human gates.

This requirement is **not** “send the run to any other chat B/C.” Cross-chat discovery, attaching another chat, and routing human commands from arbitrary sessions are separate deferred features. For the initial boundary, A remains the UI; the automated Observer/Reviewer work is moved out of its conversational model turn.

## Terminology to keep precise

The existing integration plan separates:

- **Headless Reviewer:** independent semantic reviewer. Checks task, evidence and evaluator results, then submits a bounded, hash/state-bound review result through Core's validated interface.
- **Observer:** read-side status/events/subscriptions, report presentation and durable delivery/catch-up; forwards authenticated user commands to Core. It does not decide acceptance, budgets, or run transitions.
- **Chat A UI:** launching/user-facing surface for status, reports and confirmed human input. Closing A must not stop the execution/review plane.

Do not merge Observer and Reviewer into a second controller or loop. Core remains the sole authority for execution, budgets, state transitions and acceptance.

## Original chat-transport baseline (historical gap)

For `review_transport=pi`, the receiver's `launchConfig` obtains the launching session ID, writes it into `config.pi_session_id`, records a `pi-reviewed-run` binding, and starts monitoring that session's `pi-inbox`. The bridge binds review messages to that ID; the receiver dispatches them into the same session with `pi.sendMessage(..., { deliverAs: 'followUp', triggerTurn: true })`. Therefore this compatible chat execution path uses the launching chat for Reviewer turns. New `review_execution=headless` runs use the separate adapter instead. It is not a separate headless review process, and closing that chat does not demonstrate autonomous review.

Relevant implementation/reference points:

- `extensions/pi-reviewed.ts` — `launchConfig`, receiver binding and Pi inbox delivery.
- `scripts/bridge.py` and `scripts/action_bridge.py` — review transport and Core review flow.
- `references/reviewed-runs.md`, section “Pi reviewer transport” — explicitly records that current Pi transport is bound to the launching chat and headless review remains future work.
- `docs/autonomous-run-integration-plan.md` — planning-only integration plan; its target separates Core/Worker/Evaluator/Headless Reviewer from the original chat UI. It places this after the protocol/runtime baseline. It also explicitly defers arbitrary cross-chat discovery.

A `review_transport=codex` config can target an explicit Codex thread, but that is a different configured transport; it does not mean the current Pi-launched path has an independent headless Reviewer. Do not describe Chat A as “only UI” while the Pi receiver still sends semantic review turns into A.

## Evidence and non-evidence

Manual run `test-e2e-basic-03` used the Pi transport bound to its launching chat. Its review decisions were made in that chat, so it did **not** test the UI/Observer/Reviewer separation target. Its evaluator false-negative/contract block is a separate evaluator-quality issue; do not treat that failure as proof of reviewer separation or combine the fixes without an explicit scope decision.

The current transport can review evidence and Core can validate the decision; that is not evidence that review continues after A is closed. Hiding a still-running UI tab also does not establish that A's process/session is absent.

## Historical implementation handoff (scope corrected above)

1. Inspect the target architecture, autonomous-run integration plan, operational review contract, and current receiver/bridge code before proposing changes. Treat this note as a gap report, not a ready-made implementation design.
2. Keep A as the user interface. Move semantic review execution into a separately owned headless Reviewer adapter with explicit model/provider, bounded operation, cancellation, evidence/state identity, and a narrow Core-validated submission path.
3. Keep Observer read-only for status/events/reports and authenticated-input forwarding. Do not move Core authority, create a second lifecycle loop, or let Observer make acceptance decisions.
4. Preserve existing transports/config/session-entry compatibility; do not silently migrate active runs. Do not require B/C routing, a global registry, multi-chat discovery, or a separate user-facing TUI for the first milestone.
5. Add deterministic regressions for reviewer independence, Core decision validation, reviewer unavailable/timeout behavior, no acceptance on bad/missing review, and durable report/catch-up when A is absent. Add a live close-A/reopen-the-same-A test only after the deterministic gates pass and the user separately authorizes a live run.
6. Report implemented versus planned behavior separately. A code path or unit fixture is not proof that A can close while independent review continues.

## Deferred close/reopen acceptance scenario

- Start a bounded authorized run from A; confirm the actual bound identities and durable state.
- Close A so its UI/model process is actually absent, not merely hidden.
- Demonstrate Worker → fresh Evaluator → separate Headless Reviewer → Core cycles proceed without A; reviewer failure or timeout never yields acceptance or fabricated human input.
- Keep Core as sole transition/acceptance authority; no duplicate worker or reviewer loop, unauthorized action, or replay.
- Reopen the same persisted A and receive verified status/reports from durable records. Confirmed human input, if needed, remains explicitly addressed and validated by Core.
- No B/C chat is needed for this milestone.

The original gap note performed no implementation or live run. Current implementation and verification are recorded separately in [Headless Reviewer](headless-reviewer.md); the close/reopen scenario remains unverified and outside MVP.
