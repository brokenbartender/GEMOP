from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
EVIDENCE_DIR = REPO_ROOT / "ramshare" / "evidence"
REPORTS_DIR = EVIDENCE_DIR / "reports"
STRATEGY_DIR = REPO_ROOT / "ramshare" / "strategy"
SNAPSHOT_PATH = EVIDENCE_DIR / "portfolio_snapshot.json"
LATEST_PATH = STRATEGY_DIR / "market_theme_latest.json"

HIGH_TRUST_SOURCES = (
    "reuters",
    "associated press",
    "ap news",
    "wall street journal",
    "wsj",
    "bloomberg",
    "financial times",
    "ft",
    "cnbc",
    "marketwatch",
    "federal reserve",
    "bls",
    "bea",
    "sec",
    "treasury",
    "nasdaq",
)

MEDIUM_TRUST_SOURCES = (
    "yahoo finance",
    "investopedia",
    "seeking alpha",
    "barron's",
    "morningstar",
    "fidelity",
)

NEGATIVE_WORDS = (
    "miss",
    "cut",
    "downgrade",
    "lawsuit",
    "probe",
    "ban",
    "weak",
    "bearish",
    "recall",
    "fraud",
)

POSITIVE_WORDS = (
    "beat",
    "raise",
    "growth",
    "upgrade",
    "record",
    "strong",
    "bullish",
    "buyback",
    "outperform",
    "guidance",
)

SYMBOL_STOPWORDS = {
    "USA",
    "US",
    "ETF",
    "AI",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "THIS",
    "THAT",
    "FROM",
    "WEEK",
    "BEST",
    "STOCK",
    "STOCKS",
    "NASDAQ",
    "NYSE",
    "AMEX",
    "OTC",
    "CPI",
    "PCE",
    "FOMC",
    "FED",
    "GDP",
    "EPS",
    "SA",
}

THEME_STOPWORDS = {
    "best",
    "top",
    "stocks",
    "stock",
    "investments",
    "investment",
    "this",
    "week",
    "month",
    "day",
    "for",
    "and",
    "with",
    "the",
    "to",
    "of",
    "in",
}

THEME_SEED_UNIVERSE = {
    "ai": ["AISP", "BBAI", "SOUN", "AI", "PLTR", "PATH", "UPST", "SMCI", "DELL", "MU", "AMD"],
    "artificial intelligence": ["AISP", "BBAI", "SOUN", "AI", "PLTR", "PATH", "UPST", "SMCI", "DELL", "MU", "AMD"],
    "cybersecurity": ["S", "CRWD", "PANW", "FTNT", "ZS", "SENT", "OKTA", "TENB", "RPD", "SAIL", "VRNS"],
    "semiconductor": ["NVDA", "AMD", "MU", "INTC", "QCOM", "AVGO", "MRVL", "SMCI", "SOXX", "SMH"],
    "biotech": ["XBI", "IBB", "MRNA", "VRTX", "REGN", "ALNY", "EXEL", "CRSP", "NTLA"],
    "ev": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV", "CHPT", "BLNK"],
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


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip()).strip("_").lower()
    return s[:64] if s else "theme"


def recency_score(pub: str, as_of: dt.datetime) -> int:
    try:
        ts = parsedate_to_datetime(pub)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        age_days = (as_of - ts.astimezone(as_of.tzinfo or dt.timezone.utc)).days
    except Exception:
        return 0
    if age_days <= 1:
        return 3
    if age_days <= 3:
        return 2
    if age_days <= 7:
        return 1
    if age_days <= 30:
        return 0
    return -1


def source_trust_score(name: str) -> int:
    s = (name or "").lower()
    if not s:
        return 0
    if any(k in s for k in HIGH_TRUST_SOURCES):
        return 3
    if any(k in s for k in MEDIUM_TRUST_SOURCES):
        return 1
    return 0


def signal_score(title: str) -> int:
    t = (title or "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    return pos - neg


def classify_signal(title: str) -> str:
    s = signal_score(title)
    if s >= 2:
        return "positive_catalyst"
    if s <= -1:
        return "negative_risk"
    return "neutral_watch"


def build_theme_queries(theme: str, depth: str = "deep") -> List[str]:
    t = theme.strip()
    deep = depth.lower() == "deep"
    q = [
        f"{t} stocks to watch this week",
        f"{t} analyst upgrades downgrades",
        f"{t} earnings this week",
        f"{t} SEC filings 8-k",
        f"{t} industry demand trends",
        "US economic calendar this week",
        "Federal Reserve policy outlook this week",
    ]
    if deep:
        q.extend(
            [
                f"{t} unusual options activity",
                f"{t} supply chain constraints",
                f"{t} government contracts grants",
                f"{t} mergers acquisitions rumors",
                f"{t} small cap momentum stocks",
                f"{t} ticker list NASDAQ",
                f"{t} small cap stocks under $50",
            ]
        )
    out: List[str] = []
    seen = set()
    for item in q:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def fetch_google_news(query: str, max_items: int = 8, timeout_s: int = 12) -> Tuple[List[Dict[str, Any]], str | None]:
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": "gemini-op-theme-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except Exception as e:
        return ([], f"{query}: fetch_failed ({e})")
    try:
        root = ET.fromstring(raw)
    except Exception:
        return ([], f"{query}: xml_parse_failed")

    out: List[Dict[str, Any]] = []
    as_of = dt.datetime.now().astimezone()
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        source_name = title.rsplit(" - ", 1)[-1].strip() if " - " in title else ""
        out.append(
            {
                "query": query,
                "title": title,
                "url": link,
                "published": pub,
                "source_name": source_name,
                "signal_score": signal_score(title),
                "signal_label": classify_signal(title),
                "recency_score": recency_score(pub, as_of),
                "source_trust_score": source_trust_score(source_name),
            }
        )
        if len(out) >= max_items:
            break
    return (out, None)


def extract_symbol_tokens(text: str) -> List[str]:
    out: List[str] = []

    for m in re.finditer(r"\((?:NASDAQ|NYSE|AMEX|NYSEAMERICAN|OTC)\s*:\s*([A-Za-z]{1,5})\)", text, flags=re.IGNORECASE):
        sym = m.group(1).upper().strip()
        if sym in SYMBOL_STOPWORDS:
            continue
        if sym and sym not in out:
            out.append(sym)

    for m in re.finditer(r"\$([A-Za-z]{2,5})\b", text):
        sym = m.group(1).upper().strip()
        if sym in SYMBOL_STOPWORDS:
            continue
        if sym and sym not in out:
            out.append(sym)

    for m in re.finditer(r"\b[A-Z]{3,5}\b", text):
        sym = m.group(0).upper().strip()
        if sym in SYMBOL_STOPWORDS:
            continue
        if sym and sym not in out:
            out.append(sym)
    return out


def theme_keywords(theme: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9]+", (theme or "").lower())
    out: List[str] = []
    for w in words:
        if w in THEME_STOPWORDS:
            continue
        if len(w) < 2:
            continue
        if w not in out:
            out.append(w)
    return out


def parse_theme_intent(theme: str) -> Dict[str, Any]:
    t = (theme or "").lower()
    words = set(re.findall(r"[a-z0-9]+", t))
    prefer_micro = any(x in t for x in ("micro-cap", "micro cap", "microcap")) or "micro" in words
    prefer_small = any(x in t for x in ("small-cap", "small cap", "smallcap")) or "small" in words
    prefer_weekly = "week" in words or "weekly" in words
    return {
        "prefer_micro_cap": prefer_micro,
        "prefer_small_cap": prefer_small or prefer_micro,
        "horizon_days": 7 if prefer_weekly else 21,
    }


def seed_symbols_for_theme(theme: str) -> List[str]:
    t = (theme or "").lower()
    out: List[str] = []
    for k, symbols in THEME_SEED_UNIVERSE.items():
        if k in t:
            for s in symbols:
                sym = s.upper().strip()
                if sym and sym not in out:
                    out.append(sym)
    return out


def theme_relevance_score(theme_keys: List[str], text: str) -> int:
    low = (text or "").lower()
    score = 0
    for k in theme_keys:
        if re.search(rf"\b{re.escape(k)}\b", low):
            score += 1
    return score


def symbol_mentioned_in_text(sym: str, text: str) -> bool:
    s = sym.upper().strip()
    if not s:
        return False
    if len(s) <= 2:
        # Avoid false positives for ambiguous short symbols (e.g., "AI").
        short_patterns = [
            rf"\$\s*{re.escape(s)}\b",
            rf"\((?:NASDAQ|NYSE|AMEX|NYSEAMERICAN|OTC)\s*:\s*{re.escape(s)}\)",
        ]
        return any(re.search(p, text, flags=re.IGNORECASE) for p in short_patterns)
    return re.search(rf"\b{re.escape(s)}\b", text, flags=re.IGNORECASE) is not None


def validate_symbols(candidates: Dict[str, float], max_checks: int = 40) -> List[str]:
    ranked = sorted(candidates.items(), key=lambda kv: kv[1], reverse=True)[:max_checks]
    valid: List[str] = []
    for sym, _ in ranked:
        try:
            hist = yf.Ticker(sym).history(period="1mo", interval="1d", auto_adjust=True)
            if isinstance(hist, pd.DataFrame) and not hist.empty and "Close" in hist.columns:
                px = as_float(hist["Close"].dropna().iloc[-1], 0.0)
                if px > 0:
                    valid.append(sym)
        except Exception:
            continue
    return valid


def market_cap_fit_score(mcap: float, intent: Dict[str, Any]) -> float:
    if mcap <= 0:
        return 0.0
    prefer_micro = bool(intent.get("prefer_micro_cap"))
    prefer_small = bool(intent.get("prefer_small_cap"))
    if prefer_micro:
        if 30_000_000 <= mcap <= 2_500_000_000:
            return 0.35
        if mcap <= 10_000_000_000:
            return 0.10
        return -0.35
    if prefer_small:
        if mcap <= 10_000_000_000:
            return 0.20
        if mcap <= 25_000_000_000:
            return 0.05
        return -0.20
    return 0.0


def compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean().replace(0, 1e-9)
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return as_float(rsi.dropna().iloc[-1], 50.0) if not rsi.dropna().empty else 50.0


def analyze_symbol(sym: str, lead_score: float, evidence: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any] | None:
    try:
        t = yf.Ticker(sym)
        hist = t.history(period="9mo", interval="1d", auto_adjust=True)
        if not isinstance(hist, pd.DataFrame) or hist.empty or "Close" not in hist.columns:
            return None
        close = hist["Close"].dropna()
        if close.empty:
            return None
        price = as_float(close.iloc[-1], 0.0)
        if price <= 0:
            return None
        ret_5d = as_float((close.iloc[-1] / close.iloc[-6] - 1.0), 0.0) if len(close) > 6 else 0.0
        ret_21d = as_float((close.iloc[-1] / close.iloc[-22] - 1.0), 0.0) if len(close) > 22 else 0.0
        rsi = compute_rsi(close, period=14)
        vol = close.pct_change().dropna()
        vol20 = as_float(vol.tail(20).std(), 0.0) if len(vol) >= 2 else 0.0

        avg_volume = 0.0
        if "Volume" in hist.columns:
            avg_volume = as_float(hist["Volume"].tail(20).mean(), 0.0)
        avg_dollar_vol = avg_volume * price

        info = t.info if isinstance(t.info, dict) else {}
        mcap = as_float(info.get("marketCap"), 0.0)

        lead_component = clamp(lead_score / 10.0, -1.0, 1.0)
        momentum_component = clamp((ret_5d * 2.2) + (ret_21d * 1.2), -1.0, 1.0)
        prefer_micro = bool(intent.get("prefer_micro_cap"))
        prefer_small = bool(intent.get("prefer_small_cap"))
        liq_divisor = 1_200_000.0 if prefer_micro else (2_500_000.0 if prefer_small else 8_000_000.0)
        liquidity_component = clamp((avg_dollar_vol / liq_divisor), 0.0, 1.0)
        mention_count = max(0, int(evidence.get("mention_count", 0)))
        source_diversity = max(0, int(evidence.get("source_diversity", 0)))
        evidence_component = clamp((mention_count * 0.16) + (source_diversity * 0.16), 0.0, 0.8)
        cap_fit = market_cap_fit_score(mcap, intent)
        risk_penalty = 0.2 if vol20 > 0.08 else (0.1 if vol20 > 0.05 else 0.0)
        overbought_penalty = 0.1 if rsi >= 76 else 0.0
        score = (
            (0.34 * lead_component)
            + (0.22 * momentum_component)
            + (0.16 * liquidity_component)
            + (0.16 * evidence_component)
            + (0.12 * cap_fit)
            - risk_penalty
            - overbought_penalty
        )
        score = clamp(score, -1.0, 1.0)
        confidence = clamp(abs(score) + 0.2, 0.2, 0.95)

        min_liq_buy = 200_000.0 if prefer_micro else (500_000.0 if prefer_small else 1_000_000.0)
        score_buy = 0.25 if prefer_micro else 0.35
        too_large_for_intent = (prefer_micro and mcap > 10_000_000_000) or (prefer_small and mcap > 25_000_000_000)
        if score >= score_buy and avg_dollar_vol >= min_liq_buy and source_diversity >= 1 and not too_large_for_intent:
            stance = "buy_candidate"
        elif score >= 0.15 or (prefer_micro and cap_fit > 0 and score >= 0.03):
            stance = "watch"
        else:
            stance = "avoid"

        reasons: List[str] = []
        if mention_count < 2:
            reasons.append("low_symbol_mention_count")
        if source_diversity < 2:
            reasons.append("low_source_diversity")
        if avg_dollar_vol < min_liq_buy:
            reasons.append("low_liquidity_for_intent")
        if prefer_micro and mcap > 10_000_000_000:
            reasons.append("too_large_for_micro_cap_intent")
        if prefer_small and mcap > 25_000_000_000:
            reasons.append("too_large_for_small_cap_intent")
        if not math.isfinite(score):
            reasons.append("invalid_score")
        if stance == "watch" and score < 0.15:
            reasons.append("speculative_low_conviction")

        return {
            "symbol": sym,
            "price": round(price, 4),
            "market_cap": round(mcap, 2),
            "avg_dollar_volume_20d": round(avg_dollar_vol, 2),
            "return_5d_pct": round(ret_5d * 100.0, 2),
            "return_21d_pct": round(ret_21d * 100.0, 2),
            "rsi14": round(rsi, 2),
            "volatility_20d": round(vol20, 5),
            "theme_lead_score": round(lead_score, 3),
            "mention_count": mention_count,
            "source_diversity": source_diversity,
            "cap_fit_score": round(cap_fit, 4),
            "composite_score": round(score, 4),
            "confidence": round(confidence, 3),
            "stance": stance,
            "reasons": reasons,
        }
    except Exception:
        return None


def build_horizon_plan(theme: str, picks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    top = [p for p in picks if str(p.get("stance")) == "buy_candidate"][:3]
    watch = [p for p in picks if str(p.get("stance")) == "watch"][:5]
    day = [
        f"Theme run for '{theme}': premarket-check top candidates before placing orders.",
        (
            "Top buy candidates: " + ", ".join([f"{p['symbol']} (${p['price']})" for p in top])
            if top
            else "No high-conviction buy candidate today; stay in watch mode."
        ),
        "Use only limit orders and define stop/target at entry.",
    ]
    week = [
        "Re-run theme scan daily and update ranks based on fresh catalysts and momentum drift.",
        "Scale into winners in 2-3 tranches; avoid full-size first entry.",
        (
            "Watchlist for rotation: " + ", ".join([p["symbol"] for p in watch[:4]])
            if watch
            else "No secondary watchlist symbols available this run."
        ),
    ]
    month = [
        "Keep a rolling scorecard: hit-rate, average win/loss, and thesis break reasons.",
        "Drop symbols with repeated negative catalyst drift and weak liquidity.",
        "Raise sizing only after sustained positive expectancy.",
    ]
    return {"one_day": day, "one_week": week, "one_month": month}


def main() -> None:
    ap = argparse.ArgumentParser(description="Theme-driven market research skill")
    ap.add_argument("job_file", help="Path to market_theme_research job json")
    args = ap.parse_args()

    job = load_json(Path(args.job_file), {})
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    account_id = str(inputs.get("account_id") or "unknown")
    theme = str(inputs.get("theme") or "").strip()
    if not theme:
        raise SystemExit("market_theme_research requires inputs.theme")
    search_depth = str(inputs.get("search_depth") or "deep").lower().strip()
    if search_depth not in {"standard", "deep"}:
        search_depth = "deep"
    max_candidates = max(3, min(20, int(inputs.get("max_candidates", 10))))
    max_items_per_query = max(3, min(16, int(inputs.get("max_items_per_query", 8))))
    timeout_s = max(6, min(25, int(inputs.get("timeout_s", 12))))
    offline = bool(inputs.get("offline", False))
    seed_leads = inputs.get("seed_leads") if isinstance(inputs.get("seed_leads"), list) else []
    keys = theme_keywords(theme)
    intent = parse_theme_intent(theme)

    snapshot = load_json(SNAPSHOT_PATH, {"positions": []})
    held_symbols = {
        str(p.get("symbol") or "").upper().strip()
        for p in (snapshot.get("positions") or [])
        if isinstance(p, dict)
    }
    held_symbols = {s for s in held_symbols if s}

    leads: List[Dict[str, Any]] = []
    failures: List[str] = []
    queries = build_theme_queries(theme, depth=search_depth)

    if offline:
        leads = [x for x in seed_leads if isinstance(x, dict)]
    else:
        for q in queries:
            items, err = fetch_google_news(q, max_items=max_items_per_query, timeout_s=timeout_s)
            leads.extend(items)
            if err:
                failures.append(err)

    as_of = dt.datetime.now().astimezone()
    filtered: List[Dict[str, Any]] = []
    for row in leads:
        signal = as_float(row.get("signal_score"), 0.0)
        trust = as_float(row.get("source_trust_score"), 0.0)
        rec = as_float(row.get("recency_score"), 0.0) if "recency_score" in row else recency_score(str(row.get("published") or ""), as_of)
        rel = theme_relevance_score(keys, str(row.get("title") or ""))
        quality = signal * 2.0 + trust + rec + min(rel, 3) * 1.5
        if quality < -2:
            continue
        merged = dict(row)
        merged["quality_score"] = round(quality, 3)
        merged["theme_relevance"] = rel
        merged["signal_label"] = merged.get("signal_label") or classify_signal(str(merged.get("title") or ""))
        filtered.append(merged)

    theme_rows = [r for r in filtered if int(r.get("theme_relevance", 0)) > 0]
    candidate_leads = theme_rows if theme_rows else filtered

    token_scores: Dict[str, float] = {}
    for row in candidate_leads:
        text = f"{row.get('title','')} {row.get('query','')}"
        base = as_float(row.get("quality_score"), 0.0)
        for sym in extract_symbol_tokens(text):
            if sym in held_symbols:
                continue
            token_scores[sym] = token_scores.get(sym, 0.0) + base

    seeded = [s for s in seed_symbols_for_theme(theme) if s not in held_symbols]
    for s in seeded:
        token_scores[s] = token_scores.get(s, 0.0) + 0.25

    valid_symbols = set(validate_symbols(token_scores, max_checks=50))

    lead_scores: Dict[str, float] = {}
    symbol_evidence: Dict[str, Dict[str, Any]] = {}
    for row in candidate_leads:
        text = f"{row.get('title','')} {row.get('query','')}"
        base = as_float(row.get("quality_score"), 0.0)
        source = str(row.get("source_name") or "").strip().lower()
        for sym in valid_symbols:
            if symbol_mentioned_in_text(sym, text):
                lead_scores[sym] = lead_scores.get(sym, 0.0) + base
                cur = symbol_evidence.get(sym) or {"mention_count": 0, "sources": set(), "top_quality": -99.0}
                cur["mention_count"] = int(cur["mention_count"]) + 1
                if source:
                    cur["sources"].add(source)
                cur["top_quality"] = max(as_float(cur["top_quality"], -99.0), base)
                symbol_evidence[sym] = cur

    for sym in valid_symbols:
        if sym in lead_scores:
            continue
        baseline = as_float(token_scores.get(sym), 0.0)
        if baseline <= 0:
            continue
        lead_scores[sym] = max(0.1, baseline * 0.5)
        symbol_evidence[sym] = symbol_evidence.get(sym) or {"mention_count": 0, "sources": set(), "top_quality": baseline}

    analyses: List[Dict[str, Any]] = []
    for sym, lscore in sorted(lead_scores.items(), key=lambda kv: kv[1], reverse=True)[:max_candidates * 2]:
        if sym in held_symbols:
            continue
        ev = symbol_evidence.get(sym) or {"mention_count": 0, "sources": set(), "top_quality": 0.0}
        evidence = {
            "mention_count": int(ev.get("mention_count", 0)),
            "source_diversity": len(ev.get("sources") or set()),
            "top_quality": as_float(ev.get("top_quality"), 0.0),
        }
        analyzed = analyze_symbol(sym, lscore, evidence=evidence, intent=intent)
        if analyzed is not None:
            analyses.append(analyzed)

    analyses = sorted(analyses, key=lambda r: as_float(r.get("composite_score"), -99.0), reverse=True)[:max_candidates]
    intent_safe = [
        x
        for x in analyses
        if "too_large_for_micro_cap_intent" not in (x.get("reasons") or [])
        and "too_large_for_small_cap_intent" not in (x.get("reasons") or [])
    ]
    top_candidates = [x for x in intent_safe if str(x.get("stance")) in {"buy_candidate", "watch"}][:max_candidates]
    horizon = build_horizon_plan(theme, top_candidates)

    payload = {
        "job_id": str(job.get("id") or Path(args.job_file).stem),
        "generated_at": now_iso(),
        "account_id": account_id,
        "theme": theme,
        "search_depth": search_depth,
        "theme_intent": intent,
        "constraints": {
            "no_guaranteed_profit_claims": True,
            "exclude_current_holdings": True,
            "paper_first": True,
        },
        "research_diagnostics": {
            "query_count": len(queries),
            "lead_count_raw": len(leads),
            "lead_count_filtered": len(filtered),
            "theme_relevant_lead_count": len(theme_rows),
            "theme_seed_symbol_count": len(seeded),
            "symbol_token_count": len(token_scores),
            "validated_symbol_count": len(valid_symbols),
            "intent_safe_candidate_count": len(intent_safe),
            "top_candidate_count": len(top_candidates),
            "fetch_failures_count": len(failures),
            "fetch_failures": failures[:20],
        },
        "held_symbols": sorted(held_symbols),
        "top_candidates": top_candidates,
        "all_candidates": analyses,
        "top_leads": sorted(
            filtered,
            key=lambda r: (int(r.get("theme_relevance", 0)), as_float(r.get("quality_score"), 0.0)),
            reverse=True,
        )[:25],
        "horizon_plan": horizon,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    theme_slug = slugify(theme)
    out_json = REPORTS_DIR / f"market_theme_{theme_slug}_{stamp}.json"
    out_md = REPORTS_DIR / f"market_theme_{theme_slug}_{stamp}.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LATEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Market Theme Research",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- account_id: {account_id}",
        f"- theme: {theme}",
        f"- depth: {search_depth}",
        "",
        "## Top Candidates",
    ]
    for row in top_candidates[:10]:
        lines.append(
            f"- {row.get('symbol')}: stance={row.get('stance')} score={row.get('composite_score')} "
            f"conf={row.get('confidence')} price=${row.get('price')} 5d={row.get('return_5d_pct')}% 21d={row.get('return_21d_pct')}%"
        )
    lines.extend(["", "## 1D / 1W / 1M Plan"])
    lines.append("- 1 day:")
    lines.extend([f"  - {x}" for x in horizon.get("one_day", [])])
    lines.append("- 1 week:")
    lines.extend([f"  - {x}" for x in horizon.get("one_week", [])])
    lines.append("- 1 month:")
    lines.extend([f"  - {x}" for x in horizon.get("one_month", [])])
    lines.extend(["", "## Top Leads"])
    for row in payload["top_leads"][:12]:
        lines.append(
            f"- [{row.get('signal_label')}|q={row.get('quality_score')}] {row.get('title')} ({row.get('source_name')})"
        )
        lines.append(f"  {row.get('url')}")
    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Market theme report generated: {out_json}")


if __name__ == "__main__":
    main()
