import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
MARKET_CONTEXT_PATH = REPO_ROOT / "ramshare" / "strategy" / "market_context.json"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_market_context() -> Dict[str, Any]:
    if not MARKET_CONTEXT_PATH.exists():
        return {"regime": "UNKNOWN", "sentiment_score": 0.0, "rsi_buy_threshold": 30.0}
    try:
        data = load_json(MARKET_CONTEXT_PATH)
    except Exception:
        return {"regime": "UNKNOWN", "sentiment_score": 0.0, "rsi_buy_threshold": 30.0}

    regime = str(data.get("regime") or "UNKNOWN").upper()
    sentiment = float(data.get("sentiment_score") or 0.0)
    threshold = 30.0
    if regime.startswith("BEARISH"):
        threshold = 25.0
    if sentiment <= -0.30:
        threshold -= 2.0
    threshold = float(data.get("rsi_buy_threshold") or threshold)
    return {
        "regime": regime,
        "sentiment_score": sentiment,
        "rsi_buy_threshold": threshold,
    }


def pick_ticker(job: Dict[str, Any]) -> str:
    if isinstance(job.get("input_data"), str) and job["input_data"].strip():
        return job["input_data"].strip().upper()
    inputs = job.get("inputs") or {}
    ticker = inputs.get("ticker") or inputs.get("symbol")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    return "SPY"


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.bfill()


def compute_macd(close: pd.Series) -> pd.DataFrame:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return pd.DataFrame({"macd": macd, "signal": signal, "hist": hist})


def main() -> None:
    ap = argparse.ArgumentParser(description="Market Analyst skill: generate RSI/MACD and BUY signal")
    ap.add_argument("job_file", help="Path to market analyst job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_json(job_path)
    job_id = str(job.get("id") or job_path.stem)
    ticker = pick_ticker(job)

    hist = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)
    if hist.empty or "Close" not in hist.columns:
        raise SystemExit(f"No market data returned for ticker: {ticker}")

    close = hist["Close"].dropna()
    rsi_series = compute_rsi(close)
    macd_df = compute_macd(close)
    last_rsi = float(rsi_series.iloc[-1])
    last_close = float(close.iloc[-1])
    last_macd = float(macd_df["macd"].iloc[-1])
    last_signal = float(macd_df["signal"].iloc[-1])
    market_ctx = load_market_context()
    regime = str(market_ctx.get("regime") or "UNKNOWN")
    sentiment = float(market_ctx.get("sentiment_score") or 0.0)
    rsi_buy_threshold = float(market_ctx.get("rsi_buy_threshold") or 30.0)
    macd_confirmation_required = regime.startswith("BEARISH")
    macd_confirm_ok = (last_macd > last_signal) if macd_confirmation_required else True
    buy_condition = (last_rsi < rsi_buy_threshold) and macd_confirm_ok

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"market_analysis_{ticker}_{now_stamp()}.json"
    report = {
        "job_id": job_id,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "ticker": ticker,
        "price": last_close,
        "rsi": last_rsi,
        "rsi_buy_threshold": rsi_buy_threshold,
        "macd": last_macd,
        "macd_signal": last_signal,
        "macd_confirmation_required": macd_confirmation_required,
        "market_regime": regime,
        "market_sentiment_score": sentiment,
        "buy_condition": buy_condition,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if buy_condition:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        signal_path = INBOX_DIR / f"job.buy_signal_{ticker}_{now_stamp()}.json"
        signal_job = {
            "id": f"buy-signal-{ticker}-{now_stamp()}",
            "task_type": "fidelity_trader",
            "target_profile": "fidelity",
            "inputs": {
                "action": "BUY",
                "symbol": ticker,
                "quantity": 1,
                "estimated_price": round(last_close, 2),
                "source_report": str(report_path),
            },
            "policy": {
                "risk": "high",
                "estimated_spend_usd": round(last_close, 2),
                "requires_pretrade_check": True,
            },
        }
        signal_path.write_text(json.dumps(signal_job, indent=2), encoding="utf-8")
        print(f"BUY_SIGNAL generated: {signal_path}")
        return

    print(f"No BUY signal for {ticker}. RSI={last_rsi:.2f}, threshold={rsi_buy_threshold:.2f}, regime={regime}")


if __name__ == "__main__":
    main()
