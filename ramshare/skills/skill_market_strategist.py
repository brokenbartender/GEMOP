import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

import yfinance as yf


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
PORTFOLIO_PATH = REPO_ROOT / "ramshare" / "evidence" / "portfolio_snapshot.json"
STRATEGY_DIR = REPO_ROOT / "ramshare" / "strategy"
MARKET_CONTEXT_PATH = STRATEGY_DIR / "market_context.json"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"

POSITIVE_WORDS = {
    "beat", "beats", "growth", "bullish", "upgrade", "strong", "surge", "rally", "gain", "record", "optimistic"
}
NEGATIVE_WORDS = {
    "miss", "misses", "downgrade", "weak", "bearish", "drop", "selloff", "loss", "risk", "lawsuit", "recession"
}


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback


def detect_regime() -> Dict[str, Any]:
    hist = yf.Ticker("SPY").history(period="3mo", interval="1d", auto_adjust=True)
    if hist.empty or "Close" not in hist.columns:
        raise SystemExit("Unable to fetch SPY data for regime detection.")
    close = hist["Close"].dropna()
    sma20 = close.rolling(20).mean().iloc[-1]
    last = float(close.iloc[-1])
    regime = "BULLISH/TRENDING" if last > float(sma20) else "BEARISH/VOLATILE"
    rsi_threshold = 30.0 if regime == "BULLISH/TRENDING" else 25.0
    return {
        "spy_last_close": last,
        "spy_sma20": float(sma20),
        "regime": regime,
        "rsi_buy_threshold": rsi_threshold,
    }


def portfolio_symbols() -> List[str]:
    snap = load_json(PORTFOLIO_PATH, {"positions": []})
    out: List[str] = []
    for p in snap.get("positions") or []:
        sym = str(p.get("symbol") or "").upper().strip()
        if sym and sym not in out:
            out.append(sym)
    if not out:
        out = ["SPY", "AAPL", "MSFT"]
    return out[:6]


def sentiment_score_for_headlines(headlines: List[str]) -> float:
    if not headlines:
        return 0.0
    score = 0.0
    for h in headlines:
        low = h.lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in low)
        neg = sum(1 for w in NEGATIVE_WORDS if w in low)
        score += (pos - neg)
    # Normalize to [-1, 1] by headline count.
    raw = score / max(len(headlines), 1)
    return max(-1.0, min(1.0, raw / 2.0))


def fetch_headlines(symbols: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for s in symbols:
        rows = yf.Ticker(s).news or []
        titles: List[str] = []
        for row in rows[:8]:
            title = str(row.get("title") or "").strip()
            if title:
                titles.append(title)
        out[s] = titles
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Market Strategist: regime + sentiment context")
    ap.add_argument("job_file", help="Path to market strategist job json")
    args = ap.parse_args()
    _job = Path(args.job_file)

    regime_info = detect_regime()
    symbols = portfolio_symbols()
    headlines_by_symbol = fetch_headlines(symbols)
    all_headlines: List[str] = []
    for items in headlines_by_symbol.values():
        all_headlines.extend(items)
    sentiment = sentiment_score_for_headlines(all_headlines)

    context = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "market_symbol": "SPY",
        "regime": regime_info["regime"],
        "rsi_buy_threshold": regime_info["rsi_buy_threshold"],
        "sentiment_score": sentiment,
        "spy_last_close": regime_info["spy_last_close"],
        "spy_sma20": regime_info["spy_sma20"],
        "tracked_symbols": symbols,
        "headline_count": len(all_headlines),
    }

    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_CONTEXT_PATH.write_text(json.dumps(context, indent=2), encoding="utf-8")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"market_context_{now_stamp()}.json"
    details = {
        **context,
        "headlines_by_symbol": headlines_by_symbol,
    }
    report_path.write_text(json.dumps(details, indent=2), encoding="utf-8")
    print(f"Market context updated: {MARKET_CONTEXT_PATH}")


if __name__ == "__main__":
    main()
