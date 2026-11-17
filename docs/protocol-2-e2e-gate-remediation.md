# Protocol 2 — E2E Gate Remediation

## Verdict

**BLOCKED for a real Goal/Ralph E2E campaign.** G1 is fixed locally. G2 cleanup guarantees and G3/G4 requirements for complete billing/strict isolation are not provided by the current cooperative-host architecture. They have been investigated, not obscured by new promises. The [E2E plan](protocol-2-live-e2e-plan.md) is updated; paid commands remain unauthorized.

| Gate | Remediation result | READY/BLOCKED |
| --- | --- | --- |
| G1 cancellation / EPERM | Native failure reproduced, root cause established, minimal fix, deterministic RED/GREEN, 40/40 original repetitions, full gate green | **READY locally**, not live acceptance |
| G2 Ralph detached cleanup | 8 probes of the unchanged native runner with a synthetic RPC peer; exact normal/cancel/timeout/crash boundaries confirmed | **BLOCKED for full-tree cleanup / unsafe recovery** |
| G3 metering | SDK token-usage and local-cost sources identified; two selected models checked with a synthetic stream parser. No complete nested persistence, billing truth, or dollar cap | **BLOCKED for complete actual billing/hard cap** |
| G4 isolation | 3 local regressions: disposable worktrees, evidence-escape refusal, realpath-drift halt. Shared resources and same-UID write capability confirmed | **BLOCKED for strict isolation**, local fixture boundaries PASS |

No new orchestration layers, Headless Reviewer, Observer, cross-chat, pi-tick, runtime installation, vendor patch, paid inference, external operations, commit, or merge. No real Goal/Ralph E2E was performed. Importing the installed runner/parser for local testing neither installs runtime nor calls a model.

The original HEAD remains `96a0b2e34d48e81194b863d6333a4bf02b28022e`. Previously uncommitted `docs/README.md` and the E2E plan are preserved and updated. The new fix is uncommitted: **a clone of the old HEAD does not contain it**. Live work requires a separately approved remediated candidate; this report does not authorize a commit.

## 1. G1 — reproduction, cause, fix

### Baseline and reproduction

Historical planning gate `/tmp/ppp-e2e-plan-preflight.log`: **128 PASS / 1 FAIL**. The sole failure was `Bridge2Tests.test_cancel_at_eval_completion_prevents_dispatch`: expected exit 2, got 1. The original aggregate has not been rewritten retroactively.

The first fresh remediation baseline happened to pass: **129 PASS**, `/tmp/ppp-remediation-baseline.log`. This is the expected intermittent race, not evidence that the bug is absent. For reproduction, the expected exit was not changed and the full gate was not rerun until a conveniently selected result.

Two bounded diagnostic series using the original `stop_owned` reproduced **the same failure on the seventh attempt in each series**. They used a real Core/evaluator subprocess and synthetic local fixtures, without models. Private artifacts:

- `/var/folders/cf/nv7pkv557qq8ypy9h8vhmzlc0000gn/T/ppp-remediation-EPERM-cdh70ywr/Test-6/`
- `/var/folders/cf/nv7pkv557qq8ypy9h8vhmzlc0000gn/T/ppp-remediation-exit-window-y14tot6u/Test-6/`

Traceback: after authentic cancellation, `control_point()` raised `Terminated`. Then evaluator `finally → stop_owned → os.killpg(proc.pid, SIGTERM)` received **EPERM**. The single immediate `process_result` returned None; cleanup propagated PermissionError, replacing the normal cancellation exit with generic attention/exit 1.

Observations from the second trace:

```text
killpg(SIGTERM) -> PermissionError [Errno 1]
waitid(WEXITED|WNOHANG|WNOWAIT) -> None
next exit observation -> 0
subsequent observations -> 0
final proc.wait() -> 0
```

In the first trace, `getpgid` already returned ESRCH. The evaluator was a newly owned `Popen(start_new_session=True)`, inherited UID 501, and did not change identity/privileges/groups in the fixture. Its only effect was synthetic receipt/evidence; normal exit status 0 was confirmed. The leader was not reaped before cleanup: PID identity was not released prematurely.

**Root cause:** on this Darwin host, the signal API already sees the process group disappearing, while the wait API briefly has not yet published the exit. The previous guard correctly accounted for zombie-only EPERM but incorrectly required immediate waitid visibility. This is not evidence of forged ownership, PID reuse, persistent permission denial, or a proven receipt-publication bug. It is not claimed as a universal bug across all OS/Python versions: the observation is specific to Darwin / Python 3.15.0a1.

The original failure's durable state remained `execution=cancelled`, cycle 0, acceptance unknown, with no Worker/review dispatch. The error was in cleanup/termination outcome, not false acceptance. Changing the expected exit to 1 or suppressing every PermissionError would be incorrect.

### Minimal fix

In existing `stop_owned()`, only the EPERM branch gained **up to 50 ms exit confirmation**, polling every 5 ms through existing `waitid(WNOWAIT)`. If the leader remains live at the deadline, the original PermissionError still propagates. If its exit becomes visible, existing `proc.wait()` reaps the leader.

- No saved/discovered PID, `poll()`, or premature `wait()` is used to bypass the identity guard.
- TERM/KILL behavior for ordinary Core-owned groups is unchanged.
- A real permission failure is not turned into success: a dedicated negative test confirms it is raised and no wait is performed against a live leader.
- Budgets, acceptance, F1 assessment, F2 replay guards, F3 correction allowance, control priority, and contract/CLI/schema are unchanged.
- This is bounded cleanup observation, not a Worker/model-work retry. Boundaries for detached/privilege-changing processes were not expanded.

### Deterministic RED → GREEN

New methods in `scripts/test_action_faults.py`:

| Method | What it verifies |
| --- | --- |
| `test_eperm_exit_visibility_window_waits_without_reaping_identity` | TERM and KILL EPERM; first exit observation None, next 0; exactly one final reap |
| `test_eperm_live_leader_is_not_silently_accepted` | A persistently live leader and expired deadline preserve PermissionError; no false reap/success |
| `test_cancel_evaluator_eperm_window_commits_terminal_and_reaps` | Real evaluator/Core, atomic authentic cancel, deterministic exit-visibility injection after actual kernel exit; durable cancelled, projected cancelled, cycle/consumption 0, no review apply/queue attempt, owned evaluator exit 0 and reaped |

Before fix: **3 methods, 2 subtest errors + 1 failure**, exit 1; the negative live-denial case already PASSed. `/tmp/ppp-remediation-eperm-red.log`. After fix: **3 PASS**, without weakening the original exit 2.

Additionally, the original unmodified `test_cancel_at_eval_completion_prevents_dispatch` was repeated **40 times — 40 PASS**. This is stress evidence, not a replacement for the deterministic regression. Other existing cancellation tests cover owned TERM-ignoring descendants, unrelated-process survival, Goal native-query polling, dispatch/application races, and late callbacks; the full suite passed again.

## 2. G2 — real native runner, no models

### Method

`scripts/test_runtime_boundaries.mjs` imports the installed, **unchanged** Ralph **2.1.0** `src/runner-rpc.ts` using the existing Pi **1.3.0** Jiti loader. No vendor patch/new dependency. SHA-256 of the inspected runner:

`7addd0d06621002c309d361415eb13b7e2ae290c077967232674a64f42c10320`

The standard test seam `spawnCommand/spawnArgs` is used: a synthetic Python RPC wire peer instead of `pi`. This is **not a fake real E2E**: no Goal/Ralph model iteration is run and no live PASS is inferred. The native runner's actual subprocess/abort/timeout logic is tested with kernel processes/groups and real heartbeat/stop markers.

The peer creates a child either in its group or using a separate `start_new_session=True`. PID/PGID and readiness are recorded before each probe; group membership is checked. Liveness is determined by a continuing heartbeat after owner stop, not `kill(pid,0)` on a potential zombie. Probe cleanup uses a private cooperative release file and stop acknowledgements; test code does not signal saved orphan PIDs. The only external owner-crash signal targets a fresh, owned `ChildProcess` handle. Model binaries/HTTP calls are not used.

### Observations — 8 PASS characterizations, not a full-cleanup PASS

| Boundary | Same-group descendant | Escaped descendant |
| --- | --- | --- |
| Normal peer exit | Heartbeat stops: native runner cleanup SIGKILLs group | **Continues running** outside the group |
| AbortSignal cancellation with live owner | Stops | **Continues running** |
| Native iteration timeout with live owner | Stops | **Continues running** |
| SIGKILL of native runner owner itself | Detached peer and its same-group child **continue running** | Detached peer and escaped child **continue running** |

All synthetic helpers intentionally left alive received release and stop acknowledgement before fixtures were removed. The native module best-effort signals the peer group it created; it is not a registry of every descendant and does not guarantee reaping the full tree. A stopped heartbeat proves fixture work ceased during the observation window, not a universal OS sandbox or SLA.

Source inspection is consistent with the probes:

- `runner-rpc.ts` creates a child with `detached: process.platform !== 'win32'` and stdio pipes. It does not become an additional PPP execution-FD lease.
- With a live owner, normal/timeout `settle()` closes stdin and SIGKILLs **one** peer group; AbortSignal also kills that group.
- After owner loss, its timeout/cancel callbacks no longer run. EOF behavior remains the peer’s responsibility, not a kernel death guarantee.
- Real Pi RPC `rpc-mode.js` invokes asynchronous runtime disposal on stdin EOF and SIGTERM. This cooperative path can be interrupted by SIGKILL; the source path does not prove completion within Core’s 50 ms grace.
- PPP `stop_owned()` manages its own outer Worker group. The nested native Ralph group is already beyond that boundary; tool subprocesses can escape further. Prompt-level prohibitions on detached workers are not claimed to override native implementation behavior.

### Distinguish two crash cases

1. **Only PPP Core crashes while the outer Worker remains alive:** the existing inherited `worker.lock` refuses replacement. Existing real-subprocess fault tests `test_orphan_worker_lock_and_uncertain_effect_reconciliation` and `test_orphan_evaluator_lease_refuses_duplicate_evaluation` confirm the guard. It does not kill the orphan or establish provider truth.
2. **Native Ralph owner/outer Worker is lost:** a nested child may remain after the outer lease is released. This is confirmed by native-owner-crash probes and the source stdio/group boundary. A free outer lock does not prove nested work is absent and must not alone authorize a replacement.

A combined real Pi + model crash E2E **was not performed**. No PASS is claimed. A complete guarantee cannot honestly be fixed by adding another local `killpg` or bypassing the lock; it requires a pre-approved containment domain/quiescence policy or separate runtime-level work. No process registry, persistent supervisor, vendor patch, or second semantic loop was added.

**G2 remains BLOCKED for full descendant cleanup/reconciled live-resume requirements without such evidence.** The original cooperative normal/abort/timeout boundaries are now measured and explicitly distinguished from that guarantee.

## 3. G3 — usage, cost, and actually enforceable limits

### Sources confirmed by code

For proposed `openai/gpt-6-luna` and `openai/gpt-6.1-sol`:

| Layer | Source | What is actually known |
| --- | --- | --- |
| SDK response parser | Pi AI `dist/api/openai-responses-shared.js:finalizeResponse` | Provider-returned input/output/cache/reasoning/total and `responseId`, **if a terminal response with usage is received** |
| Session artifacts / RPC stats | Persisted assistant messages, usage-only/compaction records; `AgentSession.getSessionStats()` | Usage locally recorded for that session, including records supported by this runtime; not all other processes/sessions |
| `usage.cost` | Pi AI `models.js:calculateCost`, local model catalog, tier/service-tier adjustment | **Calculated USD estimate**, not an invoice or provider balance |
| Native Ralph result | `runRpcIteration().agentEndMessages` in owner memory | The usage synthetic wire message is returned to the caller; its presence in memory does not guarantee persistence |
| Native Ralph durable logs | `runner.ts`, `runner-state.ts:IterationRecord`, markdown transcript | Full nested usage/responseId is not written to IterationRecord; transcript stores prompt/assistant text/telemetry, not a complete raw usage ledger. Nested Pi starts with `--no-session` |
| Actual USD charged | Provider billing/usage export for a separate approved account/project/credential | Billing source of truth, but access, completeness, latency/attribution were **not checked here**; the API was not called |

Outer Ralph session totals are **not** the sum of all nested calls. Aborted/crashed requests, retries/compaction, and already-started remote calls without terminal usage may be billable but absent from the local ledger. Their cost is **UNKNOWN**, not $0. Comparison/dedup requires run/actor/session/request identity and provider IDs; do not add local estimates and billing entries as though they were separate actual charges.

The persisted `model` in the Responses adapter comes from the selected `model.id`; this is not, by itself, recorded evidence of a server weight revision. Alias snapshot/version pinning requires separate provider evidence/decision; do not infer it from a local session label.

### Model-free parser regression

In the same `test_runtime_boundaries.mjs`, the real SDK parser receives a synthetic completed response for **both selected catalog models**:

- input_tokens=100, cached=20, cache-write=10 → measured input=70;
- output=8, reasoning=3 — reasoning is not counted twice;
- total=108 and responseId are preserved;
- doubling only the local tariff doubles calculated cost, not token counts.

**2 PASS**, with no network/model calls. This checks parser/accounting mechanics, not actual usage for these models or a real billing quote. Approximately $0.00001245 Luna / $0.000247 Sol under the inspected catalog for this synthetic sample are local estimates only.

### Enforceable vs operational

| Limit | Enforcement |
| --- | --- |
| Main cycles, explicit additive grant, configured test closure cap | Durable Core authority; interrupted reservation is spent, reset prohibited |
| One correction experiment per unresolved boundary | Durable Core guard; metadata cannot be erased on resume |
| Active operation deadlines | Local Core/native timeout; do not cancel an already-started remote request or cover escaped descendants |
| Native Goal finite automaticTurns/no-progress guard | Response/work guard, not a dollar cap or shared Ralph/Reviewer quota |
| Native token/max-output controls | Only if actually configured in a supported runtime/provider; the final call/other actors can overshoot. PPP config sets no global token cap |
| Elapsed campaign deadline / $5/$8/$10 from the plan | Observer **operational thresholds**, not native enforcement or a charge guarantee |
| Provider project budget/quota | Treat as a hard cap only after confirming actual enforcement/overshoot semantics; no such cap is assumed to exist |
| Immutable source/model identity | Source hashes are measurable; an alias name alone does not establish an immutable server snapshot ID |

No fictitious `max_cost_usd`, metering service, pricing API call, or paid probe was added. For strict cost control, G3 remains BLOCKED: an approved billing source for all calls and confirmed hard enforcement are required. For a consciously accepted soft-budget experiment, the owner must separately approve telemetry gaps, in-flight allowance, and policy; that approval has not been obtained.

## 4. G4 — disposable worktrees and isolation limits

New `FaultTests`:

| Test | Evidence |
| --- | --- |
| `test_disposable_worktrees_isolate_outputs_not_git_or_host_resources` | Local clone **without hardlinks**, origin removed only in disposable clone, two detached worktrees at the same OID, output A absent from B. Common Git dir is shared; a fixture host file outside the worktrees is shared. No commit/fetch/remote operation |
| `test_evidence_symlink_cannot_escape_authorized_work_directory` | Symlink and `../..` evidence escapes are rejected by existing `inside()`. The same UID can still write a neighboring lab file — evidence guards are not an OS write sandbox |
| `test_moved_run_with_identical_bytes_refuses_realpath_drift` | Governing bytes are unchanged, run is moved to a new realpath; previous pins are preserved, validation halts, run identity/consumption are not reset |

**3 PASS**. Git tests remove inherited Git environment overrides, do not read global/system Git config, and disable hooks/fsmonitor in their command invocations. They change only private clone/worktree metadata, not canonical `.git`, branches, settings, or staging. They do not execute task code from the checkout.

Actual boundaries:

- Core pinning binds config/TASK/evaluator to resolved run paths/hashes. It is not a universal pin for arbitrary external source worktrees. E2E task outputs are deliberately inside `run/work`; immutable external-source/worktree pinning requires a separate agreed check.
- TASK-selected write paths, reviewer read-only behavior, and prohibitions on changing acceptance inputs are cooperative contracts. A same-UID actor can physically modify neighboring files/state or read process environment. `cwd`, private HOME, worktrees, and 0600 do not create separate security principals.
- Common Git metadata, host kernel/network/ports, environment/runtime caches, provider account/billing, and external DBs are not isolated by worktrees. Absence of DB/ports in a fixture does not prove a deny policy for arbitrary commands.
- `env -i`, private HOME, and source receiver override reduce discovery/config drift and exclude unnecessary credentials from the declared environment; they are not an egress allowlist or sandbox against same-UID/malicious extensions.
- Local tests/probes performed only synthetic file effects and local processes. There were no email/DNS changes, payments, DB/deploy/remote Git/provider calls. This is evidence those actions did not occur in this run, **not** proof that external actions are technically impossible.

For a “fully isolated” requirement, G4 remains BLOCKED until an existing disposable environment with the required mount/write/network/process bounds is provided and approved. No container/VM/runtime was installed, host firewall changed, or new orchestrator created.

## 5. Final verification

After all code/test changes:

| Command | Result |
| --- | --- |
| `UV_OFFLINE=1 npm run check` | **PASS**, exit 0; ESLint includes the new `.mjs`, TypeScript, locked Ruff, all Python suites, and receiver |
| `python3 -B scripts/test_bridge.py` (in gate) | **15 PASS** |
| `python3 -B scripts/test_action_protocol.py` (in gate) | **56 PASS** |
| `python3 -B scripts/test_action_bridge.py` (in gate) | **33 PASS** |
| `python3 -B scripts/test_action_faults.py` (in gate) | **31 PASS** (25 previous + 3 EPERM + 3 isolation) |
| `node scripts/test_pi_receiver.mjs` (in gate) | **PASS**, no numeric count reported |
| `node scripts/test_runtime_boundaries.mjs` | **8 lifecycle characterization cases + 2 model-parser cases PASS**, not native model E2E |
| `python3 -B scripts/test_install.py --fixture-root <fresh temporary dir>/fixture` | **PASS**, synthetic install fixture only, not runtime installation |
| `.venv/bin/ruff check .`, `npm run lint` (targeted) | **PASS** |
| Plan: embedded Python AST, `bash -n`, exact Appendix hashes, local doc links | **PASS**; launch recipes were not executed |
| `git diff --check`, exact diff/status | **PASS** |

**135 Python unittest methods**, plus 40 separate stress repetitions, receiver, 8 native-runner/2 parser cases, and installer. Subtests are not counted separately. Source tests do not establish model reliability, semantic correctness, or live acceptance.

Private logs: `/tmp/ppp-remediation-baseline.log`, `/tmp/ppp-remediation-eperm-red.log`, `/tmp/ppp-remediation-final-gate.log`, `/tmp/ppp-remediation-runtime.log`. Native characterization is a separate explicit gate, not a hidden new mandatory global Ralph dependency in ordinary checks. Its module/version must already be available; the script downloads/installs nothing.

## 6. Diff, compatibility, and remaining decisions

Changes relative to the original HEAD:

- `scripts/action_bridge.py`: only bounded unreaped-exit observation in the EPERM cleanup branch.
- `scripts/test_action_faults.py`: six new regression methods; existing checks were not weakened.
- `scripts/test_runtime_boundaries.mjs`: reproducible model-free native runner/parser characterization.
- `docs/action-scoped-protocol.md`: exact exit visibility/grace and native Ralph group boundary.
- `docs/protocol-2-live-e2e-plan.md`: G1 closed locally, G2–G4 open, obsolete HEAD clone blocked, source candidate requires separate approval.
- `docs/README.md`: links and current gate labels.
- `docs/protocol-2-e2e-gate-remediation.md`: this report.

Protocol 1 defaults, Protocol 2/schema 1, CLI/receiver envelopes, pinned contracts/evidence, run/cycle/hash identity, budgets, productive unlimited closure, exactly-once assessments, non-replayable outcomes, and correction bounds are preserved. No old runs were migrated and no runtime/vendor/global Goal/Ralph settings were changed. Existing live-E2E recipes are not presented as real runs that occurred.

Expected final status (checked before handoff):

```text
 M docs/README.md
 M docs/action-scoped-protocol.md
 M scripts/action_bridge.py
 M scripts/test_action_faults.py
?? docs/protocol-2-e2e-gate-remediation.md
?? docs/protocol-2-live-e2e-plan.md
?? scripts/test_runtime_boundaries.mjs
```

HEAD was unchanged. No staging/commit/merge/install/publish. KB context previously read: project README, Source_Of_Truth, Knowledge_Read_Rules, Global_Agent_Instructions; current source/test evidence above was not replaced by older KB status. KB was not changed.

**Stop here.** The owner must decide the G2 containment/quiescence route, G3 billing/cap/identity policy, G4 approved execution environment, and immutable remediated candidate. Do not independently expand the architecture or run paid checks instead of these decisions.
