from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
EVIDENCE_DIR = REPO_ROOT / "ramshare" / "evidence"
INBOX_DIR = EVIDENCE_DIR / "inbox"
REPORTS_DIR = EVIDENCE_DIR / "reports"
STRATEGY_DIR = REPO_ROOT / "ramshare" / "strategy"
SNAPSHOT_PATH = EVIDENCE_DIR / "portfolio_snapshot.json"
PROFILE_LATEST_PATH = STRATEGY_DIR / "fidelity_profile_latest.json"
COUNCIL_LATEST_PATH = STRATEGY_DIR / "finance_council_latest.json"


FUND_LIKE_SYMBOLS = {
    "FXAIX",
    "SCHD",
    "SPY",
    "VOO",
    "IVV",
    "QQQ",
    "VTI",
    "IWM",
    "DIA",
}

CASH_LIKE_SYMBOLS = {
    "SPAXX",
    "FDRXX",
    "SPRXX",
    "VMFXX",
    "SWVXX",
}

CANDIDATE_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "XLK",
    "SMH",
    "SOXX",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "META",
    "AMZN",
]

POSITIVE_WORDS = {
    "beat",
    "growth",
    "upgrade",
    "strong",
    "surge",
    "record",
    "outperform",
    "bullish",
    "buyback",
    "raises",
    "expands",
}

NEGATIVE_WORDS = {
    "miss",
    "downgrade",
    "weak",
    "selloff",
    "lawsuit",
    "probe",
    "ban",
    "recall",
    "bearish",
    "cuts",
    "recession",
    "risk",
}

MACRO_KEYWORDS = {
    "fomc",
    "fed",
    "cpi",
    "pce",
    "jobs",
    "inflation",
    "treasury",
    "yield",
    "sp500",
    "s&p",
    "nasdaq",
}


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback or {}


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, str):
            s = v.replace(",", "").replace("$", "").strip()
            if not s:
                return default
            return float(s)
        return float(v)
    except Exception:
        return default


def finite_float(v: Any, default: float = 0.0) -> float:
    x = as_float(v, default)
    if not math.isfinite(x):
        return default
    return x


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def normalize_symbol(s: str) -> str:
    sym = re.sub(r"[^A-Za-z0-9.\-]", "", (s or "").upper())
    if sym in {"", "CASH", "HELD", "SYMBOL"}:
        return ""
    return sym[:7]


def normalize_positions(inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = inputs.get("positions") if isinstance(inputs.get("positions"), list) else []
    if not rows:
        snap = load_json(SNAPSHOT_PATH, {})
        rows = snap.get("positions") if isinstance(snap.get("positions"), list) else []

    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(str(row.get("symbol") or row.get("ticker") or ""))
        if not symbol:
            continue
        quantity = as_float(row.get("quantity", row.get("qty", 0.0)), 0.0)
        price = as_float(row.get("price", row.get("last_price", 0.0)), 0.0)
        current_value = as_float(row.get("current_value", row.get("market_value", 0.0)), 0.0)
        cost_basis = as_float(row.get("cost_basis", row.get("cost", 0.0)), 0.0)
        if current_value <= 0 and quantity > 0 and price > 0:
            current_value = quantity * price
        if quantity <= 0 and current_value <= 0:
            continue
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0
        is_cash_like = symbol in CASH_LIKE_SYMBOLS
        out.append(
            {
                "symbol": symbol,
                "quantity": round(quantity, 6),
                "price": round(price, 6),
                "current_value": round(current_value, 2),
                "cost_basis": round(cost_basis, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "is_fund_like": symbol in FUND_LIKE_SYMBOLS,
                "is_cash_like": is_cash_like,
            }
        )
    return out


def compute_portfolio_metrics(positions: List[Dict[str, Any]], account_value_hint: float) -> Dict[str, Any]:
    total_value = sum(as_float(p.get("current_value"), 0.0) for p in positions)
    account_value = max(account_value_hint, total_value)
    weights: Dict[str, float] = {}
    single_name_weight = 0.0
    for p in positions:
        s = str(p.get("symbol") or "")
        w = (as_float(p.get("current_value"), 0.0) / account_value) if account_value > 0 else 0.0
        weights[s] = w
        if not bool(p.get("is_fund_like")) and not bool(p.get("is_cash_like")):
            single_name_weight += w
    top_symbol = ""
    top_weight = 0.0
    for s, w in weights.items():
        if w > top_weight:
            top_symbol, top_weight = s, w
    hhi = sum(w * w for w in weights.values())
    return {
        "account_value": round(account_value, 2),
        "positions_value": round(total_value, 2),
        "weights": {k: round(v, 6) for k, v in weights.items()},
        "top_symbol": top_symbol,
        "top_weight_pct": round(top_weight * 100.0, 2),
        "single_name_weight_pct": round(single_name_weight * 100.0, 2),
        "hhi": round(hhi, 6),
    }


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    loss = loss.replace(0, 1e-9)
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0).bfill().ffill()


def compute_macd(close: pd.Series) -> pd.DataFrame:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return pd.DataFrame({"macd": macd, "signal": signal, "hist": hist})


def compute_atr(hist: pd.DataFrame, period: int = 14) -> pd.Series:
    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean().bfill().ffill()


def fetch_history(symbol: str) -> pd.DataFrame:
    try:
        hist = yf.Ticker(symbol).history(period="9mo", interval="1d", auto_adjust=True)
        if not isinstance(hist, pd.DataFrame) or hist.empty:
            return pd.DataFrame()
        required = {"Close", "High", "Low"}
        if not required.issubset(set(hist.columns)):
            return pd.DataFrame()
        return hist.dropna(subset=["Close", "High", "Low"])
    except Exception:
        return pd.DataFrame()


def fetch_info(symbol: str) -> Dict[str, Any]:
    try:
        info = yf.Ticker(symbol).info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}


def fetch_titles(symbol: str, cap: int = 8) -> List[str]:
    out: List[str] = []
    try:
        rows = yf.Ticker(symbol).news or []
        for row in rows[:cap]:
            title = str(row.get("title") or "").strip()
            if title:
                out.append(title)
    except Exception:
        return out
    return out


def score_headlines(titles: List[str]) -> float:
    if not titles:
        return 0.0
    score = 0.0
    for t in titles:
        low = t.lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in low)
        neg = sum(1 for w in NEGATIVE_WORDS if w in low)
        score += float(pos - neg)
    raw = score / max(len(titles), 1)
    return clamp(raw / 2.5, -1.0, 1.0)


def load_profile_leads() -> Dict[str, Any]:
    return load_json(PROFILE_LATEST_PATH, {"online_leads": [], "lead_summary": {}})


def extract_lead_symbols(leads: List[Dict[str, Any]], held_symbols: List[str]) -> List[str]:
    counts: Dict[str, int] = {}
    held = set(held_symbols)
    valid = [s for s in CANDIDATE_UNIVERSE if s not in held]
    for row in leads:
        title = str(row.get("title") or "")
        query = str(row.get("query") or "")
        label = str(row.get("signal_label") or "")
        weight = 2 if label == "positive_catalyst" else (1 if label == "neutral_watch" else -1)
        if weight <= 0:
            continue
        text = f"{title} {query}".upper()
        for sym in valid:
            if sym in text:
                counts[sym] = counts.get(sym, 0) + weight
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    out = [sym for sym, score in ranked if score > 0]
    return out[:8]


def build_candidate_universe(positions: List[Dict[str, Any]], leads: List[Dict[str, Any]], cap: int = 8) -> List[str]:
    held_symbols = [str(p.get("symbol") or "") for p in positions if str(p.get("symbol") or "")]
    lead_symbols = extract_lead_symbols(leads, held_symbols)
    merged: List[str] = []
    for sym in lead_symbols + CANDIDATE_UNIVERSE:
        if not sym:
            continue
        s = sym.upper()
        if s in CASH_LIKE_SYMBOLS:
            continue
        if s in held_symbols:
            continue
        if s in merged:
            continue
        merged.append(s)
        if len(merged) >= cap:
            break
    return merged


def symbol_lead_bias(symbol: str, leads: List[Dict[str, Any]]) -> float:
    s = symbol.upper()
    pos = 0
    neg = 0
    for row in leads:
        title = str(row.get("title") or "")
        query = str(row.get("query") or "")
        if s not in title.upper() and s not in query.upper():
            continue
        label = str(row.get("signal_label") or "")
        if label == "positive_catalyst":
            pos += 1
        elif label == "negative_risk":
            neg += 1
    return clamp((pos - neg) / max(pos + neg, 1), -1.0, 1.0)


def technical_agent(symbol: str, hist: pd.DataFrame) -> Dict[str, Any]:
    if hist.empty:
        return {"score": 0.0, "verdict": "hold", "confidence": 0.2, "reason": "insufficient_price_history"}
    close = hist["Close"]
    price = finite_float(close.iloc[-1], 0.0)
    rsi_s = compute_rsi(close)
    rsi = finite_float(rsi_s.iloc[-1], 50.0)
    macd = compute_macd(close)
    macd_gap = finite_float((macd["macd"] - macd["signal"]).iloc[-1], 0.0)
    sma20 = finite_float(close.rolling(20).mean().iloc[-1], price)
    sma50 = finite_float(close.rolling(50).mean().iloc[-1], price)
    atr = finite_float(compute_atr(hist).iloc[-1], price * 0.03)
    rets = close.pct_change().dropna()
    vol20 = finite_float(rets.tail(20).std(), 0.0) if len(rets) >= 2 else 0.0

    score = 0.0
    score += 0.30 if price > sma20 else -0.20
    score += 0.20 if sma20 > sma50 else -0.20
    score += 0.25 if macd_gap > 0 else -0.25
    if rsi < 32:
        score += 0.20
    elif rsi > 70:
        score -= 0.30
    score = clamp(score, -1.0, 1.0)
    verdict = "buy" if score >= 0.35 else ("trim" if score <= -0.35 else "hold")
    return {
        "score": round(score, 4),
        "verdict": verdict,
        "confidence": round(clamp(abs(score) + 0.25, 0.2, 0.95), 3),
        "price": round(price, 4),
        "rsi": round(rsi, 2),
        "macd_gap": round(macd_gap, 6),
        "sma20": round(sma20, 4),
        "sma50": round(sma50, 4),
        "atr": round(atr, 4),
        "atr_pct": round((atr / price * 100.0) if price > 0 else 0.0, 3),
        "vol20": round(vol20, 5),
    }


def fundamental_agent(symbol: str, is_fund_like: bool, info: Dict[str, Any]) -> Dict[str, Any]:
    if is_fund_like:
        return {
            "score": 0.1,
            "verdict": "hold",
            "confidence": 0.45,
            "reason": "fund_like_holding_uses_portfolio_level_fundamental_logic",
        }
    pe = as_float(info.get("forwardPE", info.get("trailingPE", 0.0)), 0.0)
    revenue_growth = as_float(info.get("revenueGrowth", 0.0), 0.0)
    earnings_growth = as_float(info.get("earningsGrowth", 0.0), 0.0)
    debt_to_equity = as_float(info.get("debtToEquity", 0.0), 0.0)
    profit_margin = as_float(info.get("profitMargins", 0.0), 0.0)

    score = 0.0
    if pe > 0:
        if pe < 25:
            score += 0.2
        elif pe > 45:
            score -= 0.2
    if revenue_growth > 0.10:
        score += 0.2
    elif revenue_growth < 0:
        score -= 0.2
    if earnings_growth > 0.05:
        score += 0.2
    elif earnings_growth < 0:
        score -= 0.2
    if debt_to_equity > 200:
        score -= 0.2
    elif 0 < debt_to_equity < 80:
        score += 0.1
    if profit_margin > 0.15:
        score += 0.15
    elif 0 < profit_margin < 0.05:
        score -= 0.15

    score = clamp(score, -1.0, 1.0)
    verdict = "buy" if score >= 0.30 else ("trim" if score <= -0.30 else "hold")
    return {
        "score": round(score, 4),
        "verdict": verdict,
        "confidence": round(clamp(abs(score) + 0.2, 0.2, 0.95), 3),
        "pe": round(pe, 3),
        "revenue_growth": round(revenue_growth, 4),
        "earnings_growth": round(earnings_growth, 4),
        "debt_to_equity": round(debt_to_equity, 2),
        "profit_margin": round(profit_margin, 4),
    }


def sentiment_agent(symbol: str, titles: List[str], lead_bias: float) -> Dict[str, Any]:
    lexical = score_headlines(titles)
    blended = clamp((0.65 * lexical) + (0.35 * lead_bias), -1.0, 1.0)
    verdict = "buy" if blended >= 0.30 else ("trim" if blended <= -0.30 else "hold")
    return {
        "score": round(blended, 4),
        "verdict": verdict,
        "confidence": round(clamp(abs(blended) + 0.15, 0.2, 0.95), 3),
        "headline_count": len(titles),
        "lead_bias": round(lead_bias, 4),
    }


def execution_plan(action: str, price: float, atr: float, position_qty: float, desired_qty: float) -> Dict[str, Any]:
    if price <= 0:
        return {"action": "hold", "quantity": 0.0, "order_type": "LIMIT"}
    atr = atr if atr > 0 else (price * 0.03)
    if action == "buy":
        qty = max(0.0, desired_qty)
        limit_price = price * 0.995
        stop = max(0.01, price - (1.5 * atr))
        target = price + (3.0 * atr)
    elif action == "trim":
        qty = max(0.0, min(position_qty, desired_qty))
        limit_price = price * 1.005
        stop = None
        target = None
    else:
        qty = 0.0
        limit_price = price
        stop = None
        target = None
    rr = None
    if action == "buy" and stop is not None and target is not None and price > stop:
        rr = (target - price) / max(price - stop, 1e-9)
    return {
        "action": action,
        "quantity": round(qty, 4),
        "order_type": "LIMIT",
        "limit_price": round(limit_price, 4),
        "stop_loss": round(stop, 4) if stop is not None else None,
        "target_price": round(target, 4) if target is not None else None,
        "reward_risk": round(rr, 3) if rr is not None else None,
    }


def evaluate_symbol(
    position: Dict[str, Any],
    portfolio_metrics: Dict[str, Any],
    leads: List[Dict[str, Any]],
    lead_summary: Dict[str, Any],
    max_risk_per_trade_pct: float,
    *,
    is_candidate: bool = False,
) -> Dict[str, Any]:
    symbol = str(position.get("symbol") or "")
    qty = as_float(position.get("quantity"), 0.0)
    is_cash_like = bool(position.get("is_cash_like"))
    hist = fetch_history(symbol)
    t = technical_agent(symbol, hist)
    info = fetch_info(symbol)
    f = fundamental_agent(symbol, bool(position.get("is_fund_like")), info)
    titles = fetch_titles(symbol, cap=8)
    s_bias = symbol_lead_bias(symbol, leads)
    s = sentiment_agent(symbol, titles, s_bias)

    council_score = clamp((0.45 * t["score"]) + (0.30 * f["score"]) + (0.25 * s["score"]), -1.0, 1.0)
    action = "buy" if council_score >= 0.35 else ("trim" if council_score <= -0.35 else "hold")
    confidence = clamp(abs(council_score) + 0.2, 0.2, 0.95)

    account_value = as_float(portfolio_metrics.get("account_value"), 0.0)
    weight = as_float(portfolio_metrics.get("weights", {}).get(symbol), 0.0)
    risk_budget_usd = account_value * max_risk_per_trade_pct
    price = as_float(t.get("price"), as_float(position.get("price"), 0.0))
    atr = as_float(t.get("atr"), price * 0.03)
    stop_dist = max(atr * 1.5, price * 0.02) if price > 0 else 0.0
    qty_by_risk = (risk_budget_usd / stop_dist) if stop_dist > 0 else 0.0
    max_notional = min(account_value * 0.12, 750.0)
    qty_by_notional = (max_notional / price) if price > 0 else 0.0
    desired_buy_qty = min(qty_by_risk, qty_by_notional)
    desired_trim_qty = qty * 0.25

    macro_neg = int(lead_summary.get("negative_risk_count", 0))
    macro_pos = int(lead_summary.get("positive_catalyst_count", 0))
    veto_reasons: List[str] = []
    if is_cash_like:
        veto_reasons.append("cash_like_holding_not_trade_candidate")
    if is_candidate and action == "trim":
        veto_reasons.append("candidate_symbol_cannot_be_trimmed_without_position")
    if (not is_candidate) and qty <= 0 and action == "trim":
        veto_reasons.append("no_position_size_available_to_trim")
    if action == "buy" and weight >= 0.40:
        veto_reasons.append("concentration_cap_exceeded_for_additional_buy")
    if action == "buy" and as_float(t.get("vol20"), 0.0) >= 0.06 and confidence < 0.7:
        veto_reasons.append("volatility_too_high_for_current_conviction")
    if action == "buy" and macro_neg > (macro_pos + 2) and confidence < 0.75:
        veto_reasons.append("macro_lead_flow_is_risk_heavy")
    if action == "buy" and is_candidate and confidence < 0.60:
        veto_reasons.append("candidate_conviction_below_threshold")

    exec_plan = execution_plan(
        action=action,
        price=price,
        atr=atr,
        position_qty=qty,
        desired_qty=desired_buy_qty if action == "buy" else desired_trim_qty,
    )
    if is_candidate and exec_plan["action"] == "buy" and as_float(exec_plan.get("quantity"), 0.0) > 0:
        exec_plan["entry_type"] = "new_position"
    elif (not is_candidate) and exec_plan["action"] == "buy":
        exec_plan["entry_type"] = "add_to_position"
    else:
        exec_plan["entry_type"] = "manage_existing"
    if veto_reasons:
        exec_plan = execution_plan(action="hold", price=price, atr=atr, position_qty=qty, desired_qty=0.0)
        exec_plan["entry_type"] = "blocked"

    chief_summary = {
        "score": round(council_score, 4),
        "action": exec_plan["action"],
        "confidence": round(confidence, 3),
        "vetoed": bool(veto_reasons),
        "veto_reasons": veto_reasons,
        "is_candidate": bool(is_candidate),
    }
    return {
        "symbol": symbol,
        "position": position,
        "agents": {
            "technical_analyst": t,
            "fundamental_analyst": f,
            "sentiment_analyst": s,
            "risk_manager": {
                "weight_pct": round(weight * 100.0, 3),
                "max_risk_per_trade_pct": round(max_risk_per_trade_pct * 100.0, 3),
                "risk_budget_usd": round(risk_budget_usd, 2),
                "macro_positive_leads": macro_pos,
                "macro_negative_leads": macro_neg,
                "vetoed": bool(veto_reasons),
                "veto_reasons": veto_reasons,
                "is_candidate": bool(is_candidate),
            },
            "execution_trader": exec_plan,
            "chief_of_staff": chief_summary,
        },
        "debate": [
            f"Technical Analyst: {t['verdict']} (score={t['score']})",
            f"Fundamental Analyst: {f['verdict']} (score={f['score']})",
            f"Sentiment Analyst: {s['verdict']} (score={s['score']})",
            (
                "Risk Manager: veto applied -> " + "; ".join(veto_reasons)
                if veto_reasons
                else "Risk Manager: no veto"
            ),
            f"Chief of Staff: final action={exec_plan['action']} confidence={chief_summary['confidence']}",
        ],
    }


def recommend_orders(rows: List[Dict[str, Any]], min_confidence: float = 0.55) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        chief = row.get("agents", {}).get("chief_of_staff", {})
        exec_plan = row.get("agents", {}).get("execution_trader", {})
        action = str(exec_plan.get("action") or "hold").lower()
        conf = as_float(chief.get("confidence"), 0.0)
        qty = as_float(exec_plan.get("quantity"), 0.0)
        limit_price = as_float(exec_plan.get("limit_price"), 0.0)
        if action not in {"buy", "trim"}:
            continue
        if conf < min_confidence or qty <= 0 or limit_price <= 0:
            continue
        side = "BUY" if action == "buy" else "SELL"
        out.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "side": side,
                "quantity": round(qty, 4),
                "limit_price": round(limit_price, 4),
                "notional_usd": round(qty * limit_price, 2),
                "confidence": round(conf, 3),
                "source": "council_consensus",
                "is_candidate": bool(chief.get("is_candidate", False)),
            }
        )
    return out


def build_funding_sale(
    needed_cash: float,
    held_rows: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    if needed_cash <= 0:
        return None
    ranked = sorted(
        held_rows,
        key=lambda r: as_float(r.get("position", {}).get("current_value"), 0.0),
        reverse=True,
    )
    for row in ranked:
        pos = row.get("position", {})
        if bool(pos.get("is_cash_like")):
            continue
        symbol = str(pos.get("symbol") or "")
        qty = as_float(pos.get("quantity"), 0.0)
        price = as_float(pos.get("price"), 0.0)
        if qty <= 0 or price <= 0:
            continue
        max_trim_qty = qty * 0.35
        sell_qty = min(max_trim_qty, needed_cash / price)
        if sell_qty <= 0:
            continue
        return {
            "symbol": symbol,
            "side": "SELL",
            "quantity": round(sell_qty, 4),
            "limit_price": round(price * 1.003, 4),
            "notional_usd": round(sell_qty * price * 1.003, 2),
            "confidence": 0.62,
            "source": "funding_rebalance",
            "is_candidate": False,
        }
    return None


def summarize_horizons(
    *,
    held_rows: List[Dict[str, Any]],
    candidate_rows: List[Dict[str, Any]],
    tomorrow_orders: List[Dict[str, Any]],
    portfolio_metrics: Dict[str, Any],
    settled_cash: float,
) -> Dict[str, Any]:
    top_buy = next((o for o in tomorrow_orders if o.get("side") == "BUY"), None)
    top_sell = next((o for o in tomorrow_orders if o.get("side") == "SELL"), None)
    concentration = as_float(portfolio_metrics.get("top_weight_pct"), 0.0)

    day_1 = [
        f"Execute limit orders only; settled cash available is ${settled_cash:.2f}.",
        (
            f"Primary buy: {top_buy['symbol']} qty={top_buy['quantity']} limit=${top_buy['limit_price']} "
            f"(notional=${top_buy['notional_usd']})."
            if top_buy
            else "No buy order clears confidence threshold today."
        ),
        (
            f"Funding/trim sale: {top_sell['symbol']} qty={top_sell['quantity']} limit=${top_sell['limit_price']}."
            if top_sell
            else "No funding sale required under current order set."
        ),
        "Cancel any unfilled order at end of day; do not convert to market order.",
    ]

    week_1 = [
        "Re-run council daily after major macro releases and earnings headlines.",
        "Keep max risk per position <= 2% of account and reward:risk >= 2:1.",
        (
            f"Concentration is high (top holding {concentration:.2f}%). Prefer incremental rotation into strongest candidates."
            if concentration >= 55
            else "Concentration is acceptable; prioritize setups with strongest catalyst + trend alignment."
        ),
        (
            "Top candidate watchlist: "
            + ", ".join([str(r.get("symbol")) for r in candidate_rows[:3]])
            if candidate_rows
            else "No external candidates passed quality filters this cycle."
        ),
    ]

    month_1 = [
        "Track win rate and realized R multiple on every council order.",
        "Tighten candidate threshold if 4-trade rolling expectancy drops below zero.",
        "Scale position sizing only after sustained positive expectancy for at least 10 paper/live decisions.",
        "Use monthly rebalance to keep single-name exposure controlled while preserving trend winners.",
    ]

    return {
        "one_day": day_1,
        "one_week": week_1,
        "one_month": month_1,
    }


def maybe_emit_paper_jobs(
    rows: List[Dict[str, Any]],
    *,
    source_report: Path,
    max_jobs: int,
    min_confidence: float,
) -> List[Path]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    emitted: List[Path] = []
    for row in rows:
        if len(emitted) >= max_jobs:
            break
        chief = row.get("agents", {}).get("chief_of_staff", {})
        exec_plan = row.get("agents", {}).get("execution_trader", {})
        action = str(exec_plan.get("action") or "hold").upper()
        confidence = as_float(chief.get("confidence"), 0.0)
        qty = as_float(exec_plan.get("quantity"), 0.0)
        price = as_float(exec_plan.get("limit_price"), 0.0)
        if action not in {"BUY", "TRIM"}:
            continue
        if confidence < min_confidence or qty <= 0 or price <= 0:
            continue
        fidelity_action = "BUY" if action == "BUY" else "SELL"
        if fidelity_action == "SELL":
            pos_qty = as_float(row.get("position", {}).get("quantity"), 0.0)
            qty = min(qty, pos_qty)
            if qty <= 0:
                continue
        stamp = now_stamp()
        path = INBOX_DIR / f"job.finance_council_trade_{row.get('symbol')}_{stamp}.json"
        payload = {
            "id": f"finance-council-trade-{row.get('symbol')}-{stamp}",
            "task_type": "fidelity_trader",
            "target_profile": "fidelity",
            "inputs": {
                "action": fidelity_action,
                "symbol": row.get("symbol"),
                "quantity": round(qty, 4),
                "estimated_price": round(price, 4),
                "order_type": "LIMIT",
                "live": False,
                "source_report": str(source_report),
            },
            "policy": {
                "risk": "high",
                "estimated_spend_usd": round(qty * price, 2),
                "requires_pretrade_check": True,
            },
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        emitted.append(path)
    return emitted


def launch_council_if_requested(payload: Dict[str, Any], report_path: Path, online: bool, max_rounds: int) -> Dict[str, Any]:
    summon = REPO_ROOT / "scripts" / "fidelity_council.ps1"
    if not summon.exists():
        return {"launched": False, "reason": "missing_fidelity_council_script"}
    task = (
        "Use the finance council report at "
        f"{report_path}. Debate as Technical/Fundamental/Sentiment/Risk/Execution roles, "
        "then output DECISION_JSON with final BUY/SELL/HOLD actions and order parameters for paper mode."
    )
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(summon),
        "-Task",
        task,
        "-MaxRounds",
        str(max(2, int(max_rounds))),
    ]
    if online:
        cmd.append("-Online")
    cp = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "launched": cp.returncode == 0,
        "returncode": cp.returncode,
        "stdout_tail": (cp.stdout or "").strip().splitlines()[-12:],
        "stderr_tail": (cp.stderr or "").strip().splitlines()[-12:],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Finance council skill: multi-agent-style trade debate + paper tickets")
    ap.add_argument("job_file", help="Path to finance council job json")
    args = ap.parse_args()

    job_path = Path(args.job_file).resolve()
    job = load_json(job_path, {})
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    account_id = str(inputs.get("account_id") or job.get("account_id") or "unknown")
    account_value_hint = as_float(inputs.get("account_value"), 0.0)
    max_symbols = max(1, min(10, int(inputs.get("max_symbols", 6))))
    max_risk_per_trade_pct = clamp(as_float(inputs.get("max_risk_per_trade_pct", 0.02), 0.02), 0.0025, 0.05)
    emit_paper_jobs = bool(inputs.get("emit_paper_jobs", False))
    max_paper_jobs = max(1, min(5, int(inputs.get("max_paper_jobs", 2))))
    min_confidence = clamp(as_float(inputs.get("min_confidence", 0.55), 0.55), 0.2, 0.95)
    launch_council = bool(inputs.get("launch_council", False))
    council_online = bool(inputs.get("online", True))
    council_rounds = max(2, int(inputs.get("council_rounds", 2)))

    positions = normalize_positions(inputs)
    if not positions:
        raise SystemExit("No positions provided and no snapshot available for finance_council.")

    snapshot = load_json(SNAPSHOT_PATH, {})
    settled_cash = as_float(snapshot.get("settled_cash"), 0.0)
    metrics = compute_portfolio_metrics(positions, account_value_hint)
    sorted_positions = sorted(positions, key=lambda p: as_float(p.get("current_value"), 0.0), reverse=True)
    selected_positions = sorted_positions[:max_symbols]

    profile = load_profile_leads()
    leads = profile.get("online_leads") if isinstance(profile.get("online_leads"), list) else []
    lead_summary = profile.get("lead_summary") if isinstance(profile.get("lead_summary"), dict) else {}
    clean_leads = [x for x in leads if isinstance(x, dict)]

    held_rows: List[Dict[str, Any]] = []
    for p in selected_positions:
        held_rows.append(
            evaluate_symbol(
                p,
                portfolio_metrics=metrics,
                leads=clean_leads,
                lead_summary=lead_summary,
                max_risk_per_trade_pct=max_risk_per_trade_pct,
                is_candidate=False,
            )
        )

    candidate_universe = build_candidate_universe(selected_positions, clean_leads, cap=6)
    candidate_rows: List[Dict[str, Any]] = []
    for sym in candidate_universe:
        candidate_rows.append(
            evaluate_symbol(
                {
                    "symbol": sym,
                    "quantity": 0.0,
                    "price": 0.0,
                    "current_value": 0.0,
                    "cost_basis": 0.0,
                    "is_fund_like": sym in FUND_LIKE_SYMBOLS,
                    "is_cash_like": sym in CASH_LIKE_SYMBOLS,
                },
                portfolio_metrics=metrics,
                leads=clean_leads,
                lead_summary=lead_summary,
                max_risk_per_trade_pct=max_risk_per_trade_pct,
                is_candidate=True,
            )
        )

    # Priority: actionable first, then confidence.
    def _priority(row: Dict[str, Any]) -> Tuple[int, float]:
        chief = row.get("agents", {}).get("chief_of_staff", {})
        action = str(chief.get("action") or "hold")
        conf = as_float(chief.get("confidence"), 0.0)
        pri = 2 if action == "buy" else (1 if action == "trim" else 0)
        return (pri, conf)

    held_rows = sorted(held_rows, key=_priority, reverse=True)
    candidate_rows = sorted(candidate_rows, key=_priority, reverse=True)
    rows = held_rows + candidate_rows

    tomorrow_orders = recommend_orders(rows, min_confidence=min_confidence)
    total_buy_notional = sum(as_float(o.get("notional_usd"), 0.0) for o in tomorrow_orders if str(o.get("side")) == "BUY")
    total_sell_notional = sum(as_float(o.get("notional_usd"), 0.0) for o in tomorrow_orders if str(o.get("side")) == "SELL")
    net_cash_need = max(0.0, total_buy_notional - total_sell_notional - settled_cash)
    funding_sale = build_funding_sale(net_cash_need, held_rows)
    if funding_sale:
        tomorrow_orders.insert(0, funding_sale)
        total_sell_notional += as_float(funding_sale.get("notional_usd"), 0.0)
        net_cash_need = max(0.0, total_buy_notional - total_sell_notional - settled_cash)
    horizons = summarize_horizons(
        held_rows=held_rows,
        candidate_rows=candidate_rows,
        tomorrow_orders=tomorrow_orders,
        portfolio_metrics=metrics,
        settled_cash=settled_cash,
    )

    payload = {
        "job_id": str(job.get("id") or job_path.stem),
        "generated_at": now_iso(),
        "account_id": account_id,
        "objective": "High-quality short-term execution planning with strict risk gating",
        "constraints": {
            "paper_only": True,
            "no_guaranteed_profit_claims": True,
            "max_risk_per_trade_pct": round(max_risk_per_trade_pct * 100.0, 3),
        },
        "portfolio_metrics": metrics,
        "settled_cash": round(settled_cash, 2),
        "lead_summary": lead_summary,
        "council": rows,
        "held_council": held_rows,
        "opportunity_council": candidate_rows,
        "tomorrow_orders": tomorrow_orders,
        "cash_planning": {
            "total_buy_notional_usd": round(total_buy_notional, 2),
            "total_sell_notional_usd": round(total_sell_notional, 2),
            "net_cash_need_usd": round(net_cash_need, 2),
            "funding_sale_added": bool(funding_sale),
        },
        "horizon_plan": horizons,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    safe_account = re.sub(r"[^A-Za-z0-9]+", "_", account_id).strip("_") or "acct"
    stamp = now_stamp()
    out_json = REPORTS_DIR / f"finance_council_{safe_account}_{stamp}.json"
    out_md = REPORTS_DIR / f"finance_council_{safe_account}_{stamp}.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    COUNCIL_LATEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Finance Council Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- account_id: {account_id}",
        f"- account_value: ${metrics['account_value']:.2f}",
        f"- settled_cash: ${settled_cash:.2f}",
        f"- top_symbol: {metrics['top_symbol']} ({metrics['top_weight_pct']:.2f}%)",
        f"- concentration_hhi: {metrics['hhi']:.4f}",
        "",
        "## Held Decisions",
    ]
    for row in held_rows:
        chief = row.get("agents", {}).get("chief_of_staff", {})
        exec_plan = row.get("agents", {}).get("execution_trader", {})
        lines.append(
            f"- {row.get('symbol')}: action={chief.get('action')} confidence={chief.get('confidence')} "
            f"qty={exec_plan.get('quantity')} limit={exec_plan.get('limit_price')} vetoed={chief.get('vetoed')}"
        )
    lines.extend(["", "## Opportunity Candidates"])
    for row in candidate_rows[:5]:
        chief = row.get("agents", {}).get("chief_of_staff", {})
        exec_plan = row.get("agents", {}).get("execution_trader", {})
        lines.append(
            f"- {row.get('symbol')}: action={chief.get('action')} confidence={chief.get('confidence')} "
            f"qty={exec_plan.get('quantity')} limit={exec_plan.get('limit_price')} vetoed={chief.get('vetoed')}"
        )
    lines.extend(["", "## Tomorrow Orders"])
    for order in tomorrow_orders:
        lines.append(
            f"- {order.get('side')} {order.get('symbol')} qty={order.get('quantity')} "
            f"limit={order.get('limit_price')} notional=${order.get('notional_usd')} source={order.get('source')}"
        )
    lines.extend(["", "## 1D / 1W / 1M Plan"])
    lines.append("- 1 day:")
    lines.extend([f"  - {x}" for x in horizons.get("one_day", [])])
    lines.append("- 1 week:")
    lines.extend([f"  - {x}" for x in horizons.get("one_week", [])])
    lines.append("- 1 month:")
    lines.extend([f"  - {x}" for x in horizons.get("one_month", [])])
    lines.extend(["", "## Debate Snippets"])
    for row in rows[:4]:
        lines.append(f"- {row.get('symbol')}: " + " | ".join(row.get("debate", [])[:3]))
    lines.extend(
        [
            "",
            "## Safety Notes",
            "- Paper mode only; no live execution is enabled here.",
            "- No strategy can guarantee short-term profit.",
            "- Treat this as decision support, not financial advice.",
        ]
    )
    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    emitted: List[Path] = []
    if emit_paper_jobs:
        emitted = maybe_emit_paper_jobs(
            rows,
            source_report=out_json,
            max_jobs=max_paper_jobs,
            min_confidence=min_confidence,
        )

    council_launch = {"launched": False}
    if launch_council:
        council_launch = launch_council_if_requested(
            payload=payload,
            report_path=out_json,
            online=council_online,
            max_rounds=council_rounds,
        )

    summary = {
        "report_json": str(out_json),
        "report_md": str(out_md),
        "latest_json": str(COUNCIL_LATEST_PATH),
        "paper_jobs": [str(p) for p in emitted],
        "council_launch": council_launch,
    }
    print("Finance council generated:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
