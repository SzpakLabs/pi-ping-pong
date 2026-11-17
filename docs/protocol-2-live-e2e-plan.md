# Historical protocol-2 bounded Goal/Ralph E2E plan

> **Superseded for current manual testing.** Start with [three practical cases and new-chat prompts](manual-e2e.md), using the existing worktree, installed Pi and subscription. The pinned-runtime/private-HOME/isolation/billing gates and full matrix below describe an older proposed stand, not prerequisites for those cases. Record observed versions, usage gaps and failures; do not require another lab or old candidate approval. Historical code blocks remain for reference only, not as executable current launch instructions. Protocol identity and independent acceptance safeguards still apply through the current run contract.

## 0. Historical decision: a separate minimal Goal smoke

**Goal: READY — READY FOR EXPLICITLY AUTHORIZED SMOKE TEST. Ralph: BLOCKED.** Paid launch is not authorized. This is one new, narrow profile, not authorization for the full matrix below.

Current gates, exact commands, PASS/FAIL criteria, costs, and permissions are in the [Goal/Ralph readiness report](protocol-2-goal-ralph-readiness.md); exact source/runtime/fixture pins are in the [candidate JSON](protocol-2-goal-smoke-candidate.json). Frozen execution commit **`8ad1193b261aed27d75a6df352bd4c542aac7f0e`** contains the Darwin process-exit fix; source HEAD observed during candidate preparation, **`105bcaf8d3df62a1f33258f6bafd1bb637f4e598`**, contained only external dev-workflow commits. The helper verifies actual Core bytes against the frozen commit, does not chase moving HEAD, and does not transfer approval to new code. The native Goal profile, without a model prompt, confirmed **read/write + Goal tools, without bash/codemode/MCP**. Worker creates no shell/subprocess and performs no external effects. Reviewer uses the existing Pi transport and short bound `review-v2` callbacks.

Preparation: `python3 -B scripts/prepare_goal_smoke.py --lab <fresh-private-path-outside-source>` **does not launch models**; it copies an exact Core/receiver snapshot and creates a separate empty local target, evaluator/TASK/config/private profile, and manifest. No runtime installation or commit. Dirty helper/evaluator bytes are pinned separately, not replaced by an old installed PPP. Smoke: A squares → B sum, **no more than 2 Worker cycles total**, main=2, **closure.authorized=false**, no grant/resume/retries. Cycle/review=60 s, active wall=90 s; Worker deadline≤90 s, evaluator≤60 s, review≤60 s plus cleanup. Fresh UUID/runId/accounting/evidence are required.

Estimate **≈$0.53**, corrective-review reserve estimate **≈$1.04**; **$2 operational stop threshold**, elapsed observer threshold **12 min**. There is no hard dollar cap or guaranteed maximum price for an active remote call. Provider-reported tokens and locally calculated cost are checked separately across Worker/Reviewer sessions; missing usage → COST_UNKNOWN and prohibits subsequent launches. No new billing service is needed. Worktree/realpath/read-only modes are accidental-path guards, **not an OS sandbox**. Acceptance of same-UID, in-flight cost, and dedicated auth-file risks requires separate authorization; secrets are not passed through environment or copied from a personal profile.

The full 10-run matrix, Ralph/recovery, hard-billing, and strict-isolation requirements below **remain deferred/BLOCKED in their original scope**. They are not prerequisites for this single Goal read/write-only smoke. Unresolved Ralph detached-owner/escaped-child and nested-usage gaps do not automatically block Goal. Shared tool-loadout drift, crash, or uncertain cleanup also makes the Goal smoke FAIL unless the shared risks are explicitly resolved.

## History: joint planning/remediation gate

**REMEDIATED LOCALLY; BLOCKED FOR LIVE LAUNCH.** G1 was fixed test-first; the latest shared gate: **135 Python PASS**, receiver/tooling PASS. Native runner characterization: **8 PASS**, metering parser: **2 PASS**, without models. G2 cleanup containment, G3 complete accounting/budget policy, and G4 enforced isolation remain open; details: [remediation report](protocol-2-e2e-gate-remediation.md). A newly approved source candidate and separate live authorization are also required. Earlier READY/FAIL results below are retained as history, not current results.

At the original planning stage, clean HEAD `96a0b2e34d48e81194b863d6333a4bf02b28022e`: regression fixes are in `a71f0cf1cbecd1db2223c41732712d2beb6fc8a6`, and earlier F1/F2 and F3/F4 work is preserved. The older audit describes a diff that was then uncommitted; it is now in two later commits. No Git mutation/commit was performed then. Canonical staging/commit were also unchanged during remediation; disposable local clone/worktree checks are described in the report.

The audit,  [current protocol](action-scoped-protocol.md), [integration plan](autonomous-run-integration-plan.md),  skill/reference, controller/bridge guards, receiver launch path, and actual installed Goal/Ralph boundaries were reread. Locked ingestion, grant generation, unsettled delivery recovery (including correction), cycle assessments, request binding, and owned-process cleanup were checked. Earlier reports did not replace source inspection.

Historical planning preflight `UV_OFFLINE=1 npm run check` **exited 1**:

| Check | Observation |
| --- | --- |
| ESLint / TypeScript / Ruff | PASS |
| Legacy Python | 15 PASS |
| Action protocol | 56 PASS |
| Action bridge | 32 PASS, **1 FAIL** of 33 |
| Fault regressions | 25 PASS |
| Pi receiver | PASS |

Total: **128 PASS, 1 FAIL**, not 129 PASS. Log: `/tmp/ppp-e2e-plan-preflight.log`. Failure: `test_cancel_at_eval_completion_prevents_dispatch`, exit **1 instead of 2**. Three targeted repetitions yielded 2 PASS / 1 FAIL; five subsequent isolated PASS repetitions do not erase the failure. Another bounded diagnostic series reproduced it and retained a private fixture:

`/var/folders/cf/nv7pkv557qq8ypy9h8vhmzlc0000gn/T/ppp-e2e-cancel-diagnosis-p2o4qpuo/`

Observed state: `execution=cancelled`, `cycle=0`, acceptance unknown, with no Worker/dispatch; projection — `attention_required`, reason `[Errno 1] Operation not permitted`. This is **not evidence of false acceptance**, but is a confirmed lifecycle/cleanup regression. At planning time the exact syscall/race had not been established and code was unchanged. It was later reproduced: `killpg(SIGTERM)` EPERM during normal exit: `waitid(WNOWAIT)` temporarily returns None, the next call observes exit 0. Bounded 50 ms unreaped-exit confirmation fixes the false cleanup error; a real signal failure against a live leader is not suppressed. Deterministic RED: two subtest errors and one Core/evaluator cancellation assertion failure; GREEN and 40/40 original repetitions confirmed.

### Launch blockers

| Gate | Severity / basis | Closure condition |
| --- | --- | --- |
| **G1 — CLOSED locally** | Confirmed Darwin exit-visibility race, not an ownership substitution or a proven fixture-publication bug | Fix + 3 deterministic methods, native failure traceback, 40 original repetitions PASS, shared gate PASS. The fix is now in code-only commit `8ad1193`; its regression tests are separate in `578a459`. Runtime was not installed; a clone of old `96a0b2e` still lacks the fix. |
| **G2 — BLOCKED for full cleanup** | With the actual unchanged `runner-rpc.ts` and a synthetic peer: same-group child stops on normal/cancel/timeout; escaped child survives; detached peer survives native-owner death | Approve an existing process containment/quiescence mechanism for the full execution domain before live; do not substitute an outer lease or killpg. Core-controller crash with a live Worker and native-owner crash are different cases; model-free probes are not real Goal/Ralph E2E. |
| **G3 — BLOCKED for hard/full billing** | SDK usage from provider responses is measurable, but `usage.cost` is calculated locally; native Ralph 2.1.0 does not persist complete nested usage/response IDs in iteration records. Abort/crash may lose usage. PPP has no dollar ceiling or immutable weight proof | Confirm rates/accounting for all calls and availability of exact IDs. Choose actual hard billing enforcement or explicitly accept an operational budget with possible overshoot. Record the acceptable model-version pinning level. |
| **G4 — BLOCKED for strict isolation** | Local tests PASS: detached disposable worktrees, evidence realpath-escape refusal, moved-run pin-drift halt. However, the Git common directory/host resources are shared and same-UID write paths are not constrained by kernel policy | Approve a disposable VM/container/OS policy: only the lab writable, runtime read-only, egress limited to the approved inference/billing endpoint, and no production credentials/mounts. Without such an environment, do not call a host worktree full isolation. |

G1 no longer blocks the local baseline. This does not close confirmed G2/G4 limitations or the G3 accounting gap. No acceptance/authority bypass was found in the inspected scope; READY is not granted for the full live matrix. A green local gate is not live authorization.

## 1. Matrix and limits

One sequential campaign: **10 fresh runs**, with no concurrent writable runs. S1 Goal only, S2 Ralph only; S3–S6 run in both modes. Each instance has its own worktree, private HOME, runId, evaluator hash, and reviewer session. S3 and S4 are separate runs; cancelled S3 is not revived for S4.

The limits below are **proposed explicit authorization**, not yet granted. `main` — initial cycles; `closure` — an **explicit cap for these disposable tests only**, not a new default. Only S5 allows one additional main grant `+2`. Worker cycles include spent interrupted reservations. A single native cycle may contain many model responses/calls.

| ID / modes | Journey under test | Planned Worker cycles / absolute reservation limit | Main / test closure cap | Active limits | Elapsed deadline per instance | Operational USD ceiling per instance |
| --- | --- | --- | --- | --- | --- | --- |
| **S1 Goal** | A → B → fresh eval + independent review → Core finish | 2 / 3 | 2 / 1 | cycle 180 s; Worker ≤225 s; review 180 s; wall 240 s | 15 min | **$5** |
| **S2 Ralph** | Same results through a real native iteration boundary | 2 / 3 | 2 / 1 | As S1; native max_iterations=1 / PPP cycle | 15 min | **$5** |
| **S3 Goal + Ralph** | Missing synthetic choice blocks B; A runs independently, then quiet wait | 1 / 2 | 1 / 1 | As S1 | 12 min, including 60 s quiet observation | **$8** each |
| **S4 Goal + Ralph** | Independent A; invalid response → valid response → automatic B/closure in the same runId | 2 / 2 | 1 / 1; no main grant | As S1 | 20 min | **$8** each |
| **S5 Goal + Ralph** | A → paused_budget → explicit +2 → B → C → finish | 3 / 4 | 1 + single grant of 2 / 1 | As S1 | 20 min | **$8** each |
| **S6 Goal + Ralph** | Real Worker interrupted after one local effect → reconciled resume → B → finish | 2, first interrupted / 3 | 2 / 1 | wall **60 s**, cycle **120 s**: Core deadline ≤60 s, before native Ralph timeout 120 s; review ≤60 s | 20 min, including ≤30 s quiescence check | **$10** each |

Total proposed ceiling: **$78**, up to **174 min** sequentially. Proposed first authorization package: **S1/S2 only, $10**, then a separate decision on S3–S6. This is not permission to spend the limit or a promise of native hard-dollar enforcement.

Review-attempt limits for campaign control: S1/S2 ≤8; S3 ≤6; S4 ≤10; S5 ≤12; S6 ≤10 per instance. These allow one authorized corrective verification per boundary. This is an external FAIL/stop criterion, not a new Core setting or reason to reset metadata. No additional human inputs/grants/retries beyond the matrix are authorized.

In this implementation, `wall_seconds` limits active operations, **not total accumulated run elapsed time**. Do not present it as an overall campaign timeout. A separate operator records UTC start/deadline, observes local status, and declares FAIL/sends authentic cancellation when time/cost is reached. Do not add a scheduler/watchdog/semantic loop. Account separately for cleanup/in-flight overshoot; if a hard bound on actual charges/process time is required, G3/G4 must provide it before launch.

### PASS/FAIL by scenario

**General FAIL:** scope violation, wrong runtime/model, uncertain cost or delivery, unplanned grant/reset, repeated effect, edits to pinned contract/evaluator, fake native boundary, stale evidence, exceeded limit, or missing independent evidence. `attention_required`, timeout, native complete, exit 0, and “the model said it is done” are not PASS. No hidden retries until green.

- **S1:** A contains squares of 2,3,5; B contains their sum, 38. Two selected actions, real Goal RPC session records; accepted `goal_wait` and settlement for each Worker. Fresh post-worker evaluation, real hash-bound reviewer decisions, all criteria pass/actions verified, no blockers/uncertain/unassessed; **Core `execution=finish`**. Native `goal_complete` is neither needed nor simulated: Protocol 2 finishes independently; Worker does not accept its own work. Any additional routine human confirmation is an autonomy FAIL.
- **S2:** same independent checks; `ralph/NNN/RALPH.md` with max_iterations=1, real runner status/iterations/events, nested RPC handshake/provider/model/thinking, and actual iteration completion. Verify no nested child remains live before evaluation. Outer `agent_settled` does not replace the native Ralph boundary. Core finish is mandatory.
- **S3:** input is absent from the first evaluation; only B receives a blocker. A actually runs; B does not start and its output is absent. After A, main is exhausted, blocker retained, wait uses a real grouped request. Over 60 s, consumption/Worker starts/review dispatches/usage do not change; reminder does not call a model. This scenario is PASS, but **task acceptance is NOT finish**. Then perform planned human cancellation for cleanup and preserve evidence. If the entire run stops before A, FAIL scoped independence.
- **S4:** after the same wait the human first submits addressed resolution without the required input. The independent evaluator rejects it; blocker remains, no Worker/grant. The human then atomically creates synthetic input and confirms a valid addressed receipt. Core independently validates → closure provenance → B → finish; runId remains the same, main consumption remains 1, closure consumption becomes 1. No additional “I authorize continuation” or new launch/resume. Invalid input must not be accepted from prose.
- **S5:** after A, state is paused_budget, counter 1, no B/C. The human approves exactly +2 against the **current** request ID. Fresh review validates authority; B/C run automatically as main. Initial grant is unchanged; one grant is added, cycle/consumption=3, all in the same runId. B/C cannot become closure. Do not submit duplicate/stale grants in a paid package without separate authorization; local regressions already test these.
- **S6:** A first makes `operation` reservation, then creates one create-once local receipt with a separate invocation log; before checkpoint it performs a bounded 300 s test wait. The real Core deadline interrupts the live Worker before that wait completes. Preserve the interrupted reservation/owner/session and uncertain operation. **Do not issue cancel/halt**; they are terminal. Wait until quiescence of all native children and release of the execution lease are proven; only then perform one explicit `resume`. Fresh independent evaluation confirms the actual effect succeeded and assesses the spent cycle; replacement performs B, not A. One invocation, one reservation, one receipt; original operation owner/cycle retained; new session for B; monotonic counters; same runId; finish. If runtime exits differently, a marker is missing before interruption, terminal halt occurs, an orphan is live, or reviewer delivery is pending/ambiguous, the result is FAIL/blocked, not “try resume again.” Non-replay cannot be proven by one idempotent insert that hides repetition: invocation count is checked too.

## 2. Models, versions, and cost

### Proposed pins

| Component | Pinned candidate / source |
| --- | --- |
| PPP | Full-matrix candidate requires separate approval. G1 is committed separately from tests in `8ad1193`, the frozen execution commit (source HEAD observed during preparation was `105bcaf`, dev workflow only); the new Goal-only smoke uses the separately pinned source snapshot + committed fixture helpers from section 0. Old `96a0b2e` does not contain the fix |
| Pi | `@earendil-works/pi-coding-agent` **1.3.0**, release CLI, not the mutable managed launcher |
| Goal | `@narumitw/pi-goal` **0.54.13**, `/Users/macos/.pi/agent/npm/node_modules/@narumitw/pi-goal/dist/index.ts` |
| Ralph | `@lnilluv/pi-ralph-loop` **2.1.0**, `/Users/macos/.pi/agent/npm/node_modules/@lnilluv/pi-ralph-loop/src/index.ts` |
| Toolchain inspected | Darwin; Python **3.15.0a1**; Node **v26.6.0**; platform/Git/toolchain are recorded again in the authorized execution environment |
| Worker, outer + Ralph nested | **openai / gpt-6-luna**, thinking **low** |
| Independent reviewer | **openai / gpt-6.1-sol**, thinking **low**, separate new Pi TUI session; existing PPP receiver transport only |
| Evaluator | Full Appendix A; file and fixture-generator SHA-256 recorded before binding/launch; Python argv pinned |

This proposes metered `openai`, **not a silent switch** from the default `openai-codex`. Both exact model IDs were found in the local Pi 1.3.0 catalog, but account/server availability was not checked. Subscription/OAuth limits are not a USD cap. No fuzzy substitution, provider fallback, auto-upgrade, remote package resolution, or model changes during a run. Different models require a newly approved pin and recalculation before first launch.

SHA-256 values of selected files measured during plan preparation (entrypoints do not replace a complete dependency/image manifest):

```text
Pi bundle cli.js   e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774
Goal dist/index.ts 10313c6bc030193a8cef4d8c6da31ab9dacb7d3b4b930a6bfee5404ca5871da1
Ralph src/index.ts 43bfc74acf5dab227a07f10b0b8eb003dcabeca44041cf6714e6be23dea97f63
openai.json        3598d87bd39e40fe6ae44b07ecf3f9d27cb2e745e114c8b0c0fb0a3a84dd8d3e
Appendix eval.py   001578a686df4c43c32fb3185fc04c92c06fa212c2e27a9a8eed4e219cfb2edc
Appendix prepare.py 0fe211ccd3e4ff7b34d20a5a002621b6ad92f18a3385959f298cb7cbd68c5887
```

Appendix hashes include the trailing LF, as does the extraction command. Any edit requires a new hash and reassessment before launch.

Pinning records the requested provider/model ID, local catalog hash, runtime version, actual response model, and available provider revision. These IDs do not prove immutable weight snapshots. Strict version pinning requires an existing provider snapshot ID; if unavailable, explicit consent to ID-level pinning and documentation of the limitation are required, otherwise G3 remains open.

### Estimate, not a billing quote

The local catalog `providers/data/openai.json` lists USD/1M-token rates (input tier ≤272k):

- Luna: input **0.10**, output **0.50**, cache read **0.01**, cache write **0.125**.
- Sol: input **2.00**, output **10.00**, cache read **0.10**, cache write **2.50**.

These static rates have not been verified with the provider; record the current rate/currency/tier before authorization. Different rates apply above 272k input; such a request in this package means stop/FAIL, not a silent move to a more expensive tier.

Planning unit per Worker cycle: about 60k noncached input + 8k output across all tool/model turns = **$0.010**. Per review boundary: 60k input + 5k output = **$0.170**. These are assumptions, **not enforced token limits**. Typical estimates: S1/S2 ≈$0.53 each; S3 ≈$0.35 each; S4 ≈$0.87 each; S5 ≈$0.88 each; S6 ≈$0.70 each. S6 estimate includes one additional verification contingency (not a required dispatch). Total ≈**$6.66**, planned 2× reserve ≈**$13.32**; $78 is a separate padded operational ceiling, not expected spend.

Actual-cost formula: `Σ(input*r_in + output*r_out + cacheRead*r_read + cacheWrite*r_write)/1e6`, using actual non-overlapping usage fields and the applicable tier. Reasoning is already included in output; do not double-count it. Include retries/compaction/outer Ralph/nested Ralph/reviewer/corrections/failed calls. Expected spend while waiting is zero; verify this.

**Hard-cap caveat:** PPP has no `max_cost_usd` and receives no dollar balance. Do not invent a config flag. Even Goal token guards can overshoot by one call and do not limit the separate Reviewer. A provider project budget is not a hard cap without confirmation of actual enforcement. Before execution, choose an existing real hard-billing facility or explicitly accept a soft stop plus in-flight risk with a separately approved worst-case allowance. Without this, the hard dollar-ceiling requirement is unmet and paid runs are not allowed.

For Ralph, the `--no-session` nested child means summing only `sessions/*.jsonl` is incomplete. Actual nested usage/response IDs or an agreed provider billing export for a dedicated test credential are required, with no other concurrent clients. Unknown cost is not replaced with zero; incomplete attribution means COST_UNKNOWN/FAIL measurement.

## 3. Scope, isolation, and permissions

Separate approvals are required before execution:

1. Separately approve the exact candidate for the full matrix. The G1 code fix is `8ad1193`; regression tests are in separate commit `578a459`. The Goal-only smoke has its own manifest/authorization in section 0.
2. Authorize local disposable clone/worktree/profile preparation in a specific lab root and native-boundary characterization for G2. No canonical branch/settings changes or package installation.
3. Approve an existing isolated environment for G4. Commands below are intended to run **inside it**; a host directory alone does not satisfy this gate. Do not change host firewall/VM/cloud without separate authorization. If runtime paths differ there, update and approve pins first; do not silently substitute them.
4. Authorize provider/model IDs, a dedicated test credential via environment, metering/billing read, USD ceilings, and selected hard/soft-cap policy. Do not read/print/copy personal `auth.json`; do not store the key in evidence.
5. Specify the scenario package (S1/S2 proposed first), human operator, and availability for confirmed console inputs. S5 grant and S4 valid input must be confirmed using actual IDs, not pre-fabricated receipts.
6. Authorize **only** the S6 local receipt effect, forced native timeout, and one reconciled resume. Do not authorize broad PID searches/kills, global `pkill pi`, queue purge, or unlimited recovery.

Worker write scope: only the selected action output in `RUN/work/`, its checkpoint, and S6 invocation/receipt; TASK/context/prior evidence are read-only. Human may change only `work/Test-input.json` for S4. Evaluator writes only its own unique proof. Reviewer reads contract/evidence and records decisions only through `review-v2`. Core owns state, journals, archive, and generated native prompts. Worker cannot alter evaluator, state, human inbox, reviewed files, or create approvals/grants.

No email/DNS/payments/deploy/publish/git commit/push, external DB/ports, browser tasks, production data, or remote Git/fetch. The only authorized external effect is explicitly approved inference calls and necessary metering reads. VM/container must not mount personal HOME/credentials/production worktrees; the inference credential is the only runtime secret. Private HOME prevents discovery of personal settings/skills/MCP. No additional extensions are loaded. Worktrees do not isolate DB/ports/targets; those are simply absent from the task.

All runs are new: UUID, private directory 0700, governing files 0600. Do not open/migrate historical runs or edit failed frozen contracts. An evaluator defect found after launch means FAIL for the old attempt; a new run requires separate authorization. Do not “fix” G1 in a vendor package or global Goal settings.

## 4. Exact commands — only after gates/authorization

These are **future execution instructions**, not evidence that E2E was performed. There is no command `pi install`, `npm install`, runtime sync, new scheduler, or second semantic orchestrator. Appendix helpers only create fixtures/measure files; they do not launch models, make reviewer decisions, or control Core transitions.

### 4.1 Local preflight and lab

In the approved isolated environment with read-only runtimes already available:

```bash
set -euo pipefail
umask 077
export SOURCE=/Users/macos/codex-context/skills/pi-ping-pong/.pi/worktrees/permission-friction-research
export CANDIDATE="${APPROVED_REMEDIATED_OID:?No approved remediated source candidate yet}"
# Commit/integration require separate authorization; nothing is committed here.
test -z "$(git -C "$SOURCE" status --porcelain -- scripts extensions)"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$CANDIDATE"
(cd "$SOURCE" && UV_OFFLINE=1 npm run check)  # Red gate => STOP.
export LAB=$(mktemp -d "${TMPDIR:-/tmp}/ppp-live-e2e.XXXXXX")
export RELEASE=/Users/macos/.pi/agent/install/releases/1.3.0
export REAL_PI="$RELEASE/node_modules/.bin/pi"
export GOAL_EXT=/Users/macos/.pi/agent/npm/node_modules/@narumitw/pi-goal/dist/index.ts
export RALPH_EXT=/Users/macos/.pi/agent/npm/node_modules/@lnilluv/pi-ralph-loop/src/index.ts
export NODE_BIN=$(dirname "$(command -v node)")
export PYTHON_BIN=$(dirname "$(command -v python3)")
export LIVE_PATH="$RELEASE/node_modules/.bin:$NODE_BIN:$PYTHON_BIN:/usr/bin:/bin:/usr/sbin:/sbin"
test -x "$REAL_PI" && test -f "$GOAL_EXT" && test -f "$RALPH_EXT"
git clone --local --no-hardlinks --no-checkout -- "$SOURCE" "$LAB/repo"
git -C "$LAB/repo" remote remove origin  # Disposable clone only.
test "$(git -C "$LAB/repo" rev-parse HEAD)" = "$CANDIDATE"
export PLAN="$SOURCE/docs/protocol-2-live-e2e-plan.md"
python3 -B - <<'PY'
import os,re
from pathlib import Path
text=Path(os.environ['PLAN']).read_text()
for name in ('eval.py','prepare.py'):
    blocks=re.findall(r'<!-- file: '+re.escape(name)+r' -->\n```python\n(.*?)\n```',text,re.S)
    assert len(blocks)==1,name
    p=Path(os.environ['LAB'])/name
    p.write_text(blocks[0]+'\n'); p.chmod(0o600)
print('Fixture recipes extracted; no runtime/model started')
PY
```

Before the first launch, record `runtime-manifest.json`: candidate OID; realpath, size, SHA-256 of all source scripts/receiver/evaluator/generator; Pi bundle and package.json; recursive Goal/Ralph source/dist files; versions/hashes of dependency lockfiles/approved dependencies; Node/Python binaries/versions; model catalog/rates; private Goal settings; environment allowlist without secret values. Recheck the manifest before every run/resume. Any drift => STOP and renewed approval. A version string alone is not a sufficient hash pin. Do not copy provider credentials into the manifest.

### 4.2 Prepare one instance (no auto-launch loop)

Mappings: S1/goal, S2/ralph; S3/goal and S3/ralph; S4/goal and S4/ralph; S5/goal and S5/ralph; S6/goal and S6/ralph. Choose values explicitly for each, then run this block once:

```bash
export SCENARIO=S1 MODE=goal  # Replace only with the approved matrix row.
export CASE="$SCENARIO-$MODE"
export WT="$LAB/$CASE"
git -C "$LAB/repo" worktree add --detach "$WT" "$CANDIDATE"
export RUN="$WT/.pi-ping-pong/runs/Test-$CASE"
export TEST_HOME="$LAB/home-$CASE"
export PI_PING_PONG_BRIDGE="$WT/scripts/bridge.py"
python3 -B "$LAB/prepare.py"
# Before launch: inspect TASK/config/eval, manifest hashes, and negative fixture checks.
# Do not invoke generative /pi-ping-pong preparation or let a model change the evaluator.
```

Record minimum file pins using the following command; dependency/runtime image identity is separately required for G4. It does not launch Pi. `APPROVED_IMAGE_ID` must be the approved immutable image digest or exact OS policy/profile digest, not an arbitrary label:

```bash
: "${APPROVED_IMAGE_ID:?Supply agreed isolation image or policy digest}"
export APPROVED_IMAGE_ID
python3 -B - <<'PY'
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
run=Path(os.environ['RUN']); wt=Path(os.environ['WT'])
items=[Path(shutil.which('node')),Path(shutil.which('python3')),run/'TASK.md',run/'eval.py',Path(os.environ['LAB'])/'prepare.py',wt/'extensions/pi-reviewed.ts',Path(os.environ['TEST_HOME'])/'.pi/agent/pi-goal.json']
items += sorted((wt/'scripts').glob('*.py'))
pi=Path(os.environ['RELEASE'])/'node_modules/@earendil-works/pi-coding-agent'
roots=[pi/'dist/bundle',Path(os.environ['GOAL_EXT']).parent.parent,Path(os.environ['RALPH_EXT']).parent.parent]
items += [pi/'package.json',Path(os.environ['RELEASE'])/'node_modules/@earendil-works/pi-ai/dist/providers/data/openai.json']
for root in roots:
    items += sorted(p for p in root.rglob('*') if p.is_file() and 'node_modules' not in p.relative_to(root).parts and p.suffix in {'.ts','.js','.mjs','.json','.node','.wasm','.lock'})
records=[{'path':str(p),'realpath':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dict.fromkeys(items)]
c=json.loads((run/'config.json').read_text())
toolchain={'python':sys.version,'node':subprocess.check_output(['node','--version'],text=True).strip()}
assert sys.version.split()[0]=='3.15.0a1' and toolchain['node']=='v26.6.0', 'Unapproved toolchain drift'
m={'toolchain':toolchain,'candidate':subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip(),'isolation_digest':os.environ['APPROVED_IMAGE_ID'],'files':records,'execution_contract':c['execution_contract'],'models':{k:c[k] for k in ('worker_provider','worker_model','review_provider','review_model','thinking')},'secret_environment_names_only':['OPENAI_API_KEY'],'config_binding':'Core pins actual config only after authentic launcher session binding'}
with (run/'runtime-manifest.json').open('x') as f: json.dump(m,f,indent=2)
print('Private manifest recorded; no model call')
PY
```

Before each launch/resume, recompute `files[*].sha256` and verify realpath/image/toolchain/dependency graph. After launcher binding, verify config against Core `pins`, not the pre-binding draft bytes. Do not overwrite the manifest on drift.

Before paid authorization, locally verify evaluator fixtures: missing/wrong/correct A/B/C, malformed output, missing/invalid/valid input, forged/unaddressed receipt, stale grant generation, absent/one/two receipt invocations, pending assessment and nonzero incomplete exit. Exit 0 is allowed only for actual measured outputs. Reviewer must also manually inspect criteria and causal closure. Merely compiling the Appendix does not complete this evaluator-validation gate.

### 4.3 Real Reviewer and explicit launch

A separate interactive terminal is required. `OPENAI_API_KEY` has already been supplied by the human in the process environment; do not enter it in this document, shell history, chat, or a file. The next command is unauthorized until the gates pass. Private HOME settings do not change global Goal/Ralph settings.

```bash
: "${OPENAI_API_KEY:?Provide approved test credential securely, without logging it}"
cd "$WT"
env -i HOME="$TEST_HOME" PATH="$LIVE_PATH" TERM="${TERM:-xterm-256color}" \
  OPENAI_API_KEY="$OPENAI_API_KEY" PI_OFFLINE=1 \
  PI_PING_PONG_BRIDGE="$PI_PING_PONG_BRIDGE" \
  "$REAL_PI" --no-extensions -e "$WT/extensions/pi-reviewed.ts" \
  --no-mcp --no-skills --no-prompt-templates --no-context-files \
  --provider openai --model gpt-6.1-sol --thinking low \
  --session-dir "$RUN/reviewer-sessions"
```

In this Pi TUI, the human enters explicit-path launch (obtain the exact line before entering: `printf '/pi-ping-pong %s/config.json\n' "$RUN"`):

```text
/pi-ping-pong /ABSOLUTE/APPROVED/RUN/config.json
```

`/ABSOLUTE/APPROVED/RUN` is replaced by the **actual `$RUN` from the previous block**, not an invented session ID. The launcher binds the actual reviewer session before Core pins config. Do not set `pi_session_id` or write `pi-receiver.json` manually. `PI_PING_PONG_BRIDGE` is the existing source override; otherwise the receiver defaults to an installed copy that is not approved here. Keep this Reviewer UI open: this checks the current chat-bound transport, not a Headless Reviewer.

Core actually launches real `pi --mode rpc --no-extensions -e <pinned Goal|Ralph> --no-mcp --provider openai --model gpt-6-luna --thinking low ...`. PATH contains the real release CLI, **not** a fake `pi`/`codex`, shim, or proxy. Goal receives real `/goal`, Ralph — `/ralph --path <run>/ralph/NNN`; the native runner creates nested Pi itself. Verify the nested model through the actual `set_model`/`set_thinking_level` handshake; do not infer it from outer argv.

For every callback, the Reviewer independently reads request/context, actual outputs/input, retained evidence, all criteria and causal/authority/progress facts. After review, record exactly one real decision with the command in the message, for example:

```bash
python3 -B "$PI_PING_PONG_BRIDGE" review-v2 --config "$RUN/config.json" \
  --review-id ACTUAL_CURRENT_REVIEW_ID --decision endorse \
  --feedback 'Test independently measured outputs and checked all reported judgments'
```

`ACTUAL_CURRENT_REVIEW_ID` is taken from the current request; do not hardcode 1. This is **not** shell-automation endorsement or an instruction to endorse regardless of evidence. Incorrect observation => existing correction API; contract error/ambiguous delivery => STOP. No automatic resend or second reviewer loop.

### 4.4 Human commands (actual human, separate TTY)

Run all commands with the same approved HOME/PATH/bridge; explicitly select the console human channel. Read current status/IDs:

```bash
python3 -B - <<'PY'
import json,os
from pathlib import Path
s=json.loads((Path(os.environ['RUN'])/'execution-state.json').read_text())
print(json.dumps({k:s[k] for k in ('run_id','cycle','execution','wait','blockers','requests','grants','consumption')},indent=2))
PY
env -i HOME="$TEST_HOME" PATH="$LIVE_PATH" OPENAI_API_KEY="$OPENAI_API_KEY" \
  PI_OFFLINE=1 PI_PING_PONG_BRIDGE="$PI_PING_PONG_BRIDGE" \
  python3 -B "$PI_PING_PONG_BRIDGE" human --config "$RUN/config.json"
```

The command requires TTY, interactive JSON, and `AUTHORIZE <actual-run-id>`. **Do not pipe it, use model-tool authority, or manually write an inbox file.** Use B/Q IDs from status:

- S4 invalid: `{"kind":"resolution","blocker_ids":["ACTUAL_B_ID"],"message":"Test input is configured"}`. The file does not exist yet. Wait for the independent invalid disposition; do not send valid input before it is applied.
- S4 valid: the human atomically creates input with the following command, then repeats `human` with the same actual blocker ID and message `Test supplied the requested Test-blue choice`.
- S5: `{"kind":"grant","request_id":"ACTUAL_CURRENT_Q_ID","cycles":2,"message":"Test explicitly authorize two additional main cycles for B and C"}`.
- S3 cleanup/limit stop: `{"kind":"cancel","message":"Test scenario observation complete; stop without acceptance"}`.

Atomic synthetic input (not a secret):

```bash
python3 -B - <<'PY'
import os,json
from pathlib import Path
p=Path(os.environ['RUN'])/'work/Test-input.json'
tmp=p.with_name('Test-input.pending')
with tmp.open('x') as f:
    json.dump({'choice':'Test-blue'},f); f.flush(); os.fsync(f.fileno())
tmp.chmod(0o600); os.replace(tmp,p)
PY
```

S6: wait for the actual deadline/attention, prove quiescence, and preserve a before snapshot. Only then:

```bash
env -i HOME="$TEST_HOME" PATH="$LIVE_PATH" OPENAI_API_KEY="$OPENAI_API_KEY" \
  PI_OFFLINE=1 PI_PING_PONG_BRIDGE="$PI_PING_PONG_BRIDGE" \
  python3 -B "$PI_PING_PONG_BRIDGE" resume --config "$RUN/config.json"
```

This command intentionally blocks: run it in a separate terminal and keep the Reviewer TUI available. Do not relaunch. Do not use `resume` for S4: continuation after valid input should be automatic. If G2 quiescence is unproven, S6 FAIL; do not kill saved/discovered PIDs or force the lock. Do not edit blocked verification metadata.

## 5. Evidence, independent verification, metrics

Store privately; do not publish raw logs:

- campaign/case manifest, exact argv/realpaths/runtime/model/provider IDs, evaluator/source/contract hashes; timezone-independent timestamps and limits;
- launch record, bound reviewer identity, the complete `execution-state.json` (integrity verified through existing `Store.read()`), bridge status/events, full consumption/grants/blockers/history and original session/owner IDs;
- fresh contexts/eval stdout+stderr/exit/request/review hashes, queue attempts/receipts/delivery entries, content-addressed evidence archive;
- real Goal session/tool events or Ralph native status/iterations/events/transcripts/telemetry, nested model handshake/usage and process-lifecycle evidence; incomplete transcript/usage must be explicitly marked unknown;
- actual A/B/C/input/effect/invocation bytes, hashes before/after invalid/valid/grant/resume; confirmed console receipts without secrets;
- provider request/usage/cost records, including failed/retried/nested/reviewer calls; human minutes, planned/unplanned actions, and limit/cleanup overshoot.

After each finish, a read-only checker/person independent of the Worker recomputes `2²,3²,5²`, sum 38, product 900, or local effect count; do not trust the Worker report or a lone `proof.json`. Check actual files against the Appendix, state integrity/pins, all acceptance statuses pass, all actions verified, blockers resolved, no operations started/uncertain, every consumption assessed exactly once, final review/hash chain, no post-review drift, and no live native children. For S3, instead verify independent A, absent B, open blocker, unchanged snapshots over 60 s, then cancellation without acceptance.

For S4, additionally verify ordering `human.received` → invalid resolution → valid resolution/`blocker.resolved` → `closure.validated` → B `cycle.reserved`; main/closure scopes 1/1. For S5, verify initial 1 + new grant 2, without rewriting the initial grant, and all three reservations in main. For S6, verify reservation → interrupted/uncertain → **fresh review** reconciliation succeeded/assessment → new B session; journal owner/originating cycle retained, invocation count=1. A confirmed effect does not become replayable even if its summary is damaged.

### Required metrics (no values exist before launch)

- **pass@1 / scenario_pass@1** = number of scenario-mode instances passing the full scenario on the first logical run / number launched. Include all infrastructure/provider/quality failures; planned S6 resume is not a new attempt and does not erase failure history. S3 PASS is an expected-wait test, not task finish.
- Report **verified_finish@1** separately for the eight finish-oriented instances (S1/S2/S4–S6); report expected-blocked S3 separately. Do not inflate completion rate with expected-wait cases.
- **attempts/task** = actual first-launch runIds / scenario-mode task; target 1. Any new run after an error increments attempts, even if auth/provider fails before useful work. Also report Worker reservations/starts, reviews/corrections, native turns, provider retries, and resume count.
- **human intervention rate total** = share of launched tasks receiving any human assistance; report count/minutes and planned vs unplanned separately. S4 invalid+valid = 2 planned receipts, S5 grant = 1, S6 resume = 1; S3 cancel is a separate planned cleanup action. **HIR_unplanned target 0**, S1/S2 total-assistance target 0; one authorized initial launch is not an intervention. Do not count automatic Reviewer turns as human actions or hide planned human rate behind autonomy claims.
- Actual USD, tokens by role/layer, active/wait/review/recovery elapsed time, overshoot, and missing telemetry. Subscription billed USD may be unknown; do not report $0 based only on a UI usage estimate.
- Before models: `launched=0`, actual results/cost/pass@1 **N/A**, not 0/10 failures or 10/10 PASS.

Do not run additional attempts to improve pass@1. After FAIL, stop the package and preserve evidence; rerun requires separate authorization and retention of the first result. After baseline acceptance, the next architectural stage remains separate: Headless Reviewer/original-chat UI, without adding Observer/pi-tick/cross-chat/supervisor here.

## Appendix A — concrete evaluator, not a fake runtime

Below are recipes for **future disposable files**, not an installed implementation. They independently measure task outputs through existing schema 1; they do not impersonate Pi/Goal/Ralph, create Worker output, or sign reviews. The negative fixture validation and human review described above are required before live use. Pin recipe hashes before launch; do not generate them dynamically with a model.

<!-- file: eval.py -->
```python
import hashlib
import json
import os
from pathlib import Path


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def parsed(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


ctx = json.loads(Path(os.environ['PPP_EVAL_CONTEXT']).read_text())
s, contract = ctx['state'], ctx['contract']
root = Path(ctx['task']).parent
case = json.loads((root / 'config.json').read_text())['live_e2e_scenario']
w = root / 'work'
assert Path.cwd().resolve() == w.resolve()
choice_cases = case in {'S3', 'S4'}
paths = ['a.txt', 'b.json', 'c.json', 'Test-input.json', 'Test-invocations.txt']
for name in paths:
    assert not (w / name).is_symlink(), 'Test graded files must be regular local files'
measured = {n: hashlib.sha256((w / n).read_bytes()).hexdigest() for n in paths if (w / n).is_file()}
choice = parsed(w / 'Test-input.json') == {'choice': 'Test-blue'}
if case == 'S6':
    a_ok = (w / 'a.txt').is_file() and (w / 'a.txt').read_text() == 'Test one local effect\n'
    a_ok = a_ok and (w / 'Test-invocations.txt').is_file() and (w / 'Test-invocations.txt').read_text().splitlines() == ['Test invocation']
    b_ok = a_ok and parsed(w / 'b.json') == {'Test-receipts': 1}
else:
    a_ok = (w / 'a.txt').is_file() and (w / 'a.txt').read_text() == 'Test squares: 4,9,25\n'
    expected_b = {'Test-sum': 38, **({'Test-choice': 'Test-blue'} if choice_cases else {})}
    b_ok = a_ok and parsed(w / 'b.json') == expected_b and (choice or not choice_cases)
ok = {'a': a_ok, 'b': b_ok, 'c': a_ok and b_ok and parsed(w / 'c.json') == {'Test-product': 900}}
proof = f'Test-proof-{s["review_seq"]:06}.json'
proof_value = {'files_sha256': measured, 'choice_valid': choice, 'measured_results': ok}
(w / proof).write_text(json.dumps(proof_value, sort_keys=True))
refs = [proof, *sorted(measured)]
r = {k: ctx[k] for k in ('protocol_version', 'schema_version', 'run_id')}
r.update(cycle=s['cycle'], review_id=s['review_seq'], state_sha256=sha(s), target=contract['target'], source_state=sha(proof_value), safe=True, halt_reason=None, actions=[], blockers=[], resolutions=[], grants=[], criteria={}, reconciliation={'fresh': True, 'approvals_applicable': True, 'evidence_refs': refs, 'operations': []})


def authentic(h):
    return h.get('source') == 'console-command' and h.get('session_id') == 'console:' + s['run_id']


resolved_now = False
for bid, blocker in s['blockers'].items():
    for hid, h in s['human'].items():
        if h['kind'] == 'resolution' and not h['processed'] and bid in h.get('blocker_ids', []):
            valid = authentic(h) and choice
            resolved_now = resolved_now or valid
            r['resolutions'].append({'blocker_id': bid, 'human_id': hid, 'valid': valid, 'approval_applicable': valid, 'evidence_refs': refs})
choice_authorized = any(b['status'] == 'resolved' for b in s['blockers'].values()) or resolved_now
if choice_cases and not choice_authorized:
    r['blockers'].append({'blocker': {'key': 'Test-missing-choice', 'reason': 'user_choice', 'needed': 'Test person supplies Test-blue choice in Test-input.json and addressed confirmed receipt', 'blocked_actions': ['b']}, 'evidence_refs': refs})
    if (w / 'b.json').exists():
        r.update(safe=False, halt_reason='Test dependent output appeared before authorized choice')
for hid, h in s['human'].items():
    if h['kind'] == 'grant' and not h['processed']:
        q = s['requests'].get(h.get('request_id'), {})
        if case == 'S5' and authentic(h) and h.get('cycles') == 2 and q.get('main_extension') is True and q.get('main_grant_count') == len(s['grants']):
            r['grants'].append(hid)
        else:
            r.update(safe=False, halt_reason='Test unexpected or unauthenticated grant')
for aid, a in s['actions'].items():
    raw = {k: a[k] for k in ('id', 'description', 'depends_on', 'operations')}
    rows = [row for row in s['consumption'] if row['action_id'] == aid and not row.get('assessment')]
    attempt = None
    if rows:
        assert len(rows) == 1 and rows[0]['cycle'] == s['cycle']
        attempt = {'strategy': 'Test independently inspect selected output', 'state_before': 'Test reserved cycle ' + str(rows[0]['cycle']), 'outcome': 'Test measured valid output' if ok[aid] else 'Test no verified progress', 'fingerprint': aid + ':' + sha(proof_value), 'assessment': 'verified' if ok[aid] else 'none', 'evidence_refs': refs}
    r['actions'].append({'action': raw, 'status': 'verified' if ok[aid] else 'pending', 'eligible': aid != 'b' or not choice_cases or choice_authorized, 'scope_authorized': True, 'dependencies_valid': True, 'evidence_refs': refs, 'attempt': attempt, 'experiment': None})
    r['criteria'][aid + '_ok'] = {'status': 'pass' if ok[aid] else ('blocked' if aid == 'b' and choice_cases and not choice_authorized else 'not_tested'), 'evidence_refs': refs}
for oid in s['operations']:
    r['reconciliation']['operations'].append({'id': oid, 'outcome': 'succeeded' if a_ok else 'uncertain', 'evidence_refs': refs})
print(json.dumps(r))
raise SystemExit(0 if r['safe'] and all(v['status'] == 'pass' for v in r['criteria'].values()) else 1)
```

<!-- file: prepare.py -->
```python
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

case, mode = os.environ['SCENARIO'], os.environ['MODE']
assert case in {'S1', 'S2', 'S3', 'S4', 'S5', 'S6'} and mode in {'goal', 'ralph'}
assert case != 'S1' or mode == 'goal'
assert case != 'S2' or mode == 'ralph'
root = Path(os.environ['RUN']).resolve()
root.mkdir(parents=True, mode=0o700, exist_ok=False)
(root / 'work').mkdir(mode=0o700)
home = Path(os.environ['TEST_HOME']).resolve()
(home / '.pi/agent').mkdir(parents=True, mode=0o700, exist_ok=False)
settings = home / '.pi/agent/pi-goal.json'
settings.write_text(json.dumps({'continuationLimits': {'automaticTurns': 25, 'noProgressTurns': 3}, 'rpc': {'enabled': False}}))
settings.chmod(0o600)
shutil.copyfile(Path(os.environ['LAB']) / 'eval.py', root / 'eval.py')
actions = [dict(id='a', description='Test selected independent squares' if case != 'S6' else 'Test single local receipt effect', depends_on=[], operations=[]), dict(id='b', description='Test selected dependent summary', depends_on=['a'], operations=[])]
if case == 'S5':
    actions.append(dict(id='c', description='Test selected product verification output', depends_on=['b'], operations=[]))
if case == 'S6':
    actions[0]['operations'] = [dict(id='receipt', target=str(root / 'work/a.txt'), kind='Test-local-create-once')]
c = dict(protocol_version=2, schema_version=1, run_id=str(uuid.uuid4()), mode=mode, live_e2e_scenario=case, worker_provider='openai', worker_model='gpt-6-luna', review_provider='openai', review_model='gpt-6.1-sol', review_transport='pi', human_transport='console', thinking='low', extension=os.environ['GOAL_EXT' if mode == 'goal' else 'RALPH_EXT'], task='TASK.md', eval_argv=['python3', '-B', str(root / 'eval.py')], max_cycles=1 if case in {'S3','S4','S5'} else 2, cycle_seconds=120 if case == 'S6' else 180, review_seconds=180, wall_seconds=60 if case == 'S6' else 240, execution_contract=dict(target='Test disposable ' + case + '-' + mode + ' at ' + str(root), actions=actions, criteria={a['id'] + '_ok': 'Test independently measured selected ' + a['id'] + ' output' for a in actions}, closure=dict(authorized=True, max_cycles=1), reminder_seconds=86400))
(root / 'config.json').write_text(json.dumps(c, indent=2))
task = f'''# Test disposable local task {case}/{mode}
Only cycle-context.action_id is executable. Read generated CONTRACT.md/context.
All output filenames below are relative to {root / 'work'}, not native Ralph cwd.
Write ONLY work/<selected output> and checkpoint.json, plus the explicitly named
S6 invocation file. Do not edit input, proof, evaluator, TASK, config, state,
reviews, human inbox, runtime, Git or any path outside this run's work/.
No network calls, packages, approvals, grants, queue calls or commits.
All other mounted files are read-only. Never inspect credentials/environment.
Action a normally writes a.txt with exact text: Test squares: 4,9,25\\n
Action b reads a.txt and writes b.json with Test-sum equal to 4+9+25.
For S3/S4 only, b additionally reads Test-input.json, requires its confirmed
choice Test-blue and includes Test-choice: Test-blue in b.json.
Do not create input or bypass a blocker. Only the human supplies this input.
For S5 only, c writes c.json with Test-product equal to 4*9*25.
Write a real versioned checkpoint for the selected action and actual evidence.
Goal calls goal_wait alone with current goal_id, no timer, never goal_complete.
Ralph ends the native iteration after checkpoint; never self-launch another.
'''
if case == 'S6':
    task += f'''
S6 overrides a/b outputs: a must first reserve operation receipt using
python3 {os.environ['PI_PING_PONG_BRIDGE']} operation --config {root}/config.json
--action-id a --operation-id receipt --owner <actual cycle-context.owner>.
Only after successful reservation, append exactly "Test invocation\\n" to
Test-invocations.txt, then create a.txt exclusively (Python open mode x), write
"Test one local effect\\n", flush and fsync both files. Never repeat a prior
reservation/effect; invocation log must expose any attempted repetition.
After that run python3 -c 'import time; time.sleep(300)' with tool timeout 300;
do not checkpoint before it returns. Core owns the earlier interruption.
On recovery obey selected action; do not rerun a if already reconciled.
b reads receipt and invocation count, writes b.json as {{"Test-receipts":1}},
then checkpoints normally. No other effect, no extra process/timer/approval.
'''
(root / 'TASK.md').write_text(task)
for name in ('TASK.md', 'eval.py', 'config.json'):
    (root / name).chmod(0o600)
print(json.dumps({'run': str(root), 'run_id': c['run_id'], 'eval_sha256': hashlib.sha256((root/'eval.py').read_bytes()).hexdigest(), 'status': 'prepared-not-launched'}, indent=2))
```

## 6. Preparation summary / stop

The matrix, task/evaluator recipes, native execution/human/resume commands, proposed pins, costs and enforcement limits, permissions, evidence, and PASS/FAIL/metrics are recorded. Python AST, shell syntax (without executing launch commands), local links, whitespace, and exact diff/status were checked.

The Appendix also passed **10 local scenario-mode schema/measurement smoke fixtures**: actual recipe files in a temporary directory, synthetic controller contexts/receipts, subprocess evaluator, reports applied to `Controller`, missing outputs, complete outputs, invalid→valid choice, additive grant, interrupted-operation reconciliation, wrong A, and duplicate invocation. No Pi, native Goal/Ralph, real Reviewer, archive/hash-chain transport, or model calls were used; this is not E2E evidence. The first smoke harness omitted required running-session metadata for an operation; Core correctly refused it. Only the temporary harness was corrected, after which all 10 fixtures passed. Full negative validation (including forged/stale/malformed cases) remains required before launch.

This is **not** a live E2E result and does not close G1–G4; no claim is made that real-runtime integration has been verified.

During the historical planning-only stage, only this document and its link in `docs/README.md` changed. Later remediation changed `scripts/action_bridge.py` and `scripts/test_action_faults.py`, added `scripts/test_runtime_boundaries.mjs`, and updated docs; no runtime/config/vendor packages were installed or patched. The historical planning gate found a failure, which is not hidden by later PASS results; the current remediation gate separately passed 135 Python tests. No paid calls, installation/runtime sync, external changes, or commits occurred. KB: project README, `_SYSTEM/Source_Of_Truth.md`, `_SYSTEM/Knowledge_Read_Rules.md`, `07_PROMPTS_AGENTS/Global_Agent_Instructions.md`, and skill routing were read; the older KB overview does not replace current source/test evidence. KB was not changed; project Architecture/Tech_Decisions/Next_Actions are absent.

**Stop here.** G1 fix is complete locally. Next decisions concern G2 containment/quiescence, G3 billing/cap policy, G4 execution environment, and the exact remediated source candidate. A real campaign remains unauthorized without separate approval.
