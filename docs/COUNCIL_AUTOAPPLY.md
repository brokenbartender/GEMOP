# Council: Tiered Routing + Auto-Apply

## Tiered Routing (Local vs Cloud)

The council runs via `scripts/triad_orchestrator.ps1` which spawns `scripts/agent_runner_v2.py` per seat.

- Default: **local-only** (free). No cloud calls are attempted.
- Opt-in: pass `-Online` to enable **tiered routing** (cloud when it’s selected/available; local fallback).

Commands:

```powershell
# Free/local-only council
.\start.ps1 -Council -Prompt "..."

# Tiered council (cloud enabled when available; local fallback)
.\start.ps1 -Council -Online -Prompt "..."

# Resume a run dir safely (skips agents whose round output already ends with COMPLETED)
.\start.ps1 -Council -Resume -Prompt "..."

# More seats
.\start.ps1 -Council -Agents 12 -Prompt "..."

# Tiered, but spend cloud on only the first N seats (others stay local)
.\start.ps1 -Council -Online -CloudSeats 3 -Prompt "..."

# Tiered with explicit cloud budgets (prevents surprise spend)
.\start.ps1 -Council -Online -QuotaCloudCalls 12 -QuotaCloudCallsPerAgent 2 -Prompt "..."

# Quota-cliff safety: cap concurrent local Ollama calls (prevents overload if many seats fall back to local)
.\start.ps1 -Council -Online -MaxLocalConcurrency 2 -Prompt "..."

# Extra stability: reduce concurrent processes if your machine is CPU/RAM constrained
.\start.ps1 -Council -Agents 12 -MaxParallel 2 -Prompt "..."

# Adaptive concurrency (conservative reductions based on prior round metrics)
.\start.ps1 -Council -AdaptiveConcurrency -Prompt "..."

# Safe URL fetch before Round 1 (no search, no CAPTCHA bypass; just fetch + cache)
.\start.ps1 -Council -Online -ResearchUrls "https://example.com,https://example.org" -Prompt "..."

# Optional: fail the whole run if it scores below a threshold (useful for unattended runs)
.\start.ps1 -Council -FailClosedOnThreshold -Threshold 70 -Prompt "..."
```

Suggested 12-seat organization (cloud seats first):

```powershell
.\start.ps1 -Council -Online `
  -Team "Chairman,Architect,RedTeam,Engineer,Tester,Docs,SRE,Planner,Integrator,Data,UI,QA" `
  -CloudSeats 3 `
  -MaxLocalConcurrency 2 `
  -QuotaCloudCalls 18 `
  -QuotaCloudCallsPerAgent 3 `
  -Prompt "..."
```

Implementation detail:
- Cloud routing is gated by `GEMINI_OP_ALLOW_CLOUD=1` (set by `scripts/triad_orchestrator.ps1` when `-Online` is used) and the normal checks inside `scripts/agent_runner_v2.py`.
- Seat allocation is controlled by `GEMINI_OP_CLOUD_AGENT_IDS` (set by `-CloudSeats`).
- Local fallback concurrency is controlled by `GEMINI_OP_MAX_LOCAL_CONCURRENCY` (set by `-MaxLocalConcurrency`) via a file-based semaphore in `scripts/agent_runner_v2.py`.
- Provider routing uses a circuit breaker to avoid hammering failing backends: `scripts/provider_router.py` persists state to `<run>/state/providers.json`.
- Optional fast-local path: set `GEMINI_OP_ENABLE_FAST_LOCAL=1` and `GEMINI_OP_OLLAMA_MODEL_FAST=phi3:mini` to route routine formatting/extraction tasks to a lighter local model.
- Optional per-seat local model mapping: set `GEMINI_OP_OLLAMA_MODEL_AGENT_<N>` to pin a specific seat to a specific local model.
  - Example: `GEMINI_OP_OLLAMA_MODEL_AGENT_1=phi4:latest`, `GEMINI_OP_OLLAMA_MODEL_AGENT_2=phi3:mini`.

## Kill Switch / Stop Prior Agents

There are two stop mechanisms:
- `python scripts/killswitch.py` (global hotkey listener or immediate trigger).
- `scripts/stop_agents.ps1` (writes STOP flags + best-effort terminates repo-scoped agent processes).

Commands:

```powershell
# One-shot emergency stop
python scripts/killswitch.py --trigger

# Stop prior agents before starting a fresh run
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_agents.ps1
```

Default behavior:
- `.\start.ps1 -Council` runs `scripts/stop_agents.ps1` automatically before spawning a new council run.
  - Disable with `-StopOthers:$false`.

Additional reliability detail:
- The orchestrator records spawned agent PIDs under `<run>/state/pids.json` so `scripts/stop_agents.ps1` can `taskkill /T` process trees.

## Auto-Apply Patches (Diff Blocks)

In debate mode, Round 1 is “DEBATE & DESIGN”. Rounds 2+ are “ACTUATE & IMPLEMENT”.

If you enable auto-apply, the orchestrator will:
1. Run the supervisor (`scripts/council_supervisor.py`) to score outputs.
2. Choose the best agent output for that round.
3. Extract fenced ```diff blocks and apply them using `git apply` (fail-closed).

Commands:

```powershell
# Auto-apply diffs after implementation rounds (R2+)
.\start.ps1 -Council -AutoApplyPatches -Prompt "..."

# Tiered + auto-apply
.\start.ps1 -Council -Online -AutoApplyPatches -Prompt "..."

# Auto-apply + verification pipeline (compileall + git diff --check)
.\start.ps1 -Council -AutoApplyPatches -VerifyAfterPatches -Prompt "..."
```

Safety rules (enforced by `scripts/council_patch_apply.py`):
- Rejects “guardrail weakening” diffs (uses the same detection logic as the supervisor).
- Refuses to patch sensitive paths like `.env`, `gcloud_service_key.json`, and anything under `.git/` or `.agent-jobs/`.
- Default allowlist: only patches to `docs/`, `scripts/`, `mcp/`, `configs/`, and `agents/templates/` are accepted.
- Runs a lightweight verification step (`python -m compileall scripts mcp`) after applying.
- Runs a secret scan on the current diff (`python scripts/scan_secrets.py --diff`) when `-VerifyAfterPatches` is enabled.

## Structured Decisions (DECISION_JSON)

Each agent is prompted to include a structured `DECISION_JSON` block in its markdown output.
After each round, the orchestrator can extract them into `<run>/state/decisions/`:

```powershell
.\start.ps1 -Council -ExtractDecisions -Prompt "..."
.\start.ps1 -Council -RequireDecisionJson -Prompt "..."
```

Extractor: `scripts/extract_agent_decisions.py`.

## Token Usage (Cloud)

If you run with `-Online`, `scripts/agent_runner_v2.py` logs cloud usage metadata (when available) into `logs/agent_runner_debug.log`.
Summarize it with:

```powershell
python scripts/token_usage_report.py
```
