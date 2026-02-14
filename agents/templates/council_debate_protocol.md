## Council Debate Protocol (3 seats)

Applies when running a 3-seat debate/collaboration.

### Task (input)
The task for this debate is:

`{{TASK}}`

### Rounds
- Default: 4 rounds maximum.
- R1-R2 (diverge): propose different approaches and challenge assumptions.
- R3-R4 (converge): merge into one plan; resolve contradictions.

### Stop Conditions
Stop early if:
- all 3 seats have consensus with no material caveats, or
- discussion repeats without new evidence/constraints/tests.

### Output Format (required)
- `Verdict`: Agree | Disagree | Mixed
- `Critique`: 1-3 bullets (specific; evidence/logic focused)
- `Improvement`: 1-3 bullets (actionable; testable; include file paths/commands when relevant)
- `Stop?`: Continue | Stop (1 sentence justification)

### Implementation Mode (required when applicable)
If the task text contains `MODE=implementation` or starts with `IMPLEMENT:` then the council is acting as a **control plane**.

Additional requirements:
- The **Judge** must include:
  - `DECISION: DISPATCH | STOP`
  - `JOB_JSON:` followed by exactly one fenced ```json block containing a single object.
- The job JSON must be **minimal and strict** (no prose), and must include:
  - `job_id` (string, unique)
  - `repo_root` (string, absolute path)
  - `goal` (string)
  - `hard_constraints` (array of strings, optional but recommended)
  - `acceptance` (array of strings, optional but recommended)
  - `max_repairs` (int, optional)
  - `timeout_seconds` (int, optional)

Fail-closed rule: if these fields are missing, or the JSON cannot be parsed, the correct `DECISION` is `STOP`.

### Verbosity
- Keep responses tight: <= 200-300 words per round.
- No freeform essays. Bullets only outside short labels.
