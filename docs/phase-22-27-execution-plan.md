# Phase 22-27 Execution Plan (Gemini-OP)

Date: 2026-02-11
Prereq: Phase 0-21 complete and green via `python scripts/GEMINI_verify.py --check all --strict`

## Objective
Finish the next autonomy tier quickly and safely by hardening council behavior, capability acquisition, retry learning, cluster load routing, safe full-auto lane, and world-model planning.

## Phase 22: Council-Native Execution
- Goal: every council run contains real verify/challenge behavior and fails closed if missing.
- Implemented:
  - `scripts/agent_batch_orchestrator.ps1` injects council communication contract.
  - `scripts/agent_batch_orchestrator.ps1` fail-closed gate `RequireCouncilDiscussion`.
  - `scripts/council_reflection_learner.py` protocol issue tracking (`council_protocol_not_followed`).
- Verify:
  - `python scripts/council_reflection_learner.py --run-dir .agent-jobs/<run-id>`
  - Expect `verified > 0` and `challenged > 0` for green runs.

## Phase 23: Capability Autonomy
- Goal: blocked agents can request skills/MCP/tools and broker resolves what is possible.
- Implemented:
  - `scripts/agent_capability_broker.py` parses capability requests and auto-applies MCPs.
  - `scripts/agent_batch_orchestrator.ps1` invokes broker and stores `capability-catalog.*`.
- Verify:
  - `python scripts/agent_capability_broker.py --run-dir .agent-jobs/<run-id> --auto-apply-mcp`
  - Check `.agent-jobs/<run-id>/capability-catalog.md`

## Phase 24: Retry Learning Loop
- Goal: failed-quality runs auto-rerun up to bounded attempts until threshold pass.
- Implemented:
  - `scripts/phase_24_retry_loop.ps1` (new): launch orchestrator, score, rerun bounded.
- Verify:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/phase_24_retry_loop.ps1 -RunDir .agent-jobs/<run-id> -Threshold 70 -MaxReruns 2`

## Phase 25: Multi-Node Cluster Routing
- Goal: maintain desktop-heavy compute while keeping local device smooth.
- Implemented baseline:
  - `scripts/a2a_router.py` idempotency + duplicate reject + outbox/DLQ.
  - `scripts/a2a_bridge_ssh.py` transport layer.
  - `scripts/GEMINI_a2a_send_structured.py` structured send path.
- Verify:
  - `python scripts/GEMINI_verify.py --check phase25 --strict`

## Phase 26: Safe Full-Auto Release Lane
- Goal: unattended runs are reversible and auditable.
- Implemented:
  - `scripts/safe-auto-run.ps1` checkpoint commits + push verification.
- Verify:
  - `python scripts/GEMINI_verify.py --check phase26 --strict`

## Phase 27: World-Model Planning
- Goal: persistent planning state from run summaries, quality model, council model, and capabilities.
- Implemented:
  - `scripts/world_model_snapshot.py` (new) writes `ramshare/state/world_model/latest.json`.
- Verify:
  - `python scripts/world_model_snapshot.py --refresh`
  - `python scripts/GEMINI_verify.py --check phase27 --strict`

## Fast Finish Command Set
```powershell
# 1) Verify phase foundations (0-21)
python scripts/GEMINI_verify.py --check all --strict

# 2) Run retry learning pack on target run
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/phase_24_retry_loop.ps1 -RunDir .agent-jobs/<run-id> -Threshold 70 -MaxReruns 2

# 3) Build world-model snapshot
python scripts/world_model_snapshot.py --refresh

# 4) Verify phase 22-27
python scripts/GEMINI_verify.py --check phase22 --strict
python scripts/GEMINI_verify.py --check phase23 --strict
python scripts/GEMINI_verify.py --check phase24 --strict
python scripts/GEMINI_verify.py --check phase25 --strict
python scripts/GEMINI_verify.py --check phase26 --strict
python scripts/GEMINI_verify.py --check phase27 --strict
python scripts/GEMINI_verify.py --check roadmap --strict
```

## Done Definition
- All checks above are green.
- Latest run has `avg_score >= threshold`.
- Council summary has both verify + challenge.
- Capability catalog is generated.
- World model snapshot is current.
