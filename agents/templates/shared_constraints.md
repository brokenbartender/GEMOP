## Global Constraints (Gemini-OP)

- Consumer AI UIs (ChatGPT/Copilot/Gemini) are manual interaction surfaces only. Do not automate them.
- Any action involving logins, payments, sending messages, posting publicly, or changing external state must remain human-in-the-loop.
- Canonical artifacts must be written into this repo (Markdown/JSON/CSV/code) under `.agent-jobs/`, `data/`, `docs/`, `finance/`, etc.
- Avoid hallucinations:
  - If live data cannot be fetched, say so and proceed with offline/local analysis only.
- Prefer: write code to files, then execute; avoid embedding complex multiline code in PowerShell.

## Output Discipline

- Write outputs to the paths listed in your role contract (under `.agent-jobs/<run-id>/out/...`).
- Use strict JSON where requested.
- If blocked, write a short `BLOCKED.md` describing what is missing and the next safe step.
