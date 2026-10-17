# Pi Ping Pong

> **TL;DR:** Install or update the receiver, then use Pi. Replace `<run-name>` with your chosen lowercase kebab-case name; do not type the angle brackets.
>
> ```text
> /reload
> /ppp
> /ppp <run-name>
> /ppp-status
> ```
>
> `/ppp` opens the current project's runs menu, or asks for a name if there are none. A new name reserves a private directory and prepares the task/config/eval without starting the worker. Reusing that name after preparation is the explicit launch action if the run is ready; a previously launched run shows status and is never launched again. See the [full Pi quick start](#quick-start-reviewer-in-pi).
>
> **Goal lifecycle status:** Regression tests and a live three-cycle Goal run verified checkpoint delivery, reviewer feedback, continuation, and final completion in the current development environment. This does not establish compatibility with other versions or environments.

Pi Ping Pong coordinates a **worker** and a separate **reviewer** around bounded Goal or Ralph work. The worker changes files; the reviewer checks the result and a fresh, independent evaluation (eval), then returns specific feedback. The worker can continue or revise within configured cycle and time limits.

This replaces manually copying worker summaries, files, and review notes between agent sessions. It routes compact checkpoints to the reviewer; it does not copy full worker logs into the review request.

See the [development roadmap](ROADMAP.md) for proposed milestones, acceptance gates, and current evidence limits.

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

- A POSIX host, Python, Node.js, and the `pi` CLI with RPC support. The bridge uses POSIX `fcntl` and process groups; native Windows support is not implemented.
- A reviewer/supervisor session in either Pi or Codex. Configure the reviewer provider/model separately from the application or CLI: **Codex is the application/CLI hosting a reviewer session, not a model ID.** Codex is not required for the Pi-only review route.
- Pi Goal and Ralph extensions installed on the host. The bridge defaults to the packages below; they are not bundled. It expects `/goal`, `goal_wait`, `goal_complete`, and `/ralph`. You can configure an extension path in the run config.

| Component | Minimum requirement established here | Current development environment | Upstream |
|---|---|---:|---|
| Python | 3.9+ (the bridge uses `pathlib.Path.is_relative_to`, available since Python 3.9); POSIX required | 3.15.0a1 (alpha) | [Python](https://www.python.org/) |
| Node.js | 22.19.0+ (Pi package and installed core dependencies declare `engines.node >=22.19.0`) | v26.6.0 | [Pi](https://github.com/earendil-works/pi) |
| Pi CLI | RPC-capable; no minimum CLI version is established here | 1.3.0 | [Pi](https://github.com/earendil-works/pi) |
| Codex CLI | No minimum version established; `codex queue` must exist and work for the target session | `codex-cli 0.156.1` | [Codex CLI](https://developers.openai.com/codex/cli/) |
| Goal | No minimum version established | `@narumitw/pi-goal` 0.54.11 | [Package source](https://github.com/narumiruna/pi-extensions/tree/main/packages/pi-goal) |
| Ralph | No minimum version established | `@lnilluv/pi-ralph-loop` 2.1.0 | [Package source](https://github.com/lnilluv/pi-ralph-loop) |

Minimums above are based on APIs used by this code or installed package `engines` metadata; the right column records versions observed in the current development environment, not minimums. Other versions and combinations are not claimed compatible. For Codex review, check `codex queue --help` on the host: the bridge calls `codex queue --thread ... --model ... --message ...`, and a version string alone does not establish that subcommand or target-session access. **The Goal lifecycle fix is covered by deterministic regression tests; no new live Goal run has been performed, so the route is not live-verified.** Pi's versioned npm install syntax is `pi install npm:<package>@<version>`; for example:

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

## Development checks

From the repository root, install development dependencies with `npm ci` and `uv sync --locked`. Run `npm run check` before real launches or commits; it runs lint, TypeScript checking, Ruff, and both protocol/receiver tests, collecting all command failures. An optional pre-commit hook runs the same gate. Opt in locally with `git config --local core.hooksPath .githooks`; the installer does not configure Git.

## Quick start: reviewer in Pi

1. In the Pi conversation, provide the task and any known acceptance criteria, project, and allowed paths. After installing/updating the receiver, run `/reload` in an existing session.
2. Run `/pi-ping-pong` (short alias `/ppp`). With existing project runs, a native menu lists their local states and offers **Create a new run**. With no runs, Pi asks for a readable name. Project root is the Git top-level; outside Git, Pi asks you to confirm the current folder or the private fallback.
3. Replace `<run-name>` with your chosen lowercase kebab-case name; do not type the angle brackets. Run `/ppp <run-name>` for a new name. It reserves `<project-root>/.pi-ping-pong/runs/<run-name>/` privately, then sends a preparation prompt to the current model. The model reuses the conversation and asks only for missing inputs; this is prompt-based preparation, not a fully automatic wizard. Choose the worker provider/model explicitly. The name identifies the run and is not its task description. Preparation writes no config placeholder and does not start or attach a worker. Review the generated TASK, independent evaluator, config, paths, models, and finite limits.
4. After preparation, run `/ppp <run-name>` again to explicitly launch that same name if it is ready, or select it in the menu and choose **Launch**. A previously launched run shows status and is never launched again; use another name for new work. Menu row selection alone never launches. The explicit config-path form is also supported as an advanced route below.
5. Use `/pi-ping-pong-status` (short alias `/ppp-status`) to inspect local named project runs and runs attached to this Pi session. `/reviewed-status` remains an equivalent alias. Status/menu inspection does not call models or run the evaluator.

Named runs live under `.pi-ping-pong/runs/<name>/`. The folder name is safe lowercase ASCII kebab-case (up to 48 characters); `config.json` contains a separate unique UUID `run_id`. The receiver creates the run directory with mode 0700 and its draft marker with mode 0600; preparation must keep TASK/config/eval files mode 0600. This repository ignores `.pi-ping-pong/`. In another Git project, add `.pi-ping-pong/` to that project's `.gitignore` first; preparation refuses to save if Git does not ignore the run path. Outside a Git project, choose and confirm the current folder or explicitly confirm the private fallback at `~/.pi/reviewed-runs/named/<name>/`. Existing legacy runs in `~/.pi/reviewed-runs/<UUID>/` remain untouched and can still be launched by explicit path.

### Advanced: launch an existing config by path

`/pi-ping-pong <path>/config.json` accepts an existing absolute or Pi-working-directory-relative path; `/reviewed-run` uses the same handler. A nonexistent explicit path is an error, never a request to create a named run. Legacy runs outside the project directory are not migrated. The shared launcher retains its model/session binding and duplicate-launch refusal.

After launch, the worker runs in a separate Pi RPC session. Checkpoints return as follow-up messages to the launching reviewer session. The reviewer examines the request and evidence; the bridge delivers its decision to the worker. Repeat only within configured limits.

Commands register during extension loading, without calling runtime-only APIs. Pi resolves duplicate extension command names with numbered invocation names (for example, `/ppp:1` and `/ppp:2`); inspect the `/` menu for the available names and any prompt or built-in conflicts. Skill commands use the separate `/skill:<name>` form. `/reviewed-run` and `/reviewed-status` remain compatible aliases.

## Quick start: reviewer in Codex

1. Ask the agent in the target Codex chat to prepare the run. Example **request to the agent**:

   > Prepare a Pi Ping Pong run for **[task]**. Use **[Goal or Ralph]**, worker model **[available model ID]**, reviewer model **[available model ID]**, and these acceptance criteria: **[criteria]**. Choose finite cycle and time limits. Create a private run directory containing `TASK.md`, `config.json`, and an independent eval. Do not start the run yet; show me the actual config path and limits.

2. Review the generated files and limits. The agent should prepare `TASK.md`, `config.json`, and a task-specific eval that runs independently of worker outputs. See [the full config and protocol](references/reviewed-runs.md); do not copy a placeholder path as though it exists.
3. In the shell on the host with Pi, the bridge, and the Codex host available, run this **shell command**, replacing the placeholder with the actual `config.json` path:

   ```sh
   python3 "$HOME/.agents/skills/pi-ping-pong/scripts/bridge.py" run --config <actual-run-directory>/config.json
   ```

   Confirm the run reports a running worker before ending the launch turn. The Codex reviewer receives a queued checkpoint in the configured existing chat, reviews the eval and evidence, then records a decision; the bridge returns that decision to the worker. `codex queue` availability and target-chat access are required as described above.

## Review from your phone with Codex Remote

When the supported Codex Remote/mobile workflow exposes the configured existing Codex chat, a Pi worker and bridge running on a connected host can send a checkpoint to that chat. The reviewer in that session checks the checkpoint and evidence, then returns a decision; genuine access questions or material choices are returned there too. See OpenAI's [Codex on mobile](https://learn.chatgpt.com/docs/mobile) and [Remote connections](https://learn.chatgpt.com/docs/remote-connections) documentation for the product's connection prerequisites; configure remote access and authentication separately, following the current official guidance. This README does not provide a setup procedure or guarantee that a particular session is exposed remotely.

The phone does not start the host's local Pi processes by itself. The host must stay powered on, reachable, and awake; remote access can stop if the host or app is unavailable. Queue delivery does not replace independent evidence review or the configured evaluator. A Pi-only reviewer session does not become available through Codex Remote automatically. Cycle/time limits, duplicate-launch rules, and other run budgets still apply.

## Limits and safety

- Runs have finite cycle and time limits. Exhaustion is not success. Automatic crash recovery is not implemented; inspect saved state before any explicitly authorized recovery.
- Ask a person only for a real missing input/access, required approval, or material choice. Do not invent approval, request secrets in chat, or silently reset limits.
- Keep private run artifacts outside tracked source/Git. The project's ignored `.pi-ping-pong/` run directory is allowed; keep secrets, sessions, logs, screenshots, receipts, tokens, and customer data out of tracked files and never commit them. Runtime scope restrictions are cooperative, not an OS sandbox.
- The worker and reviewer need shared filesystem visibility; keep the host online/available. Ambiguous delivery must be inspected rather than automatically resent.
- Running a task does not grant permission to commit, push, deploy, or publish.

**Claude Code / Claude remote workflows:** planned investigation; not implemented or validated.

## Development and validation

Run the local tests from the checkout:

```sh
python3 -B scripts/test_bridge.py
node scripts/test_pi_receiver.mjs
```

They use fake worker/queue APIs and do not require paid model runs. A passing unit test is not live-run acceptance. See [AGENTS.md](AGENTS.md) for maintenance invariants and [reviewed-runs.md](references/reviewed-runs.md) for configuration, protocol, recovery, and reviewer transport details.

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Artem Litvinko.
