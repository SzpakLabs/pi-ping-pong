# Evaluator removal: preparation migration

Current preparation writes **TASK.md and config.json only**. No task-specific eval.py, eval_argv, evaluator helper, preflight or source-repair loop is generated or invoked.

Worker implements the task and runs its ordinary tests, retaining commands, exits, output and relevant artifacts. Independent Reviewer sees those results and assesses only remaining judgment questions and concrete defects. Core validates the existing action/criterion schema, identities, evidence, scope, dependencies and budgets before deciding. Unknown evidence is not another Worker iteration; unavailable review does not hide available work or stop independent authorized actions.

Config remains protocol 2/schema 1, without eval_argv. Headless Reviewer returns decision/feedback and an `assessment` with the existing action/criterion fields. See [protocol](action-scoped-protocol.md) and [operational setup](../references/reviewed-runs.md).

Evaluator-era configs (including protocol 1) and already-launched evaluator runs cannot resume on this runtime. They are left unchanged; Git history contains the previous runtime. No automatic migration, artifact deletion or silent acceptance-semantic change. Receiver aliases, session entries, status and new-run CLI paths remain.

The old evaluator helpers, fixtures, preflight tests and evaluator-based smoke preparator were removed with the mechanism, not replaced by another role or gate. Existing historical docs/run artifacts are observations of the old lifecycle, not instructions to recreate it. Current manual cases are in [manual E2E](manual-e2e.md); no live model run is implied by local checks.
