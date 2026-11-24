# Current architecture diagrams

These diagrams explain the [current architecture](ARCHITECTURE.md) and [run contract](../references/reviewed-runs.md). They omit lower-level states and do not establish live compatibility.

## Components and workspaces

Default Pi route with headless review. In Pi chat review, the launching chat also receives review requests. In the Codex route, `codex queue` addresses an existing thread. Both chat routes submit an assessment to Core rather than starting a headless Reviewer.

```mermaid
flowchart TD
    Human["User"] <-->|Commands and reports| Chat["Pi receiver / Chat A"]
    Chat -->|Explicit launch or confirmed input| Core["Core bridge and action controller"]
    Core -->|Scoped dispatch| Worker["Pi Worker"]
    Core <-->|Request and judgments| Reviewer["Separate Pi Reviewer"]
    Core <-->|State, evidence and receipts| Run["Private run storage"]
    Worker -->|Edits and tests| Project["Project in place"]
    Worker -->|Checkpoint| Run
    Run -->|Retained evidence| Reviewer
    Run -->|Inbox and local status| Chat
```

Read-only Reviewer built-in tools do not make the workspace a sandbox. Chat A is a reporting and input surface in this route, not the acceptance authority.

## Worker modes and review timing

The mode changes the Worker boundary and accounting, not the review protocol. Ordinary test results travel with Worker evidence; there is no second evaluator stage.

```mermaid
flowchart TD
    Core["Core selects authorized work and reserves allowance"] --> Mode{"Worker mode"}
    Mode -->|Ping-pong| Ping["Ordinary Pi: one settled task iteration"]
    Mode -->|Goal| Goal["Native Goal: continue until result or real limit"]
    Mode -->|Ralph| Ralph["Native Ralph: bounded multi-iteration loop"]
    Ping --> Boundary["Result boundary: retain available output and evidence"]
    Goal --> Boundary
    Ralph --> Boundary
    Boundary --> Review["Independent review with its own deadline"]
    Review -->|Assessment or review limitation| Decision["Core chooses the next state"]
    Decision -->|Eligible work or concrete correction within limits| Core
    Decision -->|No next dispatch| Outcome["Wait, stop, report blocked verification, or record finish"]
```

Native Goal progress checkpoints do not force review or split the session. Ralph reserves native iterations before dispatch; interrupted or missing native result telemetry does not release that reservation. [Observed Ralph tokens](../references/reviewed-runs.md#native-ralph-accounting-and-storage) are report-only, not allowance. See [mode accounting](../references/reviewed-runs.md#budgets-and-goal-accounting).

## Result and acceptance

The decision order below abstracts [Core's transition logic](../scripts/action_protocol.py) after a settled boundary. A technical review failure holds affected actions and work that depends on them; it is not a product defect. Explicit stop and integrity controls can preempt this flow.

```mermaid
flowchart TD
    Review["Applied assessment or recorded verification limitation"] --> Finish{"All criteria pass, work assessed and complete, blockers and effects resolved?"}
    Finish -->|Yes, no verification failure| Accepted["Record finish and report verified result"]
    Finish -->|Otherwise| More{"Eligible authorized work within remaining limits?"}
    More -->|Yes, including independent work around a hold| Dispatch["Dispatch again"]
    More -->|No| Failure{"Verification blocked?"}
    Failure -->|Yes| Preserve["Report blocked verification, retained work, and any known human needs"]
    Failure -->|No| Wait{"Genuine blocker, explicit grant needed, or arranged wake?"}
    Wait -->|Yes| Pause["Report available work; wait for addressed input or event"]
    Wait -->|No| Stop["Stop and report remaining gaps"]
```

With no defect, open blocker, wait, or unreconciled effect, a stop with complete actions and only `unknown`/`not_tested` criteria remaining can be `delivered_unverified`. Not every stop or verification failure uses that outcome. A successful run report and successful report delivery are different facts.

## Wait and recovery

This shows wake and resume, not an automatic rerun on reopening the UI. Concrete human/resource events and recoverable unassessed results can require independent reconciliation. An idle, reconciled run does not need repeated review simply because Core resumed.

```mermaid
flowchart TD
    Wait["Waiting with recorded wake source"] -->|Confirmed response, matching signal, or scheduled recheck| Wake["Continue the same run"]
    Wait -.->|Reminder, no Worker or model turn| Wait
    Stop["Interrupted controller"] -->|Explicit resume| Wake
    Wake --> Check["Inspect persisted state, ownership, usage, and prior attempts"]
    Check -->|Terminal, conflicting ownership, or unsafe to replay| Hold["Refuse restart or hold ambiguous work"]
    Check -->|Concrete event or unresolved result| Reconcile["Reconcile effects and evidence; review where applicable"]
    Check -->|Already reconciled and no new review required| Decide["Core decides using existing budget and state"]
    Reconcile --> Decide
```

A durable review attempt is not permission to resend. An uncertain operation is not proof it failed. Late input cannot restart terminal work. See [waits and recovery](action-scoped-protocol.md#budgets-waits-and-recovery).
