from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
PROCESSED_DIR = REPO_ROOT / "ramshare" / "evidence" / "processed"
FAILED_DIR = REPO_ROOT / "ramshare" / "evidence" / "failed"

QUEUE_STATE_DIR = REPO_ROOT / "ramshare" / "state" / "queue"
LEDGER_PATH = QUEUE_STATE_DIR / "ledger.jsonl"
LEASES_PATH = QUEUE_STATE_DIR / "leases.json"
DEDUPE_PATH = QUEUE_STATE_DIR / "dedupe.json"
CIRCUIT_BREAKER_PATH = QUEUE_STATE_DIR / "circuit_breaker.flag"


@dataclass(frozen=True)
class Job:
    path: Path
    id: str
    task_type: str
    target_profile: str
    estimated_spend_usd: float
    requires_human_approval: bool
    approval_token: str
    score: float
    trace_id: str


def now_ts() -> float:
    return time.time()


def host_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def iter_job_files(inbox: Path) -> Iterable[Path]:
    if not inbox.exists():
        return []
    return sorted([p for p in inbox.glob("*.json") if p.is_file()])


def write_ledger(job_id: str, state: str, details: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    row = {
        "ts": now_ts(),
        "job_id": job_id,
        "state": state,  # queued|leased|running|acked|failed|dlq|skipped
        "details": details,
        "host": host_id(),
        "extra": extra or {},
    }
    append_jsonl(LEDGER_PATH, row)


def load_dedupe() -> Dict[str, float]:
    if not DEDUPE_PATH.exists():
        return {}
    try:
        raw = json.loads(DEDUPE_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            return {str(k): float(v) for k, v in raw.items()}
    except Exception:
        pass
    return {}


def save_dedupe(data: Dict[str, float]) -> None:
    DEDUPE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEDUPE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_job_seen(job_id: str, ttl_sec: int = 7 * 24 * 3600) -> bool:
    d = load_dedupe()
    t = now_ts()
    d = {k: v for k, v in d.items() if (t - float(v)) < ttl_sec}
    save_dedupe(d)
    return job_id in d


def mark_job_seen(job_id: str, ttl_sec: int = 7 * 24 * 3600) -> None:
    d = load_dedupe()
    t = now_ts()
    d = {k: v for k, v in d.items() if (t - float(v)) < ttl_sec}
    d[job_id] = t
    save_dedupe(d)


def load_leases() -> Dict[str, Dict[str, Any]]:
    if not LEASES_PATH.exists():
        return {}
    try:
        raw = json.loads(LEASES_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def save_leases(data: Dict[str, Dict[str, Any]]) -> None:
    save_json(LEASES_PATH, data)


def claim_lease(job_id: str, ttl_sec: int = 300) -> bool:
    leases = load_leases()
    t = now_ts()
    owner = host_id()
    current = leases.get(job_id)
    if current:
        exp = float(current.get("expires_at", 0))
        if exp > t and str(current.get("owner", "")) != owner:
            return False
    leases[job_id] = {"owner": owner, "updated_at": t, "expires_at": t + ttl_sec}
    save_leases(leases)
    return True


def renew_lease(job_id: str, ttl_sec: int = 300) -> None:
    leases = load_leases()
    t = now_ts()
    if job_id in leases and str(leases[job_id].get("owner", "")) == host_id():
        leases[job_id]["updated_at"] = t
        leases[job_id]["expires_at"] = t + ttl_sec
        save_leases(leases)


def lease_owner_is_self(job_id: str) -> bool:
    leases = load_leases()
    current = leases.get(job_id) or {}
    return str(current.get("owner", "")) == host_id()


def release_lease(job_id: str) -> None:
    leases = load_leases()
    if job_id in leases and str(leases[job_id].get("owner", "")) == host_id():
        leases.pop(job_id, None)
        save_leases(leases)


def recent_ledger(max_rows: int = 200) -> List[Dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    return rows[-max_rows:]


def update_circuit_breaker() -> None:
    rows = recent_ledger(120)
    terminals = [r for r in rows if str(r.get("state")) in {"acked", "failed", "dlq"}]
    if len(terminals) < 10:
        CIRCUIT_BREAKER_PATH.unlink(missing_ok=True)
        return
    fail = sum(1 for r in terminals if str(r.get("state")) in {"failed", "dlq"})
    ratio = fail / max(1, len(terminals))
    if ratio >= 0.5:
        CIRCUIT_BREAKER_PATH.parent.mkdir(parents=True, exist_ok=True)
        CIRCUIT_BREAKER_PATH.write_text(
            json.dumps(
                {
                    "state": "open",
                    "opened_at": now_ts(),
                    "fail_ratio": round(ratio, 4),
                    "cooldown_sec": 180,
                    "samples": len(terminals),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    else:
        CIRCUIT_BREAKER_PATH.unlink(missing_ok=True)


def circuit_mode() -> str:
    if not CIRCUIT_BREAKER_PATH.exists():
        return "closed"
    try:
        data = json.loads(CIRCUIT_BREAKER_PATH.read_text(encoding="utf-8-sig"))
        opened_at = float(data.get("opened_at", 0))
        cooldown = int(data.get("cooldown_sec", 180))
        if now_ts() >= opened_at + max(15, cooldown):
            return "half_open"
    except Exception:
        # Backward compatibility for legacy text breaker files.
        age = now_ts() - CIRCUIT_BREAKER_PATH.stat().st_mtime
        if age >= 180:
            return "half_open"
    return "open"


def parse_job(path: Path) -> Job:
    data = load_json(path)
    job_id = str(data.get("id") or path.stem)
    task_type = str(data.get("task_type") or data.get("type") or "unknown")
    default_profiles = {
        "uploader": "ops",
        "fidelity_trader": "fidelity",
        "bio_skill_implementer": "research",
    }
    default_profile = default_profiles.get(task_type, "research")
    target_profile = str(data.get("target_profile") or default_profile)
    policy = data.get("policy") or {}
    est = safe_float(policy.get("max_estimated_spend_usd"), safe_float(policy.get("estimated_spend_usd"), 0.0))
    requires_human_approval = bool(data.get("requires_human_approval", False))
    approval_token = str(data.get("approval_token") or policy.get("approval_token") or "")
    bid = safe_float(policy.get("bid"), safe_float(policy.get("priority"), 1.0))
    risk = str(policy.get("risk", "")).lower()
    risk_penalty = {"critical": 0.35, "high": 0.20, "medium": 0.10, "low": 0.0}.get(risk, 0.05)
    score = max(0.0, bid - risk_penalty - (est * 0.05))
    trace_id = str(data.get("trace_id") or f"trace-{uuid.uuid4()}")
    return Job(
        path=path,
        id=job_id,
        task_type=task_type,
        target_profile=target_profile,
        estimated_spend_usd=est,
        requires_human_approval=requires_human_approval,
        approval_token=approval_token,
        score=score,
        trace_id=trace_id,
    )


def move_to(path: Path, dest_dir: Path) -> Path:
    if not path.exists():
        return dest_dir / path.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        i = 1
        while True:
            cand = dest_dir / f"{path.stem}.{i}{path.suffix}"
            if not cand.exists():
                dest = cand
                break
            i += 1
    shutil.move(str(path), str(dest))
    return dest


def build_env_for_profile(profile: str) -> Dict[str, str]:
    env = dict(os.environ)
    env["GEMINI_PROFILE"] = profile
    env["GEMINI_CONFIG"] = str(REPO_ROOT / "profiles" / f"config.{profile}.toml")
    env["GEMINI_OP_REPO_ROOT"] = str(REPO_ROOT)
    if profile == "research":
        blocked_prefixes = (
            "PRINTIFY",
            "PRINTFUL",
            "ETSY",
            "SHOPIFY",
            "AMAZON_MERCH",
            "FACEBOOK",
            "META_ADS",
            "TIKTOK",
            "PINTEREST",
            "TAXJAR",
        )
        for k in list(env.keys()):
            ku = k.upper()
            if ku.startswith(blocked_prefixes):
                env.pop(k, None)
    return env


def execute_job(job: Job) -> int:
    skill_map = {
        "accountant": REPO_ROOT / "ramshare" / "skills" / "skill_accountant.py",
        "market_strategist": REPO_ROOT / "ramshare" / "skills" / "skill_market_strategist.py",
        "market_analyst": REPO_ROOT / "ramshare" / "skills" / "skill_market_analyst.py",
        "alpha_report": REPO_ROOT / "ramshare" / "skills" / "skill_alpha_report.py",
        "fidelity_trader": REPO_ROOT / "ramshare" / "skills" / "skill_fidelity_trader.py",
        "trend_spotter": REPO_ROOT / "ramshare" / "skills" / "skill_trend_spotter.py",
        "product_drafter": REPO_ROOT / "ramshare" / "skills" / "skill_product_drafter.py",
        "librarian": REPO_ROOT / "ramshare" / "skills" / "skill_librarian.py",
        "art_director": REPO_ROOT / "ramshare" / "skills" / "skill_art_director.py",
        "listing_generator": REPO_ROOT / "ramshare" / "skills" / "skill_listing_generator.py",
        "manager": REPO_ROOT / "ramshare" / "skills" / "skill_manager.py",
        "strategist": REPO_ROOT / "ramshare" / "skills" / "skill_strategist.py",
        "uploader": REPO_ROOT / "ramshare" / "skills" / "skill_uploader.py",
        "bio_skill_implementer": REPO_ROOT / "ramshare" / "skills" / "skill_bio_skill.py",
    }

    skill = skill_map.get(job.task_type)
    if skill:
        if not skill.exists():
            print(f"FAILED: missing skill script: {skill}")
            return 1
        proc = subprocess.run(
            [sys.executable, str(skill), str(job.path)],
            capture_output=True,
            text=True,
            env=build_env_for_profile(job.target_profile),
        )
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.returncode != 0:
            if proc.stderr.strip():
                print(proc.stderr.strip())
            return proc.returncode
        return 0

    print(f"FAILED: unknown job type '{job.task_type}' for {job.id}")
    return 1


def should_run_pretrade_check(job: Job) -> bool:
    if job.task_type != "fidelity_trader":
        return False
    try:
        data = load_json(job.path)
    except Exception:
        return False
    inputs = data.get("inputs") or {}
    action = str(inputs.get("action") or "").upper()
    return action in ("BUY", "SELL")


def run_pretrade_check(job: Job) -> bool:
    data = load_json(job.path)
    inputs = data.get("inputs") or {}
    action = str(inputs.get("action") or "BUY").upper()
    symbol = str(inputs.get("symbol") or "").upper().strip()
    qty = safe_float(inputs.get("quantity"), 0.0)
    est_price = safe_float(inputs.get("estimated_price"), 0.0)
    est_cost = est_price * qty if est_price > 0 and qty > 0 else safe_float((data.get("policy") or {}).get("estimated_spend_usd"), 0.0)
    order_type = str(inputs.get("order_type") or "LIMIT").upper().strip()
    live = bool(inputs.get("live") or False)
    dual_confirmation_token = str(inputs.get("dual_confirmation_token") or "")
    heartbeat_origin = str(job.id).lower().startswith("heartbeat-")
    force_live_unlock = bool(inputs.get("force_live_unlock") or False)

    if not symbol:
        print("Pretrade Status: BLOCKED | Missing inputs.symbol for trade job")
        return False

    accountant = REPO_ROOT / "ramshare" / "skills" / "skill_accountant.py"
    cmd = [
        sys.executable,
        str(accountant),
        "pretrade-check",
        "--action",
        action,
        "--symbol",
        symbol,
        "--estimated-cost-usd",
        str(est_cost),
        "--order-type",
        order_type,
        "--dual-confirmation-token",
        dual_confirmation_token,
    ]
    if live:
        cmd.append("--live")
    if heartbeat_origin:
        cmd.append("--heartbeat-origin")
    if force_live_unlock:
        cmd.append("--force-live-unlock")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=build_env_for_profile(job.target_profile))
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip())
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini-op job dispatcher with durable queue lifecycle")
    ap.add_argument("--inbox", default=str(INBOX_DIR))
    ap.add_argument("--dry-run", action="store_true", help="Do not move jobs; just print what would happen")
    ap.add_argument("--lease-ttl-sec", type=int, default=300)
    args = ap.parse_args()

    inbox = Path(args.inbox)
    update_circuit_breaker()
    mode = circuit_mode()
    if mode == "open":
        print(f"BLOCKED: circuit breaker is OPEN ({CIRCUIT_BREAKER_PATH})")
        sys.exit(3)
    if mode == "half_open":
        print(f"WARN: circuit breaker HALF_OPEN probe mode ({CIRCUIT_BREAKER_PATH})")

    kill_flag = REPO_ROOT / "STOP_ALL_AGENTS.flag"
    if kill_flag.exists():
        print(f"STOP: kill switch enabled ({kill_flag})")
        sys.exit(2)

    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import GEMINI_governance  # type: ignore
    except Exception as e:
        print(f"ERROR: unable to import scripts/GEMINI_governance.py ({e})")
        sys.exit(1)

    job_paths = list(iter_job_files(inbox))
    if not job_paths:
        print("No jobs found.")
        return

    jobs: List[Job] = []
    for p in job_paths:
        try:
            job = parse_job(p)
            write_ledger(job.id, "queued", details=f"path={p}", extra={"trace_id": job.trace_id})
            jobs.append(job)
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"FAILED: {p.name} (invalid json/job): {e}")
            write_ledger(p.stem, "failed", details=f"invalid_json: {e}")
            if not args.dry_run and p.exists():
                move_to(p, FAILED_DIR)

    # Phase 20 auction baseline: highest score gets priority first.
    jobs = sorted(jobs, key=lambda x: x.score, reverse=True)

    for j in jobs:
        if is_job_seen(j.id):
            print(f"SKIP duplicate job id: {j.id}")
            write_ledger(j.id, "skipped", details="dedupe_hit", extra={"trace_id": j.trace_id})
            if not args.dry_run and j.path.exists():
                move_to(j.path, PROCESSED_DIR)
            continue

        if not claim_lease(j.id, ttl_sec=args.lease_ttl_sec):
            print(f"SKIP lease busy job id: {j.id}")
            write_ledger(j.id, "skipped", details="lease_busy", extra={"trace_id": j.trace_id})
            continue

        try:
            agent_id = j.target_profile
            if not GEMINI_governance.fairness_allow(
                path=GEMINI_governance.default_fairness_ledger_path(),
                agent_id=agent_id,
                window=100,
                max_share=0.5,
                min_turns=10,
            ):
                print(f"SKIP fairness defer job id: {j.id} agent={agent_id}")
                write_ledger(j.id, "skipped", details="fairness_defer", extra={"agent_id": agent_id, "score": j.score, "trace_id": j.trace_id})
                continue

            if not GEMINI_governance.check_agent_budget(
                agent_budget_path=GEMINI_governance.default_agent_budget_path(),
                agent_id=agent_id,
                additional_spend_usd=j.estimated_spend_usd,
            ):
                print(f"SKIP agent over cap job id: {j.id} agent={agent_id}")
                write_ledger(
                    j.id,
                    "skipped",
                    details="agent_over_cap",
                    extra={"agent_id": agent_id, "estimated_spend_usd": j.estimated_spend_usd, "trace_id": j.trace_id},
                )
                continue

            if j.requires_human_approval and not j.approval_token.strip():
                print(f"BLOCKED: {j.id} requires_human_approval=true but approval_token missing")
                write_ledger(j.id, "failed", details="missing_approval_token", extra={"trace_id": j.trace_id})
                if not args.dry_run and j.path.exists():
                    move_to(j.path, FAILED_DIR)
                continue

            allowed = GEMINI_governance.enforce(
                budget_path=GEMINI_governance.default_budget_path(),
                kill_switch_path=GEMINI_governance.default_kill_switch_path(),
                audit_path=GEMINI_governance.default_audit_log_path(),
                action=f"dispatch job {j.id}",
                details=f"type={j.task_type} profile={j.target_profile} est_spend=${j.estimated_spend_usd:.2f}",
                estimated_spend_usd=j.estimated_spend_usd,
                write_audit=True,
                requires_human_approval=j.requires_human_approval,
                approval_token=j.approval_token,
            )
            if not allowed:
                print(f"BLOCKED: {j.id} (policy gate)")
                write_ledger(j.id, "failed", details="policy_gate_block", extra={"trace_id": j.trace_id})
                if not args.dry_run and j.path.exists():
                    move_to(j.path, FAILED_DIR)
                continue

            if args.dry_run:
                print(f"Dispatching {j.id} to {j.target_profile}")
                write_ledger(j.id, "leased", details="dry_run", extra={"trace_id": j.trace_id})
                continue

            write_ledger(j.id, "leased", details=f"profile={j.target_profile}", extra={"trace_id": j.trace_id})
            renew_lease(j.id, ttl_sec=args.lease_ttl_sec)
            print(f"Dispatching {j.id} to {j.target_profile}")

            if should_run_pretrade_check(j):
                ok = run_pretrade_check(j)
                if not ok:
                    print(f"BLOCKED: {j.id} (pretrade checks)")
                    write_ledger(j.id, "failed", details="pretrade_check_failed", extra={"trace_id": j.trace_id})
                    move_to(j.path, FAILED_DIR)
                    continue

            write_ledger(j.id, "running", details=f"task_type={j.task_type}", extra={"trace_id": j.trace_id})
            stop_heartbeat = threading.Event()
            lease_lost = {"value": False}

            def _lease_heartbeat() -> None:
                interval = max(5, args.lease_ttl_sec // 3)
                while not stop_heartbeat.wait(interval):
                    if not lease_owner_is_self(j.id):
                        lease_lost["value"] = True
                        stop_heartbeat.set()
                        return
                    renew_lease(j.id, ttl_sec=args.lease_ttl_sec)

            heartbeat = threading.Thread(target=_lease_heartbeat, daemon=True)
            heartbeat.start()
            rc = execute_job(j)
            stop_heartbeat.set()
            heartbeat.join(timeout=2)
            if lease_lost["value"]:
                rc = 90
            if rc == 0:
                move_to(j.path, PROCESSED_DIR)
                write_ledger(j.id, "acked", details="completed", extra={"trace_id": j.trace_id})
                mark_job_seen(j.id)
                GEMINI_governance.record_agent_spend(
                    agent_budget_path=GEMINI_governance.default_agent_budget_path(),
                    agent_id=agent_id,
                    amount_usd=j.estimated_spend_usd,
                    reason="job_acked",
                    meta={"job_id": j.id, "task_type": j.task_type},
                )
                GEMINI_governance.fairness_register(
                    path=GEMINI_governance.default_fairness_ledger_path(),
                    agent_id=agent_id,
                    job_id=j.id,
                )
            else:
                move_to(j.path, FAILED_DIR)
                write_ledger(j.id, "failed", details=f"executor_exit={rc}", extra={"trace_id": j.trace_id})
        finally:
            release_lease(j.id)
            update_circuit_breaker()


if __name__ == "__main__":
    main()
