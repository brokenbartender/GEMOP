# Gemini OP (Market-Ready v1.0)

Gemini OP is an agentic workspace runner with a hardened PowerShell orchestrator and supporting scripts (Python + Node MCP daemons).

## The Sovereign Mythos

The system has been refined through the **Heraclean Cycle** and the **Silicon Goetia**, integrating 8 layers of agentic logic:

1.  **Solomonic (Authority):** Intent verification via the Signet Seal.
2.  **Greek (Precision):** Context pruning (Lotus) and budget control (Damocles).
3.  **Egyptian (Identity):** Cryptographic identity guarding (Ren).
4.  **Atlantean (Infrastructure):** Heartbeat monitoring and stability (Djed).
5.  **Indigenous (Wisdom):** Immutable decision treaties (Wampum).
6.  **Chinese (Alignment):** Real-time goal consistency (Zhinan).
7.  **Slavic (Resilience):** Dual-phase system recovery (Dead/Living Water).
8.  **Physics (Unified Field):** Telluric resonance and Higgs-based compute allocation.

The **Sword of Gryffindor** logic enables the system to autonomously assimilate high-performance patterns from external repositories into the core.

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

- `scripts\smart_summon.ps1` — The primary entrypoint for multi-repo, autonomous tasks.
- `scripts\triad_orchestrator.ps1` — primary orchestrator engine.
- `scripts\event_horizon.py` — Schwarzschild-style pre-dispatch context-collapse guard.
- `scripts\hawking_emitter.py` — failure micro-summary emitter for terminated loops/tasks.
- `scripts\myth_runtime.py` — consolidated Phase VI plugin dispatcher (Hubble/Wormhole/Dark-Matter).
- `scripts\phase6_schema.py` — shared schema constants/validators for Phase VI task artifacts.
- `scripts\task_contract.py` — canonical task contract extraction (objective/constraints/deliverables/verification).
- `scripts\task_pipeline.py` — per-round planner/executor/verifier pipeline + deterministic ranking artifacts.
- `scripts\yeet.ps1` — Sovereign delivery tool (Verified Push).
- `scripts\slavic_recovery.ps1` — System healing and resurrection.

## Logging

The orchestrator writes a structured log file to the run directory by default:
- `triad_orchestrator.log`

Logs are sanitized to avoid accidental secret disclosure.
