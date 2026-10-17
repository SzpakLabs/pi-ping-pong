# Maintaining Pi Ping Pong

This repository contains one shared bridge for Goal and Ralph, plus a Pi queue receiver. Keep mode differences in the existing implementation; do not fork the protocol per launcher.

- Read SKILL.md and references/reviewed-runs.md before changing lifecycle behavior.
- Preserve run/cycle/hash identity checks, independent fresh evals, finite bounds, durable delivery records and duplicate-launch refusal.
- Never equate exit 0 or native completion with acceptance. Passing geometry does not establish visual correctness.
- Human escalation requires an actual missing input, access, approval or choice. Never invent approval or silently reset limits.
- Keep existing CLI/config contracts and Pi receiver session entries compatible. Explain migrations when compatibility cannot be retained.
- Do not patch vendor packages or change global Goal/Ralph settings as a side effect.
- Keep private artifacts outside source; use synthetic fixtures. Simulated people must have Test in their names.
- Run python3 -B scripts/test_bridge.py and node scripts/test_pi_receiver.mjs for protocol/receiver changes. Live model runs require task authorization; unit tests do not imply live acceptance.
- Install development checks with `npm ci` and `uv sync --locked`; run `npm run check` before real launches or commits. This repository does not configure Git hooks automatically. To opt in locally, run `git config --local core.hooksPath .githooks`.
- Inspect the exact diff and git status. Do not commit, publish or push without authorization. License choice belongs to the owner.

While this package lives inside codex-context/skills, this directory is canonical. Install runtime copies after changes; do not maintain a separate runtime implementation. Legacy pi-codex-handoff and pi-goal-handoff are compatibility entrypoints.
