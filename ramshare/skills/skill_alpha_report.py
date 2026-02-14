import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
TRADE_HISTORY_PATH = REPO_ROOT / "ramshare" / "evidence" / "trade_history.json"
MARKET_CONTEXT_PATH = REPO_ROOT / "ramshare" / "strategy" / "market_context.json"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
STRATEGY_DIR = REPO_ROOT / "ramshare" / "strategy"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback


def _float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def compute_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        peak = max(peak, val)
        dd = peak - val
        max_dd = max(max_dd, dd)
    return max_dd


def summarize_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "expectancy": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "avg_notional": 0.0,
            "trade_frequency_per_day": 0.0,
        }

    pnls = [_float(t.get("pnl"), 0.0) for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    count = len(trades)
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / count
    win_rate = wins / count if count else 0.0

    win_pnls = [p for p in pnls if p > 0]
    loss_pnls = [p for p in pnls if p < 0]
    avg_win = (sum(win_pnls) / len(win_pnls)) if win_pnls else 0.0
    avg_loss_abs = (abs(sum(loss_pnls) / len(loss_pnls))) if loss_pnls else 0.0
    expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss_abs)

    # Simple realized-equity curve based on trade PnL sequence.
    eq = []
    bal = 0.0
    for p in pnls:
        bal += p
        eq.append(bal)
    max_dd = compute_drawdown(eq)

    notionals = [_float(t.get("notional_usd"), 0.0) for t in trades]
    avg_notional = (sum(notionals) / count) if count else 0.0

    # Trade frequency from first to last timestamp.
    ts_values = []
    for t in trades:
        raw = str(t.get("ts") or "")
        try:
            ts_values.append(dt.datetime.fromisoformat(raw).astimezone())
        except Exception:
            continue
    if len(ts_values) >= 2:
        span_days = max((max(ts_values) - min(ts_values)).total_seconds() / 86400.0, 1.0 / 24.0)
        freq = count / span_days
    else:
        freq = float(count)

    return {
        "count": count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_pnl": avg_pnl,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
        "max_drawdown": max_dd,
        "avg_notional": avg_notional,
        "trade_frequency_per_day": freq,
    }


def split_by_regime(trades: List[Dict[str, Any]], default_regime: str) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "BULLISH/TRENDING": [],
        "BEARISH/VOLATILE": [],
        "UNKNOWN": [],
    }
    for t in trades:
        regime = str(t.get("regime") or default_regime or "UNKNOWN").upper()
        if regime not in buckets:
            regime = "UNKNOWN"
        buckets[regime].append(t)
    return buckets


def recommendations(summary: Dict[str, Any], by_regime: Dict[str, Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
    recs: List[str] = []
    current_threshold = _float(context.get("rsi_buy_threshold"), 30.0)

    if summary["count"] < 10:
        recs.append("Increase paper sample size before tuning thresholds (need >= 10 trades).")
    if summary["max_drawdown"] > 100:
        recs.append("Drawdown elevated: reduce max_order_notional_usd or increase cooldown_minutes.")
    if summary["win_rate"] < 0.5 and summary["count"] >= 10:
        recs.append("Win rate below 50%: tighten entry criteria and require stronger confirmation.")

    bear = by_regime.get("BEARISH/VOLATILE", {})
    bull = by_regime.get("BULLISH/TRENDING", {})
    if bear.get("count", 0) >= 5 and bear.get("win_rate", 0.0) < bull.get("win_rate", 0.0):
        new_thr = max(20.0, current_threshold - 2.0)
        recs.append(
            f"Bearish underperformance detected: consider lowering RSI buy threshold to {new_thr:.1f} in bearish regime."
        )
    if not recs:
        recs.append("No urgent tuning changes. Continue collecting paper trades.")
    return recs


def write_feedback(recs: List[str], summary: Dict[str, Any], context: Dict[str, Any]) -> Path:
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    out = STRATEGY_DIR / "alpha_feedback.json"
    payload = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_context": {
            "regime": context.get("regime", "UNKNOWN"),
            "sentiment_score": _float(context.get("sentiment_score"), 0.0),
            "rsi_buy_threshold": _float(context.get("rsi_buy_threshold"), 30.0),
        },
        "summary": summary,
        "recommendations": recs,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Alpha report generator from trade history and market context")
    ap.add_argument("job_file", help="Path to alpha_report job json")
    args = ap.parse_args()
    _job_path = Path(args.job_file)

    history = load_json(TRADE_HISTORY_PATH, {"trades": []})
    context = load_json(MARKET_CONTEXT_PATH, {"regime": "UNKNOWN", "sentiment_score": 0.0, "rsi_buy_threshold": 30.0})
    trades = history.get("trades") or []

    total = summarize_trades(trades)
    regime_buckets = split_by_regime(trades, str(context.get("regime") or "UNKNOWN"))
    by_regime = {k: summarize_trades(v) for k, v in regime_buckets.items()}
    recs = recommendations(total, by_regime, context)
    feedback_path = write_feedback(recs, total, context)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    json_out = REPORTS_DIR / f"alpha_report_{stamp}.json"
    md_out = REPORTS_DIR / f"alpha_report_{stamp}.md"

    payload = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "context": {
            "regime": context.get("regime"),
            "sentiment_score": _float(context.get("sentiment_score"), 0.0),
            "rsi_buy_threshold": _float(context.get("rsi_buy_threshold"), 30.0),
        },
        "overall": total,
        "by_regime": by_regime,
        "recommendations": recs,
        "feedback_path": str(feedback_path),
    }
    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Alpha Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- regime: {payload['context']['regime']}",
        f"- sentiment_score: {payload['context']['sentiment_score']:.2f}",
        f"- rsi_buy_threshold: {payload['context']['rsi_buy_threshold']:.2f}",
        "",
        "## Overall",
        f"- trades: {total['count']}",
        f"- win_rate: {total['win_rate']:.2%}",
        f"- avg_pnl: {total['avg_pnl']:.2f}",
        f"- expectancy: {total['expectancy']:.2f}",
        f"- total_pnl: {total['total_pnl']:.2f}",
        f"- max_drawdown: {total['max_drawdown']:.2f}",
        f"- avg_notional: {total['avg_notional']:.2f}",
        f"- trade_frequency_per_day: {total['trade_frequency_per_day']:.2f}",
        "",
        "## By Regime",
    ]
    for reg, s in by_regime.items():
        lines.extend(
            [
                f"### {reg}",
                f"- trades: {s['count']}",
                f"- win_rate: {s['win_rate']:.2%}",
                f"- expectancy: {s['expectancy']:.2f}",
                f"- total_pnl: {s['total_pnl']:.2f}",
                "",
            ]
        )
    lines.append("## Recommendations")
    lines.extend([f"- {r}" for r in recs])
    lines.append("")
    lines.append(f"- feedback_file: {feedback_path}")
    md_out.write_text("\n".join(lines), encoding="utf-8")

    print(f"Alpha report generated: {json_out}")


if __name__ == "__main__":
    main()
