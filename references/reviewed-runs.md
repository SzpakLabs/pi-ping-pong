# Reviewed run setup

For manual setup (advanced), use an isolated run directory on the host that owns Pi and can reach the target Codex app-server. Keep private artifacts out of Git, e.g. a project's ignored `data/raw/<run-id>/`. Both agents must see the same paths.

Create `TASK.md`, an independent task-specific `eval.py` outside worker outputs, and `config.json`. The bridge creates `work/`, `reviews/`, `sessions/` and the protocol contract. Report/checkpoint evidence paths are relative to `work/`; this directory is not a source checkout. TASK.md must explicitly identify any authorized project source paths outside `work/`. Workers may edit those paths directly, including project scripts, without copying the project into the run. Without explicit task authorization, authored outputs remain inside `work/`; cwd and Git ancestry do not grant write scope. The active run's config, task, evaluator, reviewer files, protocol state and preserved baselines remain protected. External source files cannot be listed directly as checkpoint evidence: use reports/manifests inside `work/`, and have the independent evaluator inspect the authorized source state. Never put secrets in prompts, checkpoints or review feedback.

Example config (substitute actual authorized values, no guessed thread IDs):

```json
{
  "run_id": "reviewed-pilot-unique-id",
  "mode": "goal",
  "thread_id": "exact-existing-codex-thread-id",
  "worker_provider": "openai-codex",
  "worker_model": "gpt-6-luna",
  "review_model": "gpt-6.1-sol",
  "thinking": "low",
  "task": "TASK.md",
  "eval_argv": ["python3", "/absolute/run/eval.py"],
  "max_cycles": 10,
  "cycle_seconds": 600,
  "review_seconds": 1800,
  "wall_seconds": 7200
}
```

These are example limits, not permission to spend the full budget. Match limits to the task and human availability. A wait consumes wall time but no model polling. Goal's installed automatic-work/no-progress limits remain enabled. Do not enable managed-run RPC globally: direct `/goal` and Pi's documented RPC transport suffice. No token budget is invented by the bridge.

For Pi preparation/readiness, `eval_argv` supports exactly these Python forms:

```json
["python3", "/absolute/run/eval.py"]
["python3", "-B", "/absolute/run/eval.py"]
```

A script path may also be relative; it resolves from the run's `work/` directory, which is the bridge's execution working directory. No other interpreter, Python flag, or argument layout is inferred. Readiness checks the script path and private-file protections without executing it.

Run:

```sh
python3 "$HOME/.agents/skills/pi-ping-pong/scripts/bridge.py" run --config /absolute/run/config.json
```

Start from an execution facility that survives ending the Codex turn. Confirm `bridge-status.json` shows `running` and a Pi session path. Long-running process launch may require host/sandbox permission. Do not close the desktop app or resume its thread with another writer.

## Protocol and return decisions

Worker reads generated `CONTRACT.md` and `work/cycle-context.json`, performs one logical result/correction, then writes `work/checkpoint.json`:

```json
{
  "run_id": "reviewed-pilot-unique-id",
  "cycle": 1,
  "status": "ready",
  "summary": "Requested result created; ready for final review.",
  "evidence": ["result.txt"],
  "next_step": "Await independent review",
  "reason_code": null
}
```

Other statuses: `progress` (intermediate) and `needs_human`. Human reasons: `missing_secret`, `missing_access`, `approval_required`, `user_choice`, `external_blocker`. A missing secret is detected by presence checks without printing its value.

Goal then calls `goal_wait` without a resume timer. The bridge waits for accepted `goal_wait` and `agent_settled`; it does not treat rejected terminal tools or an arbitrary tool-free answer as a checkpoint. Goal lifecycle regression coverage now verifies that intermediate `agent_settled` events do not end a cycle, and only an accepted `goal_wait` followed by settlement creates a review boundary. A new live Goal run has not been performed; this does not establish that the Goal route is live-verified. Ralph must save a checkpoint before its single iteration ends. Shared outputs are retained; each new native iteration gets its own `ralph/NNN/` directory.

The bridge snapshots evidence hashes, runs `eval_argv` freshly, writes `reviews/NNN/request.json` and queues a compact review into the exact Codex chat. It sends no images or full tool logs. Evaluator output may contain private data: inspect locally and summarize safely.

The reviewer reads task + request + necessary evidence, then writes a decision atomically:

```sh
python3 "$HOME/.agents/skills/pi-ping-pong/scripts/bridge.py" decide \
  --config /absolute/run/config.json --cycle 1 --decision revise \
  --feedback 'Fix the specific failed requirement; preserve the passing artifacts.'
```

Decisions: `continue`, `revise`, `complete`, `wait_human`, `stop`. `continue`/`complete` require eval exit 0; completion additionally requires a `ready` checkpoint. Decisions carry run/cycle/hash identities; stale/mutated evidence and duplicate final decisions are refused.

Use `wait_human` for actual user action and ask a precise question in the chat. Pi stays alive and waiting, bounded by review/overall deadlines. After the user resolves the blocker, replace `wait_human` with a decision using `--human-resolved`; this flag records actual user input, not permission for an agent to approve itself. Provide no secret values in feedback.

For Goal, the decision is delivered into the same RPC session. Final `complete` lets it call `goal_complete`; for Ralph, the accepted decision either starts the next bounded iteration with feedback or ends the run. Finite cycle/time exhaustion does not become task success. A callback review must end its Codex turn after recording the decision, freeing the chat for the next checkpoint.

## Failure/recovery boundaries

- Queue attempts are recorded before dispatch. Failed/ambiguous dispatch is not retried automatically; inspect receipts and target chat before any manual resend.
- Unexpected Pi exit, provider/policy pause without a checkpoint, malformed protocol, changed artifacts and deadlines produce `attention_required`, stop the process group and queue a compact report when possible. Native logs/session preserve diagnosis; do not report them as task completion.
- An existing run directory cannot be silently started again. The current bridge intentionally refuses automatic crash recovery: inspect saved session and pending review before preparing an explicitly authorized recovery run. Normal review wakeups do not restart Pi.
- `wait_human` is not forever: select a reasonable review deadline. If that expires, resolve access then explicitly recover from evidence; do not renew the budget automatically.
- Never run workers concurrently on the same writable task outputs. This bridge is for cooperative local execution, not isolation from malicious extensions or workers with the same OS permissions.

Tests: `python3 scripts/test_bridge.py` beside the bridge exercises transport/routing invariants without paid model use. A live queued test is separate evidence and may complete over later Codex turns.

## Pi reviewer transport

The same bridge supports `review_transport=pi`; Codex remains the default for existing configs. No `thread_id` is needed for Pi. Do not invent `pi_session_id`: the shared launcher binds the actual session only when a run is explicitly launched. `/reviewed-run` and `/ppp` use the same handler as `/pi-ping-pong`; `/reviewed-status` and `/ppp-status` use the same handler as `/pi-ping-pong-status`.

The source receiver is `../extensions/pi-reviewed.ts`. Install a copy in `~/.pi/agent/extensions/pi-reviewed.ts` for automatic discovery, then `/reload` in an existing Pi. For a one-off session, `pi -e /absolute/path/pi-reviewed.ts` loads it explicitly. Keep the installed copy in sync with the skill source. No global Pi Goal settings or vendor npm packages are changed.

In Pi, `/pi-ping-pong` (short alias `/ppp`) with no arguments opens a native menu for the current project's immediate named run directories. A Git project uses its top-level root, not the current subdirectory. If there are no runs, the command asks for a readable name; in a non-Git folder it asks you to confirm that folder, or offers the private fallback. Cancelling either dialog makes no run changes. The menu shows local states and details; choosing a row never launches. A ready run has a separate **Launch** action, and an incomplete run a **Continue preparation** action. `/pi-ping-pong-status` (aliases `/reviewed-status` and `/ppp-status`) is local filesystem/session inspection only: it does not call a model, run the evaluator, or start/restart a worker.

A new `/pi-ping-pong <task description>` reserves `<project-root>/.pi-ping-pong/runs/<generated-name>/` exclusively with mode 0700. The generated name is a readable lowercase ASCII slug derived from the full task, with a short content hash to avoid collisions. A lone kebab-case argument is treated as an explicit run name. Names are lowercase ASCII kebab-case, 1–48 characters; there are no slashes, traversal components, hidden names, or `latest` symlinks. Explicit names are never silently suffixed. The directory includes a small mode-0600 `.draft.json` marker so interrupted preparation retains its chosen name without a fake `config.json`. Full readiness is determined from the actual TASK/eval/config, not the marker. The independent UUID `run_id` belongs inside `config.json`; it is not the folder name. The extension requires the project run path to be Git-ignored before creating or preparing it. This repository ignores `.pi-ping-pong/`; for other Git projects, add that pattern to the project's `.gitignore` yourself and verify it is ignored. The extension does not edit another project's Git settings. In a confirmed non-Git project it uses the folder you confirmed; if no folder is confirmed, it can use `~/.pi/reviewed-runs/named/<name>/`. Existing legacy runs at `~/.pi/reviewed-runs/<UUID>/` are not listed/migrated and remain launchable by explicit path.

`/pi-ping-pong <task description>` on a new task sends a preparation prompt to the current model using Pi's `sendUserMessage` API. It reuses the conversation, uses the currently selected Pi model as reviewer without asking for confirmation, and asks only if no model is selected or the user requests a different reviewer. Unless the task asks otherwise, preparation defaults to worker_provider=openai-codex, worker_model=gpt-6-luna, thinking=low, and max_cycles=10; these approved defaults do not require confirmation. The prompt includes the confirmed project root, reserved path, no-overwrite and no-launch rules, task/criteria, allowed paths, independent evaluator requirements, and finite bounds. This is prompt-based preparation, not a fully automatic wizard. It creates no placeholder config, launch marker, `pi_session_id`, or session attachment. The model writes TASK.md, config.json with a unique UUID `run_id`, and task-specific eval.py there; all must be private (files mode 0600). Review the task, criteria, models, allowed paths, evaluator, and finite limits before launch. A continuation sees existing file names and must inspect/preserve existing content; launched runs and evidence cannot enter preparation.

If an explicit named run is fully ready and has never launched, `/pi-ping-pong <name>` is the explicit launch action and invokes the existing shared launcher; from the menu, choose **Launch** instead. Task-text commands never launch an existing generated-name run; a repeated task reports its existing run without replaying it. Readiness checks the private TASK/evaluator files, UUID, required config/models, Pi transport, and positive finite bounds without executing the evaluator. The launcher still applies model/provider binding and duplicate-launch checks. A directory with a launch record or bridge status is status-only, even if the receiver is offline; use a different name for new work. Status derives running/waiting/completed/stopped/attention from durable bridge status, not a process exit code or native Goal status. Missing or malformed metadata is shown as attention/unknown and never permits replay.

For advanced or legacy runs, the existing explicit-path workflow remains available. Prepare TASK.md, eval.py and config.json with explicit worker/reviewer models and finite bounds, then in Pi run an absolute or Pi-working-directory-relative path:

```
/pi-ping-pong /absolute/or/relative/run/config.json
```

`/reviewed-run` and `/ppp` use the same handler and checks. A missing explicit path is an error, not a new run name; a bare valid kebab-case argument selects explicit-name behavior, while all other non-path text is a task that receives an automatically generated name. This preserves launch of older configs under `~/.pi/reviewed-runs/<UUID>/` without automatic migration. Newly named runs use UUID `run_id` values, while explicit legacy configs retain the bridge's compatible safe-string ID contract (`[A-Za-z0-9][A-Za-z0-9._-]{0,100}`); detailed status validates that contract and the config/status identity match before displaying lifecycle metadata.

This starts the bridge as a detached child and returns immediately. A parent model must not wait synchronously for the bridge to finish. It watches the run-local durable `pi-inbox/` and injects each checkpoint using `pi.sendMessage` with `deliverAs: followUp` and `triggerTurn: true`. While the reviewer is busy, Pi queues the message for after current work. This is not an urgent steering interruption. While idle, a new review turn starts. Custom messages remain visibly distinguishable from human prompts.

`pi-receiver.json` records the bound session/run; each message carries those identities. `*.delivery.json` records dispatch so reloads do not blindly repeat messages. A wrong-session message is rejected. If the currently selected reviewer model/provider differs from config, delivery is held with a UI notice; selecting the required model releases it. Keep that model selected while queued reviews run. A review still requires independent artifacts/eval checks; queue receipt alone proves only enqueueing.

Subscriptions persist as `pi-reviewed-run` custom session entries. Reopening the same session restores mailbox monitoring; switching to another session does not inherit it. Shutdown disposes timers, marks the receiver offline and leaves pending inbox files durable. Already-running workers remain governed by existing deadlines; they do not receive automatic approval while the reviewer is offline. Do not relaunch a run just to restore its receiver.

`/pi-ping-pong-status`, `/reviewed-status`, and `/ppp-status` are equivalent names registered to one handler. They show detailed current-project named runs plus matching-session attached explicit-path runs, deduplicated by canonical path; details include phase/state, cycle/budget, elapsed/state age when known, worker/reviewer, paths, reason and next action. They do not launch/restart workers, create config, run evaluators, or call models. The receiver publishes compact local lifecycle updates through its own native footer status key and clears it on session shutdown/switch. Material terminal/human-blocker transitions use narrow private session/run notification receipts keyed by state, cycle, reason and observed re-entry, so refresh/reload does not repeat unchanged notices and queue-delivery identities remain separate. Existing state-only notification receipts are upgraded on observation without replaying their current notice. These API-level regression tests are not a live visual TUI test. Check `launcher.log` if launch fails. `dispatching` without a terminal delivery acknowledgement is ambiguous: inspect the Pi transcript before manual recovery, never automatically resend.

The receiver registers commands in its factory without calling runtime-only APIs such as `getCommands()`, which throws before Pi binds the runtime. Pi's native resolver disambiguates duplicate extension names with numbered invocation names (for example `/ppp:1` and `/ppp:2`), rather than silently choosing an owner. Check the `/` menu for the available names and prompt/built-in conflicts. Skills use separate `/skill:<name>` commands. Receiver tests load the actual extension through Pi's uninitialized loader and exercise native duplicate-name resolution without model calls.

For Codex-free operation, results and human questions return to the launching Pi session. Codex mobile Remote is not a Pi UI; access to that Pi terminal/session requires the user's existing terminal/remote setup.

Tests: `python3 -B scripts/test_bridge.py` covers both transport contracts and original Codex behavior. `node scripts/test_pi_receiver.mjs` exercises the real TypeScript receiver using a fake ExtensionAPI without model usage; it uses the installed Pi package's jiti loader. These tests verify preparation-prompt wiring, not the quality of an evaluator generated during a live preparation. Live two-model/RPC runs are additional evidence, not implied by these unit tests.

## Compact checkpoint evidence

`max_evidence_files` is an optional positive integer in config.json (default 20); it bounds top-level evidence references, not total artifact count or Pi tokens. Raise it for a justified package, e.g. 100, rather than modifying code. Usually keep checkpoints to report + manifest/measurement index + relevant code + changed final outputs. Intermediate screenshot strips/logs stay on disk; manifests should include their paths/hashes and the independent task evaluator should verify referenced inputs. Compacting checkpoint references must not delete raw evidence or waive checks.
