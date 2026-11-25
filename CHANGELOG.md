# Changelog

## 0.1.2 - 2026-11-25

- Make `pi install npm:pi-ping-pong` the primary installation command; Git remains an alternative.
- Maintainers: publish to npm from a pushed `v*` tag with GitHub Actions trusted publishing.

## 0.1.1 - 2026-11-25

- Add `npm:pi-ping-pong` as an alternative Pi package source, with the receiver, skill, runtime scripts, and operational docs. Git installs and the standalone Codex skill remain available; Python remains a separate prerequisite.

## 0.1.0

First tagged release of the Pi package. The project was already available from Git before this release.

- Run bounded Pi Goal, Ralph, and ping-pong workflows with independent review.
- Continue useful work from concrete reviewer feedback; distinguish unverified delivery from acceptance.
- Work in an existing project, including uncommitted changes, with retained run evidence.
- Install and update as a Pi Git package, with a separate skill-only installation option for Codex.
- Report observed token usage where available; partial measurements are not billing totals.

## Before versioned releases

- `b86a950`: introduced bounded reviewer-driven execution, replacing the separate evaluator workflow. Evaluator-era runs cannot be resumed by the new runtime.
- `015a5bf`: introduced project-local Pi run storage, while retaining discovery of legacy runs.
- `f20ef72`: introduced best-effort observed Ralph Worker token accounting.
- `b923b42`: clarified reviewer continuations for concrete gaps rather than uncertainty alone.
- `42653c8`: completed Git package installation and migration guidance.

These commits mark development milestones, not releases published at the time. The `milestone/bounded-review` Git tag identifies the architectural transition at `b86a950`.
