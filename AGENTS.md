# Maintaining Pi Ping Pong

## Agent skills

### Issue tracker

Issues and specs are tracked as local Markdown under `.scratch/`.
See `docs/agents/issue-tracker.md`.

### Domain docs

This is a single-context repository.
See `docs/agents/domain.md`.

This repository contains one shared bridge for Goal and Ralph, plus a Pi queue receiver. Keep mode differences in the existing implementation; do not fork the protocol per launcher.

## Foundational product contract

One user prompt starts autonomous work toward the fullest achievable result. Worker executes and runs ordinary tests; independent Reviewer identifies actual gaps not established by those tests and route actionable corrections back to Worker within the existing finite budget. They exist to advance the task, not enforce internal ceremony.

- Continue every independent authorized action despite a missing input, access, approval, choice, or a failure in another part. Make ordinary reversible choices without asking. Once useful independent work is exhausted, deliver the created result and one grouped list of genuinely human-dependent gaps and their dependencies. The user need not monitor or answer intermediate routine questions.
- Internal JSON, schemas, evidence paths, evaluator/reviewer failures, and other role or transport errors must not by themselves discard or hide work, demand routine human intervention, or stop independent work. Repair or work around them within the existing budget; if verification cannot be completed, deliver the result with the exact limitation. Do not silently claim failed or missing checks passed.
- Assess the user's actual requirements and behavior. Do not invent product requirements, prescribed selectors, file formats, approvals, or acceptance gates for evaluator convenience. A valid negative assessment guides further work; do not retry it merely to obtain a positive verdict.
- Verification serves the user's result, not the reverse. Use unit tests and deterministic tools for checks they can establish; do not ask an evaluator or model reviewer to re-prove those checks routinely. Independent evaluation and review add evidence about the actual requested outcome where useful, not duplicate checks or prescribe incidental scenario details. A failed or unreliable evaluator is not proof that the product failed. Do not turn repair of verification, additional test fixtures, repeated reviews, or a live model test into a prerequisite for delivering available work. Report genuine verification limitations without inventing acceptance or weakening safety and identity checks.
- Distinguish delivery/completion of the available result from verified acceptance: report completed work, unverified items and unresolved gaps truthfully, including on budget exhaustion. Existing `finish`/acceptance semantics and CLI compatibility must not be silently redefined; implement any new completion behavior explicitly and compatibly.
- Preserve concrete safety and integrity protections: identity and ownership, finite cumulative budgets, no duplicate or uncertain external effects, and no false acceptance. These safeguards must not become invented product requirements or prevent delivery of existing results.

Existing implementation and historical documentation may not yet satisfy this contract. When changing them, resolve conflicts in favor of this product contract without silently weakening the concrete safety and compatibility requirements above. Tests must cover result delivery when internal verification fails, continued independent work, grouped human-dependent gaps, and repeated Worker corrections—not just protocol formatting.

- Read SKILL.md and references/reviewed-runs.md before changing lifecycle behavior.
- Preserve run/cycle/hash identity checks, independent hash-bound Reviewer assessments, finite bounds, durable delivery records and duplicate-launch refusal.
- Never equate exit 0 or native completion with acceptance. Passing geometry does not establish visual correctness.
- Human escalation requires an actual missing input, access, approval or choice. Never invent approval or silently reset limits.
- Keep existing CLI/config contracts and Pi receiver session entries compatible. Explain migrations when compatibility cannot be retained.
- Do not patch vendor packages or change global Goal/Ralph settings as a side effect.
- Keep private artifacts out of tracked source; ignored `.pi-ping-pong/` inside the existing worktree is valid for manual E2E. Use synthetic fixtures. Simulated people must have Test in their names.
- For user-operated E2E, follow docs/manual-e2e.md: ordinary installed Pi/subscription, existing worktree, report before preparation, three case prompts. Do not impose historical pinned-runtime/private-HOME/snapshot/profile-smoke gates. Keep old experiments as history; record actual failures and missing results without silently relaunching.
- Put supplementary documentation (guides, designs, feature specs and notes) in docs/ and link it from docs/README.md. Keep README.md, AGENTS.md and SKILL.md in the root; preserve references/reviewed-runs.md as the operational skill contract.
- Run python3 -B scripts/test_bridge.py and node scripts/test_pi_receiver.mjs for protocol/receiver changes. Live model runs require task authorization; unit tests do not imply live acceptance.
- Install development checks with `npm ci` and `uv sync --locked`. Fast checks: `bun run check:python` runs Ruff plus bridge and action-protocol tests; `bun run check:ts` runs ESLint, TypeScript and the Pi receiver suite. `bun run check` (also `npm run check` for compatibility) runs both fast groups, not the slow integration suites. Run `bun run check:bridge` only when changing action-bridge end-to-end behavior or contracts (worker/reviewer flow, wait/wake, cancellation, delivery, acceptance/evidence or launch behavior). Run `bun run check:faults` only when changing durable state/recovery, crash or replay boundaries, dispatch/ack races, leases, or process-tree cleanup. `bun run check:integration` runs both for broad changes spanning those areas. Docs-only changes need `git diff --check` and validation of changed local links/examples, not language suites. Before a real launch, run the fast combined check and only the integration check(s) applicable to changed behavior. Do not rerun unrelated suites just because a commit is planned. This repository does not configure Git hooks automatically. To opt in locally, run `git config --local core.hooksPath .githooks`.
- Inspect the exact diff and git status. Do not commit, publish or push without authorization. License choice belongs to the owner.

Evaluator-era runs and protocol 1 are not supported by the current lifecycle. Preserve their files unchanged; use Git history for the old implementation. Do not create task-specific eval.py, require eval_argv, repair a separate evaluator, or manufacture Worker corrections from unknown verification. No mandatory pre-work model review or repeated pre/post verification.

While this package lives inside codex-context/skills, this directory is canonical. Install runtime copies after changes only when the task authorizes installation; do not maintain a separate runtime implementation. Legacy pi-codex-handoff and pi-goal-handoff are compatibility entrypoints.
