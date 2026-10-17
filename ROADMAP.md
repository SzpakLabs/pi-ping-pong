# Pi Ping Pong — Development Roadmap v6

Date: 2026-10-17

Status: development plan with an agreed product-priority addendum; implementation and release status are separate.

This is the canonical repository roadmap. It preserves v5's consolidation of the user-supplied v4 roadmap and its addenda, and records the product priorities agreed in the 2026-10-17 conversation. Agreement on this plan does not authorize milestone implementation, paid live runs, commits, publication, deployment, or changes to external systems. Policy choices marked proposed require resolution before the affected implementation.

## Mission and product boundary

**Make Existing Coding Agents Reliably Autonomous.**

Pi Ping Pong is a lightweight, model-agnostic supervision layer over existing Pi Goal/Ralph runtimes. It coordinates bounded work, independent fresh evaluation, and a separate Codex or Pi reviewer. It avoids continuously streaming worker transcripts into reviewer context.

```text
Task + authorized scope + acceptance criteria
  → Pi worker (Goal / Ralph)
  → checkpoint + artifacts
  → fresh independent eval + supervisor review
  → continue | revise | complete | wait_human | stop
  → result delivered to the originating session where supported
```

Core remains headless and usable without a dashboard, AG-UI, backend service, database, or cloud hosting. Goal and Ralph share one protocol; their runtime lifecycle differences remain inside the existing implementation.

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
| 1 | Confirmed launch report, persistent Pi status, readable detailed status; graceful and forced stop; simpler package installation; run archiving and deletion | Nearest delivery slice. These controls do not depend on the optional dashboard. |
| 2 | One execution followed by fresh eval and independent review (`single`) | Next execution mode; no automatic fix/retry cycle. |
| 3 | Easier skill entry / possible `pi-ping-pong-light` (`pppl`); feature spec-run | Follow-on work. Light skill has medium priority. Start spec-run with one feature and sequential tasks. |
| 4 | External spec readers and broader product orchestration | Extend the feature workflow after its contract is verified. |
| 5 | Claude CLI integration | Low priority; separate worker, reviewer and return-to-existing-chat compatibility evidence. |

### English interface and run visibility

- All PPP product UI is English: persistent statuses, menus, notifications, launch reports and command reports. This does not change the user's conversation language.
- Use Pi's native `ctx.ui.setStatus()` with a PPP-specific key for a persistent status in the footer area. Preserve the existing token/context display and other extensions' statuses. The worker's Goal status is in a separate process and does not automatically appear in the launching reviewer session.
- Show the readable run name, actual execution/review phase, cycle/limit where applicable and elapsed time. Support narrow terminals and multiple runs without emitting model calls or chat messages on every refresh. `/ppp-status` provides readable details, models, limits, state age, paths and the next required action; distinguish launching, working, evaluating, awaiting review, awaiting input, stopping, stopped, failure and verified completion.
- Report launch accepted separately from worker/session startup confirmed. A spawned bridge PID is not proof of a running worker. Surface startup failure and timeout instead of leaving the user with silence. Read durable bridge state locally; show unavailable/stale information honestly. Emit chat reports for meaningful transitions, not continuous worker logs.
- Example English labels: `working`, `evaluating`, `awaiting review`, `awaiting your input`, `stopping after current turn`, `stopped`, `force stopped`.

### User stop controls

- Target commands: `/ppp-stop` and `/ppp-stop --force`; allow `/ppp-stop <name>` with the same force flag. Resolve the current run from the session; when multiple runs are eligible, require explicit selection rather than guessing.
- Graceful stop durably records intent immediately, allows the current agent turn and its in-flight tools to finish, then stops the run. It must suppress subsequent native automatic continuations, PPP cycles and new eval/review work. Do not wait for the entire Goal/Ralph task or require the next review checkpoint. Define and test the actual turn boundary against Pi lifecycle events before implementation acceptance.
- If already waiting for review or human input, stop without waiting for a reply. If an evaluator is already running, prevent any subsequent work and settle or terminate it under the existing deadlines. Record terminal state only after owned execution is stopped.
- Force stop interrupts active work without waiting for a turn boundary and terminates the run's owned worker/evaluator process groups and bridge execution. It must not stop the parent Pi/reviewer session, unrelated runs or processes based solely on an unverified stale PID. Verify process ownership and report termination failures.
- Repeated stop is idempotent; force can escalate an outstanding graceful stop. A persisted stop takes precedence over queued or late reviewer decisions and survives reload/recovery without resuming work. Existing cycle/wall-time deadlines remain effective and are never renewed by stop.
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
| v0.2a | Trusted review and acceptance boundary | Enforce reviewer/worker permissions; protect task, criteria and evaluator; bind acceptance to the actual source state. Define risk and authorization policy. | Negative tests show forbidden writes fail; changed criteria/evaluator/source invalidate acceptance; unsupported isolation configurations cannot claim enforced protection. |
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

Run `npm run check` before real launches or commits. Protocol/receiver changes also require the existing Python and Node test suites, covered by that gate. Live model runs need task authorization and separate evidence. Release changes need the applicable independent checks and human approval; an experimental worker must not overwrite the supervisor governing its work.

Preserve CLI/config contracts, legacy skill aliases and Pi session entries. Document schema/config migrations and recovery compatibility. Install authorized runtime updates from this canonical directory; do not maintain divergent runtime implementations or patch vendor packages/global Goal/Ralph settings.

## Non-goals and external inspirations

Do not build a replacement tool-calling runtime, memory/compaction system, MCP gateway, scheduler, distributed orchestrator or mandatory database/cloud layer without a demonstrated unmet requirement. Parallelism and assistants remain conditional; they are not prerequisites for a useful stable Core.

The v4 research references remain design inspirations: `wassname/pi-goals`, `tintinweb/pi-supervisor`, `mikefreno/ralpi`, `praxstack/agent-org`, `nexu-io/looper`, and Anthropic code-review practices. Their current APIs, compatibility and empirical claims were not verified for this revision. They are not dependencies or policy authority. GSD completion-gate integration remains an optional adapter proposal, using Core's existing authority and evidence rules; it must not introduce a second acceptance authority.

## Immediate next deliverable

Produce a verified v0.1 baseline record and a bounded v0.2a specification: supported environment, live evidence references, trusted-state boundary, permission mechanism, risk/authorization matrix, and negative-test acceptance criteria. Define the pilot comparison and minimal event fields before implementing v0.2. Resolve documented status conflicts from evidence; do not infer live success from tests or documentation.

The agreed next product slice is launch/status visibility, graceful/forced stop, Pi package installation and archive/delete controls, followed by `single`. Specify their lifecycle, installation/migration and negative-test acceptance alongside that baseline work. Basic terminal visibility is not deferred until the optional v0.4 dashboard. Implementation order within the first slice may follow dependencies; the addendum does not authorize a live run, commit or release.

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
