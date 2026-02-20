import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
DEFAULT_PORTFOLIO_PATH = REPO_ROOT / "ramshare" / "evidence" / "portfolio_snapshot.json"
DEFAULT_TRADE_HISTORY_PATH = REPO_ROOT / "ramshare" / "evidence" / "trade_history.json"
DEFAULT_POLICY_PATH = REPO_ROOT / "ramshare" / "state" / "trading_policy.json"


def load_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback


def parse_iso(ts: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def parse_est_spend_lines(lines: Iterable[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    rx = re.compile(r"^\-\s+([^[]+)\s+\[[^\]]+\].*est_spend=\$([0-9]+(?:\.[0-9]{1,2})?)")
    for line in lines:
        m = rx.search(line)
        if not m:
            continue
        ts = parse_iso(m.group(1).strip())
        if ts is None:
            continue
        out.append({"ts": ts, "amount_usd": float(m.group(2))})
    return out


def compute_hourly_spend(now: dt.datetime, entries: List[Dict[str, Any]]) -> float:
    cutoff = now - dt.timedelta(hours=1)
    return sum(float(e.get("amount_usd") or 0.0) for e in entries if isinstance(e.get("ts"), dt.datetime) and e["ts"] >= cutoff)


def append_audit(audit_path: Path, message: str, severity: str = "CRITICAL") -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    header = "# Audit Log (Local)\n\n"
    existing = audit_path.read_text(encoding="utf-8") if audit_path.exists() else header
    now_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"- {now_iso} [{severity}] {message}\n"
    audit_path.write_text(existing + line, encoding="utf-8")


def budget_status(
    *,
    budget_path: Path,
    audit_path: Path,
    kill_path: Path,
    default_daily_limit_usd: float,
) -> Dict[str, Any]:
    now = dt.datetime.now().astimezone()
    budget = load_json(
        budget_path,
        {
            "date": now.date().isoformat(),
            "daily_limit_usd": 0.0,
            "spent_today_usd": 0.0,
            "events": [],
        },
    )
    events = budget.get("events") or []

    spent_today = float(budget.get("spent_today_usd") or 0.0)
    configured_limit = float(budget.get("daily_limit_usd") or 0.0)
    effective_limit = configured_limit if configured_limit > 0 else float(default_daily_limit_usd)

    event_entries: List[Dict[str, Any]] = []
    for e in events:
        ts = parse_iso(str(e.get("ts") or ""))
        if ts is None:
            continue
        event_entries.append({"ts": ts, "amount_usd": float(e.get("amount_usd") or 0.0)})

    if audit_path.exists():
        audit_lines = audit_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        event_entries.extend(parse_est_spend_lines(audit_lines))

    spend_per_hour = compute_hourly_spend(now, event_entries)
    over = spent_today > effective_limit

    if over:
        kill_path.write_text(
            f"EMERGENCY STOP: Budget Exceeded at {now.isoformat(timespec='seconds')}\n"
            f"spent_today_usd={spent_today:.2f} limit_usd={effective_limit:.2f}\n",
            encoding="utf-8",
        )
        append_audit(
            audit_path,
            f"EMERGENCY STOP: Budget Exceeded | spent_today=${spent_today:.2f} limit=${effective_limit:.2f}",
            severity="CRITICAL",
        )
    return {
        "spent_today_usd": spent_today,
        "effective_limit_usd": effective_limit,
        "spend_per_hour_usd": spend_per_hour,
        "over_budget": over,
    }


def load_portfolio_snapshot(path: Path) -> Dict[str, Any]:
    return load_json(path, {"settled_cash": 0.0, "positions": []})


def load_trade_history(path: Path) -> Dict[str, Any]:
    return load_json(path, {"trades": []})


def load_trading_policy(path: Path) -> Dict[str, Any]:
    defaults = {
        "paper_only_mode": True,
        "allow_symbols": ["SPY", "AAPL", "MSFT", "QQQ"],
        "require_limit_orders": True,
        "max_order_notional_usd": 250.0,
        "max_orders_per_day": 5,
        "max_daily_notional_usd": 1000.0,
        "cooldown_minutes": 30,
        "require_dual_confirmation": True,
        "min_paper_trades": 10,
        "min_paper_win_rate": 0.55,
    }
    data = load_json(path, defaults)
    for k, v in defaults.items():
        data.setdefault(k, v)
    return data


def detect_wash_sale_risk(
    *,
    symbol: str,
    history: Dict[str, Any],
    lookback_days: int = 30,
) -> Tuple[bool, str]:
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=lookback_days)
    trades = history.get("trades") or []
    sym = symbol.upper().strip()

    for t in trades:
        if str(t.get("symbol", "")).upper().strip() != sym:
            continue
        side = str(t.get("side", "")).upper().strip()
        pnl = float(t.get("pnl", 0.0) or 0.0)
        ts = parse_iso(str(t.get("ts", "")))
        if side == "SELL" and pnl < 0 and ts and ts >= cutoff:
            return True, f"Recent loss sale detected for {sym} on {ts.date().isoformat()} (pnl={pnl:.2f})"
    return False, ""


def daily_trade_stats(history: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    today = now.date().isoformat()
    count = 0
    notional = 0.0
    last_ts: dt.datetime | None = None
    for t in history.get("trades") or []:
        ts = parse_iso(str(t.get("ts", "")))
        if ts is None:
            continue
        if ts.date().isoformat() == today:
            count += 1
            notional += float(t.get("notional_usd") or 0.0)
        if last_ts is None or ts > last_ts:
            last_ts = ts
    return {"count_today": count, "notional_today": notional, "last_trade_ts": last_ts}


def paper_performance(history: Dict[str, Any]) -> Dict[str, Any]:
    paper = [t for t in (history.get("trades") or []) if str(t.get("mode", "")).lower() == "paper"]
    if not paper:
        return {"count": 0, "win_rate": 0.0}
    wins = 0
    judged = 0
    for t in paper:
        if "pnl" in t:
            judged += 1
            if float(t.get("pnl") or 0.0) > 0:
                wins += 1
    if judged == 0:
        return {"count": len(paper), "win_rate": 0.0}
    return {"count": len(paper), "win_rate": wins / judged}


def pretrade_check(
    *,
    action: str,
    symbol: str,
    estimated_cost_usd: float,
    order_type: str,
    live: bool,
    dual_confirmation_token: str,
    heartbeat_origin: bool,
    force_live_unlock: bool,
    portfolio_snapshot_path: Path,
    trade_history_path: Path,
    policy_path: Path,
) -> Tuple[bool, str]:
    policy = load_trading_policy(policy_path)
    sym = symbol.upper().strip()
    action_u = action.upper().strip()
    order_t = order_type.upper().strip() or "MARKET"
    now = dt.datetime.now().astimezone()
    history = load_trade_history(trade_history_path)

    if sym not in [str(s).upper().strip() for s in policy.get("allow_symbols", [])]:
        return False, f"Symbol {sym} is not in allowlist."

    if bool(policy.get("require_limit_orders", True)) and order_t != "LIMIT":
        return False, f"Order type {order_t} blocked: limit orders required."

    if live:
        if heartbeat_origin:
            return False, "Live trading blocked for heartbeat-originated jobs."
        if bool(policy.get("paper_only_mode", True)) and not force_live_unlock:
            return False, "Paper-only mode enabled by policy."
        if bool(policy.get("require_dual_confirmation", True)) and not dual_confirmation_token.strip():
            return False, "Dual confirmation token is required for live trades."
        perf = paper_performance(history)
        if perf["count"] < int(policy.get("min_paper_trades", 0) or 0):
            return False, f"Need more paper trades before live mode ({perf['count']} recorded)."
        if perf["win_rate"] < float(policy.get("min_paper_win_rate", 0.0) or 0.0):
            return False, f"Paper win rate {perf['win_rate']:.2%} below required threshold."

    if estimated_cost_usd > float(policy.get("max_order_notional_usd", 0.0) or 0.0):
        return False, f"Order notional ${estimated_cost_usd:.2f} exceeds max per-order cap."

    day = daily_trade_stats(history, now)
    if day["count_today"] >= int(policy.get("max_orders_per_day", 0) or 0):
        return False, f"Daily order count cap reached ({day['count_today']})."
    if (day["notional_today"] + estimated_cost_usd) > float(policy.get("max_daily_notional_usd", 0.0) or 0.0):
        return False, "Daily notional cap would be exceeded."

    cooldown_min = int(policy.get("cooldown_minutes", 0) or 0)
    if cooldown_min > 0 and day["last_trade_ts"] is not None:
        delta = now - day["last_trade_ts"]
        if delta < dt.timedelta(minutes=cooldown_min):
            return False, f"Cooldown active: wait {cooldown_min} minutes between trades."

    snap = load_portfolio_snapshot(portfolio_snapshot_path)
    if action_u == "BUY":
        settled_cash = float(snap.get("settled_cash") or 0.0)
        if settled_cash < estimated_cost_usd:
            return False, f"Insufficient settled cash: have ${settled_cash:.2f}, need ${estimated_cost_usd:.2f}"
        wash_risk, reason = detect_wash_sale_risk(symbol=sym, history=history, lookback_days=30)
        if wash_risk:
            return False, f"Wash-sale risk: {reason}"

    return True, "Pretrade checks passed."


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Accountant skill: budget + pretrade risk checks")
    ap.add_argument("--budget-path", default=str(Path.home() / ".gemini" / "budget_tracking.json"))
    ap.add_argument("--audit-log-path", default=str(REPO_ROOT / "ramshare" / "evidence" / "audit_log.md"))
    ap.add_argument("--kill-switch-path", default=str(REPO_ROOT / "STOP_ALL_AGENTS.flag"))
    ap.add_argument("--default-daily-limit-usd", type=float, default=5.0)

    sub = ap.add_subparsers(dest="cmd")
    sub.required = False

    pre = sub.add_parser("pretrade-check", help="Validate settled cash and wash-sale constraints")
    pre.add_argument("--action", required=True, choices=["BUY", "SELL", "HOLD"])
    pre.add_argument("--symbol", required=True)
    pre.add_argument("--estimated-cost-usd", type=float, default=0.0)
    pre.add_argument("--order-type", default="LIMIT")
    pre.add_argument("--live", action="store_true")
    pre.add_argument("--dual-confirmation-token", default="")
    pre.add_argument("--heartbeat-origin", action="store_true")
    pre.add_argument("--force-live-unlock", action="store_true")
    pre.add_argument("--portfolio-snapshot-path", default=str(DEFAULT_PORTFOLIO_PATH))
    pre.add_argument("--trade-history-path", default=str(DEFAULT_TRADE_HISTORY_PATH))
    pre.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    if args.cmd == "pretrade-check":
        ok, reason = pretrade_check(
            action=args.action,
            symbol=args.symbol,
            estimated_cost_usd=float(args.estimated_cost_usd),
            order_type=args.order_type,
            live=bool(args.live),
            dual_confirmation_token=str(args.dual_confirmation_token or ""),
            heartbeat_origin=bool(args.heartbeat_origin),
            force_live_unlock=bool(args.force_live_unlock),
            portfolio_snapshot_path=Path(args.portfolio_snapshot_path),
            trade_history_path=Path(args.trade_history_path),
            policy_path=Path(args.policy_path),
        )
        if ok:
            print(f"Pretrade Status: OK | {reason}")
            return
        print(f"Pretrade Status: BLOCKED | {reason}")
        raise SystemExit(4)

    status = budget_status(
        budget_path=Path(args.budget_path),
        audit_path=Path(args.audit_log_path),
        kill_path=Path(args.kill_switch_path),
        default_daily_limit_usd=float(args.default_daily_limit_usd),
    )
    if status["over_budget"]:
        print(
            "Budget Status: STOP "
            f"[{status['spent_today_usd']:.2f}/{status['effective_limit_usd']:.2f}] | "
            f"Spend/Hour ${status['spend_per_hour_usd']:.2f}"
        )
        raise SystemExit(3)

    print(
        "Budget Status: OK "
        f"[{status['spent_today_usd']:.2f}/{status['effective_limit_usd']:.2f}] | "
        f"Spend/Hour ${status['spend_per_hour_usd']:.2f}"
    )


if __name__ == "__main__":
    main()
