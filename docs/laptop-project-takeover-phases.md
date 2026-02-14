# Laptop Project Takeover Plan (Next 10 Phases)

Owner:
- Laptop workstation (`Work`) is now the execution lead for day-to-day development and orchestration.
- Desktop (`CODYDESKTOP`) remains server/control-plane host.

## Phase 1: Leadership Handover
- Laptop becomes primary operator for commits, planning, and run control.
- Desktop runs daemons, sync, and policy enforcement.

## Phase 2: Sync Baseline Validation
- Verify `GeminiRamshareSync` (desktop) and `GeminiRamsharePull` (laptop) succeed for 3 cycles.
- Confirm both sides show current `ramshare/state`, `ramshare/strategy`, `ramshare/evidence`.

## Phase 3: Policy Mode Workflow
- Use `scripts/set-policy-mode.ps1` for explicit mode switches:
  - `restricted` default
  - `open` only when user explicitly requests all-tools access

## Phase 4: MCP Runtime Selection
- Keep full MCP profile available.
- Drive runtime tool usage via policy-proxy gating and task intent, not manual profile churn.

## Phase 5: Reliability Hardening
- Monitor sync lock behavior for stale-lock recovery.
- Add alerting on repeated non-zero task results.

## Phase 6: Evidence Integrity
- Keep audit/evidence chain active for high-risk actions.
- Verify evidence files sync to laptop and are reviewable there.

## Phase 7: Agent Orchestration Cadence
- Laptop runs planning/manager flows.
- Desktop enforces guardrails and executes long-running background tasks.

## Phase 8: Sidecar + UI Operations
- Keep sidecar containment requirements active.
- Use laptop as human control console for approvals and intervention.

## Phase 9: Cost + Budget Enforcement
- Use governance budget checks before any spend-capable operation.
- Record spends and maintain daily limits.

## Phase 10: Weekly Optimization Loop
- Weekly review of logs, policy, and task outcomes.
- Update presets/rules and phase backlog from measured bottlenecks.
