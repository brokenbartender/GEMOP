# Top 20 A2A Improvements (Consolidated)

Ranked by impact and implementation readiness for `Gemini-op`.

| Rank | Improvement | Category | Impact | Effort | Primary Files |
|---|---|---|---|---|---|
| 1 | Unify repo root/state root resolution (`GEMINI_REPO_ROOT`, script-relative fallback) | Reliability | H | S | `scripts/a2a_router.py`, `scripts/a2a_bridge_ssh.py`, `scripts/sync-ramshare.ps1` |
| 2 | Auto-route failover: remote -> local with bounded retries and explicit fallback audit fields | Reliability | H | M | `scripts/a2a_router.py` |
| 3 | Remove forced `--no-preflight --force` from router/bridge path; make opt-in only | Safety | H | S | `scripts/a2a_router.py`, `scripts/a2a_bridge_ssh.py` |
| 4 | Harden SSH invocation defaults (`BatchMode`, `ConnectTimeout`, `StrictHostKeyChecking`, known_hosts pinning) | Security | H | S | `scripts/a2a_bridge_ssh.py`, `scripts/sync-ramshare.ps1` |
| 5 | Fix remote command injection risk by strict quoting/validation of `remote_repo`, `host`, and args | Security | H | M | `scripts/a2a_bridge_ssh.py` |
| 6 | Add durable WAL outbox + replay worker before network send | Recovery | H | M | `scripts/a2a_router.py`, `scripts/a2a_replay_outbox.py` |
| 7 | Add explicit ACK + idempotency ledger (`task_id` dedupe) to prevent replay/double execution | Reliability | H | M | `scripts/a2a_router.py`, `scripts/gemini_a2a_send_structured.py` |
| 8 | Make audit logging structured JSONL with `trace_id`, no raw sensitive payload/body | Observability/Security | H | M | `scripts/a2a_router.py`, `scripts/gemini_governance.py` |
| 9 | Add OpenTelemetry spans across router -> bridge -> send path | Observability | M | M | `scripts/a2a_router.py`, `scripts/a2a_bridge_ssh.py` |
| 10 | Add Prometheus-style metrics textfile (`latency`, `retry_count`, `queue_depth`, `failure_total`) | Observability | M | M | `scripts/a2a_router.py`, `scripts/gemini_budget.py`, `scripts/sync-ramshare.ps1` |
| 11 | Add queue backpressure + DLQ for poison messages (max queue, max attempts) | Reliability | H | M | `scripts/a2a_router.py` |
| 12 | Enforce schema validation on payload/job ingress with version field compatibility checks | Reliability | M | S | `scripts/a2a_router.py`, job schemas |
| 13 | Atomic checkpoint/state writes (`tmp+replace`) for run state and payload files | Recovery | H | S | `scripts/safe-auto-run.ps1`, `scripts/a2a_router.py` |
| 14 | Safe-auto hard gates: runtime cap, idle cap, push opt-in, allowlisted staging paths | Safety/Autonomy | H | M | `scripts/safe-auto-run.ps1` |
| 15 | Budget guardrails as execution gates (`--fail-threshold`, nonzero exit for critical) | Safety | H | S | `scripts/gemini_budget.py`, `scripts/safe-auto-run.ps1` |
| 16 | Branch safety: forbid direct `main` pushes for autonomous jobs; enforce `auto/*` only | Safety | H | S | Git hooks / workflow scripts |
| 17 | Expand stale-lock handling into shared helper and apply to all locking scripts | Reliability | M | S | `scripts/sync-ramshare.ps1`, `scripts/health.ps1` |
| 18 | Add CI suite: pytest + Pester + static analysis + fault-injection jobs | Testing | H | M | `tests/*`, `.github/workflows/*` |
| 19 | Add deterministic chaos tests (network timeout, auth fail, process kill) with expected recoveries | Testing | M | M | router/bridge/sync scripts + CI |
| 20 | Add batching path for A2A sends to reduce per-message process/transport overhead | Performance | M | M | `scripts/a2a_router.py`, `scripts/gemini_a2a_send_structured.py` |

## First Week (Do First)

1. Implement items 1-5 (root unification, failover, preflight/force removal, SSH hardening, injection fixes).
2. Implement items 6-8 (WAL outbox, ACK/idempotency, structured trace-safe audit logging).
3. Add safety gates from items 14-16 in `safe-auto-run` and git workflow.
4. Add tests for 1-8 + 14-16 (unit + integration + Pester smoke).
5. Run a 24h unattended soak on `auto/*` branch with rollback drill.
