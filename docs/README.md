# Documentation

## Use Pi Ping Pong

- [User guide](GUIDE.md): setup, launch, models and transports, status, human input, and validation limits.
- [Current architecture](ARCHITECTURE.md) and [diagrams](architecture-diagrams.md): component ownership, mode boundaries, review decisions, and recovery.
- [Run contract](../references/reviewed-runs.md) and [protocol 2 / schema 1](action-scoped-protocol.md): configuration, assessment schema, budgets, operations, and compatibility.
- [Headless Reviewer](headless-reviewer.md): separate reviewer session, evidence, failure handling, and Chat A reporting.
- [Project workspace](project-workspace.md): in-place edits, [private run storage](project-workspace.md#private-run-storage), Ralph storage, and limited launch comparisons/fallback discovery.
- [Evaluator-era compatibility](evaluator-preparation.md): prepare a new run; older configs and runs are not migrated.
- [Manual E2E](manual-e2e.md) and [private report template](manual-e2e-report-template.md): separate user-operated validation, not an acceptance claim.
- [Development checks](GUIDE.md#development-checks) and [maintenance instructions](../AGENTS.md).

## Agent configuration

- [Local issue tracker](agents/issue-tracker.md) and [domain documentation rules](agents/domain.md).

## Development history

These notes document earlier requirements, prototypes, and verification. Some use the removed evaluator lifecycle or propose future work that is not implemented. They do not override the current contract or establish live acceptance of this checkout.

- Design and planning: [roadmap v7](ROADMAP.md), [three-mode design](three-mode-target.md), [Worker/Reviewer pipeline note](mvp-pipeline.md), [observer separation](observer-reviewer-separation.md), and [autonomous-run integration plan](autonomous-run-integration-plan.md).
- Investigations: [start/status dogfooding](start-status-dogfooding.md), [permission friction](permission-friction-research.md), and [action-scoped execution](action-scoped-execution.md).
- Action-scoped implementation: [plan](action-scoped-implementation-plan.md), [implementation report](action-scoped-implementation-report.md), [verification](action-scoped-verification.md), and [independent audit](action-scoped-independent-audit.md).
- Earlier protocol-2 evidence: [F1/F2 hardening](protocol-2-f1-f2-hardening.md), [F3/F4 hardening](protocol-2-f3-f4-hardening.md), [regression audit](protocol-2-regression-audit.md), and [E2E gate remediation](protocol-2-e2e-gate-remediation.md).
- Historical smoke stand: [live E2E plan](protocol-2-live-e2e-plan.md), [Goal/Ralph readiness](protocol-2-goal-ralph-readiness.md) and [candidate manifest](protocol-2-goal-smoke-candidate.json), and [Goal preflight/result (NOT RUN)](protocol-2-goal-smoke-e2e-result.md).

Keep supplementary docs here and the agent's operational reference under `references/`. Private run artifacts stay in ignored run storage, not in `docs/`.
