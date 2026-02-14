import argparse
import datetime as dt
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional


def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _today_local() -> str:
    return dt.datetime.now().astimezone().date().isoformat()


def default_budget_path() -> Path:
    # User requested ".Gemini/budget_tracking.json". This is the shared location across sessions.
    return Path(os.path.expanduser(r"~\.Gemini\budget_tracking.json"))


def default_kill_switch_path() -> Path:
    return REPO_ROOT / "STOP_ALL_AGENTS.flag"


def default_audit_log_path() -> Path:
    # Keep audit evidence local-only (ramshare/evidence is gitignored except README).
    return REPO_ROOT / "ramshare" / "evidence" / "audit_log.md"


def default_agent_budget_path() -> Path:
    return REPO_ROOT / "ramshare" / "state" / "governance" / "agent_budgets.json"


def default_fairness_ledger_path() -> Path:
    return REPO_ROOT / "ramshare" / "state" / "governance" / "fairness_ledger.jsonl"


def approval_token_path() -> Path:
    return REPO_ROOT / "ramshare" / "state" / "governance" / "approval_tokens.json"


def load_approval_tokens(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def is_approval_token_valid(path: Path, token: str) -> bool:
    if not token.strip():
        return False
    data = load_approval_tokens(path)
    # Allow explicit raw token lookup and sha256 hash lookup.
    sha = hashlib.sha256(token.encode("utf-8")).hexdigest()
    valid_raw = token in data and bool(data.get(token, {}).get("active", True))
    valid_sha = sha in data and bool(data.get(sha, {}).get("active", True))
    return valid_raw or valid_sha


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_budget(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "date": _today_local(),
            "daily_limit_usd": 0.0,
            "spent_today_usd": 0.0,
            "events": [],
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Corrupt file: fail closed by treating as over budget until fixed.
        return {
            "date": _today_local(),
            "daily_limit_usd": 0.0,
            "spent_today_usd": float("inf"),
            "events": [{"ts": _now_iso(), "amount": 0, "reason": "budget file unreadable"}],
        }


def save_budget(path: Path, data: Dict[str, Any]) -> None:
    ensure_parent_dir(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_agent_budgets(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_agent_budgets(path: Path, data: Dict[str, Any]) -> None:
    ensure_parent_dir(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def rotate_agent_budgets(data: Dict[str, Any]) -> Dict[str, Any]:
    today = _today_local()
    for _, row in data.items():
        if not isinstance(row, dict):
            continue
        if row.get("date") != today:
            row["date"] = today
            row["spent_today_usd"] = 0.0
            row["events"] = []
    return data


def rotate_budget_if_new_day(data: Dict[str, Any]) -> Dict[str, Any]:
    today = _today_local()
    if data.get("date") != today:
        return {
            "date": today,
            "daily_limit_usd": float(data.get("daily_limit_usd") or 0.0),
            "spent_today_usd": 0.0,
            "events": [],
        }
    return data


def check_kill_switch(flag_path: Path) -> bool:
    """
    Return False if the global kill switch is enabled.
    """
    return not flag_path.exists()


def check_budget(budget_path: Path, additional_spend_usd: float = 0.0) -> bool:
    """
    Return True if allowed to proceed given daily budget, otherwise False.
    A daily_limit_usd of 0 means "no spend allowed" (fail closed).
    """
    data = rotate_budget_if_new_day(load_budget(budget_path))
    limit = float(data.get("daily_limit_usd") or 0.0)
    spent = float(data.get("spent_today_usd") or 0.0)
    # Fail closed: require explicit positive limit to allow spend.
    if limit <= 0:
        return False if additional_spend_usd > 0 else True
    return (spent + float(additional_spend_usd or 0.0)) <= limit


def check_agent_budget(agent_budget_path: Path, agent_id: str, additional_spend_usd: float = 0.0) -> bool:
    data = rotate_agent_budgets(load_agent_budgets(agent_budget_path))
    row = data.get(agent_id)
    if not isinstance(row, dict):
        # No row configured means no explicit cap.
        return True
    limit = float(row.get("daily_limit_usd") or 0.0)
    spent = float(row.get("spent_today_usd") or 0.0)
    if limit <= 0:
        return False if additional_spend_usd > 0 else True
    return (spent + float(additional_spend_usd or 0.0)) <= limit


def record_spend(budget_path: Path, amount_usd: float, reason: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = rotate_budget_if_new_day(load_budget(budget_path))
    data["spent_today_usd"] = float(data.get("spent_today_usd") or 0.0) + float(amount_usd)
    ev = {
        "ts": _now_iso(),
        "amount_usd": float(amount_usd),
        "reason": reason,
        "meta": meta or {},
    }
    data.setdefault("events", []).append(ev)
    save_budget(budget_path, data)
    return data


def record_agent_spend(
    agent_budget_path: Path,
    agent_id: str,
    amount_usd: float,
    reason: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = rotate_agent_budgets(load_agent_budgets(agent_budget_path))
    row = data.setdefault(
        agent_id,
        {
            "date": _today_local(),
            "daily_limit_usd": 0.0,
            "spent_today_usd": 0.0,
            "max_share": 0.5,
            "events": [],
        },
    )
    row["spent_today_usd"] = float(row.get("spent_today_usd") or 0.0) + float(amount_usd)
    row.setdefault("events", []).append(
        {
            "ts": _now_iso(),
            "amount_usd": float(amount_usd),
            "reason": reason,
            "meta": meta or {},
        }
    )
    data[agent_id] = row
    save_agent_budgets(agent_budget_path, data)
    return row


def fairness_register(path: Path, agent_id: str, job_id: str) -> None:
    ensure_parent_dir(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"ts": _now_iso(), "agent_id": agent_id, "job_id": job_id},
                separators=(",", ":"),
            )
            + "\n"
        )


def fairness_stats(path: Path, window: int = 100) -> Dict[str, Any]:
    if not path.exists():
        return {"window": window, "total": 0, "shares": {}}
    rows = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    rows = rows[-max(1, int(window)) :]
    total = len(rows)
    counts: Counter[str] = Counter(str(r.get("agent_id", "")) for r in rows if str(r.get("agent_id", "")).strip())
    shares = {k: (v / total if total > 0 else 0.0) for k, v in counts.items()}
    return {"window": int(window), "total": total, "counts": dict(counts), "shares": shares}


def fairness_allow(path: Path, agent_id: str, window: int = 100, max_share: float = 0.5, min_turns: int = 10) -> bool:
    stats = fairness_stats(path, window=window)
    if int(stats.get("total", 0)) < int(min_turns):
        return True
    share = float((stats.get("shares") or {}).get(agent_id, 0.0))
    return share <= float(max_share)


def audit_log_append(audit_path: Path, action: str, details: str = "", severity: str = "HIGH") -> None:
    ensure_parent_dir(audit_path)
    line = f"- { _now_iso() } [{severity}] {action}"
    if details.strip():
        line += f" | {details.strip()}"
    audit_path.write_text(
        (audit_path.read_text(encoding="utf-8") if audit_path.exists() else "# Audit Log (Local)\n\n")
        + line
        + "\n",
        encoding="utf-8",
    )


def enforce(
    *,
    budget_path: Path,
    kill_switch_path: Path,
    audit_path: Path,
    action: str,
    details: str = "",
    estimated_spend_usd: float = 0.0,
    requires_human_approval: bool = False,
    approval_token: str = "",
    write_audit: bool = True,
) -> bool:
    """
    One-call gate for high-risk actions.
    Returns True if allowed, False if blocked.
    """
    if not check_kill_switch(kill_switch_path):
        if write_audit:
            audit_log_append(audit_path, action=f"BLOCKED (kill switch): {action}", details=details, severity="CRITICAL")
        return False

    if estimated_spend_usd > 0 and not check_budget(budget_path, additional_spend_usd=estimated_spend_usd):
        if write_audit:
            audit_log_append(audit_path, action=f"BLOCKED (budget): {action}", details=f"est=${estimated_spend_usd:.2f} {details}".strip(), severity="CRITICAL")
        return False

    if requires_human_approval and not is_approval_token_valid(approval_token_path(), approval_token):
        if write_audit:
            audit_log_append(
                audit_path,
                action=f"BLOCKED (approval required): {action}",
                details=details,
                severity="CRITICAL",
            )
        return False

    if write_audit:
        audit_log_append(audit_path, action=action, details=details, severity="HIGH")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini-op governance gate: kill switch, budget, audit log")
    ap.add_argument("--budget-path", default=str(default_budget_path()))
    ap.add_argument("--kill-switch-path", default=str(default_kill_switch_path()))
    ap.add_argument("--audit-log-path", default=str(default_audit_log_path()))

    sub = ap.add_subparsers(dest="cmd", required=True)

    s_status = sub.add_parser("status", help="Print current governance status")
    s_status.add_argument("--estimated-spend-usd", type=float, default=0.0)

    s_agent_status = sub.add_parser("agent-budget-status", help="Check per-agent budget gate")
    s_agent_status.add_argument("--agent-id", required=True)
    s_agent_status.add_argument("--estimated-spend-usd", type=float, default=0.0)

    s_enforce = sub.add_parser("enforce", help="Gate a high-risk action; exit 0 if allowed, 2 if blocked")
    s_enforce.add_argument("--action", required=True)
    s_enforce.add_argument("--details", default="")
    s_enforce.add_argument("--estimated-spend-usd", type=float, default=0.0)
    s_enforce.add_argument("--requires-human-approval", action="store_true")
    s_enforce.add_argument("--approval-token", default="")

    s_spend = sub.add_parser("record-spend", help="Record spend and update budget file")
    s_spend.add_argument("--amount-usd", type=float, required=True)
    s_spend.add_argument("--reason", required=True)

    s_audit = sub.add_parser("audit", help="Append to audit log")
    s_audit.add_argument("--action", required=True)
    s_audit.add_argument("--details", default="")
    s_audit.add_argument("--severity", default="HIGH")

    s_agent_spend = sub.add_parser("record-agent-spend", help="Record per-agent spend event")
    s_agent_spend.add_argument("--agent-id", required=True)
    s_agent_spend.add_argument("--amount-usd", type=float, required=True)
    s_agent_spend.add_argument("--reason", required=True)

    s_fair_status = sub.add_parser("fairness-status", help="Show fairness share window")
    s_fair_status.add_argument("--window", type=int, default=100)

    args = ap.parse_args()

    budget_path = Path(args.budget_path)
    kill_path = Path(args.kill_switch_path)
    audit_path = Path(args.audit_log_path)
    agent_budget_path = default_agent_budget_path()
    fairness_ledger_path = default_fairness_ledger_path()

    if args.cmd == "status":
        data = rotate_budget_if_new_day(load_budget(budget_path))
        allowed = check_kill_switch(kill_path) and check_budget(budget_path, additional_spend_usd=float(args.estimated_spend_usd))
        out = {
            "kill_switch_enabled": kill_path.exists(),
            "budget": data,
            "would_allow_estimated_spend_usd": float(args.estimated_spend_usd),
            "allowed": allowed,
            "paths": {"budget": str(budget_path), "kill_switch": str(kill_path), "audit_log": str(audit_path)},
            "approval_token_store": str(approval_token_path()),
        }
        print(json.dumps(out, indent=2))
        return

    if args.cmd == "agent-budget-status":
        allowed = check_agent_budget(
            agent_budget_path=agent_budget_path,
            agent_id=str(args.agent_id),
            additional_spend_usd=float(args.estimated_spend_usd),
        )
        out = {
            "agent_id": str(args.agent_id),
            "estimated_spend_usd": float(args.estimated_spend_usd),
            "allowed": allowed,
            "agent_budget_path": str(agent_budget_path),
        }
        print(json.dumps(out, indent=2))
        raise SystemExit(0 if allowed else 2)

    if args.cmd == "enforce":
        ok = enforce(
            budget_path=budget_path,
            kill_switch_path=kill_path,
            audit_path=audit_path,
            action=args.action,
            details=args.details,
            estimated_spend_usd=float(args.estimated_spend_usd),
            requires_human_approval=bool(args.requires_human_approval),
            approval_token=str(args.approval_token or ""),
            write_audit=True,
        )
        raise SystemExit(0 if ok else 2)

    if args.cmd == "record-spend":
        data = record_spend(budget_path, float(args.amount_usd), args.reason)
        print(json.dumps(data, indent=2))
        return

    if args.cmd == "record-agent-spend":
        row = record_agent_spend(
            agent_budget_path=agent_budget_path,
            agent_id=str(args.agent_id),
            amount_usd=float(args.amount_usd),
            reason=str(args.reason),
            meta={},
        )
        print(json.dumps({"ok": True, "agent_id": args.agent_id, "row": row}, indent=2))
        return

    if args.cmd == "audit":
        audit_log_append(audit_path, action=args.action, details=args.details, severity=args.severity)
        print(json.dumps({"ok": True, "audit_log": str(audit_path)}, indent=2))
        return

    if args.cmd == "fairness-status":
        stats = fairness_stats(fairness_ledger_path, window=int(args.window))
        out = {"ok": True, "fairness_ledger_path": str(fairness_ledger_path), "stats": stats}
        print(json.dumps(out, indent=2))
        return


if __name__ == "__main__":
    main()

