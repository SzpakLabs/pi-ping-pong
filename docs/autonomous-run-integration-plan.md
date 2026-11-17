# Autonomous runs: integration plan and decision reconciliation

Status: planning only. No implementation, dependency adoption, live run, installation, or migration is authorized by this document.

## Governing MVP scope decision

The [final PPP MVP boundary](observer-reviewer-separation.md#final-ppp-mvp-boundary) supersedes this plan's earlier milestone terminology. Reproducible real Goal/Ralph E2E with independent acceptance, correct continuation, budget compliance and safe blockers **while Chat A is available** is the principal MVP criterion. Worker executes; Evaluator measures; Reviewer assesses; Core decides. Chat A is human-operated and receives Core reports; the Reviewer runs in a separate Core-owned headless session with independent provider/model configuration.

A separate Headless Reviewer is **required for MVP**; see [adapter and evidence](headless-reviewer.md). Arbitrary other-chat access, Core lifecycle independence from A, Observer/durable outbox/catch-up and close/reopen-A tests remain **Post-MVP / Deferred**, not MVP readiness gates. Existing durable state and supported reconciled recovery remain in scope. Sections below describing the UI-only chat and the “first autonomous milestone” are future targets, not additional MVP requirements. Paid E2E still requires separate explicit authorization; this decision neither launches tests nor claims successful E2E. Do not broaden architecture without demonstrated necessity.

## Purpose and evidence

Reconcile the earlier headless-reviewer/Observer discussions with the agreed [action-scoped architecture](action-scoped-execution.md) and the current [independent audit](action-scoped-independent-audit.md). The supplied discussion is historical design context, not current source/API verification. In particular, pi-tick commands, versions, RPC behavior, timeout semantics, and process-tree guarantees have not been independently checked here. Do not adopt pi-tick or repeat its example CLI as an established integration.

## Target outcome

A user starts a run in chat A, closes that chat, and later reopens the same persisted chat A. The run has continued through independent worker/evaluator/headless-reviewer cycles. Reopened A can read verified results and catch-up reports, address specific blockers, and authorize main-budget extensions. Validated input resumes work without a second routine confirmation. Reports are durable; losing a report subscriber does not block execution. Required human input still blocks its dependent actions.

The first autonomous milestone separates the execution plane (Core, Worker, Evaluator, Headless Reviewer) from the original chat interface (launch, status, reports, confirmed human input). Closing A means its UI/reviewer process is actually absent, not merely a hidden tab. Restoring the original persisted chat must preserve or explicitly verify its identity without editing transcript files.

Protocol 2 alone does not currently deliver this outcome: its review transport still depends on a configured chat session. Durable state and explicit reconciled recovery exist. Cross-chat access, global registry/Observer, concurrent writable-run support, pi-tick, external notifications, and automatic host-reboot recovery are deferred, not prerequisites for the first milestone.

## Responsibility boundaries

- **Core/controller:** sole authority over execution, budgets, acceptance, operation records, and recovery transitions. Reuse the existing controller; do not build a second semantic loop.
- **Worker:** performs the selected authorized action; supplies untrusted claims and evidence.
- **Evaluator:** fresh actual checks against task/source/environment; does not manufacture semantic or human approval.
- **Reviewer:** independent semantic judgments and findings, through a narrow validated submission channel. Future headless review is an additional transport/runtime adapter, not a new authority.
- **Observer:** discovery/read API, event subscriptions, report presentation, delivery receipts/catch-up, and forwarding authenticated commands to Core. No budget or acceptance decisions, no direct worker control, no canonical state mutation.
- **Host supervision:** optional process availability/restart and timer delivery. It may be packaged near Observer but is logically separate; it requests reconciled recovery from Core, never blindly relaunches a run.
- **Scheduler (possibly pi-tick):** optional future trigger/runtime infrastructure. Not the task source of truth and not a substitute for headless review or Core recovery.

## Reconciled conflicts

| Earlier discussion | Governing interpretation / proposed resolution |
| --- | --- |
| Add a new autonomous supervisor loop | Existing `ActionBridge.run()` already implements the semantic loop. Add missing adapters and availability features around it. |
| A thin Observer is enough to close the launching chat | Incomplete. Headless reviewer transport is required before Observer can provide chat-independent execution. Prioritize it in the post-baseline design. |
| Reviewer returns `continue/revise/complete/wait_human` | Historical legacy language. Protocol 2 has controller-owned transitions and independently checked observations. Do not restore a second decision authority or silently change legacy semantics. |
| Missing input immediately stops the entire run | Superseded by scoped blockers, independent work, and deferred/grouped escalation. Global safety halt remains immediate. |
| Cycle/wall exhaustion terminates all work | Main pauses for an explicit additive grant. Pre-authorized causal closure has no numerical default cap. Human waiting is indefinite and worker-free. Active operations remain bounded. |
| Report delivery failure stops execution | Distinguish required verification from user reporting. Losing reviewer transport blocks acceptance/verification; losing a report subscriber does not. Both need durable, non-blind delivery handling. |
| Any new chat can approve a run | Target capability, not current behavior. Requires explicit attachment/authorization and request/blocker/state-bound human ingress. Read subscription alone must not grant write authority. |
| Headless RPC can issue the existing human command | Not acceptable. RPC/model calls must not manufacture human authority. Preserve confirmed interactive input or define another explicit authenticated human channel. |
| Recovery means a new Pi session | A replacement session is allowed only after ownership/effect reconciliation. Logical run identity and accumulated accounting persist. |
| `amend` can edit the task/evaluator in place | Not agreed for the current protocol. Governing files remain pinned. Contract revisions, approval invalidation, and linked forks need a separate future specification; additive grants are not general contract amendments. |
| pi-tick kill/timeout owns the complete run | Unverified and unsafe to assume for detached children. External runner exit must not mean accepted task completion; process supervision must respect durable wait and uncertainty. |
| Evaluator is the sole judge (illustration) | The illustration is conceptual. Evaluator checks and reviewer judgment feed the Core gate; neither alone owns acceptance. |

## Preserve the immediate five-step order

1. **Negative regressions for audit F1/F2, then minimal fixes.** Enforce cycle-bound progress assessment and valid operation-outcome transitions. Do not introduce arbitrary default closure caps.
2. **Resolve nonterminal review correction and cancellation boundaries (F3/F4).** Define who can correct an observation without mutating frozen evaluator/criteria or silently approving bad evidence. Distinguish reviewer unavailability, malformed observation, technical process failure, and a true security halt. Check cancellation before dispatch/application and supervise owned evaluator processes as specified.
3. **Existing suites plus targeted deterministic fault injection.** Include crash boundaries, stale decisions, grant duplication, ownership, retained evidence, human receipts, causal closure, and corrected observations. Test using local synthetic executables, not paid models or real external effects. Cross-chat/headless features are not silently included in this hardening slice.
4. **Separately authorized, bounded real Goal/Ralph E2E.** Exercise finish, independent footer work with deferred blocker, invalid/valid response, closure after main exhaustion, main extension, and recovery against local safe outputs. Explicitly declare the task-specific active limits and any test closure cap. Existing review transport may be used to establish protocol integration; that does not prove chat-independent operation.
5. **After acceptance of that baseline, design and implement Headless Reviewer plus the original chat as a UI-only interface.** Include run-local durable events, catch-up, worker-free waiting, and explicit reconciled recovery. Do not build a second loop or require cross-chat/global infrastructure. Then prove the same-chat autonomous journey below.

A baseline accepted after step 4 is a protocol/runtime baseline, not acceptance of the final autonomous-platform goal.

## Post-baseline implementation slices

### A. Headless independent reviewer

Add a Core-owned reviewer adapter with explicit provider/model, private context, source/evidence identity, independent findings, validated submissions, bounded execution, cancellation, and process reconciliation. No dependency on an open launching chat. Preserve existing Pi/Codex review transports for legacy/explicitly configured use.

Use deterministic checks + semantic review + a deterministic Core gate. Evaluator supplies actual test results, exit codes, hashes, HTTP observations, artifact presence, and other measured facts. Reviewer assesses requirement satisfaction, action independence, causal closure necessity, informative progress, and evidence sufficiency. Core validates authority, identities, budgets, dependencies, and transitions using both inputs.

Reviewer PASS cannot override a failed mandatory deterministic check. Valid reviewer JSON is not proof of semantic truth. Conflicting evidence leaves acceptance unconfirmed and enters the bounded observation-correction path specified during F3 hardening. Separate that path from worker task repair. Moving semantic judgments out of the current frozen evaluator contract requires an explicitly versioned schema change, not silently changing schema 1. Design this with the headless adapter after the baseline; F1–F4 fixes remain within the current contract.

Gate: chat A can close after start and a local task still completes real review cycles. Reviewer crash/timeout never becomes PASS or fabricated human input. A reviewer cannot edit graded source or governing acceptance inputs under the declared trust profile; do not claim enforced isolation from prompts alone.

### Deferred: cross-chat discovery and human commands

Use run-local durable records as the source of truth; global registry entries are authorized discovery pointers/read projections, not another mutable run state. Add explicit attach/discover and addressed human command routing from a new authorized session. Bind commands to run ID, current request/blocker identity, applicable state, and deduplication identity. Preserve old receipts/history without pretending the new chat is the original session.

Gate: chat B reads actual results and can resolve B1 without resolving B2; stale requests, forged/model input, duplicate grants, and unapproved attachments are refused. Authentication/attachment policy must be agreed before implementation.

### B. Original-chat reports and catch-up

Keep reports and confirmed human input bound to original chat A for the first milestone, independently of the headless reviewer identity. Provide run-local durable events and stable delivery cursors/receipts. While A is closed, retain reports without attempting to write its transcript or requiring a live model. On reopening A, restore status and deliver relevant catch-up without duplicate control actions. Reporting failure must not interrupt the execution plane.

Gate: A is genuinely closed while several execution/review cycles proceed. Reopening the same persisted A restores status, pending blockers, reports and confirmed input routing without a new run or automatic approval. Conversational explanation may use read tools on demand; passive delivery needs no LLM. A standalone/global Observer, multi-chat subscriptions and discovery are deferred.

### Deferred: host availability and timers

Choose a host service/watchdog only after defining owned process boundaries. Recovery requests go through Core reconciliation, inherited locks, operation outcomes, and durable state. Preserve run identity and budget accounting. Reminders require an available timer host; a sleeping/offline machine cannot be treated as running.

Gate: restart after controller/host loss produces no concurrent worker, repeated external effect, reset counters, or invented resolution. Availability failure is not task failure/acceptance by itself. Test active operation deadlines separately from indefinite waiting.

### Deferred: optional scheduling/pi-tick

Perform a bounded, pinned-source compatibility assessment only if scheduling is needed. Verify actual CLI/RPC commands, reviewer lifecycle, passive/durable wait behavior, detached process ownership, kill semantics, logs/privacy, and nested usage accounting. Recurring independent tasks need explicit new-run creation; recovery of an existing task must never be mistaken for another scheduled fresh run.

Adoption gate: measurable avoided infrastructure without a second authority, blind replay, or dependence on scheduler exit 0 as task success. pi-tick research/integration belongs in a separate future worktree and is not a prerequisite for the first autonomous milestone.

## Additional cross-cutting requirements to retain

- Action-local loop detection must cover verifier/reviewer correction loops as well as worker attempts.
- Source drift during review/finalization must invalidate affected acceptance/approvals; hashing report files alone does not freeze an external source checkout.
- The intended source-isolation route is separate Git worktrees managed through `@narumitw/pi-worktree`. Pin each run's authorized worktree realpath and verify it before restoration; changing a user's UI cwd must not silently retarget Core. Extension behavior was not independently verified in this planning update. Worktrees do not isolate shared databases, ports, Docker resources, paths outside the worktree, or deployment targets. Concurrent writable-run support and a full workspace-lock system are deferred; do not claim external-resource isolation from separate worktrees alone.
- Keep findings stable across review sessions: IDs, evidence, status, reopen reasons, and required versus optional criteria. Do not reissue closed findings merely because reviewer context is fresh.
- An allowed secret must be configured securely and reach the actual execution environment; a human message is not evidence that a long-running process has refreshed its environment.
- Reports and registry discovery must not expose private project content across unauthorized sessions. Store only justified metadata, with raw logs outside public documentation.
- Transport changes must not invalidate a running contract or silently change the selected reviewer model.

## First autonomous milestone acceptance scenario

1. Start a safe task from chat A in its authorized worktree.
2. Close A so its UI/model process is absent; merely hiding a live tab is insufficient. Core and its headless reviewer must remain independent processes.
3. Worker -> Eval -> Headless Reviewer -> Core complete multiple cycles without A.
4. Independent work finishes; a real scoped blocker is retained and Core waits without an active worker.
5. Reopen the same persisted chat A and receive current status and durable catch-up reports.
6. Submit an invalid and then a valid addressed resolution through confirmed human input. Add a separate main grant only if required.
7. Core validates, reconciles and automatically completes the permitted work under the same run ID. Independent acceptance is confirmed and A receives the result.

Fault variants: reviewer failure, report-delivery loss, controller crash, repeated human response, and restoration without repeating an uncertain external effect. Until a permanent host supervisor exists, controller-crash recovery may use explicit `resume`. Automatic recovery after a machine reboot is a separate future guarantee.

No cross-chat discovery, global registry, pi-tick, or parallel-run infrastructure is required to pass this milestone. A future test can replace reopened A with authorized B after cross-chat authority is implemented.

## Decisions still requiring explicit agreement

1. Cross-chat human authority is deferred. For the first milestone, preserve confirmed human input through original chat A and validate run/request/blocker applicability. Do not conflate original chat identity with the new headless reviewer identity. Future read-only discovery must not automatically grant command authority.
2. Headless reviewer selection: proposed default is a new-run opt-in transport with explicit model/provider, preserving old transports. Do not migrate active runs in place.
3. Contract amendment (`amend`) is deferred; budget grants and validated resolutions suffice for the current milestone. Any future scope/evaluator revision needs invalidation and reconciliation rules.

These are future feature decisions, not blockers to steps 1–4. Do not broaden the current hardening work to implement all of this document.
