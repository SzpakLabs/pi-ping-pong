# Pi Ping Pong — Development Roadmap v7

Date: 2026-10-18

Status: development plan with an agreed product-priority addendum; implementation and release status are separate.

Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) records the desired component boundaries, state ownership and extension rules. This roadmap owns delivery order and milestone gates; the architecture document does not mark planned work implemented or reorder agreed priorities.

This is the canonical repository roadmap. It preserves v5's consolidation of the user-supplied v4 roadmap and its addenda, records the product priorities agreed in the 2026-10-17 conversation, and adds Trusted Artifact Generation on 2026-10-18. Agreement on this plan does not authorize milestone implementation, paid live runs, commits, publication, deployment, or changes to external systems. Policy choices marked proposed require resolution before the affected implementation.

## Mission and product boundary

**Make Existing Coding Agents Reliably Autonomous.**

Pi Ping Pong is a lightweight, model-agnostic supervision layer over existing Pi Goal/Ralph runtimes. It coordinates bounded work, independent fresh evaluation, and a separate Codex or Pi reviewer. It avoids continuously streaming worker transcripts into reviewer context.

```text
Task + authorized scope + acceptance criteria
  → Pi worker (Goal / Ralph): implementation + substantive report
  → PPP controller: trusted checkpoint envelope + source manifest
  → fresh independent eval + supervisor review
  → continue | revise | complete | wait_human | stop
  → result delivered to the originating session where supported
```

Core remains headless and usable without a dashboard, AG-UI, backend service, database, or cloud hosting. Goal and Ralph share one protocol; their runtime lifecycle differences remain inside the existing implementation.

Controller-generated artifacts in this target flow are planned, not an assertion of current implementation.

## Current baseline and evidence limits

Local source inspection on 2026-10-17 established the following. Tests and live compatibility were not revalidated while drafting this roadmap. An installer-scope comparison found additional source/runtime differences in development tooling and metadata; synchronizing this roadmap does not resolve that separate installation drift.

| Capability | Current evidence | Status / limitation |
|---|---|---|
| Shared Goal/Ralph bridge and Codex/Pi review routing | `scripts/bridge.py`, `extensions/pi-reviewed.ts`, `references/reviewed-runs.md` | Implemented in source; each live runtime/transport combination needs its own evidence. |
| Fresh eval invocation, checkpoint/evidence hashes, decision identity checks, finite limits | `scripts/bridge.py` | Implemented in source. Hashing listed artifacts does not establish protection of the entire source checkout or evaluator. |
| Durable status, event log, dispatch records, duplicate-launch refusal | `scripts/bridge.py`, `extensions/pi-reviewed.ts` | Partial foundation for recovery and observability; automatic crash recovery is not implemented. |
| Named-run preparation, project menu/status, legacy launch aliases, Pi session binding | `extensions/pi-reviewed.ts`, `README.md` | Implemented in source; generated task/evaluator quality requires separate validation. |
| Local development gate and protocol/receiver tests | `package.json`, `scripts/check.sh`, `scripts/test_bridge.py`, `scripts/test_pi_receiver.mjs` | Present; no fresh pass claimed by this document. Hosted CI is not established by these files. |
| Installer, documentation, MIT license, compatibility entrypoints | `scripts/install.py`, `SKILL.md`, `README.md`, `LICENSE`, sibling legacy skills | Present in source; publication and reproducible external installation remain unverified here. |
| Technically enforced worker/reviewer isolation | Current run contract describes cooperative filesystem scope | Missing as an enforced security boundary. A worktree and private file modes alone do not supply it. |
| Goal live-validation status | README opening reports a live three-cycle success; later README sections and the run reference say no new live run occurred | Conflicting documentation. Reconcile against dated run artifacts, exact source revision, installed files, and dependency versions before claiming live verification. |
| Dashboard, replay benchmarks, adaptive supervision, AG-UI assistants | No implementation established by this bounded inspection | Planned; no shipped capability claimed. |

## Agreed product priorities — 2026-10-17

The following requirements and relative priorities were agreed in conversation. They are planned work, not shipped capabilities. Command names and examples below are target interfaces until implemented and verified. This near-term delivery order supplements the versioned milestones below; it does not remove baseline, trust, compatibility or acceptance gates. The existing review decision `stop` is not an anytime user stop command.

| Order | Deliverable | Agreed priority / boundary |
|---|---|---|
| 0 | Trusted Artifact Generation | P0 baseline hardening within v0.2a. Remove model-authored technical identity and manifests from the checkpoint path; preserve rejection and independent acceptance gates. |
| 1 | Confirmed launch report, persistent Pi status, readable detailed status and compact managing-chat callbacks; graceful and forced stop; simpler package installation; run archiving and deletion | Nearest delivery slice. These controls do not depend on the optional dashboard. |
| 2 | One execution followed by fresh eval and independent review (`single`) | Next execution mode; no automatic fix/retry cycle. |
| 3 | Easier skill entry / possible `pi-ping-pong-light` (`pppl`); feature spec-run | Follow-on work. Light skill has medium priority. Start spec-run with one feature and sequential tasks. |
| 4 | External spec readers and broader product orchestration | Extend the feature workflow after its contract is verified. |
| 5 | Claude CLI integration | Low priority; separate worker, reviewer and return-to-existing-chat compatibility evidence. |

The 2026-10-18 planning addition prioritizes trusted artifacts before final integration of the current status feature. It does not accept that feature, reopen a stopped run, renew its limits, or adopt the accompanying analysis's other proposed priority changes. The remaining delivery order stays as recorded above.

### Trusted Artifact Generation — P0, baseline hardening / v0.2a

**Problem and evidence boundary.** Current dogfooding exposed a checkpoint containing a directory name instead of the run UUID and a source manifest containing a shortened base commit ID. Rejecting invalid identity is correct supervisor behavior; it does not establish feature completion. Startup has independent acceptance evidence; footer behavior has test evidence but the affected checkpoint was rejected. Final status, notifications, documentation and integration remain unaccepted. These observations motivate this work; they do not prove unattended execution, recovery or cost savings.

**Scope.** Extend the existing bridge/controller with a small deterministic artifact-generation path. Do not create another runtime, protocol, acceptance authority or large subsystem. A run-local helper is an experiment until the shared implementation and compatibility tests establish support.

| Responsibility | Owner / trusted input |
|---|---|
| Implementation, tests, documentation and substantive explanation | Worker; reports and requested completion remain untrusted claims. |
| `run_id`, cycle identity (`cycle` / `cycle_id`), `base_commit` / existing base-revision field | Controller-owned run configuration and lifecycle state; record the full object ID obtained from Git, without assuming one hash algorithm or accepting an abbreviation. |
| Source hashes, source manifest and checkpoint envelope | Deterministic controller code over the declared source snapshot and authorized scope, including relevant untracked files. |
| Fresh criterion checks and acceptance evidence | Independent evaluator using protected task, criteria and evaluator versions. |
| Substantive findings and `continue` / `revise` / `complete` / `wait_human` / `stop` | Independent reviewer within existing policy and evidence gates. |

The worker supplies its report and declared artifact references through a narrow input contract. It does not serialize or repair authoritative run/cycle/base identity, calculate authoritative hashes, or certify acceptance. Existing CLI/config/checkpoint fields remain compatible through the shared implementation or an explicit documented adapter/migration.

**Generation and rejection contract**

- Derive identity only from controller-owned state; validate run, current cycle, base revision, allowed paths and required files before emitting an envelope. A worker-provided conflicting identity must be rejected explicitly, never silently rebound to the current run. Apply the same checks to legacy/model-authored inputs during migration.
- Snapshot or freeze the evaluated source state; include the complete declared source changes and relevant untracked files. Bind manifest and envelope to that state and protected acceptance inputs. Detect changes between generation, evaluation and final decision; invalidate stale evidence instead of accepting a mixture of revisions.
- Publish artifacts atomically with private permissions. Define duplicate invocation and crash behavior: an identical retry may return the same artifact; a conflicting or partial write must not replace a valid envelope or create another cycle. Hashing alone does not establish filesystem isolation or trustworthy provenance; retain the v0.2a enforcement boundary below.
- Reject wrong run identity, stale cycles, wrong base revision, changed hashes, missing artifacts and out-of-scope paths with an actionable reason. Preserve rejected evidence and the original run history; never edit an old checkpoint to make it pass or use generation as implicit approval.
- Preserve finite cumulative limits and duplicate-launch refusal. Artifact generation grants no new worker turn, recovery attempt, scope, commit permission or external action. A valid envelope and passing deterministic checks remain necessary but insufficient for verified completion.

**Experiment: Trusted Checkpoint.** Compare the existing validation path with controller-generated artifacts on a fixed synthetic fixture set: valid checkpoint; wrong `run_id`; stale cycle; wrong base commit; missing source artifact; modified artifact hash. Include scope violations, duplicate generation and interrupted writes as regression cases for the shared implementation. Use fresh deterministic checks; no paid model run is needed to generate or repair technical identity in this experiment.

Acceptance criteria:

1. Zero invalid or foreign checkpoint identities accepted; every negative fixture rejected for the intended reason without altering earlier evidence or binding it to another run.
2. All valid fixture scenarios accepted by the artifact validator, including full Git object IDs and relevant untracked artifacts. Validator acceptance is separate from task acceptance.
3. No scenario requires an LLM to create or correct authoritative identity, manifest or hashes. A missing substantive report may still require worker work within the existing bounds.
4. Mutation, repeated invocation and crash fixtures cannot produce a valid envelope for stale/mixed state, overwrite a conflicting accepted record, duplicate execution or renew limits.
5. Existing Goal/Ralph, CLI/config, decision identity and Pi session contracts pass compatibility tests, or the affected migration is documented and tested. Required protocol/receiver checks pass before an authorized live trial.

Report protocol-invalid checkpoint counts and deterministic fixture results first. Measure cost/time improvements separately on comparable end-to-end tasks, including failed attempts and human effort; synthetic success does not prove general autonomy or cheaper operation.

### English interface and run visibility

- All PPP product UI is English: persistent statuses, menus, notifications, launch reports and command reports. This does not change the user's conversation language.
- Use Pi's native `ctx.ui.setStatus()` with a PPP-specific key for a persistent status in the footer area. Preserve the existing token/context display and other extensions' statuses. The worker's Goal status is in a separate process and does not automatically appear in the launching reviewer session.
- Show the readable run name, actual execution/review phase, cycle/limit where applicable and elapsed time. Support narrow terminals and multiple runs without emitting model calls or chat messages on every refresh. `/ppp-status` provides readable details, models, limits, state age, paths and the next required action; distinguish launching, working, evaluating, awaiting review, awaiting input, stopping, stopped, failure and verified completion.
- Report launch accepted separately from worker/session startup confirmed. A spawned bridge PID is not proof of a running worker. Surface startup failure and timeout instead of leaving the user with silence. Read durable bridge state locally; show unavailable/stale information honestly. Emit chat reports for meaningful transitions, not continuous worker logs.
- Example English labels: `working`, `evaluating`, `awaiting review`, `awaiting your input`, `stopping after current turn`, `stopped`, `force stopped`.

### Compact managing-chat callbacks

- Replace visible instruction walls with a compact English run summary: readable run name, Goal/Ralph mode, actual outcome/phase, cycle/limit when applicable, concrete reason and next action. Cover confirmed startup, review requested, verified completion, stopped/failed/limit reached and genuine human blockers. Keep the normal summary to approximately 4–6 short lines; use restrained status icons and formatting where supported, with a readable plain-text fallback.
- Keep the machine control payload separate from its human presentation. Preserve exact run/cycle/hash identity, authorized review scope, evidence references, decision instructions and delivery receipts in controller-owned structured records. Use a supported host attachment/metadata channel or a short validated reference that the receiver/reviewer can resolve; do not assume every chat supports hidden payloads, cards or buttons. Unsupported presentation must not prevent delivery or review.
- Do not place full UUIDs, absolute paths, raw logs or long operational instructions in the normal summary. Provide supported artifact/details links or an explicit details view for authorized access; retain full identity in those details. Never invent a working link or expose private artifacts through a public destination. Escape untrusted names/text for the target renderer.
- Render known state and reason deterministically without an extra model call. Distinguish native completion from verified acceptance, remaining cycles from permission to resume, and `attention_required` from an actual human blocker. Show unknown/unavailable data explicitly. Use `Next:` for automatic review/diagnosis or a stopped outcome; show `Action required:` only for a real missing input, access, approval or choice. A callback or details link does not authorize restart, extra budget or scope expansion.
- Reuse durable delivery receipts keyed to run and event/transition identity. Reload/reconnect/retry must not duplicate a delivered notification or drop a distinct cycle's review request; preserve existing callback routing and decision gates. Do not send a chat message on every status refresh.

Illustrative stopped-run presentation; the reason must come from verified state:

```text
⚠ PPP · start-status-followup-luna · Ralph
Stopped · cycle 4/6
Reason: checkpoint run identity mismatch.
Next: diagnose within authorized scope; no automatic restart.
```

Where supported, append a real `Details` link to the private run record. Review-request callbacks should instead state `Awaiting review` and identify the review cycle; the managing agent still receives or resolves the complete authorized review contract.

Acceptance: fixtures cover every listed outcome, long names/narrow displays, unknown state, plain-text fallback, safe details resolution, exact control identity/scope preservation, and deduplication across reload/retry. Completion requires independent acceptance; a compact presentation must never conceal a blocking reason, bypass review or imply that the user must intervene when automatic work is authorized. This belongs to the current visibility/notification delivery slice and does not require the optional dashboard.

### User stop controls

- Target commands: `/ppp-stop` and `/ppp-stop --force`; allow `/ppp-stop <name>` with the same force flag. Resolve the current run from the session; when multiple runs are eligible, require explicit selection rather than guessing.
- Graceful stop durably records intent immediately, allows the current agent turn and its in-flight tools to finish, then stops the run. It must suppress subsequent native automatic continuations, PPP cycles and new eval/review work. Do not wait for the entire Goal/Ralph task or require the next review checkpoint. Define and test the actual turn boundary against Pi lifecycle events before implementation acceptance.
- If already waiting for review or human input, stop without waiting for a reply. If an evaluator is already running, prevent any subsequent work and settle or terminate it under the existing deadlines. Record terminal state only after owned execution is stopped.
- Force stop interrupts active work without waiting for a turn boundary and terminates the run's owned worker/evaluator process groups and bridge execution. It must not stop the parent Pi/reviewer session, unrelated runs or processes based solely on an unverified stale PID. Verify process ownership and report termination failures.
- Repeated stop is idempotent; force can escalate an outstanding graceful stop. A persisted stop takes precedence over queued or late reviewer decisions and survives reload/recovery without resuming work. Existing cycle/wall-time deadlines remain effective and are never renewed by stop.
- Implement local durable stop intent in this control slice; full crash recovery remains v0.3. Safe stop must not depend on shipping the entire recovery engine.
- Preserve artifacts, logs, identity and stop reason. A stopped run is not accepted/complete and cannot be silently replayed. Force stop can leave partial files and cannot undo already executed external actions; reflect that limit in its report. Stop is separate from deletion.

### Simpler installation

- Primary Pi distribution: one Pi package containing the receiver extension, skill and Python bridge, installable through Pi's Git/package mechanism, with npm as an optional later distribution source. Target flow: `pi install <published-package-source>`, `/reload` in an existing session, then `/ppp`. Do not claim repository/package availability or a working installation before verification.
- Declare package resources explicitly. Resolve bridge/resources relative to the installed package; remove reliance on a separate hard-coded `~/.agents/skills/pi-ping-pong` installation for this route while retaining compatible legacy entrypoints and overrides.
- Detect Python, Pi and the selected runtime/model requirements; provide actionable English setup messages. Evaluate shipping compatible Goal/Ralph packages as dependencies with explicit resource resolution. If not viable, provide exact dependency setup steps. Bundling versus guided dependency installation remains an implementation decision; do not silently alter global Goal/Ralph settings or credentials. `single` should not require Goal/Ralph.
- Provide migration from the manually copied receiver, preventing duplicate command owners/subscriptions. Verify clean install, update, removal, missing prerequisites and legacy coexistence in isolated fixtures/environments. Preserve private run data when removing the package.
- Skill-directory/catalog installation is an additional entry for other agent hosts. Installing skill instructions alone does not register Pi commands or a persistent footer. Keep documentation clear about which integration is installed and which capabilities are available.

### Archive and delete runs

- Add project-menu actions to archive a run and permanently delete its artifacts. Archiving removes it from the default `/ppp` list and moves its artifacts out of the project into private archive storage. Hiding a row alone does not satisfy project cleanup.
- Active runs must first be stopped and confirmed inactive; unavailable or malformed state is not proof of inactivity. Show the exact run, paths and deletion scope before permanent deletion; never delete project source outputs as part of run-artifact cleanup.
- Detach receiver subscriptions and reconcile pending deliveries so archived/deleted runs cannot restart or generate repeated missing-path notices. Keep minimal durable identity/terminal records outside the cleaned project run directory to preserve duplicate-launch refusal; reusing a readable name must not reuse a prior run identity.
- Preserve full evidence for archives, keep archive data private and provide explicit access outside the default active-project list. Archive, irreversible purge and recovery are distinct actions.

### Single execution with review

- Add `single` alongside Goal/Ralph through the shared protocol: execute once, run a fresh independent task evaluator, obtain a separate reviewer decision, then report the outcome.
- No automatic revision or second worker cycle. Failed eval, review findings or partial work produce an honest non-success report. Further work requires an explicit new action with its own recorded identity and bounds. Genuine missing inputs/access follow the existing human-blocker contract without granting extra execution cycles.
- Preserve independent review, identity/hash checks, finite limits, durable delivery and duplicate-launch refusal. A native Pi worker should not require Goal/Ralph extensions; one Ralph cycle is only an approximation of the desired mode.

### Light entry and spec-run

- Light entry: reuse task, criteria and authorized scope from chat; ask only for missing inputs. Prefer a simple entry over the shared engine. Evaluate a separate skill-only `pi-ping-pong-light`/`pppl` for low-setup hosts, but do not promise durable detached execution, callbacks or independent reviewers when the host cannot supply them. Self-review must be labeled as such. The final short command name and packaging remain design choices; a Pi slash command requires extension registration.
- Keep dimensions separate: light is an entry experience; `single`/Goal/Ralph are execution modes; Pi/Claude CLI are runtimes; spec-run coordinates task dependencies. Do not fork the review protocol for each combination.
- First spec-run scope: one feature, sequential dependent tasks, explicit requirements and non-goals, design, task dependencies, criterion IDs linked to checks/evidence and final integrated feature verification. Proposed native files: `requirements.md`, `design.md`, `tasks.md`. Task execution reuses the shared execution/review contracts and finite overall budget; more cycles alone do not replace a specification. Scope changes must be explicit and invalidate affected prior acceptance.
- Larger product work follows verified feature orchestration; parallel/distributed work retains the existing evidence gates. Material requirements/design choices go to the user, while routine work within authorized scope may continue.
- Kiro is a possible attributed workflow inspiration. Author PPP's own text/templates; attribution alone is not permission to copy another tool's code, prompts or documentation. Confirm applicable licenses before reusing material. Do not imply affiliation or verified compatibility.
- Later readers: Kiro, GSD, GitHub Spec Kit and OpenSpec. Preserve original files, record source format/version, map criteria/tasks into PPP's internal contract, show unsupported/ambiguous content, and import read-only first. Reading a format does not authorize its commands, mutations or acceptance policy. Do not introduce a second acceptance authority.

### Deferred Claude CLI investigation

Programmatic CLI execution and structured events are a plausible adapter route, not implemented PPP support. Investigate worker execution first, then an independent reviewer, and separately event delivery into an already open Claude session. No local live compatibility was established in this discussion (`claude` was not found in PATH). Keep this behind the agreed Pi usability/control, installation and execution work; do not substitute an Anthropic Pi provider setting for a Claude CLI runtime adapter.

## Development sequence

Versions are milestones, not calendar commitments. The v0.2 subdivisions are delivery checkpoints within the same milestone. A small comparative benchmark begins there; v0.5 expands it. The promo site can proceed independently once its baseline claims are verified.

| Version | Milestone | Scope | Exit evidence |
|---|---|---|---|
| v0.1 | Reconcile and verify the current harness | Inventory source/install versions; reconcile live-run claims; retain existing CLI, aliases, installer and MIT scope. Establish CI using the local check gate. | Fresh local and CI results; a compatibility table separating tested, untested and unsupported combinations; authorized live smoke evidence for each combination claimed supported. |
| v0.2a | Trusted artifacts, review and acceptance boundary | Begin with deterministic identity, checkpoint envelope and source-manifest generation. Enforce reviewer/worker permissions; protect task, criteria and evaluator; bind acceptance to the actual source state. Define risk and authorization policy. | Trusted Checkpoint fixtures pass without model-authored identity; invalid identities and stale artifacts are rejected. Negative tests show forbidden writes fail; changed criteria/evaluator/source invalidate acceptance; unsupported isolation configurations cannot claim enforced protection. |
| v0.2b | Review contract and structured events | Stable findings, evidence-backed closure, bounded convergence; minimal versioned run/event schema. Record model/usage data when available. | Findings survive cycles without duplicate churn; unresolved blockers prevent completion; event fixtures explain decisions and retain unknown usage values. |
| v0.2c | Pilot benchmark and dogfooding | Small versioned task set comparing standalone and supervised Pi; start isolated dogfooding using a stable supervisor. | Repeated paired runs report completion, cost, time and human effort, including failures. Findings can show benefit, no benefit, or harm; no broad reliability claim from a small pilot. |
| v0.3 | Durable execution and recovery | Build on existing records: crash-safe state transitions, restart/resume, idempotent dispatch/callback, stale/racing checkpoint handling, explicit uncertain outcomes. | Injected failures at persistence/dispatch boundaries recover without duplicating confirmed effects, replaying ambiguous effects, or resetting elapsed budgets. |
| v0.3.1 | Promo website — parallel, optional track | Static Vue 3 + Vite site: product, architecture, use cases, quick start, docs, roadmap, FAQ, illustrations, verified repository/release/contact links. | Responsive page and tested instructions/links; demo data and unavailable destinations labeled honestly; no required backend. Publishing needs task authorization. |
| v0.4 | Observability and optional UI | Read-only `pi-ping-pong-ui`: runs, timeline, findings, outcomes, available model/token/cost data. Prepare a bounded context/data API. | A run can be explained from Core-owned structured evidence without full transcripts. Authorized data stays private; public examples use synthetic or explicitly approved sanitized data. |
| v0.5 | Replay and expanded benchmarks | Replay immutable checkpoints; compare interchangeable reviewer models; labeled defect cases and incident/revert regressions; expand paired end-to-end trials. | Versioned dataset, evaluator, prompts, environment and model IDs; reproducible method; false-positive/negative results; fair quality/time/cost comparisons that retain negative results. |
| v0.6 | Adaptive supervision — evidence gated | Drift signals, adaptive checkpoint intervals, risk-based review depth, cost-aware model selection, focused follow-up. | Against a fixed policy, show earlier useful detection or better verified outcomes within declared cost/latency limits. Keep the fixed policy when adaptation does not help. |
| v1.0 | Stable release | Hardened CI/security/regression checks; protected approval gates; install/migration docs; compatibility checks for declared Linux/VPS/macOS environments; rollback/staged release where applicable. | Reproducible installation and meaningful task results, including interruption, denied access, uncertain side effects and recovery. Required human approvals bind to the reviewed state. |
| v1.1 | Dual assistants — conditional direction | Public docs/install assistant and private run-analysis copilot, initially read-only; Vue/AG-UI/CopilotKit integration only after a bounded API/version prototype. | Traceable answers, version-aware docs, labeled uncertainty and access separation. Proceed only when observed user needs justify assistants. |
| v1.2+ | Advanced operations and parallel work — conditional direction | First approval-gated dashboard actions; then optional parallel workers, task dependencies, isolated worktrees, conflict detection and evidence aggregation. Distributed hosting only with measured need. | Core enforces scoped authorization and idempotency; parallelism improves wall time without reducing verified completion/quality. |

## v0.2 contracts to settle before implementation

### Trusted state and isolation

- Separate the worker's writable project outputs, reviewer evidence access, trusted task/evaluator configuration, and narrow decision channel. A reviewer may submit a validated decision; it must not modify graded artifacts or acceptance gates.
- Declare the threat model and supported permission mechanism. Enforce restrictions on tools and processes, including evaluator dependencies; prompt instructions and a worktree are insufficient. A host without enforcement must report cooperative mode explicitly.
- Bind acceptance to run/cycle identity, the criteria/evaluator versions, base revision, complete in-scope source diff including relevant untracked files, and artifact hashes. Revalidate that state at final acceptance and before any approved external action. Freeze or snapshot inputs so concurrent edits cannot silently pass.
- Treat worker summaries, repository text and evidence as untrusted inputs. A separate reviewer context and read-only access do not eliminate prompt injection or correlated model errors. Trusted policy must remain outside worker-controlled content.
- Preserve functional, visual and human acceptance distinctions. Structural checks, screenshots existing on disk, exit 0, and native completion are insufficient on their own. Criteria that need judgment require the corresponding review evidence.

### Proposed risk and authorization policy

The following is a candidate default, not a claim that current permission enforcement exists. Ratify the tiers and sensitive-path rules before implementing automatic decisions.

| Class / action | Proposed handling |
|---|---|
| Low-risk, reversible local work inside an already authorized scope | May continue and complete automatically when required eval/review evidence passes and no separate approval gate applies. |
| Medium-risk changes, such as broad refactors or public API changes | Define stronger checks and approval requirements during task preparation; stop for a material choice or scope expansion. |
| High-risk work, sensitive paths, destructive operations, release or production impact | Explicit human review/approval at the required boundary, tied to the exact reviewed state and action. |
| Commit, push, deploy, publish, or other external mutation | Requires applicable task/workflow authorization regardless of risk tier. Risk classification never grants permission. |
| Missing access, credential, approval or material decision | `wait_human` with a precise request; preserve limits. Ask for credential setup, never plaintext secrets in chat. |

Task authorization and later review approval are separate records. Do not request approval again when existing authorization already covers the action. Material changes invalidate an approval unless the explicit approval policy covers them; a model cannot approve itself.

### Findings and convergence

- Record a stable finding ID, severity, criterion, concrete location/evidence, new versus pre-existing classification, and lifecycle status. Keep actionable defects separate from nits.
- Separate deterministic eval results from model findings. Report zero findings explicitly; that result alone does not establish acceptance.
- A blocking finding closes only with evidence of a fix or an evidence-backed disposition such as duplicate/not applicable. A rationale cannot silently waive a failed acceptance requirement or required human gate.
- Re-review relevant changes while checking regressions and unresolved findings. Track reopened findings; do not endlessly reissue closed ones without new evidence.
- Use finite review/fix cycles and wall-time limits. Three rounds is a candidate to evaluate, not an approved universal default. Exhaustion produces a non-success outcome and a concrete next action.
- Turn recurring confirmed defects into versioned regression cases or focused review guidance. Re-evaluate reviewer changes against both misses and false positives.

### Minimal structured record

Define a versioned event envelope with event/run/cycle identity, ordering, timestamp, event type, actor, reviewed-state identity, and references to relevant artifacts, decisions and dispatch receipts. Use explicit unavailable values for missing provider/model/usage data. Preserve existing consumers through adapters or documented migration.

Capture the data needed for early comparison before building the UI. Do not require distributed tracing infrastructure. Raw private prompts, transcripts, screenshots, credentials and token-bearing links remain outside public telemetry.

## Recovery contract

Extend the existing duplicate-launch refusal and durable delivery records; do not replace them with automatic retries.

- Distinguish intent recorded, dispatch attempted, acknowledged, applied and outcome unknown. An enqueue receipt does not prove execution or acceptance.
- Specify recovery for crashes before/after each transition, including bridge death, worker death, reviewer disconnect, lost acknowledgement and simultaneous recovery attempts.
- Reattach or reconcile an existing session where supported. If the runtime cannot resume safely, report that limit; do not silently start a new worker on the same outputs.
- Preserve cumulative cycle/time limits across restarts. Define how wall time includes downtime and human waits; never silently renew limits. Enforce token/cost caps only where reliable provider/runtime data supports them.
- Reconcile ambiguous external effects using authoritative evidence or human action. Do not promise exactly-once execution for arbitrary external systems.

## Evaluation and metrics

Define eligibility, exclusions, stopping rules and target thresholds before measuring. Report sample sizes, time windows, versions, environment, missing data and privacy handling.

| Metric | Definition / reporting rule |
|---|---|
| Verified completion rate | Verified-complete tasks divided by eligible attempted tasks. Retain failures, timeouts and unresolved outcomes in the results. |
| Human minutes per task | Measured setup, intervention, review and approval time, with categories separated; escalation count is supplementary. |
| Cost per verified task | All worker/reviewer and failed-attempt costs divided by verified completions. Report unknown costs; with zero completions, show total spend and no finite per-completion claim. |
| Time and convergence | Time to verified completion, review latency, cycles, repeated/reopened findings and unresolved blockers. |
| Artifact reliability and review effort | Protocol-invalid checkpoints by reason; valid/invalid fixture acceptance; reviewer time/tokens per cycle where available. Compare equivalent scopes and include retries; never count a valid envelope as a verified task. |
| Reviewer accuracy | False positives and false negatives on independently labeled cases; disclose ambiguous labels and adjudication. |
| Recovery and regressions | Recovery success under defined injected faults; rollback/revert rates where meaningful. |

For the pilot, fix a small task set covering a feature, a bug fix, a meaningful test change and a failure/recovery case. Start with synthetic fixtures; simulated people's names must contain `Test`. Use independent acceptance criteria, repeated paired trials, isolated starting states and declared budgets. Separate reviewer-model comparisons from end-to-end system comparisons so gains are attributable. Replay must evaluate stored state without replaying external side effects; it does not establish live recovery or future worker behavior.

Before expanding the UI or adaptive policies, use pilot results to decide what to retain, change or stop. Context-read/reuse accounting is optional until its semantics, measurement and use are reliable.

## UI and assistant boundaries

- **Core:** owns run truth, validation, policy enforcement, supervisor decision records and durable events. A supervisor interprets evidence within these rules; it cannot bypass them.
- **Private dashboard:** authorized local/private run data; read-only first. Any future actions go through Core's scoped gates.
- **Promo site:** public documentation and approved aggregate statistics. A public demo dashboard may use synthetic or explicitly approved sanitized snapshots; private run exposure requires a separate audience/authentication/data decision.
- **Public website assistant:** public versioned documentation only; install guidance/config generation without silent machine changes or private-repo access.
- **Private dashboard copilot:** only authorized run/benchmark context, with run/event references and uncertainty. It cannot certify its own independent verification or grant approval.

Choose assistant libraries and hosting only after validating the specific integration and need. Placeholders must not imply shipped dashboards, assistants, releases or live statistics.

## Dogfooding and release discipline

Use a pinned stable Pi Ping Pong installation to develop the next version in an isolated branch/worktree. Keep the running supervisor and trusted acceptance gates immutable from the worker; keep candidate code separate. Gather private run/eval data for later observability and benchmarks.

Use deterministic preflight for prerequisites and artifact validity before spending a worker/reviewer turn. Deliver stages with explicit criteria; record progress from authorized source diffs/hashes separately from a native runtime's service-directory tracking. Review relevant changes and unresolved findings using evidence bound to the current source state; reducing repeated context must not omit required independent review or regression checks.

For the current incomplete feature, preserve the source diff, baseline, prior decisions and rejected checkpoints. Complete trusted artifact generation, then finish status/lifecycle, notifications/diagnostics, tests and documentation before final integration acceptance. Any authorized follow-up has its own recorded identity and an explicit link to earlier evidence. Recovery must retain the applicable cumulative cycle/time limits, including the original deadline when authorized only within remaining limits. A new budget requires explicit authorization; do not add cycles until tests happen to pass or describe a manual follow-up as automatic recovery. A bounded live dogfooding run follows deterministic checks only when separately authorized and needed for an unverified runtime behavior.

Run `npm run check` before real launches or commits. Protocol/receiver changes also require the existing Python and Node test suites, covered by that gate. Live model runs need task authorization and separate evidence. Release changes need the applicable independent checks and human approval; an experimental worker must not overwrite the supervisor governing its work.

Preserve CLI/config contracts, legacy skill aliases and Pi session entries. Document schema/config migrations and recovery compatibility. Install authorized runtime updates from this canonical directory; do not maintain divergent runtime implementations or patch vendor packages/global Goal/Ralph settings.

## Non-goals and external inspirations

Do not build a replacement tool-calling runtime, memory/compaction system, MCP gateway, scheduler, distributed orchestrator or mandatory database/cloud layer without a demonstrated unmet requirement. Parallelism and assistants remain conditional; they are not prerequisites for a useful stable Core.

The v4 research references remain design inspirations: `wassname/pi-goals`, `tintinweb/pi-supervisor`, `mikefreno/ralpi`, `praxstack/agent-org`, `nexu-io/looper`, and Anthropic code-review practices. Their current APIs, compatibility and empirical claims were not verified for this revision. They are not dependencies or policy authority. GSD completion-gate integration remains an optional adapter proposal, using Core's existing authority and evidence rules; it must not introduce a second acceptance authority.

## Immediate next deliverable

Produce a verified v0.1 baseline record and a bounded v0.2a specification: supported environment, live evidence references, trusted-state boundary, permission mechanism, risk/authorization matrix, and negative-test acceptance criteria. Define the pilot comparison and minimal event fields before implementing v0.2. Resolve documented status conflicts from evidence; do not infer live success from tests or documentation.

The first baseline-hardening deliverable is a bounded Trusted Artifact Generation specification and Trusted Checkpoint fixture experiment within v0.2a. Then finish independent acceptance of launch/status visibility and continue the agreed control/install queue: graceful/forced stop, Pi package installation and archive/delete controls, followed by `single`. Specify their lifecycle, installation/migration and negative-test acceptance alongside that baseline work. Basic terminal visibility is not deferred until the optional v0.4 dashboard. This planning addition does not authorize a live run, commit or release.

## Changes from v6

- Added P0 Trusted Artifact Generation to baseline hardening / v0.2a, with explicit Worker, Controller, Evaluator and Reviewer responsibilities.
- Defined deterministic identity/manifest generation, conflict rejection, source-state binding, atomic writes and compatibility requirements without claiming implemented protection.
- Added the Trusted Checkpoint experiment, negative fixtures and measurable acceptance criteria; kept task acceptance and cost/autonomy claims separate.
- Added compact English managing-chat callbacks with separate structured control records, private details access, deterministic rendering, durable deduplication and host-compatible fallback.
- Recorded bounded follow-up dogfooding, source-based progress and deterministic-first checks; clarified that local durable stop intent precedes full v0.3 recovery.
- Preserved the remaining agreed queue; other priority changes in the supplied analysis remain proposals.

## Changes from v5

- Recorded the conversation-approved product priorities without marking them implemented or replacing v5's safety/evidence milestones.
- Added English Pi footer status and confirmed-start reporting, graceful/forced user stop semantics, package installation/migration and out-of-project archive/delete requirements.
- Recorded `single`, medium-priority light entry, feature-first spec orchestration, future external spec readers and low-priority Claude CLI investigation.
- Kept unresolved packaging details, command naming and runtime compatibility explicit; no paid live runs or release actions are implied.

## Changes from v4

- Added a source-backed baseline with explicit evidence limits and the unresolved Goal status conflict.
- Split v0.2 into trust, review/events and pilot checkpoints; moved basic CI and comparison data collection earlier.
- Bound acceptance to actual source/evaluator/criteria state and added prompt-injection and correlated-error limits.
- Added a proposed authorization matrix, evidence-backed finding closure and explicit recovery semantics.
- Kept the promo site parallel/optional and later assistants, adaptive policies and distributed/parallel work conditional on measured need.
- Consolidated addenda into one plan while preserving unresolved decisions and optional GSD integration status.
