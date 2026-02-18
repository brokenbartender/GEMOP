# Phase 0-21 Execution Plan (Gemini-OP)

Date: 2026-02-11
Sources:
- `.agent-jobs/source-review-20260211-1400/Grand univeseal.extracted.md`
- `.agent-jobs/source-review-20260211-1400/Universal plan flow.extracted.md`
- `.agent-jobs/source-review-20260211-1400/dna to entropy.extracted.md`
- `.agent-jobs/source-review-20260211-1400/research process loop.extracted.md`
- `.agent-jobs/source-review-20260211-1400/Gemini-OS_ Universal Initialization Protocol.extracted.md`
- `.agent-jobs/source-review-20260211-1400/Gemini Universal Plan Expansion.extracted.md`

## Goal
Operationalize the conceptual Phase 0-21 model into measurable runtime behavior with safe autonomy gates.

## Scope
- Preserve existing Phase 0-18 foundations.
- Implement and validate Phase 19-21 runtime features:
  - Phase 19: Adaptive immunity (adversarial pattern signatures, persistence, replay defense)
  - Phase 20: Auction/resource equilibrium (bounded bidding + fairness + anti-monopoly)
  - Phase 21: Chronobiology (offline consolidation and scheduled optimization cycles)

## Sprint 1 (Immediate)
1. Phase 19 implementation baseline
- Files: `scripts/a2a_router.py`, `scripts/gemini_dispatcher.py`, `ramshare/state/a2a/idempotency.json`, `ramshare/state/audit/security_alerts.jsonl`
- Deliver:
  - signature capture for recurrent failure/malicious patterns
  - hard reject path with explicit reason codes
  - persistence across restart

2. Phase 20 implementation baseline
- Files: `scripts/gemini_governance.py`, `scripts/gemini_budget.py`, `scripts/safe-auto-run.ps1`
- Deliver:
  - per-agent budget quotas
  - auction/priority scoring with hard cap
  - fairness guard (no single agent monopolization)

3. Phase 21 implementation baseline
- Files: `scripts/memory-ingest.ps1`, `scripts/gemini_memory.py`, `scripts/gemini_watchdog.py`, `scripts/gemini_hud.py`
- Deliver:
  - scheduled consolidation cycle
  - summarize/distill recent runs into memory store
  - health-aware pause/resume window

4. Genesis startup gate
- Files: `scripts/gemini_preflight.py`, `scripts/safe-auto-run.ps1`
- Deliver:
  - startup checks for budget, policy mode, queue health, stale locks, capability readiness
  - fail-closed with clear operator remediation

5. Verification + rollback
- Files: `scripts/gemini_verify.py`, `scripts/verify_evidence_chain.py`, `docs/safe-auto-mode.md`
- Deliver:
  - machine-verifiable acceptance checks
  - rollback points before each major mutation

## Acceptance Criteria
- Phase 19-21 each has:
  - code path implemented
  - at least one automated verification command
  - one failure-path test proving safe behavior
- Safe-auto can run one full cycle and emit:
  - `learning-summary.json`
  - `efficiency-summary.json`
  - `capability-catalog.json`
  - no critical policy violations

## Current Status
- Phase 19: Implemented baseline idempotency/replay rejection in `scripts/a2a_router.py` with persisted state in `ramshare/state/a2a/idempotency.json`.
- Phase 20: Implemented baseline in `scripts/gemini_governance.py` + `scripts/gemini_dispatcher.py`:
  - per-agent budget quotas via `ramshare/state/governance/agent_budgets.json`
  - auction ordering (`Job.score`) and fairness deferral
  - spend/fairness registration on ACK
- Phase 21: Implemented runtime consolidation in `scripts/chronobio_consolidation.py`:
  - STOP + IN_CONSOLIDATION gating
  - learning close-loop + council reflection + memory compact
  - run reports in `ramshare/state/chronobio/runs/`
- Verification: strict built-in checks now pass with `python scripts/gemini_verify.py --check all --strict` (Phases 19, 20, 21 all green).

## Run Commands
```powershell
# Direct CLI (stable)
Gemini-os --version

# Council run on prepared sprint pack
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_batch_orchestrator.ps1 `
  -RunDir .agent-jobs/phase-19-21-sprint1 `
  -EnableCouncilBus `
  -CouncilPattern debate `
  -InjectLearningHints `
  -InjectCapabilityContract `
  -AutoApplyMcpCapabilities
```

## Notes
- Keep `Gemini` defaulting to raw CLI; only use smart mode via `Gemini smart "..."`.
- Do not push direct to `main` for autonomous jobs.
