# Pi Ping Pong user guide

[Project overview](../README.md) · [Run contract](../references/reviewed-runs.md) · [Protocol](action-scoped-protocol.md)

## Requirements

- A POSIX host (macOS or Linux), `python3` (use Python 3.10+, the project's declared minimum), and an RPC-capable `pi` on `PATH`. Native Windows is not supported. Use a Node.js version supported by your Pi installation; the Pi package pinned for repository development declares Node.js 22.19.0 or newer. The pin is not a requirement to downgrade your installed Pi.
- The Goal extension for `goal`, or the Ralph extension for `ralph`; neither is needed for the ordinary Pi Worker in `ping-pong`. The bridge looks for the installed `@narumitw/pi-goal` and `@lnilluv/pi-ralph-loop` packages by default; [the run contract](../references/reviewed-runs.md) describes the runtime options.
- Working Pi model access for the selected Worker and, with headless Pi review, the selected Reviewer provider/model. The preparation defaults are not portable model IDs; choose IDs available in your environment. Explicit Pi extension lists are supported for provider registration; load only trusted code. No Claude Code runtime or particular Claude provider/model pairing is established by this mechanism.
- Worker and Reviewer need access to the relevant local files. Keep the host available and the launching session open for normal Pi reporting; UI-close autonomy and cross-chat catch-up are not claimed.

## Install

If you used `scripts/install.py` before, [disable that receiver first](#migrate-from-the-copy-installer). Install PPP with Pi:

```sh
pi install npm:pi-ping-pong
```

To follow the Git repository instead, use `pi install git:github.com/SzpakLabs/pi-ping-pong`. To try an unpublished checkout, run `pi install /absolute/path/to/pi-ping-pong`. Pi loads that checkout in place; update it with Git, not `pi update`. Install only one source for PPP at a time.

Open a new Pi session or run `/reload`. To check the installation without starting work, look for `/skill:pi-ping-pong` in command completion and run `/ppp-status`. The package includes the receiver, skill, and Python bridge. npm does not install Python: `python3 --version` should report 3.10 or newer, and no Python libraries need to be installed for PPP. The package also does not install model credentials, Goal, or Ralph.

### Update or remove

```sh
pi update npm:pi-ping-pong
# For a Git installation, use this instead:
# pi update git:github.com/SzpakLabs/pi-ping-pong
# Or update all installed Pi packages:
pi update --extensions
```

Bare `pi update` updates Pi itself, not PPP. An exact npm version pin (for example, `npm:pi-ping-pong@0.1.1`) or a Git tag/commit pin stays fixed. Update between runs: Pi can replace package files in place, and an existing bridge can still need its companion scripts. Reopen Pi or run `/reload` to load the updated resources.

Use `pi remove <source>` with the source in `pi list` (for example, `pi remove npm:pi-ping-pong` or `pi remove git:github.com/SzpakLabs/pi-ping-pong`). When switching sources, remove the old one before installing the new one. Project run records and any independent Codex skill copy remain in place.

### Migrate from the copy installer

1. Between runs, move the old receiver out of Pi's discovery. For the default installer path, keep a local backup:

   ```sh
   mv -i ~/.pi/agent/extensions/pi-reviewed.ts ~/.pi/agent/extensions/pi-reviewed.ts.disabled
   ```

   If you used a custom location or explicitly configured the old file, disable that entry in `pi config` instead. Do not change run directories or session records.
2. Install the package, then `/reload` or restart Pi. Don't rerun the legacy installer without `--skill-only`: doing so recreates the copied receiver and causes duplicate commands and subscriptions.
3. If you keep `~/.agents/skills/pi-ping-pong` for Codex, use `pi config` to disable **only** that standalone skill in Pi and leave the package skill enabled. On Pi versions with exact resource exclusions, the equivalent is appending `"-~/.agents/skills/pi-ping-pong/SKILL.md"` to the existing `skills` array in Pi's user settings. If you don't need the standalone skill, you can move it outside the discovered skills directory instead.

`PI_PING_PONG_BRIDGE` still overrides bridge selection for both launch and wake. Without it, the receiver prefers the bridge alongside its package. A standalone receiver copied by the legacy installer still uses the bridge under `~/.agents/skills/pi-ping-pong`.

### Install the Codex skill

From an up-to-date Git checkout (the copy installer is not in the npm package):

```sh
python3 scripts/install.py --skill-only
```

This installs or updates `~/.agents/skills/pi-ping-pong`, backing up differing files, without copying a Pi receiver. Installing or updating the Pi package does not update this separate copy. For a legacy copy-only Pi installation, `python3 scripts/install.py` without this flag still installs both the skill and receiver; use that route **instead of**, not alongside, the Pi package.

## Prepare and launch

1. Open the intended project in Pi and describe the result, authorized scope, acceptance criteria, and known test commands. Choose a Worker mode and available provider/model. Use `/ppp <task description>` or `/ppp <unused-kebab-case-name>` to prepare. A lone kebab-case argument is a run name, not the task text. `/ppp` opens the run menu.
2. Review `TASK.md`, `config.json`, project target, provider/model choices, and finite limits. Preparation writes those two contract files in the private run directory; it does not do product work or launch a Worker. New named runs use `.pi/ping-pong/runs/<name>/`. PPP tries to exclude only its new service path via local Git rules; an absent or unknown ignore produces a warning, not a gate. See [storage and Git visibility](project-workspace.md#private-run-storage). Store no secrets in these files; do not prefill `pi_session_id`. New Pi drafts use separate headless review with an explicit provider/model, defaulting to the model used for preparation.
3. Explicitly launch with `/ppp <ready-name>` or `/ppp /actual/run/config.json` in the same chat. For same-name legacy and current runs, choose the intended row in `/ppp` or use the exact config path. The launcher binds the actual session and refuses a second launch of that run. Menu selection alone does not launch. `/pi-ping-pong` and `/reviewed-run` are aliases.
4. Use `/ppp-status` (also `/reviewed-status`) for read-only local status without a model call. Select project scope or technical details when needed. Reopening the same Pi session restores monitoring, not execution replay.

The product target is the selected existing project, including its uncommitted edits, or the explicit file/subdirectory in the task. Its run `work/` directory is service storage by default, not a checkout. There is no mandatory clean Git, commit, fetch, or separate worktree. See [workspace and fallback discovery](project-workspace.md).

## Review, reports, and human input

Worker runs ordinary tests and retains actual results in checkpoint evidence (command, exit status, output, and relevant artifacts). The Ralph Worker prompt asks for actual results of requested tests before the native loop ends, without prescribing a format. For browser work, Core can pass a resolved Playwright module to the Worker; resolution alone does not prove browser or login availability. The Reviewer uses the evidence rather than repeating deterministic checks. It assesses the requested result, remaining semantic or visual questions, and concrete defects. A continuation names the original requirement, the observed omission or defect, and a useful safe next step. Core validates the review against the run and evidence, then chooses the transition. See [Headless Reviewer](headless-reviewer.md) and the [decision contract](action-scoped-protocol.md#decisions-and-delivery).

With headless review, Chat A (the launching chat) reports what was produced, what was verified, and which gaps remain. A missing check is not a defect, and a failed Reviewer is not a human approval request. Core continues eligible independent work before grouping genuine human needs such as missing access, input, approval, or a material choice. While waiting, reminders do not spend Worker/model turns.

Use `/ppp-respond` to choose an addressed request, supply ordinary non-secret text, and confirm it. Advanced `/ppp-respond <run-id> <JSON>` and interactive `python3 scripts/bridge.py human --config /actual/run/config.json` for console ingress are also available. Late input cannot restart a terminal run. Grants are explicit and additive; a passing test cannot grant authority.

## Safety, budgets, and recovery

Worker and Reviewer budgets are separate. Ping-pong counts settled task iterations and has a separate bound on checkpoint repairs; Ralph reserves native iterations before launch; Goal uses cumulative active Worker time, a finite launch count, and an optional token limit. Corrections spend remaining allowance. Ralph token totals in `/ppp-status` are [report-only](../references/reviewed-runs.md#native-ralph-accounting-and-storage): an observed lower bound or “not measured,” not a limit or a bill. See [accounting by mode](../references/reviewed-runs.md#budgets-and-goal-accounting).

Use status and saved records to diagnose an interruption. `python3 scripts/bridge.py resume --config /actual/run/config.json` and event-driven wake preserve run identity, budget accounting, and prior effects. Reconcile ownership and unknown effects before continuing; do not blindly resend a review or repeat a possible external effect. Report-delivery failure does not unset acceptance recorded by Core. These controls are cooperative host safeguards, not an OS sandbox.

## Quick start: reviewer in Codex

This optional route uses `review_transport=codex` with the exact existing `thread_id` and configured review model. [Install the standalone skill](#install-the-codex-skill) if you want Codex to discover it. This route does not start a headless Codex Reviewer or a Codex Worker. The host's `codex queue` command must be available and authorized for that chat; check `codex queue --help` on the host. Do not use `codex exec resume` as a second writer to the same chat.

Prepare a private `TASK.md` and protocol 2 / schema 1 `config.json`, following the [run contract](../references/reviewed-runs.md). Review both before starting the bridge from the checkout (replace the config path):

```sh
python3 scripts/bridge.py run --config /actual/run/config.json
```

The Reviewer submits a direct `review-v2 --assessment`; see the [CLI and schema](action-scoped-protocol.md#independent-reviewer-boundary). Pi chat review (`review_execution=chat`, or omitted for a new Pi config) is also distinct from headless review: the launching chat receives review requests rather than only reports.

## Compatibility and validation

Current runs use protocol 2 / schema 1 without `eval_argv`. There is no separate evaluator or mandatory pre-work model review. Evaluator-era configs/runs, including protocol 1, cannot launch/resume on this runtime. Old files remain unchanged; inspect the original runtime in Git history if needed. See [migration](evaluator-preparation.md).

[Manual E2E cases](manual-e2e.md) use an existing worktree and configured Pi, with a private report saved before preparation. Local tests do not establish live provider compatibility, model judgment, or UI-close behavior. Do not treat historical smoke-stand prerequisites or results as current launch requirements or acceptance evidence.

## Development checks

From the repository root, `npm ci` and `uv sync --locked` install development dependencies. `bun run check` runs the fast Python and TypeScript suites. For changes spanning lifecycle and recovery, run `bun run check:integration`; scope narrower integration checks as described in [AGENTS.md](../AGENTS.md). The optional pre-commit hook runs `git diff --cached --check`, not the test suite.

### Try your checkout in Pi

Install only one PPP source at a time, so test a checkout instead of the npm copy, not beside it.

- **One run:** `pi -ne -e /absolute/path/to/pi-ping-pong`. `-e` loads the checkout without changing settings; `-ne` skips other installed extensions, including the npm copy. Add `-e` for each extension you still need, such as Goal or Ralph. Check `/ppp-status`.
- **Longer testing:** `pi remove npm:pi-ping-pong`, then `pi install /absolute/path/to/pi-ping-pong`. Pi loads the checkout in place, so update it with Git, not `pi update`. To return, remove that path and run `pi install npm:pi-ping-pong`.

Both options run local code only. Paid Worker and Reviewer runs remain a separate manual test.
