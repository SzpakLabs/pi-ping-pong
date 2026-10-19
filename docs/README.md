# Documentation

Keep supplementary project documentation here rather than in the repository root.

## Start here

- [User guide](GUIDE.md): setup, daily use, troubleshooting and development checks.
- [Roadmap](ROADMAP.md): proposed delivery order and evidence gates.
- [Target architecture](ARCHITECTURE.md): desired boundaries, ownership and invariants.
- [Architecture diagrams](architecture-diagrams.md): target-design diagrams, not implementation evidence.
- [Start/status dogfooding](start-status-dogfooding.md): bounded development notes and experimental workflow.

## Placement rules

- Root: `README.md` (entrypoint), `AGENTS.md` (maintenance instructions), `SKILL.md` (agent skill entrypoint), license and tooling configuration.
- `docs/`: guides, design decisions, feature specifications, diagrams and development notes. Add new supplementary documents here and link them from this index.
- `references/`: operational references directly consumed by the skill, currently the [reviewed run contract](../references/reviewed-runs.md). Preserve its stable path.
- Private run artifacts: ignored run storage, never this documentation directory.

When bringing `worktree-workflow.md` from its owning branch, place it in `docs/` and update its links and this index. It is not present in this checkout; this note does not claim it was imported or implemented.

Moving documents does not change implementation status, authorization, architecture ownership or roadmap priority. Relative links resolve from the document's directory; shell examples continue to assume repository root unless explicitly stated otherwise.
