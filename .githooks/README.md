# Git Hooks

This repo uses git hooks to enforce two policies:

- Commit messages must include an `Other-Computer:` section (`.githooks/commit-msg`).
- Generated docs must stay in sync and obvious secrets/risky code must not be committed (`.githooks/pre-commit`).
- Local-only snapshot branches should not be pushed accidentally (`.githooks/pre-push`).

## Enable

```powershell
git config core.hooksPath .githooks
```

## Overrides

- To allow committing code flagged as "risky" (not secrets): set `GEMINI_OP_ALLOW_RISKY_CODE=1` for that commit.
- To push `wip/*` branches: set `ALLOW_WIP_PUSH=1` for that push.

