# Reviewed run setup

For manual setup (advanced), use an isolated run directory on the host that owns Pi and can reach the target Codex app-server. Keep private artifacts out of Git, e.g. a project's ignored `data/raw/<run-id>/`. Both agents must see the same paths.

Create `TASK.md`, an independent task-specific `eval.py` outside worker outputs, and `config.json`. The bridge creates `work/`, `reviews/`, `sessions/` and the protocol contract. Task output paths are relative to `work/`. Never put secrets in prompts, checkpoints or review feedback.

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
  "max_cycles": 4,
  "cycle_seconds": 600,
  "review_seconds": 1800,
  "wall_seconds": 7200
}
```

These are example limits, not permission to spend the full budget. Match limits to the task and human availability. A wait consumes wall time but no model polling. Goal's installed automatic-work/no-progress limits remain enabled. Do not enable managed-run RPC globally: direct `/goal` and Pi's documented RPC transport suffice. No token budget is invented by the bridge.

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

The same bridge supports `review_transport=pi`; Codex remains the default for existing configs. No `thread_id` is needed for Pi. Do not invent `pi_session_id`: `/pi-ping-pong` binds the launching session itself; `/reviewed-run` is its compatibility alias to the same handler.

The source receiver is `../extensions/pi-reviewed.ts`. Install a copy in `~/.pi/agent/extensions/pi-reviewed.ts` for automatic discovery, then `/reload` in an existing Pi. For a one-off session, `pi -e /absolute/path/pi-reviewed.ts` loads it explicitly. Keep the installed copy in sync with the skill source. No global Pi Goal settings or vendor npm packages are changed.

In Pi, `/pi-ping-pong` with no arguments sends a preparation prompt into the current conversation through Pi's `sendUserMessage` API. It reuses details already present, asks only for missing information, and suggests the currently selected reviewer model; the worker model must be explicitly chosen. This is a prompt-based preparation flow, not a fully automatic wizard. It prepares `TASK.md`, `config.json`, and an independent task-specific `eval.py` under the private default path `~/.pi/reviewed-runs/<UUID>/`, outside the source project. Review the resulting criteria, paths, models, evaluator, and finite limits, then explicitly invoke `/pi-ping-pong /absolute/run/config.json` to launch. Preparation itself does not create launch or session-attachment state. `/pi-ping-pong-status` and `/reviewed-status` show only locally attached launched runs, never drafts.

For the advanced manual-config workflow, prepare TASK.md, eval.py and config.json with explicit worker/reviewer models and finite bounds. In the Pi session, select its configured review_model, then run the primary launcher command:

```
/pi-ping-pong /absolute/run/config.json
```

`/reviewed-run` remains a compatible alias to the same handler: without arguments it enters the same preparation flow, and with `/absolute/run/config.json` it uses the existing-config launcher checks. The explicit-path form requires an existing `config.json`; manual config generation remains an advanced workflow.

This starts the bridge as a detached child and returns immediately. A parent model must not wait synchronously for the bridge to finish. It watches the run-local durable `pi-inbox/` and injects each checkpoint using `pi.sendMessage` with `deliverAs: followUp` and `triggerTurn: true`. While the reviewer is busy, Pi queues the message for after current work. This is not an urgent steering interruption. While idle, a new review turn starts. Custom messages remain visibly distinguishable from human prompts.

`pi-receiver.json` records the bound session/run; each message carries those identities. `*.delivery.json` records dispatch so reloads do not blindly repeat messages. A wrong-session message is rejected. If the currently selected reviewer model/provider differs from config, delivery is held with a UI notice; selecting the required model releases it. Keep that model selected while queued reviews run. A review still requires independent artifacts/eval checks; queue receipt alone proves only enqueueing.

Subscriptions persist as `pi-reviewed-run` custom session entries. Reopening the same session restores mailbox monitoring; switching to another session does not inherit it. Shutdown disposes timers, marks the receiver offline and leaves pending inbox files durable. Already-running workers remain governed by existing deadlines; they do not receive automatic approval while the reviewer is offline. Do not relaunch a run just to restore its receiver.

`/pi-ping-pong-status` and `/reviewed-status` are equivalent names registered to one handler. Both print locally attached run status only; they do not launch or restart workers, create config, or call models. Check `launcher.log` if launch fails. `dispatching` without a terminal delivery acknowledgement is ambiguous: inspect the Pi transcript before manual recovery, never automatically resend.

For Codex-free operation, results and human questions return to the launching Pi session. Codex mobile Remote is not a Pi UI; access to that Pi terminal/session requires the user's existing terminal/remote setup.

Tests: `python3 -B scripts/test_bridge.py` covers both transport contracts and original Codex behavior. `node scripts/test_pi_receiver.mjs` exercises the real TypeScript receiver using a fake ExtensionAPI without model usage; it uses the installed Pi package's jiti loader. These tests verify preparation-prompt wiring, not the quality of an evaluator generated during a live preparation. Live two-model/RPC runs are additional evidence, not implied by these unit tests.

## Compact checkpoint evidence

`max_evidence_files` is an optional positive integer in config.json (default 20); it bounds top-level evidence references, not total artifact count or Pi tokens. Raise it for a justified package, e.g. 100, rather than modifying code. Usually keep checkpoints to report + manifest/measurement index + relevant code + changed final outputs. Intermediate screenshot strips/logs stay on disk; manifests should include their paths/hashes and the independent task evaluator should verify referenced inputs. Compacting checkpoint references must not delete raw evidence or waive checks.
