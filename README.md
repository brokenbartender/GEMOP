# Gemini OP (Market-Ready v1.0)

Gemini OP is an agentic workspace runner with a hardened PowerShell orchestrator and supporting scripts (Python + Node MCP daemons).

## Quick start (Windows)

1) Install prerequisites:
- Git
- Python 3.x (ensure `python` is in PATH)
- Node.js + `npx`
- PowerShell (Windows PowerShell 5.1 or PowerShell 7)

2) Configure local settings:
- Copy `config.local.example.toml` to `config.local.toml`
- Set required secrets via environment variables referenced in the file (recommended)

3) Run the orchestrator on a run directory:
```powershell
pwsh .\scripts\triad_orchestrator.ps1 -RepoRoot (Resolve-Path .) -RunDir .\.agent-jobs\<your-run> -EnableCouncilBus
```

## One-line "Summon a Council" (Recommended)

Create a new run directory, auto-select skills from both `~/.codex/skills` and `~/.gemini/skills`, and run a multi-agent council:

```powershell
pwsh .\scripts\summon.ps1 -Task "Fix the failing tests and add coverage for the new feature" -Online
```

## Key scripts

- `scripts\triad_orchestrator.ps1` — primary orchestrator (this is the supported entrypoint).
- `scripts\agent_batch_orchestrator.ps1` — deprecated wrapper kept for backward compatibility.
- `scripts\safe-auto-run.ps1` / `scripts\safe-auto-rollback.ps1` — guarded automation runner and rollback.
- `scripts\summon.ps1` — command-center entrypoint: creates a run dir and summons a council with auto-selected skills.

## Logging

The orchestrator writes a structured log file to the run directory by default:
- `triad_orchestrator.log`

Logs are sanitized to avoid accidental secret disclosure.

## Security notes

- Do not commit real secrets to the repository. Prefer environment variables and local-only config files.
- `config.local.toml` is git-ignored and should only contain placeholders or env var references.
