# Future ideas

Not planned for a release. Nothing here is implemented or promised.

## Decision models (`models.classify()`)

Pi 1.6.1 added cheap structured "decision models" (for example GitHub Copilot `gpt-6-luna-decisions`, local llama.cpp classifiers) callable from codemode or from an extension via `ctx.modelRegistry.classify()`. Questions are `choice`, `score` or `bool`, answered with probabilities; images are supported. Findings from a read-only investigation (2026-11-26):

- **Not available to everyone.** It needs a provider that exposes a decision model; a ChatGPT-style `openai-codex` login alone does not. Without one, every use below must fall back to today's behavior.
- **Reachable only from a Pi session.** There is no RPC command. The Python bridge and the headless Reviewer (`--no-extensions`) cannot call it unless a trusted extension is added.
- **Worth trying first: screenshot checks.** For UI tasks, the Worker could classify a screenshot ("is the layout broken?") as an ordinary check and keep the answer as checkpoint evidence. The Reviewer weighs it; no gate is added; no model means `not_tested`.
- **Marginal:** detecting a task typed as plain chat and offering to prepare a run; advisory "defect vs style" labels on Reviewer findings (measure first, never filter).
- **Not worth it:** triaging Reviewer verdicts (Core already validates evidence-bound assessments), scope checks (deterministic), turning free text into grants (a model must not invent human authority), default model choice, notification labels, skipping the Reviewer.
- **Risks:** experimental API, probabilistic answers, prompt injection from Worker output, classify cost may be missing from Core usage accounting, code and screenshots would go to an extra provider.
- **Optional zero-cost experiment:** hand-label about 40 recorded Reviewer corrections as defect or style and compare with a local llama.cpp classifier before any paid use.

Constraint: no new gates; decisions stay with Core.
