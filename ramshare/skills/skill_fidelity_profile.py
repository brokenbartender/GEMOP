from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
EVIDENCE_DIR = REPO_ROOT / "ramshare" / "evidence"
REPORTS_DIR = EVIDENCE_DIR / "reports"
STRATEGY_DIR = REPO_ROOT / "ramshare" / "strategy"
SNAPSHOT_PATH = EVIDENCE_DIR / "portfolio_snapshot.json"

FUND_LIKE_SYMBOLS = {
    "FXAIX",
    "SCHD",
    "SPY",
    "VOO",
    "IVV",
    "QQQ",
    "VTI",
    "IWM",
}

POSITIVE_WORDS = (
    "beat",
    "raise",
    "growth",
    "upgrade",
    "record",
    "strong",
    "bullish",
    "buyback",
    "dividend increase",
)

NEGATIVE_WORDS = (
    "miss",
    "cut",
    "downgrade",
    "lawsuit",
    "probe",
    "ban",
    "export restriction",
    "weak",
    "bearish",
    "recall",
)

CATALYST_WORDS = (
    "earnings",
    "guidance",
    "cpi",
    "fomc",
    "fed",
    "inflation",
    "jobs report",
    "pce",
)

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
)

MEDIUM_TRUST_SOURCES = (
    "yahoo finance",
    "investopedia",
    "seeking alpha",
    "barron's",
    "morningstar",
    "nasdaq",
    "fidelity",
)

LOW_TRUST_SOURCES = (
    "longforecast",
    "coincodex",
    "30rates",
    "catacal",
    "tipranks",
)


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


def parse_account_value_from_text(blob: str) -> float:
    if not blob:
        return 0.0
    m = re.search(r"account\s+value[^0-9$-]*\$?\s*([0-9][0-9,]*\.?[0-9]*)", blob, re.IGNORECASE)
    if not m:
        return 0.0
    return as_float(m.group(1), 0.0)


def parse_positions_from_text(blob: str) -> List[Dict[str, Any]]:
    if not blob:
        return []
    out: List[Dict[str, Any]] = []
    for raw in blob.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"\([^)]*\)", " ", line)
        m = re.match(r"^([A-Z]{1,6})\b", line)
        if not m:
            continue
        symbol = m.group(1).upper().strip()
        if symbol in {"CASH", "HELD", "SYMBOL"}:
            continue
        before_first_price = line.split("$", 1)[0]
        qty_candidates = re.findall(r"-?[0-9][0-9,]*\.?[0-9]*", before_first_price)
        qty = as_float(qty_candidates[-1], 0.0) if qty_candidates else 0.0

        dollars = re.findall(r"\$([0-9][0-9,]*\.?[0-9]*)", line)
        dvals = [as_float(v, 0.0) for v in dollars]
        price = dvals[0] if len(dvals) >= 1 else 0.0
        cost_basis = dvals[1] if len(dvals) >= 2 else 0.0
        current_value = dvals[2] if len(dvals) >= 3 else (qty * price if qty > 0 and price > 0 else 0.0)
        if qty <= 0 and current_value <= 0:
            continue
        out.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "price": price,
                "cost_basis": cost_basis,
                "current_value": current_value,
            }
        )
    return out


def normalize_positions(inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = inputs.get("positions") if isinstance(inputs.get("positions"), list) else []
    out: List[Dict[str, Any]] = []

    if not rows:
        raw_text = str(inputs.get("positions_text") or inputs.get("raw_text") or "").strip()
        if raw_text:
            rows = parse_positions_from_text(raw_text)

    if not rows:
        snap = load_json(SNAPSHOT_PATH, {})
        if isinstance(snap.get("positions"), list):
            rows = snap.get("positions") or []

    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        qty = as_float(row.get("quantity"), 0.0)
        price = as_float(row.get("price"), 0.0)
        current_value = as_float(row.get("current_value"), 0.0)
        if current_value <= 0 and qty > 0 and price > 0:
            current_value = qty * price
        cost_basis = as_float(row.get("cost_basis"), 0.0)
        if cost_basis <= 0 and qty > 0:
            cb_price = as_float(row.get("cost_basis_price"), 0.0)
            if cb_price > 0:
                cost_basis = qty * cb_price
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0
        out.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "price": price,
                "current_value": round(current_value, 2),
                "cost_basis": round(cost_basis, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "is_fund_like": symbol in FUND_LIKE_SYMBOLS,
            }
        )
    return out


def score_lead(title: str) -> Dict[str, Any]:
    t = (title or "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    catalyst = sum(1 for w in CATALYST_WORDS if w in t)
    score = pos - neg + catalyst
    if score >= 2:
        label = "positive_catalyst"
    elif score <= -1:
        label = "negative_risk"
    else:
        label = "neutral_watch"
    return {"score": score, "label": label}


def classify_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("fomc", "fed", "cpi", "pce", "jobs", "inflation", "treasury", "yield", "s&p", "nasdaq", "dow", "sp500")):
        return "macro"
    return "symbol"


def extract_source_name(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def source_trust_score(source_name: str) -> int:
    s = source_name.lower()
    if not s:
        return 0
    if any(k in s for k in LOW_TRUST_SOURCES):
        return -2
    if any(k in s for k in HIGH_TRUST_SOURCES):
        return 3
    if any(k in s for k in MEDIUM_TRUST_SOURCES):
        return 1
    return 0


def parse_pubdate(pub: str) -> dt.datetime | None:
    if not pub:
        return None
    try:
        v = parsedate_to_datetime(pub)
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def recency_score(published: dt.datetime | None, as_of: dt.datetime) -> Tuple[int, int]:
    if not published:
        return (-1, 10_000)
    age = (as_of - published.astimezone(as_of.tzinfo or dt.timezone.utc)).days
    if age <= 1:
        return (3, age)
    if age <= 3:
        return (2, age)
    if age <= 7:
        return (1, age)
    if age <= 30:
        return (0, age)
    if age <= 90:
        return (-1, age)
    return (-2, age)


def fetch_google_news(query: str, max_items: int = 5, timeout_s: int = 12) -> Tuple[List[Dict[str, Any]], str | None]:
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": "gemini-op-fidelity-profile/1.0"})
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
    query_type = classify_query(query)
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        s = score_lead(title)
        source_name = extract_source_name(title)
        out.append(
            {
                "query": query,
                "query_type": query_type,
                "title": title,
                "url": link,
                "source_name": source_name,
                "published": pub,
                "signal_score": s["score"],
                "signal_label": s["label"],
            }
        )
        if len(out) >= max_items:
            break
    return (out, None)


def build_queries(symbols: List[str], depth: str = "deep") -> List[str]:
    qs: List[str] = []
    deep = depth.lower() == "deep"
    for s in symbols[:5]:
        qs.append(f"{s} stock earnings guidance next two weeks")
        qs.append(f"{s} analyst upgrade downgrade")
        qs.append(f"{s} earnings date conference call")
        qs.append(f"{s} sec filing 8-k")
        if deep:
            qs.append(f"{s} export restriction supply chain risk")
            qs.append(f"{s} options implied move")
    qs.append("Federal Reserve FOMC schedule rate decision")
    qs.append("US CPI inflation release date")
    qs.append("US jobs report release date")
    qs.append("US PCE inflation release date")
    qs.append("US Treasury yield market reaction")
    if deep:
        qs.append("S&P 500 macro catalysts this week")
        qs.append("Nasdaq market breadth risk on risk-off day")
    seen = set()
    out: List[str] = []
    for q in qs:
        if q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out


def is_stale_lead(query_type: str, age_days: int, symbol_max_age_days: int, macro_max_age_days: int) -> bool:
    if age_days < 0:
        return False
    if query_type == "macro":
        return age_days > macro_max_age_days
    return age_days > symbol_max_age_days


def enrich_and_filter_leads(
    leads: List[Dict[str, Any]],
    as_of: dt.datetime,
    symbol_max_age_days: int,
    macro_max_age_days: int,
    max_total: int,
    min_source_trust_score: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    diagnostics = {
        "input_count": len(leads),
        "dropped_stale_count": 0,
        "dropped_duplicate_count": 0,
        "dropped_low_quality_count": 0,
        "dropped_irrelevant_symbol_count": 0,
        "dropped_low_trust_source_count": 0,
    }
    enriched: List[Dict[str, Any]] = []
    for row in leads:
        pub = parse_pubdate(str(row.get("published") or ""))
        rec_score, age_days = recency_score(pub, as_of)
        src = str(row.get("source_name") or "")
        src_score = source_trust_score(src)
        quality_score = int(row.get("signal_score", 0)) * 2 + src_score + rec_score
        query_type = str(row.get("query_type") or "symbol")
        query = str(row.get("query") or "")
        title_upper = str(row.get("title") or "").upper()
        query_symbol = query.split(" ", 1)[0].upper().strip()
        if query_type == "symbol" and query_symbol and query_symbol.isalnum():
            # Reject unrelated symbol headlines (common RSS bleed-through noise).
            if query_symbol not in title_upper:
                diagnostics["dropped_irrelevant_symbol_count"] += 1
                continue
        if src_score < min_source_trust_score:
            diagnostics["dropped_low_trust_source_count"] += 1
            continue
        if src_score <= -2 and query_type == "symbol":
            diagnostics["dropped_low_quality_count"] += 1
            continue
        if is_stale_lead(query_type, age_days, symbol_max_age_days, macro_max_age_days):
            diagnostics["dropped_stale_count"] += 1
            continue
        if quality_score <= -4:
            diagnostics["dropped_low_quality_count"] += 1
            continue
        row = dict(row)
        row["age_days"] = age_days
        row["source_trust_score"] = src_score
        row["recency_score"] = rec_score
        row["quality_score"] = quality_score
        enriched.append(row)

    dedup: Dict[str, Dict[str, Any]] = {}
    for row in enriched:
        key = str(row.get("url") or "").strip()
        if not key:
            key = f"{row.get('title','')}::{row.get('source_name','')}"
        if key in dedup:
            diagnostics["dropped_duplicate_count"] += 1
            if int(row.get("quality_score", 0)) > int(dedup[key].get("quality_score", 0)):
                dedup[key] = row
            continue
        dedup[key] = row

    ranked = sorted(
        dedup.values(),
        key=lambda r: (int(r.get("quality_score", 0)), -int(r.get("age_days", 10_000))),
        reverse=True,
    )[:max_total]
    return (ranked, diagnostics)


def build_event_watchlist(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rules = [
        ("fomc|federal reserve|powell", "fed_policy"),
        ("cpi|inflation", "inflation_cpi"),
        ("jobs report|nonfarm|unemployment", "labor_jobs"),
        ("pce", "inflation_pce"),
        ("earnings|guidance", "earnings"),
        ("yield|treasury", "rates"),
    ]
    events: List[Dict[str, Any]] = []
    seen = set()
    for row in leads:
        title = str(row.get("title") or "").lower()
        event_type = ""
        for pat, evt in rules:
            if re.search(pat, title):
                event_type = evt
                break
        if not event_type:
            continue
        dedupe_key = f"{event_type}:{row.get('title','')}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        impact = int(row.get("quality_score", 0)) + int(row.get("signal_score", 0))
        events.append(
            {
                "event_type": event_type,
                "title": row.get("title"),
                "source_name": row.get("source_name"),
                "published": row.get("published"),
                "impact_score": impact,
            }
        )
    return sorted(events, key=lambda e: int(e.get("impact_score", 0)), reverse=True)[:12]


def concentration_metrics(positions: List[Dict[str, Any]], account_value: float) -> Dict[str, Any]:
    if account_value <= 0:
        account_value = sum(as_float(p.get("current_value"), 0.0) for p in positions)
    weights = []
    top_symbol = ""
    top_weight = 0.0
    single_name_weight = 0.0
    for p in positions:
        value = as_float(p.get("current_value"), 0.0)
        w = (value / account_value) if account_value > 0 else 0.0
        weights.append(w)
        if w > top_weight:
            top_weight = w
            top_symbol = str(p.get("symbol"))
        if not bool(p.get("is_fund_like")):
            single_name_weight += w
    hhi = sum(w * w for w in weights)
    return {
        "account_value": round(account_value, 2),
        "top_symbol": top_symbol,
        "top_weight_pct": round(top_weight * 100.0, 2),
        "single_name_weight_pct": round(single_name_weight * 100.0, 2),
        "hhi": round(hhi, 4),
    }


def build_recommendations(
    metrics: Dict[str, Any],
    positions: List[Dict[str, Any]],
    lead_summary: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> List[str]:
    recs: List[str] = []
    recs.append("No strategy can guarantee short-term profit; use risk-capped position sizing and hard exits.")

    if as_float(metrics.get("single_name_weight_pct"), 0.0) > 30:
        recs.append("Reduce single-stock exposure toward 20-30% of account to lower gap-risk concentration.")
    if as_float(metrics.get("top_weight_pct"), 0.0) > 65:
        recs.append("Your top holding dominates the account; consider a 5-10% cash buffer for opportunistic entries.")

    pos_count = int(lead_summary.get("positive_catalyst_count", 0))
    neg_count = int(lead_summary.get("negative_risk_count", 0))
    if neg_count > pos_count:
        recs.append("Lead flow is risk-heavy; prioritize capital preservation and wait for confirmed upside catalysts.")
    elif pos_count > neg_count:
        recs.append("Lead flow is catalyst-positive; use staggered entries and avoid chasing one-day spikes.")
    else:
        recs.append("Lead flow is mixed; trade smaller size until directional edge improves.")

    if positions:
        recs.append("Use 1-2% max account risk per trade and pre-define stop/target before each order.")
    if int(lead_summary.get("high_trust_count", 0)) < 4:
        recs.append("High-trust lead coverage is thin; cut size and require confirmation from primary sources before acting.")
    if int(diagnostics.get("fetch_failures_count", 0)) > 0:
        recs.append("Some lead queries failed; rerun profile before placing larger orders.")
    return recs


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a short-term fidelity profile from positions + online leads.")
    ap.add_argument("job_file", help="Path to fidelity_profile job json")
    args = ap.parse_args()

    job_path = Path(args.job_file).resolve()
    job = load_json(job_path, {})
    job_id = str(job.get("id") or job_path.stem)
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}

    account_id = str(inputs.get("account_id") or "unknown").strip()
    raw_blob = str(inputs.get("positions_text") or inputs.get("raw_text") or "")
    account_value = as_float(inputs.get("account_value"), 0.0)
    if account_value <= 0:
        account_value = parse_account_value_from_text(raw_blob)
    positions = normalize_positions(inputs)
    if not positions:
        raise SystemExit("No positions provided and no portfolio snapshot available.")

    metrics = concentration_metrics(positions, account_value)

    search_depth = str(inputs.get("search_depth") or "deep").lower().strip()
    if search_depth not in {"standard", "deep"}:
        search_depth = "deep"
    max_leads = int(inputs.get("max_leads", 40))
    max_items_per_query = int(inputs.get("max_items_per_query", 5))
    symbol_max_age_days = int(inputs.get("symbol_max_age_days", 21))
    macro_max_age_days = int(inputs.get("macro_max_age_days", 60))
    timeout_s = int(inputs.get("timeout_s", 12))
    min_source_trust_score = int(inputs.get("min_source_trust_score", 0))
    as_of = dt.datetime.now().astimezone()

    offline = bool(inputs.get("offline", False))
    symbols = [str(p.get("symbol")) for p in positions if str(p.get("symbol"))]
    leads: List[Dict[str, Any]] = []
    fetch_failures: List[str] = []
    if not offline:
        for q in build_queries(symbols, depth=search_depth):
            items, err = fetch_google_news(q, max_items=max_items_per_query, timeout_s=timeout_s)
            leads.extend(items)
            if err:
                fetch_failures.append(err)

    leads, filter_diag = enrich_and_filter_leads(
        leads=leads,
        as_of=as_of,
        symbol_max_age_days=symbol_max_age_days,
        macro_max_age_days=macro_max_age_days,
        max_total=max_leads,
        min_source_trust_score=min_source_trust_score,
    )

    positive = sum(1 for x in leads if str(x.get("signal_label")) == "positive_catalyst")
    negative = sum(1 for x in leads if str(x.get("signal_label")) == "negative_risk")
    neutral = sum(1 for x in leads if str(x.get("signal_label")) == "neutral_watch")
    high_trust = sum(1 for x in leads if int(x.get("source_trust_score", 0)) >= 2)
    high_quality = sum(1 for x in leads if int(x.get("quality_score", 0)) >= 4)
    lead_summary = {
        "lead_count": len(leads),
        "positive_catalyst_count": positive,
        "negative_risk_count": negative,
        "neutral_watch_count": neutral,
        "high_trust_count": high_trust,
        "high_quality_count": high_quality,
    }

    diagnostics = {
        "search_depth": search_depth,
        "query_count": len(build_queries(symbols, depth=search_depth)),
        "fetch_failures_count": len(fetch_failures),
        "fetch_failures": fetch_failures[:20],
    }
    diagnostics.update(filter_diag)

    recommendations = build_recommendations(metrics, positions, lead_summary, diagnostics)
    action_plan_10d = [
        "Day 1-2: Build event watchlist (earnings, Fed, CPI, jobs report) and tag each position by catalyst proximity.",
        "Day 1-10: Only enter with predefined stop and target; skip trades without >= 2:1 reward:risk.",
        "Day 3-10: If a headline materially changes thesis, cut losers quickly and rotate into highest-quality catalyst setup.",
        "Daily close: Log PnL by symbol and compare realized edge vs lead quality; reduce size when edge decays.",
    ]
    event_watchlist = build_event_watchlist(leads)

    payload = {
        "job_id": job_id,
        "generated_at": now_iso(),
        "account_id": account_id,
        "objective": "Short-term tactical growth with capped downside risk",
        "constraints": {
            "capital_preservation_first": True,
            "no_guaranteed_profit_claims": True,
            "max_risk_per_trade_pct": 2.0,
        },
        "portfolio": {
            "metrics": metrics,
            "positions": positions,
        },
        "lead_summary": lead_summary,
        "research_diagnostics": diagnostics,
        "event_watchlist": event_watchlist,
        "online_leads": leads,
        "recommendations": recommendations,
        "action_plan_10d": action_plan_10d,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    safe_account = re.sub(r"[^A-Za-z0-9]+", "_", account_id).strip("_") or "acct"
    stamp = now_stamp()
    json_out = REPORTS_DIR / f"fidelity_profile_{safe_account}_{stamp}.json"
    md_out = REPORTS_DIR / f"fidelity_profile_{safe_account}_{stamp}.md"
    latest_out = STRATEGY_DIR / "fidelity_profile_latest.json"

    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Fidelity Short-Term Profile",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- account_id: {account_id}",
        f"- objective: {payload['objective']}",
        "",
        "## Portfolio Snapshot",
        f"- account_value: ${metrics['account_value']:.2f}",
        f"- top_symbol: {metrics['top_symbol']} ({metrics['top_weight_pct']:.2f}%)",
        f"- single_name_weight: {metrics['single_name_weight_pct']:.2f}%",
        f"- concentration_hhi: {metrics['hhi']:.4f}",
        "",
        "## Lead Summary",
        f"- leads: {lead_summary['lead_count']}",
        f"- positive_catalyst: {lead_summary['positive_catalyst_count']}",
        f"- negative_risk: {lead_summary['negative_risk_count']}",
        f"- neutral_watch: {lead_summary['neutral_watch_count']}",
        f"- high_trust: {lead_summary['high_trust_count']}",
        f"- high_quality: {lead_summary['high_quality_count']}",
        "",
        "## Event Watchlist",
    ]
    for event in event_watchlist[:8]:
        lines.append(
            f"- [{event.get('event_type')}] {event.get('title')} ({event.get('published')})"
        )
    lines.extend(
        [
            "",
            "## Research Diagnostics",
            f"- query_count: {diagnostics.get('query_count')}",
            f"- fetch_failures: {diagnostics.get('fetch_failures_count')}",
            f"- dropped_stale: {diagnostics.get('dropped_stale_count')}",
            f"- dropped_duplicate: {diagnostics.get('dropped_duplicate_count')}",
            f"- dropped_low_quality: {diagnostics.get('dropped_low_quality_count')}",
            "",
            "## Recommendations",
        ]
    )
    lines.extend([f"- {r}" for r in recommendations])
    lines.extend(["", "## 10-Day Action Plan"])
    lines.extend([f"- {r}" for r in action_plan_10d])
    lines.extend(["", "## Top Leads"])
    for row in leads[:10]:
        lines.append(
            f"- [{row.get('signal_label')}|q={row.get('quality_score')}] {row.get('title')} ({row.get('published')})"
        )
    md_out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Fidelity profile generated: {json_out}")


if __name__ == "__main__":
    main()
