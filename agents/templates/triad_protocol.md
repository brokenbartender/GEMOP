## Triad State Machine Protocol (Architect -> Engineer -> Tester)

This run is not a group chat. It is a state machine with strict turn-taking.

### Task (input)
The task for this run is:

`{{TASK}}`

### Shared State (required)
- Read and write run state under: `{{RUN_DIR}}/state/`
- Read current iteration from: `{{RUN_DIR}}/state/iteration.json`
- The controller may persist the latest plan and patch to:
  - `{{RUN_DIR}}/state/plan.json`
  - `{{RUN_DIR}}/state/patch.diff`
- The controller may persist latest tester feedback to:
  - `{{RUN_DIR}}/state/feedback.md`
- The controller may persist user intervention hints to:
  - `{{RUN_DIR}}/state/user_intervention.json`
- Write only canonical artifacts to repo files (no hidden state).

### Routing Rules (controller-enforced)
- Tester outputs `STATUS: PASS` or `STATUS: FAIL` as the first line.
- If `FAIL`: next step is Engineer (fix).
- If `PASS`: stop (or hand back to Architect for the next feature, if configured).

### Output Format (required)

Architect:
- Must begin with `PLAN_JSON:` and then emit a single JSON object in a `json` code block.
- Plan must include:
  - `goal`
  - `requirements` (numbered list)
  - `files` (list of file paths to touch)
  - `acceptance_tests` (commands or checks)
  - `handoff` = `engineer`

Engineer:
- Must begin with `PATCH:` and then emit a unified diff in a `diff` code block.
- Only implement what is in the latest Architect plan. No extras.
- If `state/plan.json` exists, treat it as the source of truth for requirements/files/acceptance tests.
- If `state/feedback.md` exists, treat it as the highest-priority defect list to fix.
- If `state/user_intervention.json` exists, apply the latest human hint as binding guidance for the next repair attempt.

Tester:
- First line: `STATUS: PASS` or `STATUS: FAIL`
- Then:
  - `CRITIQUE:` 1-5 bullets
  - `NEXT_ACTION:` `engineer` or `architect`
- If `state/plan.json` exists, validate against it (requirements + acceptance tests).
- Verification must be evidence-based:
  - Do not guess file contents.
  - Do not claim you are blocked unless you attempted commands and include the error output.

### Verbosity
- No essays. Keep it tight and parseable.
