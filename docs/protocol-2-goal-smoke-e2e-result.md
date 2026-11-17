# Historical Goal smoke — NOT RUN

> **Superseded launch recipe.** Current tests: [three manual E2E cases and prompts](manual-e2e.md). Use the existing worktree, installed Pi and existing subscription. No separate HOME/OAuth/TUI, pinned Pi release, source snapshot or old profile probe is required. Everything below records the earlier experiment, not current instructions, current process liveness, or prerequisites. Do not reopen its OAuth/tmux flow or reuse its run as one of the new cases.

## Historical launch convention

The user-operated `/pi-ping-pong <absolute-path>/config.json` launch replaced assistant terminal control. Authentic session binding remains launcher-owned. See [the operational instructions](../references/reviewed-runs.md#user-operated-smoketest-launch).

**Recorded test verdict: NOT RUN.** Earlier wording calling the assistant's inability to enter the command a smoke FAIL was incorrect; the test itself never ran. These historical observations do not assert compatibility or incompatibility with today's installed runtime. The new cases have no live result yet.

## Historical assistant launcher-access failure (not a smoke verdict)

The owner explicitly authorized one subscription smoke using the **existing running Pi TUI**, no new HOME/OAuth profile/TUI/session/run, no Core or acceptance changes, at most two Worker cycles, no restart. Current Pi session: `01a15c15-f08b-72e2-bfd1-10885e30d9f8`; current model: **openai-codex/gpt-6.1-sol**, installed Pi **1.4.0**.

**FAIL at launcher transport, before Core launch.** The assistant's available tools cannot invoke `/pi-ping-pong` inside this running TUI. Pi's documented RPC controls a separately launched RPC process, not an existing interactive TUI. The current process is on `ttys006` and is not the previously created tmux pane. The supported Orca terminal route returned `runtime_unavailable`: `Could not read Orca runtime metadata at /Users/macos/Library/Application Support/orca/orca-runtime.json. Start the Orca app first.` No new app, TUI or runtime was started to work around this.

Knowing `PI_SESSION_ID` is not authentic launcher binding. No session transcript was edited, no `pi_session_id` was fabricated, no manual launch record or receiver receipt was synthesized, and no direct unbound Core start was substituted for the required existing TUI launcher. No current-runtime hash was claimed: runtime/config activation did not happen. The earlier pinned private-lab manifest below remains historical, not evidence of a 1.4.0 launch.

| Requested result | Actual result |
| --- | --- |
| PASS/FAIL | **NOT RUN** — earlier launcher-access failure was not a test result |
| Worker cycles | **0**, not a failed Worker cycle |
| Evaluator | Not invoked live; prior offline fixture results below are not acceptance |
| Reviewer | No live review request, verdict or callback |
| Core | Not started; no finish or terminal Core state exists |
| Models/usage | 0 smoke inference calls, 0 Worker/Reviewer smoke turns; no provider usage responses or subscription quota measurements |
| Retries/new runs | None; original run ID and empty work directory retained |

Actual run inspection confirmed **no** `launch-attempt.json`, `bridge-status.json`, or `pi-receiver.json`, and **empty** `work/`. The previously assistant-created `ppp-subscription-smoke` tmux session was closed, cancelling its pending private OAuth flow; the owner's running Pi was not closed or changed. No new OAuth, credential copy, API key, API fallback, Ralph, installation, commit or merge.

This is a concrete technical failure to launch, **not a live Goal/Worker/model failure and not a PASS**. There is no automatic retry. The required native launcher command was not executed by this assistant. The historical private-profile assumptions below must not be treated as a current-runtime configuration or launch instruction. Launching without adapting the Worker profile could lose the required read/write-only restriction; no unrestricted Worker was launched.

## Historical private-profile preparation (superseded by current-TUI request)

### Previous verdict

**Static/profile preflight PASS; private OAuth login pending. Live smoke NOT RUN.** No live PASS/FAIL is claimed. Ralph remains BLOCKED. This report supersedes the former API-key/pay-as-you-go instructions; those were the wrong authentication model.

The current task authorizes exactly one subscription Goal smoke after successful preflight, at most two Worker cycles, no automatic retries, grants, resume, or Ralph. It does not authorize an API key or paid-API fallback.

## Authentication and exact models

- Existing managed Pi is **1.4.0**. `pi auth check --provider openai-codex --json` returned `status=ready, authType=oauth`; exact-model checks for `gpt-6-luna` and `gpt-6.1-sol` also returned OAuth ready. These are credential readiness checks, not inference/server-entitlement or subscription-quota proofs.
- Installed **Pi 1.3.0**, retained for the pinned smoke, and current Pi list the exact IDs **openai-codex/gpt-6-luna** and **openai-codex/gpt-6.1-sol**. Listed contexts are 272K and 500K respectively; these are context windows, not remaining subscription allowances. Thinking remains **low**. No fuzzy model substitution.
- No tokens were read by the assistant, printed, copied, or stored in evidence. Only Pi's native credential-status commands were used; no `--credentials` or credential-print command.
- The dedicated profile has no configured subscription credentials: native auth check returned `not_ready / credentials_not_configured`. This does **not** mean the owner's subscription is unavailable.
- Native `/login openai-codex` → **Device code login (headless)** was started in the private Reviewer TUI. The human must complete it there. Do not paste credentials, redirect URLs, or device codes into chat. Do not copy/symlink personal `auth.json` into the lab.

## Fresh disposable lab

```text
LAB=/private/var/folders/cf/nv7pkv557qq8ypy9h8vhmzlc0000gn/T/ppp-goal-subscription.Aaw4Zk/Test-lab
RUN=$LAB/Test-project/.pi-ping-pong/runs/Test-goal-smoke
run_id=9962e813-7af3-4aa9-be4c-32124bdb8e71
TUI: tmux attach -t ppp-subscription-smoke
```

Private launcher: sibling `Test-reviewer.sh`. It starts the real pinned 1.3.0 TUI with only the frozen source receiver, `read,bash` for independent review, no MCP/skills/context discovery, and the exact subscription Reviewer model. No inference prompt or launch command has been sent. The native login may expire; an expired login is not permission to retry a smoke.

The helper now generates both providers as `openai-codex`; it still generates no credentials. Candidate authentication/accounting metadata and the helper hash were updated. Frozen Core/receiver commit **8ad1193b261aed27d75a6df352bd4c542aac7f0e** and evaluator bytes remain unchanged. Observed source HEAD: `fd7cb5b3c35c059ca7f6ac77c5984c347421ec59`.

| Artifact | SHA-256 |
| --- | --- |
| Candidate JSON | `66987f320fca7623b955ea0887664ef61a90cbd826e5e754677a5608b3ff5323` |
| Lab manifest | `488807838ac74847f03b278f45581202e2ba115812a55a7183a5bbded12b7e76` |
| Prebinding config | `feb6b834b991b05c34f11a7243c53cf4d71ee78838a369971446b583459b2156` |
| Preparation helper | `ad2ff10e9231df914d64bfae6e9ed60269d6152161d17858ff32e3171360187f` |
| Unchanged evaluator | `dde9f5699a04457413f14cb536283621cde1c4c8df19c6144c05d19c5361ec54` |

The first post-TUI hash check correctly rejected settings drift: native startup added only `lastChangelogVersion=1.3.0`. Exact settings were inspected; tool restrictions and disabled retry/cache-warming/compaction were unchanged. This prelaunch metadata-only change was explicitly recorded in the private manifest, retaining the old hash. The repeated hash check passed. No launched contract/state was repinned.

## Checks and remaining gates

- `python3 -B scripts/test_goal_smoke.py`: **1 PASS**, offline evaluator/Controller fixture, not live acceptance.
- `node scripts/test_goal_profile.mjs`: **PASS**, real Goal extension, exactly `read/write` + `goal_wait/goal_blocked/goal_complete`, zero prompts/model calls. No shell/codemode/MCP or other Worker extensions.
- Frozen Core/receiver equality, candidate/runtime trees and file hashes, config/model/bounds, empty outputs: **PASS**.
- Main max **2**, closure unauthorized, cycle/review **60 s**, active-operation wall **90 s**; existing Goal continuation limits **8/3** and disabled automatic retry unchanged. No new acceptance logic or allowlist.
- `UV_OFFLINE=1 npm run check`: **INCOMPLETE**, harness timeout at 120 s. ESLint/TypeScript/Ruff and 15 legacy + 56 protocol tests passed before interruption; action-bridge suite had not finished. This is not a full-gate PASS; repeat with an adequate bound before launch. Private log: `/tmp/ppp-subscription-check.log`.
- Authentic Reviewer binding: **PENDING**, not fabricated. The existing TUI receiver is loaded, but only the explicit `/pi-ping-pong <RUN>/config.json` launch can bind the actual session. Do not write a session ID or launch record manually. Repeat preflight after login before that single command.

## Live/accounting/cleanup

Attempts **0**, Worker cycles **0**, smoke inference calls **0** (Worker **0**, Reviewer **0**). OAuth device authorization traffic is not model inference. Token usage: **N/A**, no provider usage responses. Subscription remaining quota/reset times: **not obtained**. No API-cost estimate is reported as actual subscription expense; no billing/export endpoint was queried.

No Core, Worker, or evaluator was started for this run. The explicitly owned Reviewer TUI remains open for human OAuth login; it is not a forgotten Worker. Outputs, fresh evaluator/reviewer evidence, Core finish, cumulative accounting, and final owned-process cleanup remain **UNVERIFIED** until an authorized live attempt actually runs. Never infer PASS from local fixture tests or native completion.

## Next action

Do not execute the historical lab recipe. Open a normal Pi chat in the existing worktree and use one of the [current manual case prompts](manual-e2e.md). Keep this unlaunched historical run/evidence intact; new case reports begin NOT RUN and record actual outcomes, including missing results.
