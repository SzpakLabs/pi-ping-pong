# Historical protocol-2 Goal / Ralph readiness

> **Historical stand assessment, not a current manual-test gate.** Use [three ordinary-worktree E2E cases and prompts](manual-e2e.md). Their installed Pi version is recorded, not pinned; they require no new HOME/OAuth, copied source/runtime or old read/write-only profile. The READY/BLOCKED labels, approvals, prices, exact-version checks, commands and next actions below apply only to the old experiment. They do not establish live acceptance or block today's Goal cases. Retain the candidate/helpers for optional reproduction; do not run them as current preflight.

## Historical authentication override — subscription only

The current Goal smoke uses **ChatGPT subscription OAuth**, with confirmed installed IDs **openai-codex/gpt-6-luna** (Worker) and **openai-codex/gpt-6.1-sol** (Reviewer), thinking low. No OpenAI API key, API project, pay-as-you-go, or API fallback is authorized. Use Pi's native `/login openai-codex` in the dedicated private profile; never copy personal tokens. The candidate/helper now select this provider explicitly, without changing Core or evaluator logic.

The API-key credential-shape preflight, `/login openai`, `--provider openai`, dollar estimates/thresholds and additional paid-confirmation instructions below are **superseded historical instructions, not executable current guidance**. Current one-run authorization, new lab, hashes, OAuth/login status and remaining live gates are in [the subscription smoke report](protocol-2-goal-smoke-e2e-result.md). Existing readiness tests are not live acceptance. Report tokens and available subscription quotas; local API prices do not establish subscription charges. The pinned installed Pi 1.3.0 is retained even though the managed launcher is now 1.4.0; no runtime installation/update occurred.

## Historical decision and preparation

| Runtime / scope | Decision | Basis |
| --- | --- | --- |
| **Goal, only the profile below** | **READY — READY FOR EXPLICITLY AUTHORIZED SMOKE TEST** | G1 fixed; owned-group/cancel/timeout/late-dispatch regressions PASS; the real Goal extension was checked with private `defaultTools=[read,write]` and no model prompt; disposable target, evaluator and two main cycles were measured |
| Goal with shell, external effects, crash/resume, or unattended execution | **BLOCKED by this assessment** | Those guarantees were not tested for this profile; read/write are not a path sandbox, and a remote request cannot be reliably recalled |
| **Ralph** | **BLOCKED** | The native runner always creates nested detached Pi; owner crash leaves the peer, and escaped descendants survive normal/cancel/timeout. Durable nested usage is also incomplete |

Ralph-specific G2 does not automatically apply to Goal. Hard billing infrastructure and an OS sandbox are **not prerequisites for the proposed cooperative local smoke**, but their absence is an explicit risk for separate authorization, not an implied guarantee. Earlier joint BLOCKED/READY results in [remediation](protocol-2-e2e-gate-remediation.md) and [audit](protocol-2-regression-audit.md) are historical results for different gates, not this narrow profile. The [integration plan](autonomous-run-integration-plan.md) is future work, not a smoke prerequisite.

**Paid runs: 0. No launch permission has been granted.** READY means the experiment is prepared, not live acceptance or permission to run the commands below.

## 1. Exact version and dirty state

- Starting HEAD was `6d1cba6a1f33b76f704fc05d01c69c9e0dd6333c`; its bridge change and regression tests are now split into code commit `8ad1193b261aed27d75a6df352bd4c542aac7f0e` and test commit `578a459`. Five staged docs/native-test files; full input `git diff HEAD --binary` SHA-256 `62715b492905504041146002aa2a373f2863cebaaaff24163709bb6667609670`.
- During work, the frozen execution candidate contained the same Core/receiver bytes now in `8ad1193b261aed27d75a6df352bd4c542aac7f0e`. The full diff and `git diff 6d1cba6 HEAD` were checked: **production code did not change**. The pin guard correctly rejected the new HEAD first; the candidate was then explicitly updated. Later history cleanup split code, tests, and docs, and folded translations into the relevant documentation commits without changing the four execution files.
- Subsequent external commits `d8d2749` / `105bcaf8d3df62a1f33258f6bafd1bb637f4e598` changed only `.githooks/pre-commit`, `Makefile`, `docs/GUIDE.md`, and `scripts/test-commit.sh`; the complete diff was reviewed. I did **not** run those commit commands. Last observed HEAD: **`105bcaf8d3df62a1f33258f6bafd1bb637f4e598`**.
- **Frozen execution implementation: `8ad1193b261aed27d75a6df352bd4c542aac7f0e`**, the code-only G1 fix commit. No production diff exists in the four executable files relative to it. The helper does not chase HEAD: it compares all Core/receiver bytes with the frozen commit and manifest hashes, and records the current source HEAD separately. Any actual execution-byte drift is rejected; approval does not transfer to new code. The committed fixture/profile helpers below are part of the smoke package, not installed runtime; their hashes are in the [candidate manifest](protocol-2-goal-smoke-candidate.json).
- Pi **1.3.0**, Goal **0.54.13**, Ralph **2.1.0** (reference only); Node **v26.6.0**, Python **3.15.0a1**, macOS **15.5 x86_64**. Worker **openai/gpt-6-luna**, Reviewer **openai/gpt-6.1-sol**, thinking **low**. Account access was not tested; catalog IDs do not pin immutable weights. No fallback.
- Manifest contains binary/lock/source hashes and executable/config asset-tree hashes: Pi release dependencies **9,244 files / 67,888,489 bytes**, Goal **28 / 439,531**, pi-tui-kit **69 / 270,925**. Ralph tree is recorded separately and is **not a Goal launch gate**. System dylibs/OS image are not claimed to be hermetic. Active Node/Python realpaths and host version are checked, not just version labels.
- Evaluator SHA-256: `dde9f5699a04457413f14cb536283621cde1c4c8df19c6144c05d19c5361ec54`. Config/TASK/private settings are generated by a deterministic pinned helper with a fresh UUID and absolute lab target; exact bytes/hashes enter the lab manifest. Config may change **only through authentic receiver binding before Core pins it**; no session ID is fabricated.

The full final dirty patch and untracked-file inventory are stored privately outside Git in `/tmp/ppp-goal-readiness-final-evidence/`; this is snapshot evidence, not a runtime registry. No circular self-hash of this document is used. Authorization should identify the candidate JSON and specific prepared lab manifest, not just HEAD or an old installed PPP copy.

## 2. Minimum gates and residual risks

**Goal process gate PASS within the tested boundary:** Core owns a new POSIX process group, retains the leader through `waitid(WNOWAIT)`, then TERM → 50 ms → KILL → reap; Darwin EPERM permits up to 50 ms for exit visibility, while a real permission denial against a live leader is not suppressed. Authentic cancellation is committed before refusing further transitions; after cancellation is consumed, no new Worker/Reviewer authorizations occur and late callbacks are not applied. An already enqueued/in-flight Reviewer cannot be recalled or refunded. Existing source fixtures check TERM-ignoring same-group children, unexpected/Goal-query leader exit, and that an unrelated group stays alive. This is not a crash-orphan cleanup SLA.

**A shared, not Ralph-only, hazard:** Pi's built-in `bash` creates a detached group. Therefore the smoke Worker is configured **without bash/powershell/codemode/MCP**: private settings select `read,write`; native Goal adds only `goal_wait/goal_blocked/goal_complete`. A native SDK session with the real extension verified exactly those five tools, with no prompt/model; Goal source does not create a Ralph-style nested runner or change the active tool list. Shell, timers, `goal_complete`, other Goal commands, and tool/loadout changes are prohibited. The separate Reviewer has `read,bash` only for short callbacks, with a 5-second tool timeout. Its session is not owned by Core and must remain open during review.

**Target gate PASS:** helper refuses a reused lab, a lab inside source, unexpected production/runtime drift, and ancestor context/resources. It creates a separate empty non-Git `Test-project`, private HOME and empty `work`; it does not check out working projects or install runtime. It copies four exact Core/receiver files into a private read-only snapshot after comparing with the commit; `PI_PING_PONG_BRIDGE` points only to that snapshot. Realpaths and bytes are recorded; governing drift halts. Existing disposable-worktree/evidence-escape/moved-run tests PASS. Worktrees, read-only modes and `read/write` **do not constrain arbitrary host paths like an OS sandbox**.

**Scope:** only `a.txt`, `b.json`, and the selected checkpoint; evaluator writes its exclusive proof files; Core owns state/reviews/archive/session artifacts. No DB, ports, browser, email, DNS changes, payments, deploy, Git mutations, packages, or network task actions. The only intended external activity is explicitly authorized inference/auth. No supervisor, sandbox, billing platform, or new transition loop was added.

**Residual risks requiring explicit acceptance:** same-UID/file tools can access other paths; prompts do not protect against a malicious actor. Isolation from all host files cannot be proven. Do not update runtimes/profile or work on the lab during the smoke. There is no automatic crash recovery: crash/escaped process/uncertain quiescence => FAIL and **no resume/replacement/retry**. Do not delete the lab while a process may be live and do not signal saved/discovered PIDs; the owner must investigate through the normal lifecycle. No production data/credentials belong in declared input/profile. Real API access requires an authentication secret: use only a dedicated inference-only test credential in the lab `auth.json`, never environment/source/run evidence. The same UID can read it; this is a separate accepted risk. If the ban on secrets also covers that auth file/provider-client memory, real API smoke is **BLOCKED until an approved auth mechanism exists**, not “secret-free.”

**Separate Ralph admission:** require an established containment/quiescence route for the nested peer after owner loss and escaped tools, evidence for safe timeout/cancel/crash, and an agreed source for nested usage or explicit acceptance of incomplete telemetry. No full hard-billing solution or universal sandbox is being built here. An outer lock or free PID alone does not satisfy these conditions; do not launch Ralph before then.

## 3. One smoke and exact commands

Fixture: action **a** writes `Test squares: 4,9,25\n`; **b** depends on a, recomputes the sum, and writes `{"Test-sum":38}`. Only the selected action runs, with an actual schema-1 checkpoint, accepted native `goal_wait` without a timer, then settlement. **At most two main cycles; `closure.authorized=false`; grants/retries/resume prohibited.** This is task-specific authority, not a change to the unlimited closure default.

Limits: cycle **60 s**, review **60 s**, active-operation wall **90 s**. Core Worker deadline `min(cycle+45, wall)` = **90 s**, evaluator ≤60 s, review ≤60 s, plus bounded cleanup/host scheduling overhead. Private Goal `automaticTurns=8`, `noProgressTurns=3` are not caps on all model requests/tokens. Retry/cache warming/compaction are disabled in private settings. Normally expect **3 review boundaries**; with the existing correction allowance, maximum **6**; correction does not start a Worker. More/ambiguous delivery => FAIL; do not clear metadata. Operator elapsed threshold **12 min**, not a native cumulative wall cap.

**Step A — preparation only, no models.** Run once in an ordinary shell. Fresh lab must be outside source and working projects:

```bash
set -euo pipefail
umask 077
export SOURCE=/Users/macos/codex-context/skills/pi-ping-pong/.pi/worktrees/permission-friction-research
export LAB="$(mktemp -d "${TMPDIR:-/tmp}/ppp-goal-smoke.XXXXXX")/Test-lab"
python3 -B "$SOURCE/scripts/prepare_goal_smoke.py" --lab "$LAB"
export RUN="$LAB/Test-project/.pi-ping-pong/runs/Test-goal-smoke"
export TEST_HOME="$LAB/Test-home"
export RELEASE=/Users/macos/.pi/agent/install/releases/1.3.0
export LIVE_PATH="$RELEASE/node_modules/.bin:$(dirname "$(command -v node)"):$(dirname "$(command -v python3)"):/usr/bin:/bin"
export PI_PING_PONG_BRIDGE="$LAB/candidate/scripts/bridge.py"
printf '/pi-ping-pong %s/config.json\n' "$RUN"
```

The human inspects `TASK.md/config.json/eval.py`, `manifest.json`, models and tariffs, then obtains separate authorization for **one** smoke. In this private Pi profile, the human configures a **new test credential** via the normal `/login openai`; this was not done here. Never copy personal auth/storage or pass keys through environment/chat/history. Auth setup may happen only after auth-related approval, and before paid approval there must be no prompts/launch. The only credential in the profile is plain `openai` `api_key`, not `!command`, OAuth refresh/env overrides, or credentials for other systems.

**Step B — after separate authorization, exactly one TUI launch and one slash command.** Preflight makes no model calls; on failure STOP, do not regenerate pins:

```bash
python3 -B - <<'PY'
import hashlib,json,os,shutil,stat,sys
from pathlib import Path
lab=Path(os.environ['LAB']); m=json.loads((lab/'manifest.json').read_text())
cp=Path(os.environ['SOURCE'])/'docs/protocol-2-goal-smoke-candidate.json'
assert hashlib.sha256(cp.read_bytes()).hexdigest()==m['runtime_candidate_sha256']
candidate=json.loads(cp.read_text())
for tool,expected in candidate['executables'].items():
    assert str(Path(shutil.which(tool,path=os.environ['LIVE_PATH'])).resolve())==expected,tool
assert str(lab.resolve())==m['lab_realpath']
assert str(Path(os.environ['RUN']).resolve())==m['run_realpath']
sys.path.insert(0,str(Path(os.environ['SOURCE'])/'scripts'))
from prepare_goal_smoke import runtime_tree
for name,h in {**m['source_files'],**m['runtime_files']}.items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h, name
for root,pin in m['runtime_trees'].items(): assert runtime_tree(root)==pin,root
config=Path(os.environ['RUN'])/'config.json'
assert hashlib.sha256(config.read_bytes()).hexdigest()==m['config_prebinding_sha256']
auth=Path(os.environ['TEST_HOME'])/'.pi/agent/auth.json'
assert not auth.is_symlink() and stat.S_IMODE(auth.stat().st_mode)==0o600
value=json.loads(auth.read_text()); assert set(value)=={'openai'}
a=value['openai']; assert set(a)=={'type','key'} and a['type']=='api_key'
assert isinstance(a['key'],str) and a['key'].strip() and not a['key'].startswith('!')
assert not list((Path(os.environ['RUN'])/'work').iterdir())
print('Pins and credential shape PASS; no credential values printed, no model calls')
PY
cd "$LAB/Test-project"
env -i HOME="$TEST_HOME" PI_CODING_AGENT_DIR="$TEST_HOME/.pi/agent" \
  PATH="$LIVE_PATH" TERM="${TERM:-xterm-256color}" PI_OFFLINE=1 \
  PI_PING_PONG_BRIDGE="$PI_PING_PONG_BRIDGE" \
  "$RELEASE/node_modules/.bin/pi" --no-extensions \
  -e "$LAB/candidate/extensions/pi-reviewed.ts" --no-mcp --no-skills \
  --no-prompt-templates --no-context-files --tools read,bash \
  --append-system-prompt 'Test single Goal smoke reviewer: independently inspect every request, task, actual and retained evidence. Use read for inspection; bash only for the exact current review-v2 callback, with tool timeout 5 seconds. Never auto-endorse, edit outputs/governing files/state/settings, launch workers, make grants or inspect credentials/environment/unrelated projects. Missing evidence means no acceptance. No other shell/network commands.' \
  --provider openai --model gpt-6.1-sol --thinking low \
  --session-dir "$RUN/reviewer-sessions"
```

In **that TUI**, the human enters exactly the line printed in Step A: `/pi-ping-pong <actual RUN>/config.json`. No generative preparation, invented session IDs, or shell `/goal`. Receiver authentic bind → source-snapshot Core → real release `pi --mode rpc -e <Goal>` → Worker → eval → existing Pi Reviewer transport. `PI_OFFLINE=1` disables background metadata/update activity, **not provider inference**. Do not close/switch the Reviewer or launch it a second time.

The Reviewer independently reads each request, pinned evaluator, actual/retained evidence, and state/criteria. Only after semantic review does it execute **one addressed `review-v2` command from the current message**, using bash with a **5 s** tool timeout; never unconditional auto-endorse. `correct` is allowed only through the existing bound API, not by changing the evaluator. Reviewer does not edit outputs/state/settings. Unknown delivery/error => FAIL and stop; do not resend.

**Human emergency stop** from another TTY, using the RUN/HOME/PATH saved in Step A:

```bash
env -i HOME="$TEST_HOME" PATH="$LIVE_PATH" \
  python3 -B "$PI_PING_PONG_BRIDGE" human --config "$RUN/config.json"
```

Enter `{"kind":"cancel","message":"Test stop the single Goal smoke"}` and `AUTHORIZE <actual-run-id>`. Do not pipe it or use model approval. Observe durable cancelled state and absence of new starts; abort any active Reviewer through its **own TUI**. Close that TUI only after settlement; do not `pkill`, blindly kill a PID, or delete evidence. If quiescence cannot be established, retain the lab for diagnosis and do not continue.

## 4. PASS/FAIL and usage

**PASS only if all hold:**

1. Manifest identity is preserved before/after; prebinding config changes only through authentic binding; Core pins match actual governing bytes; `Store.read()` passes integrity. Final source/runtime/realpath checks match the manifest; do not compare post-binding config to the draft hash.
2. Actual `a.txt` has exact bytes and regular `b.json` has the exact object; new proof files exist; actual accepted Goal waits/settlement; **two** Worker starts in **two distinct session IDs**, with one original runId.
3. Core `execution=finish`, all criteria pass/actions verified; consumption cycles **1,2**, scope main/main, assessed exactly once; initial grant unchanged, closure use **0**, additional grants **0**, no blockers/operations/verification pending. `active_seconds` is cumulative, not reset.
4. Three normal fresh eval/review boundaries (or explicitly recorded bounded corrections, ≤6 reviews), authentic Reviewer identity, and matching request/state/eval/checkpoint/live+archive hashes. Independently inspect archived bytes, not just Worker report/exit 0/native completion.
5. No in-flight Worker/evaluator; evidence of final owned-group cleanup; no Worker shell/tool-loadout drift, unrelated effects/processes, or unaccounted usage. Absence of a marker is not universal proof of quiescence.

Any unproven item => **FAIL/UNKNOWN, not PASS**. Cancel/timeout/crash/attention is not finish. No automatic retry or resume. Preserve a failed attempt; first logical launch is one attempt, and routine human approvals during work mean autonomy FAIL. Until a live launch occurs, pass@1/verified_finish@1 are **N/A**, attempts **0**.

**Estimate, not invoice:** Worker: 2 × (60k input × $0.10/M + 8k output × $0.50/M) = **$0.020**; Reviewer: 3 × (60k input × $2/M + 5k output × $10/M) = **$0.510**. Total **≈$0.53**, reserve with three corrective reviews ≈**$1.04** using local catalog rates for input ≤272k. These are assumed aggregate turns, not token enforcement; tariffs/account availability were not queried from provider.

**Operational stop threshold: $2 calculated usage cost for this smoke, or 12 min elapsed.** At threshold the operator stops further launches and authentic-cancels/aborts the current one if still possible. This is **not a hard cap**: an active remote call/Reviewer may already cost more, report later, or return no usage. No maximum per-active-run charge is guaranteed. Any error, missing usage/identity, rate/tier change, request >272k input, or unverified cleanup also prohibits another run regardless of amount.

After completion/before any future run, collect provider-reported input/output/cache/total from **both Worker sessions plus the fresh Reviewer session**, including usage-only records and failed calls; preserve response IDs when available and deduplicate entries. Do not add reasoning a second time on top of output. SDK/session `usage.cost` is a local estimate; provider billing/export, if available, is actual charge evidence and must be reported separately, not added to the estimate. Missing terminal usage = **COST_UNKNOWN**, not $0; investigate and obtain new authorization before any next run. Cache warming/retry/compaction are disabled to reduce hidden activity, not to guarantee billing truth.

## 5. Permissions, checks, and diff

Separate approval is required for: **one** prepared Goal run and its manifest/UUID; exact candidate/models; disposable lab/private-profile writes; dedicated inference auth file and its same-UID risk; metered inference and **soft $2 threshold with possible overshoot**; cooperative host without OS sandbox; operator/Reviewer presence and described cancellation. No approval is requested or granted for Ralph, installation, commit/merge, real external mutations, crash/resume, or further attempts. Production/personal keys/data are prohibited.

Local checks (no models):

| Gate | Result |
| --- | --- |
| `UV_OFFLINE=1 npm run check` | **135 Python PASS** (15 legacy +56 protocol +33 bridge +31 fault), receiver, ESLint/TypeScript/Ruff PASS; production bytes identical to final HEAD at that time |
| `node scripts/test_runtime_boundaries.mjs` | **8 Ralph lifecycle characterizations + 2 metering parser cases PASS**, preserving SURVIVES as a confirmed limitation |
| `node scripts/test_goal_profile.mjs` | **PASS**, real SDK/Goal extension: exactly read/write + 3 Goal tools; 0 messages/model calls, runtime-created auth.json empty |
| `python3 -B scripts/test_goal_smoke.py` | **1 PASS**, missing/wrong/malformed/extra/UTF8/symlink/premature-peer measurements, two-cycle `Controller.apply/transition`, unchanged runId, main/main assessed, no closure, duplicate lab refused |
| lint/Ruff, shell syntax, local links, pins, exact diff/status | **PASS** |

Existing suites cover Darwin race/live EPERM denial, no dispatch after cancellation, late callbacks, owned descendants, Goal query polling, evaluator timeout, realpath/worktrees, F1–F4 and Protocol 1. The new fixture test applies reports directly to Controller **without transport**: schema/accounting measurement, not real independent review/hash-chain acceptance. Native profile probe did not activate `/goal` or check a model. The first final fixture gate also rejected repeated external HEAD drift; due to `&&` short-circuit, the following displayed log was old, not a fresh native test. That was not a new PASS. Provenance was then split into frozen execution commit and moving source HEAD without changing Core byte guards; both tests were explicitly rerun. Initial harness assumptions (HEAD drift, SDK creates empty auth file, wrong test API signature) were recorded and fixed without production changes or weakening expected exits; they are not misreported as failed live attempts.

New files: this report, candidate JSON, `scripts/prepare_goal_smoke.py`, `scripts/fixtures/goal_smoke_eval.py`, `scripts/test_goal_smoke.py`, `scripts/test_goal_profile.mjs`. Updated `docs/protocol-2-live-e2e-plan.md`, `docs/README.md`. No production/vendor/config/global runtime changed; private temp fixtures were cleaned through their normal path and evidence kept separately. Final `git status` (this agent did not stage):

```text
 M docs/README.md
 M docs/protocol-2-live-e2e-plan.md
?? docs/protocol-2-goal-ralph-readiness.md
?? docs/protocol-2-goal-smoke-candidate.json
?? scripts/fixtures/
?? scripts/prepare_goal_smoke.py
?? scripts/test_goal_profile.mjs
?? scripts/test_goal_smoke.py
```

It is stored in private final evidence with the complete dirty patch, untracked bytes/hashes, and separate diff of external tooling commits. KB project README/routing were read; KB was not changed, and its older overview does not override current source/test evidence. **Stop here; do not run real models.**
