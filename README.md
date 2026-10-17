# Pi Ping Pong

Bounded Pi workers, independent evaluations, and checkpoint feedback in the launching Codex or Pi session. One skill; choose `mode: goal` or `mode: ralph` in the run config.

Worker → checkpoint + fresh eval → reviewer queue → decision → worker. The launching turn ends after confirmed start; a queued message starts the review later. Full worker logs are not copied into the reviewer context.

## Status

Local working prototype, prepared for later extraction into a public repository. Original Goal/Ralph and Codex/Pi queue routes passed live PING → revise → PONG → complete tests. The renamed package is checked with local automated tests; a new live run is not implied. Known limitation: the bridge may stop Goal at the first `agent_settled` without `goal_wait`, although native Goal remains active and begins another turn. This project is not affiliated with Pi or OpenAI.

## Requirements

- POSIX host (the bridge uses `fcntl` and process groups), Python 3.10+, Node.js, authenticated `pi` CLI with RPC support. Windows native support is not implemented.
- Installed Pi Goal and Ralph extensions exposing `/goal`, `goal_wait`, `goal_complete`, and `/ralph` as used by the bridge. These vendor extensions are not bundled.
- For Codex review: a running authenticated Codex host with `codex queue --thread ... --model ... --message ...` support and the target chat ID. `exec resume` conflicts with an active desktop writer.
- For Pi review: the bundled receiver extension loaded in the original reviewer session, with its configured model selected.
- Task-specific dependencies and access for the worker and evaluator. Both agents must see the same filesystem paths. The host must remain awake and online.

Tested predecessor environment: Pi 1.3.0 on macOS. Other versions/platforms require verification; no universal compatibility claim.

## Install

From this directory:

```sh
python3 scripts/install.py
```

Installs the skill to `~/.agents/skills/pi-ping-pong` and the receiver to `~/.pi/agent/extensions/pi-reviewed.ts`. Existing differing files are backed up before replacement. Reload the reviewer Pi with `/reload`. Do not load a second copy of this receiver alongside the installed one.

For a custom skill directory, pass `--skills-dir /absolute/skills`; set `PI_PING_PONG_BRIDGE=/absolute/skills/pi-ping-pong/scripts/bridge.py` in the reviewer Pi environment. This package does not change Goal limits, credentials, or provider configuration.

## Use from Codex

Invoke `$pi-ping-pong` and specify Goal or Ralph, the task, acceptance criteria, worker/reviewer models, and finite bounds. The agent prepares an isolated run directory containing `TASK.md`, `config.json`, and an independent evaluator. Follow [the run contract](references/reviewed-runs.md) for the exact schema and decision commands.

```sh
python3 "$HOME/.agents/skills/pi-ping-pong/scripts/bridge.py" run --config /absolute/run/config.json
```

The launcher must survive the chat turn ending. Confirm `bridge-status.json` records a running worker before ending the turn. Do not stream logs or repeatedly poll using model turns.

## Use from Pi

Prepare the same config, select the configured reviewer model, then:

```text
/reviewed-run /absolute/run/config.json
/reviewed-status
```

The receiver binds the launching session automatically. `mode=goal` keeps a single worker session waiting at logical checkpoints. `mode=ralph` runs one native iteration per review boundary with shared outputs. No vendor package is patched. These commands do not change ordinary standalone `/goal` or `/ralph` behavior.

## Acceptance and escalation

- `continue`: independently verified intermediate result; eval passed.
- `revise`: repairable failure within scope, with specific feedback.
- `complete`: all requirements verified, ready checkpoint, fresh eval passed.
- `wait_human`: actual missing access/secret, approval, or material user choice.
- `stop`: no authorized useful continuation.

Exit 0 and native completion statuses alone never prove task success. Visual tasks need visual acceptance as well as file/geometry checks. Missing initial outputs mean bootstrap, not human escalation. Keep checkpoints compact; default `max_evidence_files=20` is configurable and counts top-level references, not all artifacts or tokens.

Cycle/time bounds, repeated identical failure, malformed protocol, changed evidence or ambiguous delivery stop the run. Automatic crash recovery is not implemented: inspect saved evidence and delivery state before any explicitly authorized recovery. Never silently replay an existing directory or reset its limits.

## Development

```sh
python3 -B scripts/test_bridge.py
node scripts/test_pi_receiver.mjs
```

Receiver tests use the installed Pi package's `jiti` loader. Set `PI_PACKAGE_JSON` to its absolute package.json path for a different installation. Tests use fake worker/queue APIs and no paid model calls. See [AGENTS.md](AGENTS.md) for maintenance invariants.

## Privacy and publication

Keep run configs, sessions, logs, screenshots, receipts, tokens and customer data outside this repository. Runtime scope restrictions are cooperative contracts, not an OS sandbox. Never put secrets into checkpoint feedback or chat.

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Artem Litvinko. Before public release, inspect the exact tracked files and dependency provenance. This package contains no run artifacts or personal host paths. No remote repository, commit, push or publication is created by setup.
