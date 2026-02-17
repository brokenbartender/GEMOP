## Council Debate Protocol (3 seats)

Applies when running a 3-seat debate/collaboration. This protocol is designed to be machine-checkable and fail-closed.

### Task (input)
`{{TASK}}`

### Rounds (default 4 max)
- R1 (Diverge): 10 best options with clear acceptance criteria and the 1-2 risks most likely to sink each option.
- R2 (Cross-exam): attack the top 3 options; propose fixes; remove duplicates.
- R3 (Converge): one consolidated plan; define verification commands/tests.
- R4 (Implement when requested): produce patches as unified diffs; minimal commands; no hand-waving.

Stop early only if the council has a single plan + verification checklist and no open blockers.

### Output Contract (required every round, every seat)
- `Verdict`: Agree | Disagree | Mixed
- `Critique`: 1-5 bullets (specific; falsifiable; cite repo files/paths when possible)
- `Improvement`: 1-5 bullets (actionable; include file paths + exact commands)
- `Stop?`: Continue | Stop (1 sentence)
- `DECISION_JSON`: exactly one fenced block named `DECISION_JSON`.

`DECISION_JSON` schema (minimal, strict):
- `summary` (string)
- `files` (array of repo-relative paths; empty allowed)
- `commands` (array of shell commands to verify; empty allowed)
- `risks` (array of strings; empty allowed)
- `confidence` (number 0..1)

### Implementation Mode
If the task text contains `MODE=implementation` or starts with `IMPLEMENT:` then:
- If you propose changes: include at least one fenced ` ```diff` block (unified diff) that applies cleanly.
- `commands` must include at least one deterministic verification step (e.g. `python -m compileall ...`, `python -m pytest -q`, `node ...`).
- Fail-closed: if you cannot supply clean diffs and verify commands, set `Stop?` to `Stop` and lower confidence.

### Verbosity
- Tight: <= 250-350 words per round.
- No essays; prefer bullet lists and explicit file/command references.
