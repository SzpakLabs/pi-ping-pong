# Manual E2E — <attempt>

Copy into `.pi/ping-pong/manual-e2e/<attempt>/report.md` **before preparation**, not into tracked docs. Keep it out of Git. Keep private (directory 0700, file 0600). Replace placeholders with observations or `unknown`/`not received`; never fabricate a timestamp, zero count, decision or PASS. This template is not a completed run report. Reports sent to the launching chat must put the task result before paths and follow the ordered **STATUS → TL;DR → Summary → Report → Suggested action → Full run status** contract in [reviewed-run guidance](../references/reviewed-runs.md). The chat report must remain readable without opening artifacts; evidence paths support claims but do not replace explaining what happened.

## Status

- Case / attempt:
- Created UTC:
- Last observed UTC:
- Observation stage: preparation / awaiting user launch / running / waiting human / terminal / postmortem
- Task outcome: **NOT RUN** / RUNNING / BLOCKED / INCOMPLETE / PASS / FAIL / UNKNOWN
- Lifecycle: not started / active / waiting / stopped / complete / unknown
- Test assertions (separate from task completion):
- Concrete failure / missing result:

A human-gate test may pass while its task remains BLOCKED. No terminal evidence means no claimed Core finish. A timeout observing the run does not prove its processes stopped.

## Input and launch

- Full original user prompt (or immutable local copy path):
- Worktree realpath:
- Run directory / run_id (unknown until prepared):
- TASK / config / evaluator paths:
- User launch command:
- User launch observed UTC / evidence (or `not received`):
- Initial Git revision / working-tree changes:
- Final Git revision / observed changes since start:
- Installed Pi version, executable path (observed, not a version gate):
- Actual receiver / bridge path, source/install differences:
- Goal version if available:
- Worker provider/model/thinking:
- Reviewer provider/model:
- Launching session / actual reviewing session identity:
- Reviewer separate from Worker? Separate from launching chat? Evidence, not assumption:
- Configured main/closure authority, cycle/review/active-operation limits:
- Repository check command / exit / log:

Do not dump environment, auth files, secret application config, addresses or credential values. Source/install differences and updates are observations; preserve actual errors rather than applying historical candidate gates.

## Timeline — append observations

| Observed UTC | Event | Run/cycle/review identity | Evidence path | Result / next step |
| --- | --- | --- | --- | --- |
| | Report created before preparation | | | NOT RUN |

Include preparation failure, launch receipt, Worker boundaries, evaluator results, actual Reviewer decisions, human request/response, continuation, terminal state or last known event. Preserve earlier entries when correcting an interpretation. Do not invent missing events from the intended sequence.

## Checks

| Requirement | PASS / FAIL / UNVERIFIED / NOT RUN | Actual measurement / error | Evidence |
| --- | --- | --- | --- |
| Task-specific outputs | | | |
| Independent fresh evaluator | | | |
| Actual semantic Reviewer | | | |
| Core acceptance / finish | | | |
| Browser assertions + visual review (site cases) | | | |
| Human wait / quiet state / same-run continuation (case 3) | | | |
| External delivery (case 3; separate from API acceptance) | | | |
| Scope violations / unrelated writes | | | |

## Process data and retained artifacts

- `launch-attempt.json`: path or **absent**
- `bridge-status.json`: path or **absent**; observed status/reason
- `execution-state.json`: path or **absent**; observed execution/cycle/consumption/blockers
- `launcher.log`: path or **absent**; relevant bounded error excerpt
- `reviews/`: actual requests, evaluator reports and decisions, or **absent**
- `pi-inbox/` and delivery receipts: actual paths/status, or **absent**
- `sessions/` / native events: actual paths, or **absent**
- Checkpoints and retained evidence: actual paths, or **absent**
- Browser assertions, console errors, screenshots: paths or **not received**
- Human gate before/after observations: paths and timestamps, or **not received**
- Actual Worker cycles and count source: **unknown until measured**
- Evaluator runs / Reviewer turns and count sources: **unknown until measured**
- Worker/Reviewer token usage separately, source and completeness: **unknown until measured**
- Available subscription quota: **unknown unless reported**
- Owned local server / process cleanup: observed stopped / still active / unknown

Raw artifacts stay in their original ignored run paths; link them, do not paste full transcripts into chat. Keep config/TASK/eval and prior reviews intact. Do not collect unrelated personal sessions. Usage missing is not zero; catalog USD prices are not subscription charges. If no artifacts appeared, preserve this report and the command/error evidence anyway.

## Conclusion

- Last proven event:
- Expected but absent events/artifacts:
- Task outcome and independent test-assertion outcomes:
- Concrete cause, or unknown (distinguish hypothesis):
- User action required, if any:
- Unverified / incomplete:
- No relaunch, resume, replay or automatic external-send retry performed:
