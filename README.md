# Pi Ping Pong

**Let Pi work on a coding task while an independent reviewer checks the result.**

You describe the task, allowed paths and limits. A Worker builds and runs the tests. A separate Reviewer looks at what those tests do not settle. A controller (Core) then decides: continue with a concrete correction, wait for you, stop, or accept.

> **Experimental (0.x).** The workflow may change. Use it on tasks whose results you can inspect.

## Why a reviewer

A green test suite only proves what it checks. A Worker can pass it and still miss a requirement, touch files outside scope, or leave a result that is hard to verify. The Reviewer examines those gaps. It does not rerun the same tests, and its opinion is not treated as proof.

```text
Task + limits -> Worker: build, test -> Reviewer: check gaps -> Core decides
                      ^                                             |
                      +------- concrete correction, within limits --+
                               or: ask you / stop / accept
```

If review is unavailable or evidence is incomplete, your work is kept and the report says what is unverified. Uncertainty alone never sends the Worker back for another change.

## Quick start

1. **Install** (Python 3.10+ must be on `PATH` as `python3`):

   ```sh
   pi install npm:pi-ping-pong
   ```

   Use one install source only. Prefer Git? `pi install git:github.com/SzpakLabs/pi-ping-pong`. Used the old copy installer? [Disable the copied receiver first](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/GUIDE.md#migrate-from-the-copy-installer).

2. **Open Pi in your project** and run `/reload` if you just installed it.
3. **Describe the task**, allowed paths and how you will judge the result, then run `/ppp <name>` with an unused kebab-case name. Review the generated `TASK.md` and `config.json`, including models and limits. Nothing starts yet.
4. **Launch** with `/ppp <name>` again. Follow progress with `/ppp-status`. If the run asks you for input, answer with `/ppp-respond`.

Example: “Add a dark-mode toggle. Limit edits to `src/` and `tests/`. It must survive reload and work by keyboard. Run the tests and tell me any browser behavior you couldn't verify. Prepare the run, don't launch yet.”

Prerequisites, updates and the Codex skill: [user guide](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/GUIDE.md#install).

## Three ways to run the Worker

| Mode | Review happens | Bounded by |
|---|---|---|
| **Ping-pong** | after each Worker iteration | iterations and active time |
| **Goal** | when a native Goal completes or hits a limit | active time, Goal launches, optional token cap |
| **Ralph** | when a native Ralph loop returns or hits a limit | iterations and active time |

Goal and Ralph need their Pi extensions installed. Review has its own deadline, and corrections use the remaining allowance. Details: [run contract](https://github.com/SzpakLabs/pi-ping-pong/blob/main/references/reviewed-runs.md).

## Good to know

- **Works in place.** The Worker edits your selected project, including uncommitted files. Scope and budgets do not grant commit, push or deploy permission. The Reviewer's read-only tools are not an OS sandbox.
- **Runs locally.** Keep the host and Pi session open. Model calls may cost money. Codex is an optional review transport, not a Worker mode ([prerequisites](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/GUIDE.md#quick-start-reviewer-in-codex)).
- **Run records** live in `.pi/ping-pong/runs/`. Keep them out of version control; [Git exclusion is best effort](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/project-workspace.md#private-run-storage).
- **Older runs.** `.pi-ping-pong/runs/` runs stay discoverable and are not migrated. Evaluator-era (protocol 1) runs cannot launch or resume on this version; their files are left alone.
- **Local tests are not live validation.** [Manual validation](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/manual-e2e.md) is separate.

[User guide](https://github.com/SzpakLabs/pi-ping-pong/blob/main/docs/GUIDE.md) · [Documentation](https://github.com/SzpakLabs/pi-ping-pong/tree/main/docs) · [Skill](https://github.com/SzpakLabs/pi-ping-pong/blob/main/SKILL.md) · [MIT License](https://github.com/SzpakLabs/pi-ping-pong/blob/main/LICENSE)
