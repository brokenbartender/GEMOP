# Agentic Estate Spec

## Purpose
Translate the "house" analogy into an actionable architecture spec for Gemini-OP with concrete files, risks, guardrails, and verification commands.

## Design Principles
- Fail closed on unsafe or ambiguous states.
- Keep autonomous runs reversible (checkpoint + push verification).
- Prefer explicit contracts between agents/services.
- Keep observability first-class (trace IDs, ledgers, health snapshots).
- Optimize for safe unattended operation.

## Mapping Table
| Estate Component | Gemini-OP Implementation | Primary Failure Mode | Guardrail / Control | Verification |
|---|---|---|---|---|
| Bricks (tokens/work units) | Agent prompt + run artifacts in `.agent-jobs/*` | Low-quality output from underspecified prompts | Prompt contracts + quality scoring in `scripts/agent_self_learning.py` | `python scripts/agent_self_learning.py score-run --run-dir .agent-jobs/<run-id>` |
| Mortar (attention/coherence) | Council protocol in `scripts/agent_batch_orchestrator.ps1` | Agents disagree silently, weak synthesis | Required `VERIFIED`/`CHALLENGED` + fail-closed council checks | `python scripts/gemini_verify.py --check phase22 --strict` |
| Floors (context window) | Run summaries + distilled lessons in `ramshare/state/learning/*` | Context drift or forgetting important outcomes | Close-loop learning and distilled task generation | `python scripts/agent_self_learning.py close-loop --run-dir .agent-jobs/<run-id> --threshold 70` |
| Walls (sandbox boundaries) | Profile routing + env scoping in `scripts/gemini_dispatcher.py` | Cross-domain tool misuse or privilege spillover | Profile-constrained env and policy gating | `python scripts/gemini_verify.py --check phase20 --strict` |
| Pipes (A2A transport) | `scripts/a2a_router.py`, `scripts/a2a_bridge_ssh.py` | Lost, duplicated, or poison messages | Idempotency, outbox, DLQ, retry/backoff | `python scripts/gemini_verify.py --check phase25 --strict` |
| Hallways (bandwidth/traffic) | Queue + lease logic in `scripts/gemini_dispatcher.py` | Overload, lease contention, starvation | Circuit breaker + fairness deferral + lease TTL | `python scripts/gemini_verify.py --check phase20 --strict` |
| Utility meters (cost/rate) | Governance + budgets in `scripts/gemini_governance.py` | Runaway spend | Agent budget caps, policy checks, kill switch | `python scripts/gemini_verify.py --check phase20 --strict` |
| Fence + sensors (security) | Governance enforce calls in `scripts/safe-auto-run.ps1` and dispatcher | Unsafe actions proceed unattended | Governance gates before start/checkpoint/final checkpoint | `python scripts/gemini_verify.py --check phase26 --strict` |
| Camera system (observability) | Ledger/audit JSONL + trace IDs in dispatcher/router | Untraceable failures | Trace IDs + explicit state transitions + latency telemetry | `python scripts/gemini_verify.py --check roadmap --strict` |
| Thermostat (self-regulation) | World model in `scripts/world_model_snapshot.py` | False “healthy” status when stale | Freshness-aware health (`freshness_ok`, `stale_run_seconds`) | `python scripts/gemini_verify.py --check phase27 --strict` |
| Breaker panel (resilience) | Circuit breaker in `ramshare/state/queue/circuit_breaker.flag` | Cascading failures | Open/half-open/closed dispatch control | `python scripts/gemini_dispatcher.py --dry-run` |
| Control room (orchestrator) | `scripts/agent_batch_orchestrator.ps1` | Invalid council state or malformed manifest | Council manifest validation + strict run-script parsing | `python scripts/gemini_verify.py --check phase22 --strict` |
| Blueprints archive (audit/replay) | Run artifacts + safe-auto reports in `.safe-auto/runs/*` | Can’t reconstruct decisions | State snapshots + runner/Gemini logs + report | `powershell -File scripts/safe-auto-run.ps1 -Task "<task>"` |
| Expansion rooms (scaling) | Parallel lanes in orchestrator (`MaxParallel`, `AgentsPerConsole`) | Host overload or stalled throughput | Safe parallel cap + watchdog timeout | `powershell -File scripts/agent_batch_orchestrator.ps1 -RunDir .agent-jobs/<run-id> -NoLaunch` |
| Neighborhood rules (compliance/policy) | Policy checks in governance module | Non-compliant execution path | Enforcement at dispatch and safe-auto gates | `python scripts/gemini_verify.py --check phase20 --strict` |

## Current Gaps To Prioritize
1. Add stronger A2A ACK contract semantics beyond transport success (explicit ack state schema).
2. Add schema version tag to all council and A2A messages for compatibility checks.
3. Add automated stale lock cleanup checks for long-running orchestrations.
4. Add a dedicated “estate SLO” report (latency, error ratio, failover events, spend/hour).
5. Add replay tool for a single run ID to regenerate key state transitions deterministically.

## Agent Council Operating Profile (Recommended Default)
- Pattern: jury-style 8-agent council with explicit `VERIFIED`/`CHALLENGED` evidence.
- Concurrency policy: `MaxParallel` auto-tuned from learning model with host-safe cap.
- Bus policy: council bus enabled for cross-agent communication during active run.
- Runtime policy: hard timeout per agent + fail-closed threshold gating.
- Output policy: each agent must emit implementation-ready actions with file paths and commands.

## Self-Learning Feedback Loop
1. Run council batch and collect artifacts in `.agent-jobs/<run-id>`.
2. Score outputs using `scripts/agent_self_learning.py score-run`.
3. Close loop with `scripts/agent_self_learning.py close-loop` to distill mistakes and wins.
4. Inject learned prompt hints and capability contracts into the next run.
5. Re-validate via strict checks before merge/push.

### Learning Loop Commands
```powershell
# Score and distill previous run
python scripts/agent_self_learning.py score-run --run-dir .agent-jobs/<run-id>
python scripts/agent_self_learning.py close-loop --run-dir .agent-jobs/<run-id> --threshold 70

# Run next council with learned hints and council bus enabled
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_batch_orchestrator.ps1 `
  -RunDir .agent-jobs/<next-run-id> `
  -EnableCouncilBus `
  -RequireCouncilDiscussion `
  -InjectLearningHints `
  -InjectCapabilityContract `
  -AutoTuneFromLearning `
  -Threshold 70
```

## Immediate Operator Commands
```powershell
# 1) Foundation verification
python scripts/gemini_verify.py --check all --strict
python scripts/gemini_verify.py --check roadmap --strict

# 2) Build world-model snapshot
python scripts/world_model_snapshot.py --refresh

# 3) Run a council pack safely (no launch) for contract checks
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_batch_orchestrator.ps1 `
  -RunDir .agent-jobs/<run-id> `
  -EnableCouncilBus `
  -RequireCouncilDiscussion `
  -NoLaunch `
  -Threshold 70

# 4) Dispatcher policy/fairness/circuit behavior dry run
python scripts/gemini_dispatcher.py --dry-run
```

## Definition of Done (Estate-Grade)
- Strict verification is green for phases 20, 22, 25, 26, 27 and roadmap.
- Latest world-model snapshot indicates freshness and health status is explainable.
- Every unattended run is checkpointed, pushed, and replay-auditable.
- Agent outputs include council verification/challenge evidence.
- Queue and A2A paths emit traceable telemetry suitable for postmortems.
