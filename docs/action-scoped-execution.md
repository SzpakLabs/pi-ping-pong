# Action-Scoped Execution and Deferred Escalation

> Evaluator-era design/history: current execution is Worker (ordinary tests) → independent Reviewer (remaining judgments) → Core. Separate evaluator/preflight/repair and old-run resume were removed. Current [protocol](action-scoped-protocol.md) and [migration](evaluator-preparation.md) supersede lifecycle/compatibility instructions below; historical results are not live verification of the new cycle.

Status: **Agreed architectural specification; Protocol-2 source implementation and local F1–F4 hardening exist.** See the [regression audit](protocol-2-regression-audit.md) for current evidence and limits. Live integration and the chat-independent vNext runtime are not established by local gates.

This document records the agreed replacement execution model following the [permission-friction research](permission-friction-research.md). It is not a claim about current CLI, schema, recovery, budget, or receiver capabilities. JSON examples are illustrative, not finalized wire schemas. Existing runs remain governed by their original contracts.

## 1. Purpose

A user delegates a task and leaves. PPP performs all available authorized work, collects genuine blockers, and requests human input in one grouped message when needed. After the response, PPP independently validates the resolutions, resumes automatically, completes the work, and verifies the outcome without requiring manual approval of routine steps.

Explicit actions and dependencies do not require a general-purpose workflow engine or a full DAG scheduler. This architectural concept does not assign a protocol or schema version; those versions must be defined separately during implementation.

## 2. Separate execution, blockers, and acceptance

- **Execution:** what has been done, what remains, and what can currently run.
- **Blockers:** conditions preventing particular actions.
- **Acceptance:** whether independent evidence establishes that the result satisfies the requirements.

Worker settlement, lifecycle termination, evaluator exit 0, budget exhaustion, and blocker resolution are not task acceptance. A valid audit report can be accepted as an audit while the product it evaluates still fails its own acceptance criteria.

## 3. Actions and dependencies

Maintain actions with stable IDs, execution states, and explicit blocker dependencies. Preserve completed actions and their evidence, not merely a list of pending work. Execution completion is a worker claim until independently verified.

```json
{
  "actions": [
    {"id": "footer", "status": "pending", "blocked_by": []},
    {"id": "send_email", "status": "pending", "blocked_by": ["B1"]}
  ]
}
```

Block the affected action and its dependents, not the entire run. An independent action may proceed only if it is already authorized, does not require the missing condition, does not bypass the blocker, does not create unsafe shared-state interference, and can produce trustworthy evidence. Review must validate material dependency judgments; workers cannot gain permission by labeling work independent.

For example, a missing Resend key blocks real email sending, but not an independent footer implementation or local form-validation tests. Unverified runtime identity may block all interactions with that runtime while still allowing independently authorized local analysis.

## 4. Durable blocker registry

Store a list of blocker objects across cycles:

```json
{
  "blockers": [
    {
      "id": "B1",
      "reason": "missing_secret",
      "blocked_actions": ["send_email"],
      "needed": "Configure RESEND_API_KEY in the runtime",
      "status": "open",
      "escalation": "deferred",
      "found_cycle": 3
    },
    {
      "id": "B2",
      "reason": "missing_access",
      "blocked_actions": ["connect_domain"],
      "needed": "Provide authorized DNS access",
      "status": "open",
      "escalation": "deferred",
      "found_cycle": 5
    }
  ]
}
```

Rules:

- Cycle completion never deletes an open blocker.
- A new blocker gets its own identity; rediscovery updates the existing blocker instead of creating duplicates.
- Resolving B1 does not resolve B2.
- Retain resolved blockers and the evidence or human-response references establishing their disposition.
- Blockers are visible in status immediately, even when escalation is deferred.
- Never store secret values in records, evidence, feedback, or chat; request secure configuration instead.

## 5. Deferred and immediate escalation

`escalation: deferred` means: the blocker is known, but independent authorized work remains, so continue that work before requesting human intervention. It grants no approval and does not resolve the blocker.

When no independent work remains, present all outstanding actionable questions in one grouped request. Notify earlier if an answer is needed by a concrete deadline. An escalation must identify an actual missing input, access, approval, or material choice; a technical failure alone is not a human blocker.

Global risks require immediate `halt`, not deferred escalation. Examples include revoked authorization, an unsafe or unidentifiable execution target, compromised credentials, uncertain unauthorized external effects, or compromised governing task/approval/protocol integrity. Scope the halt to the affected run; do not mutate unrelated systems or execution.

## 6. Human response is not blocker resolution

```text
response received -> validate resolution -> resolved | still open
```

Associate responses with specific blocker IDs. A partial response unblocks only the affected actions. A claimed configured key must be safely checked using authorized operations; do not expose it or invent an external test recipient. Approval requires an authentic human response applicable to the specific state/action; technical success cannot substitute for it.

A technical blocker may resolve without human input if restoration is independently established. A required human approval cannot be manufactured by a worker, reviewer, flag, or passing test.

After validation, continue automatically without asking the user to separately say “continue.” Apply incoming responses at a safe execution boundary; never spawn a second concurrent worker merely because a response arrived.

## 7. Roles and decision authority

```text
Worker -> checkpoint and evidence -> independent eval/review
       -> verified state -> Controller -> permitted next transition
```

- **Worker:** performs authorized work, reports claims, diagnostics, and blockers; cannot self-accept the task.
- **Verifier/reviewer:** independently checks outputs, evidence, semantics, dependency judgments, resolutions, and meaningful progress.
- **Controller:** applies deterministic transition rules to validated state, authorization, budgets, and safety conditions.

Semantic judgments do not become deterministic merely by placing them in the controller. The controller consumes verified judgments where necessary. Review logical boundaries, not every tool call. Unmet overall acceptance does not itself prohibit useful independent work.

Conceptual decisions/states:

| Name | Meaning |
| --- | --- |
| `continue` | Perform available authorized work. |
| `replan` | Select a materially different, justified approach. |
| `wait` | Await a specific external condition or human response. |
| `paused_budget` | Productive main work remains but requires a budget grant. |
| `halt` | Immediately stop run execution for a global safety or authorization reason. |
| `stop` | Terminate without full acceptance. |
| `finish` | Report independently confirmed task acceptance. |

These names do not silently redefine existing protocol decisions, particularly legacy `continue`, which currently requires a passing eval. Exact wire enums and execution/acceptance state schemas must be defined during implementation design.

## 8. Main and closure are independent execution authorities

### Main

The initial main budget bounds ordinary autonomous implementation and repair. Only explicit authorization extends it. Add grants; never reset cumulative counters or rewrite history.

### Closure

The initial run contract authorizes closure. Validated blocker resolution activates the applicable work without a separate budget confirmation. Closure does not consume main budget and, **by default, has no numerical budget limit**. Optional configured caps must be explicit; they are not the default agreed policy.

Unlimited closure does not grant unlimited scope or waive approval, safety, independent verification, or loop detection.

Closure is restricted to this causal chain:

```text
resolved blocker -> unblocked action -> required fixes and verification
```

Merely being necessary for final acceptance is insufficient: all task work can be described that way. Unrelated unfinished work remains main work. Newly discovered necessary repairs may qualify for closure when their causal connection is evidenced; closure is not restricted to a frozen list of commands.

### Example at main-budget exhaustion

| Work | State | Authority required |
| --- | --- | --- |
| Footer | Completed and verified | None remaining. |
| Send email | Missing key | Closure after validated B1 resolution. |
| Connect domain | Missing DNS access | Closure after validated B2 resolution. |
| Repair provider-error handling | Discovered by unblocked email verification | Closure with causal provenance. |
| Analytics integration | Not started, unrelated to blockers | Additional main grant. |

The mere existence of B1 or B2 cannot convert analytics work into unlimited closure.

## 9. Mandatory closure provenance

Every closure action must retain:

- The originating blocker ID.
- The action that was unblocked.
- For a repair or verification, its parent action and why the additional work is necessary.
- Evidence references supporting the causal relationship.

```json
{
  "id": "fix_email_error_handling",
  "scope": "closure",
  "provenance": {
    "blocker_id": "B1",
    "unblocked_action_id": "send_email",
    "parent_action_id": "verify_email_delivery",
    "reason": "Verification exposed incorrect handling of provider errors",
    "evidence_refs": ["email-verification.json"]
  }
}
```

The controller must enforce this boundary using validated provenance, not accept an unsupported worker label. Without an established causal chain, the action remains main work.

## 10. Budget ledger and continuation in the same run

Represent grants durably rather than resetting limits:

```json
{
  "grants": [
    {"id": "G1", "scope": "main", "maxCycles": 10, "reason": "Initial budget", "authorizedBy": "initial-contract"},
    {"id": "G2", "scope": "closure", "maxCycles": null, "reason": "Closure policy", "authorizedBy": "initial-contract"},
    {"id": "G3", "scope": "main", "maxCycles": 10, "reason": "Additional main cycles", "authorizedBy": "user-response-reference"}
  ]
}
```

Here G3 is an additional ten cycles, not a replacement total. Record consumption and grant application sufficiently to prevent double-spending or replay of the same authorization. `null` denotes no numerical cap, not arbitrary action authority. An authorization reference must point to real authority; a model-supplied string does not create it.

| Situation when main budget is exhausted | Controller behavior |
| --- | --- |
| No blockers; unfinished productive main work | `paused_budget`; request an additional grant. |
| Only blocked actions and their required completion remain | `wait`; validate resolutions, then closure. |
| Blockers plus unrelated unfinished main work | One request containing blocker questions and a distinct main-extension request. |
| Acceptance already independently confirmed | `finish`; no additional work needed. |
| No productive work, justified experiment, or specific wake event | `stop` with diagnosis, without PASS. |
| Global safety risk or authorization withdrawal | `halt` regardless of budget. |

A late response does not automatically restart an explicitly stopped/cancelled run. Waiting or budget-paused runs resume through validated transitions, not duplicate launch.

## 11. Durable waiting and reminders

Human waiting is indefinite by default and requires no active worker. It consumes no work cycles or model-execution budget. An earlier overall wall deadline must not silently terminate this human-wait policy; bound active operations separately and define clock accounting explicitly.

Keep state durable and provide reminders. A wait must have a specific wake source: human response, resource-restoration signal, or an arranged bounded recheck. Do not poll with paid worker turns. Explicit cancellation prohibits automatic continuation.

Before resuming, reconcile and check whether environment, evidence, approvals, and target identity remain applicable. Reminder cadence, channels, deduplication, cancellation, and re-entry mechanics require implementation specifications; reminders must not repeatedly invoke models or replay worker execution.

New blockers discovered during closure enter the same registry. Continue available work, group remaining questions, and resume after validated resolutions. A new blocker grants neither new scope nor a fresh budget. Its underlying action must still satisfy main/closure authority rules.

## 12. Evidence-based progress and loop detection

Detect lack of productive prospects, not simply lack of success. A failed attempt can provide meaningful information.

| Observation | Assessment |
| --- | --- |
| Action independently passes | Verified progress. |
| Blocker resolution is validated | Verified progress. |
| New diagnostic evidence narrows the cause | Informative attempt. |
| Materially different justified hypothesis yields useful evidence | Potentially informative attempt. |
| Same operation, equivalent conditions, same error | No progress. |
| Reworded plan | No progress. |
| Code changed but observed behavior did not | Not sufficient by itself. |
| Waiting for a person or external resource | Not applicable to execution-progress assessment. |

Keep attempts tied to actions, strategy, prior-state identity, outcome, and evidence:

```json
{
  "actionId": "send_email",
  "strategy": "Test whether provider rejection is caused by sender configuration",
  "stateBefore": "state-reference",
  "outcome": "diagnostic-result-reference",
  "evidenceRefs": ["provider-diagnostic.json"]
}
```

```text
Confirmed progress?
  yes -> continue
  no -> justified next experiment?
          yes -> attempt
          no -> action stalled
```

A new strategy must identify the hypothesis, material difference, evidence it can obtain, and how the result changes the next step. Cosmetic command changes do not evade loop detection. Equivalent retries require a reason to expect changed conditions; justified transient retries may use backoff and bounded active retry behavior.

`stalled` belongs to an action. Continue independent work. Stop the run only when no available work, justified experiment, or concrete wake event remains. Do not invent a human blocker merely to ask the user “what should I do?”

A qualitative loop detector must itself be independently evidence-based; a lack of PASS alone cannot justify stopping. Exact attempt-fingerprint and assessment mechanics require implementation design.

## 13. Run identity, worker sessions, and reconciliation

One logical run retains its `runId`, history, blockers, evidence, decisions, grants, and accumulated counters across waits, extensions, worker restarts, and new Pi sessions.

```text
PPP Run
  worker A: main work
  paused_budget
  additional main grant
  worker B: continued main work
  wait: B1 and B2
  worker C: closure
```

Resuming the same run does not require retaining the same Pi process or context. Before restoring a worker, the controller must reconcile durable state, verify execution ownership, exclude concurrent workers, establish environment freshness, and determine outcomes of unfinished operations.

Never blindly replay an external action with an uncertain result. A replacement session must restore the applicable task context, grants, restrictions, blocker state, and evidence; it must not restart the task from scratch.

## 14. Acceptance and legacy compatibility

`finish` requires independently verified acceptance of all required criteria. `blocked`, `not_tested`, and unknown are never PASS. Evidence schemas and existing screenshots are not semantic or visual acceptance. Native completion and exit 0 are lifecycle/check signals only.

After implementation, new runs use an explicitly versioned contract for this execution model. Old runs remain on their original protocol through a legacy adapter; do not rewrite their TASK, evaluator, state, decisions, approvals, or budgets. Exact schema versions, compatibility adapters, migration restrictions, transport messages, and CLI names must be specified before implementation.

Preserve run/cycle/hash identity checks, independent fresh evals, durable delivery records, duplicate-launch refusal, approval authenticity, and the prohibition on unauthorized external writes. Controlled session restoration under this model is a reconciled transition, not blind duplicate launch or an implicit extension of legacy finite bounds.

## 15. End-to-end example

A task authorizes a website with a form, Resend delivery, and a domain connection.

1. During main work the worker discovers no Resend key and records B1 as deferred.
2. It finishes the independent footer and other available work.
3. DNS access is unavailable; it adds B2 without overwriting B1.
4. Independent checks run. The completed footer is verified; overall acceptance remains pending.
5. No available work remains. PPP sends one request for key configuration and DNS access, saves state, and waits without an active worker. Reminders do not consume worker cycles.
6. In the morning the user reports both conditions addressed.
7. PPP validates each resolution, reconciles execution state, and automatically starts the applicable closure actions in the same run, even if main budget was exhausted.
8. Necessary causal fixes and checks remain closure work. Unrelated unfinished analytics, if in scope, requires a main extension when its budget is exhausted.
9. If the key is invalid, B1 stays open while independent B2 work can proceed. New genuine blockers enter the same registry.
10. When all required criteria are independently confirmed, the controller records `finish`. Otherwise it preserves an honest pending/partial/failed acceptance outcome with the appropriate execution state.

## 16. Agreed invariants

1. **Run identity persists.** Budget extension, waiting, worker restart, and a new Pi session do not create a new logical run.
2. **Main extension is explicit.** Add ledger grants without resetting accumulated counters.
3. **Closure is pre-authorized.** Validated blocker resolution activates corresponding work without another budget approval.
4. **Closure is causally bounded.** Resolved blocker -> unblocked action -> required fixes/verification; other work remains main.
5. **No numerical cap does not mean no control.** Scope, approvals, safety, and loop detection always apply.
6. **Worker recovery requires reconciliation.** No parallel execution or blind repetition of uncertain external actions.
7. **Stalled is action-local.** Stop the run only if there is no available work, justified next experiment, or concrete wake event.
8. **Finish requires confirmed acceptance.** Neither budget exhaustion, blocker resolution, nor native worker completion is sufficient.

Mandatory closure provenance makes invariant 4 enforceable rather than merely declarative.

## 17. Implementation handoff and regression requirements

This architectural agreement authorizes documentation, not a worker launch or an implementation by itself. Before coding, define a bounded implementation plan covering controller state transitions, durable schemas, action and blocker validation, grants and consumption, closure provenance, attempts, resolutions, reconciliation, legacy adapters, and reminder delivery. Do not add a separate general-purpose scheduler merely to support action lists.

Target regression coverage:

- Missing Resend key does not prevent completion of the independent footer.
- Multiple blockers persist, deduplicate, and produce grouped questions.
- Partial or invalid human responses resolve only validated blockers.
- Technical restoration cannot manufacture human approval; existing applicable approval is not requested again.
- Main exhaustion supports explicit extension in the same run without counter reset.
- Resolved blockers permit authorized closure after main exhaustion, but unrelated analytics cannot enter closure.
- Closure fixes require validated causal provenance; new blockers do not grant extra scope.
- Indefinite waiting and reminders create no active worker/model polling or duplicate continuation.
- Informative failures permit new justified experiments; equivalent futile retries become action-local stalled states.
- Resumed sessions reconcile ownership and uncertain effects; duplicate workers and blind external replay are refused.
- Halt/cancellation takes precedence over late responses and queued work.
- Final acceptance remains independent from execution completion, report validity, and passing individual checks.
- Legacy CLI/config/receiver contracts and frozen runs retain their original semantics.

Run the applicable repository protocol, receiver, and installation checks for implementation changes. Unit tests do not establish live acceptance. Any live model runs, installation changes, commits, or external mutations require their applicable authorization.
