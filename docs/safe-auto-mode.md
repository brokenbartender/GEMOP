# Safe Auto Mode (Unattended)

This mode runs `Gemini --full-auto` on an isolated branch and checkpoints changes to remote so progress is always reviewable and reversible.

## What it does

1. Verifies clean `main`.
2. Resets `main` to `origin/main`.
3. Creates `auto/<task>/<timestamp>` branch.
4. Starts `Gemini` with provided args.
5. On each interval:
   - commits changes
   - pushes branch
   - verifies remote head equals local head
6. Stops if push verification fails.
7. Writes run artifacts under `.safe-auto/runs/<run-id>/`.

## Run it

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\safe-auto-run.ps1 `
  -Task "app-build-pass-1" `
  -RepoRoot "<REPO_ROOT>" `
  -CheckpointSeconds 60 `
  -MaxCheckpoints 200 `
  -GeminiArgs "--full-auto"
```

## Artifacts

- `.safe-auto/runs/<run-id>/runner.log`
- `.safe-auto/runs/<run-id>/Gemini.stdout.log`
- `.safe-auto/runs/<run-id>/Gemini.stderr.log`
- `.safe-auto/runs/<run-id>/state.json`
- `.safe-auto/runs/<run-id>/report.md`

## Rollback to clean base

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\safe-auto-rollback.ps1 `
  -RunId "<run-id>"
```

Optional delete the run branch after recovery:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\safe-auto-rollback.ps1 `
  -RunId "<run-id>" `
  -DeleteRunBranch
```

## Notes

- This mode never pushes directly to `main`.
- It requires git credentials already configured for push.
- Keep tasks scoped. Very long runs should be split across multiple tasks.
