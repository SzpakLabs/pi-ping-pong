# Pi Ping Pong

> **TL;DR:** A worker performs the task; a reviewer checks each result and returns concrete feedback. Install this skill and receiver → run `/reload` in Pi → ask an agent to prepare a bounded run and `config.json` → run `/pi-ping-pong <actual-config-path>`. The config must exist first: this command launches a prepared run; it does not turn arbitrary task text into a config. See the [full Pi quick start](#quick-start-reviewer-in-pi).
>
> **Goal lifecycle status:** A lifecycle fix is covered by deterministic fake-RPC regression tests. A new live Goal run has not been performed, so Goal routing is not live-verified.

Pi Ping Pong coordinates a **worker** and a separate **reviewer** around bounded Goal or Ralph work. The worker changes files; the reviewer checks the result and a fresh, independent evaluation (eval), then returns specific feedback. The worker can continue or revise within configured cycle and time limits.

This replaces manually copying worker summaries, files, and review notes between agent sessions. It routes compact checkpoints to the reviewer; it does not copy full worker logs into the review request.

## Example workflow

For example, a worker adds tests, the independent eval runs them, a reviewer checks the changes and eval evidence, and sends concrete corrections back to the worker. The worker makes the next bounded revision and submits another checkpoint. This describes the workflow, **not a live run**. Choose model IDs available and authenticated in your own environment; names used in examples are not required model IDs.

| Term | Meaning |
|---|---|
| **Worker** | The Pi Goal or Ralph process that performs the task. |
| **Reviewer** | A separate model/session that examines the checkpoint, evidence, and eval result. |
| **Checkpoint** | The worker's compact summary and references to files for one review boundary. |
| **Eval** | A task-specific command run freshly by the bridge, independently of the worker. |

Model review complements eval; it does not replace it. A zero exit code is not proof that requirements or visual quality are satisfied, and a reviewer decision cannot accept a failed eval.

## Goal and Ralph modes

| Goal | Ralph |
|---|---|
| Keeps one Pi worker session and waits for review decisions at logical checkpoints. | Runs one native Ralph iteration per review boundary. Iterations share the task's `work/` outputs; each gets its own iteration directory. This is not a fully isolated sandbox. |

**Prototype status:** this is a local working prototype, not a release-readiness claim. The Goal lifecycle issue where an intermediate `agent_settled` ended the bridge cycle is covered by deterministic regression tests. A new live Goal run has not been performed; this fix does not establish that the Goal route is live-verified.

**Validation note:** the predecessor had live PING → revise → PONG → complete runs. Those runs do not establish live validation of this renamed/current repository. Local unit tests cover protocol behavior, not a live run.

## Requirements

- A POSIX host, Python 3.10+, Node.js, and the `pi` CLI with RPC support. The bridge uses POSIX `fcntl` and process groups; native Windows support is not implemented.
- Pi Goal and Ralph extensions installed on the host. The bridge defaults to the packages below; they are not bundled. It expects `/goal`, `goal_wait`, `goal_complete`, and `/ralph`. You can configure an extension path in the run config.

| Component | Current development environment | Upstream |
|---|---:|---|
| Pi | 1.3.0 | [Pi](https://github.com/earendil-works/pi) |
| Goal | `@narumitw/pi-goal` 0.54.11 | [Package source](https://github.com/narumiruna/pi-extensions/tree/main/packages/pi-goal) |
| Ralph | `@lnilluv/pi-ralph-loop` 2.1.0 | [Package source](https://github.com/lnilluv/pi-ralph-loop) |

These are versions present in the current development environment, not recommendations, a compatibility guarantee, or a claim that the packages were tested together. **The Goal lifecycle fix is covered by deterministic regression tests; no new live Goal run has been performed, so the route is not live-verified.** Pi's versioned npm install syntax is `pi install npm:<package>@<version>`; for example:

```sh
pi install npm:@narumitw/pi-goal@0.54.11
pi install npm:@lnilluv/pi-ralph-loop@2.1.0
```

These commands are examples only; this repository's installer does not install or update either dependency.
- Worker credentials and access for the selected provider, plus reviewer credentials for the selected reviewer model. Pi supports provider-specific OAuth/API-key authentication; configure it in Pi before running. Keep credentials out of run files and Git.
- Both agents must be able to read the same run/work files. The host must remain available while the run and review are pending.

**Reviewer in Pi:** load this repository's receiver in the original reviewer session, select the configured reviewer model, and keep that session available. The receiver uses Pi's extension APIs to deliver queued checkpoints to that session.

**Reviewer in Codex:** a running authenticated Codex host and an existing target chat are required. The bridge invokes `codex queue --thread ... --model ... --message ...`. `codex queue` is a Codex CLI subcommand, not a command provided by this repository; it is environment/version dependent and must be available in your installation. Do not assume every Codex setup has it. `codex exec resume` is not a substitute when the desktop host is already writing to that chat.

The bridge's default extension paths, supported platform, and CLI behavior are implementation details, not a promise that every Pi/Codex version or provider configuration works. See [the full run contract](references/reviewed-runs.md).

## Install

The intended clone URL is `https://github.com/SzpakLabs/pi-ping-pong.git`. Repository availability and publication are not asserted here. If the repository is available to you, clone it and install from the checkout:

```sh
git clone https://github.com/SzpakLabs/pi-ping-pong.git
cd pi-ping-pong
python3 scripts/install.py
```

The installer copies the skill to `~/.agents/skills/pi-ping-pong` and the receiver to `~/.pi/agent/extensions/pi-reviewed.ts`; differing existing files are backed up. In Pi, run `/reload` to load the receiver in an existing session. **Do not load a second copy of this receiver alongside the installed copy.** The installer does not install Goal/Ralph vendor packages or configure credentials.

## Quick start: reviewer in Pi

1. In your Pi session, ask the agent to prepare a bounded run. Example **request to the agent** (edit to suit your task):

   > Prepare a Pi Ping Pong run for **[task]**. Use **[Goal or Ralph]**, worker model **[available model ID]**, reviewer model **[available model ID]**, and these acceptance criteria: **[criteria]**. Choose finite cycle and time limits. Create a private run directory containing `TASK.md`, `config.json`, and an independent eval. Do not start the run yet; show me the actual config path and limits.

2. Review the generated task, criteria, and limits. Select the configured reviewer model in Pi.
3. In Pi, use these primary commands:

   ```text
   /pi-ping-pong <actual-config-path>
   /pi-ping-pong-status
   ```

   Compatible older names with identical behavior:

   ```text
   /reviewed-run <actual-config-path>
   /reviewed-status
   ```

   `/reviewed-run` is equivalent to `/pi-ping-pong`; `/reviewed-status` is equivalent to `/pi-ping-pong-status`. The config path is a placeholder: `config.json` must already exist. Status commands only inspect locally attached run status; they do not start a worker or call a model.
4. The worker runs in a separate Pi RPC session. Checkpoints return as follow-up messages to the launching reviewer session. The reviewer examines the request and evidence; the bridge delivers its decision to the worker. Repeat only within the configured limits.

## Quick start: reviewer in Codex

1. Ask the agent in the target Codex chat to prepare the run. Example **request to the agent**:

   > Prepare a Pi Ping Pong run for **[task]**. Use **[Goal or Ralph]**, worker model **[available model ID]**, reviewer model **[available model ID]**, and these acceptance criteria: **[criteria]**. Choose finite cycle and time limits. Create a private run directory containing `TASK.md`, `config.json`, and an independent eval. Do not start the run yet; show me the actual config path and limits.

2. Review the generated files and limits. The agent should prepare `TASK.md`, `config.json`, and a task-specific eval that runs independently of worker outputs. See [the full config and protocol](references/reviewed-runs.md); do not copy a placeholder path as though it exists.
3. In the shell on the host with Pi, the bridge, and the Codex host available, run this **shell command**, replacing the placeholder with the actual `config.json` path:

   ```sh
   python3 "$HOME/.agents/skills/pi-ping-pong/scripts/bridge.py" run --config <actual-run-directory>/config.json
   ```

   Confirm the run reports a running worker before ending the launch turn. The Codex reviewer receives a queued checkpoint in the configured existing chat, reviews the eval and evidence, then records a decision; the bridge returns that decision to the worker. `codex queue` availability and target-chat access are required as described above.

## Limits and safety

- Runs have finite cycle and time limits. Exhaustion is not success. Automatic crash recovery is not implemented; inspect saved state before any explicitly authorized recovery.
- Ask a person only for a real missing input/access, required approval, or material choice. Do not invent approval, request secrets in chat, or silently reset limits.
- Keep configs, sessions, logs, screenshots, receipts, tokens, and customer data outside this repository. Runtime scope restrictions are cooperative, not an OS sandbox.
- The worker and reviewer need shared filesystem visibility; keep the host online/available. Ambiguous delivery must be inspected rather than automatically resent.
- Running a task does not grant permission to commit, push, deploy, or publish.

## Development and validation

Run the local tests from the checkout:

```sh
python3 -B scripts/test_bridge.py
node scripts/test_pi_receiver.mjs
```

They use fake worker/queue APIs and do not require paid model runs. A passing unit test is not live-run acceptance. See [AGENTS.md](AGENTS.md) for maintenance invariants and [reviewed-runs.md](references/reviewed-runs.md) for configuration, protocol, recovery, and reviewer transport details.

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Artem Litvinko.
