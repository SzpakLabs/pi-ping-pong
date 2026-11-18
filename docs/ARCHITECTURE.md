# Current architecture

Pi Ping Pong is a local run controller around Pi, not a coding runtime or a separate evaluator. This page describes the current implementation. See the [diagram atlas](architecture-diagrams.md) for the main flows, the [run contract](../references/reviewed-runs.md) for configuration, and the [protocol](action-scoped-protocol.md) for state and review rules.

## Components and authority

| Component | Responsibility |
|---|---|
| [Pi receiver](../extensions/pi-reviewed.ts) / Chat A | Reserves named drafts, binds the launching session on explicit launch, shows local status, consumes the Pi inbox, and records confirmed addressed human responses. With headless review, Chat A reports Core's state; it does not review or accept the result. |
| [Core bridge](../scripts/bridge.py), [run loop](../scripts/action_bridge.py), and [action controller](../scripts/action_protocol.py) | Pin the task and config, select authorized work, own Worker/Reviewer lifetimes, retain evidence, validate judgments, account for cumulative use, and choose transitions. Keep durable state and refuse overlapping or duplicate execution. |
| Worker | Runs in Pi with one of three [execution modes](../README.md#execution-modes). Implements the scoped task and runs ordinary tests. A checkpoint is a claim with evidence references, not acceptance. |
| [Headless Reviewer](../scripts/headless_reviewer.py) | Fresh, separate Pi RPC session per review boundary with an explicit provider/model and read-only built-in tools. Uses retained evidence to assess task fit, omissions, and concrete defects. It cannot set acceptance or grant budget. |

Headless review is the new Pi preparation default. Optional Pi chat or Codex queue transports submit judgments to the same Core; they do not inherit the headless adapter's tool restrictions. Explicit provider extensions execute trusted code in their respective processes; neither the tool list nor cooperative ownership is a hostile-code sandbox.

## Work, review, and continuation

Initial work uses the recorded task, scope, actions, and dependencies without a pre-work model or evaluator. Ping-pong stops for review after a settled iteration. Goal and Ralph can handle multiple authorized actions inside one native result boundary; progress checkpoints there do not trigger mandatory reviews. Goal corrections reuse the same Pi history; new native windows and Ralph iterations remain subject to cumulative limits.

At a review boundary Core binds the run, cycle, current state, checkpoint (if any), and retained evidence to the request. Reviewer uses ordinary test results for what those tests establish and judges what remains. Core validates before recording and applying review; `endorse` submits an assessment, not a terminal outcome. A concrete fix or unfinished eligible action can justify further work within authority and remaining budget. Unknown alone cannot.

`finish` requires passing criteria, completed actions, assessed cycles, resolved blockers, and reconciled effects. If review is missing or unavailable, Core preserves available work and continues eligible work that does not depend on the held actions or uncertain operations, then reports the limitation. The specific `delivered_unverified` outcome means an applied review found no open defect or blocker but at least one criterion is still unknown/not tested; it is not the status of every review failure or partial result.

## Workspace, waits, and recovery

Worker operates on the selected project in place; [project run storage](project-workspace.md#private-run-storage) retains private run state, logs, and evidence. The [workspace notes](project-workspace.md) describe Ralph task storage, bounded fallback discovery, and the best-effort Git launch comparison for dirty/untracked-at-launch files. These are inspection aids, not complete snapshots or attribution of changes to Worker.

Core runs independent work before grouping genuine human requests and may pause for an explicit budget grant or a recorded resource event. Confirmed input is addressed to the same run; it is not automatic resolution or a budget reset. Reminders do not spend Worker/model turns. Resume/wake reconcile durable ownership, prior reviews, and operation effects before acting. An ambiguous external effect or attempted review is not blindly replayed. There is no implied permission to commit, push, deploy, or exceed task scope.

Run status and delivery records are separate from result acceptance. A failed report does not undo recorded acceptance; an enqueue receipt does not prove a report was read. No live-model compatibility or UI-close autonomy is established by these diagrams or the deterministic checks.
