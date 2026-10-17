---
name: pi-ping-pong
description: Run bounded Pi/Ralph or Pi Goal work from Codex or Pi, review logical checkpoints through the launching session queue, and return decisions automatically within scope.
---

# Pi Ping Pong

Keep the desktop Codex host running for mobile access. Use `codex queue --thread <exact-id> --model <explicit-model>` for delivery into its existing chat; `codex exec resume` conflicts with the desktop writer. Queue delivery is not itself an evaluation or a Pi wake signal.

## Launching from Pi

For an interactive Pi reviewer, load the bundled [Pi receiver](extensions/pi-reviewed.ts) and run `/reload` after installing/updating it in an existing session. `/pi-ping-pong` opens a local menu of runs at the Git top-level project's `.pi-ping-pong/runs/`; when none exist, it asks for a readable name. `/pi-ping-pong <kebab-name>` reserves a new private directory and sends the current model a preparation prompt, or offers to continue an incomplete run. Preparation reuses conversation context, asks only for missing data, requires an explicit worker model, and never launches or session-attaches a worker. `/pi-ping-pong <ready-name>` explicitly launches an unstarted ready run; a run with any launch record shows status and is never replayed. Menu selection alone never launches. `/ppp` aliases the launcher/menu command; `/pi-ping-pong-status` and `/ppp-status` share the local status handler. `/reviewed-run` and `/reviewed-status` remain compatible aliases. An existing absolute or relative `<path>/config.json` still launches through the same checks, including legacy runs under `~/.pi/reviewed-runs/`. Pi's `getCommands()` API is checked before registration; conflicting known extension/resource commands are skipped, while built-in TUI command names are not exposed by that API and must be checked in Pi's `/` menu. See [Pi receiver setup](references/reviewed-runs.md#pi-reviewer-transport) for project roots, private storage, Git ignore, model holds, and lifecycle.

Do not send into an active Pi by reopening its session file or writing transcript entries. Delivery happens inside its existing process through `pi.sendMessage(..., {deliverAs:"followUp", triggerTurn:true})`.

## Choose the run

- For a single final report, the existing one-shot Ralph launch plus fresh post-run eval and queued callback remains suitable.
- For reviewed automatic cycles, use [the shared bridge](scripts/bridge.py) and [its run contract](references/reviewed-runs.md). It supports `mode=ralph` and `mode=goal`. Read that reference before preparing a run.
- Goal keeps one Pi RPC session and calls `goal_wait` at each logical checkpoint. Ralph runs one native iteration per review boundary, preserving shared task outputs and separate iteration logs. This does not patch vendor packages or change all standalone `/ralph` runs.

## Review routing

- Review a finished logical deliverable, not every tool call or model response. Read the task, checkpoint, fresh eval and relevant artifacts; load full transcripts only for an actual diagnostic need.
- Passing intermediate result: `continue`. Recoverable in-scope failure: `revise` with concrete feedback. All requested results independently verified: `complete`.
- Missing key/access, actual approval gate or material user choice: `wait_human`, ask here, leave Pi waiting. Never ask the user to paste secrets into chat. Human approval must come from the user; a model decision cannot manufacture it.
- Repeated identical failure, exhausted cycle/time budget, ambiguous queue delivery or failed transport: stop with compact evidence and required next action. Never silently renew the budget or replay a run.
- Native Goal status and Ralph `iteration.completed`/exit 0 are lifecycle signals, not task success. Inspect reason, artifact coverage and eval before deciding. Goal may be waiting for either Codex or a human; keep those reasons separate.

## Before dispatch

Record exact chat, worker/reviewer models, task/work directory, eval command and finite bounds. Existing authorization to build/test or launch this scoped work is enough; do not ask for it again. Do not infer site writes, commit/push/deploy or publication permission.

Missing outputs on the first pass mean create them. Do not make a strict missing-output check a pre-work blocker. Strict evaluation happens after work and again at final acceptance. A partial report does not turn failed captures into success.

For browser work, load `browser-routing` inside Pi when installed, using tools available to Pi. Otherwise explicitly choose the available browser route in TASK.md. Prefer capable Node Playwright for exact viewports and file outputs; do not assume Codex MCP tools are shared. Capture readiness must cover the actual document or nested scroll container, not PNG existence alone.

After confirmed start, return the run directory/ID and end the chat turn. Do not stream Pi logs. The queued checkpoint starts a later Codex review turn; write its decision using the bridge `decide` command and end that turn. Routine decisions need no user response. On final return, distinguish complete, partial and blocked with evidence paths.

The host must stay awake/online. Scope and host filesystem access are cooperative contracts, not a security sandbox. Queue/file review transport is a small adapter around Pi's lifecycle; it does not replace Pi/Ralph's tools or Goal accounting.
