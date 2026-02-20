import argparse
import datetime as dt
import email.utils
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
STRATEGY_PATH = REPO_ROOT / "ramshare" / "state" / "strategy.json"
KNOWN_MI_SPOTS = [
    "Mackinac Island",
    "Sleeping Bear Dunes",
    "Pictured Rocks",
    "Tahquamenon Falls",
    "Traverse City",
    "Grand Rapids",
    "Ann Arbor",
    "Detroit Riverwalk",
    "Isle Royale",
    "Saugatuck",
]
GENERIC_SPOT_TOKENS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "official",
    "guide",
    "restaurant",
    "activities",
    "your",
    "northern",
}
SOURCE_WEIGHTS = {
    "google_trends_rss": 1.1,
    "google_news_rss": 1.0,
    "google_news_site_probe": 1.05,
    "youtube_rss_search": 0.95,
    "reddit_search_json": 0.8,
    "news_pinterest_probe": 0.9,
}
TREND_TOKEN_HINTS = {
    "trend",
    "trending",
    "popular",
    "viral",
    "best",
    "top",
    "guide",
    "things to do",
    "gift",
    "etsy",
    "pinterest",
    "tiktok",
    "instagram",
    "youtube",
    "reels",
    "shorts",
    "x",
    "twitter",
    "renovation",
    "renovated",
    "reopened",
    "landmark",
    "iconic",
    "architecture",
    "aerial",
}
RELEVANCE_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "your",
    "this",
    "that",
    "from",
    "into",
    "onto",
    "around",
    "best",
    "top",
    "trend",
    "trending",
    "trendy",
    "spot",
    "spots",
    "place",
    "places",
    "2023",
    "2024",
    "2025",
    "2026",
}
TRAVEL_INTENT_TOKENS = {"travel", "trip", "visit", "destination", "roadtrip", "spots", "places", "tour", "tourism"}
TRAVEL_CONTENT_TOKENS = {
    "travel",
    "visit",
    "destination",
    "trip",
    "vacation",
    "park",
    "island",
    "dunes",
    "falls",
    "riverwalk",
    "guide",
    "itinerary",
    "beach",
    "trail",
    "camping",
}
NIGHTLIFE_INTENT_TOKENS = {"bar", "bars", "nightlife", "cocktail", "club", "brewery", "pub", "speakeasy"}
NIGHTLIFE_CONTENT_TOKENS = {
    "bar",
    "bars",
    "nightlife",
    "cocktail",
    "cocktails",
    "club",
    "clubs",
    "brewery",
    "breweries",
    "pub",
    "pubs",
    "speakeasy",
    "lounge",
    "lounges",
    "taproom",
    "music",
    "dj",
}
NIGHTLIFE_NOISE_TOKENS = {"vacation", "beach", "camping", "trail", "roadtrip", "hiking"}
HARD_NEWS_NOISE_TOKENS = {
    "arrested",
    "military",
    "war",
    "navy",
    "olympic",
    "forecast",
    "protester",
    "lawsuit",
    "shooting",
    "crime",
    "politics",
}
LOCATION_HINT_TOKENS = {
    "michigan",
    "detroit",
    "ann",
    "arbor",
    "grand",
    "rapids",
    "mackinac",
    "island",
    "dunes",
    "falls",
    "traverse",
    "saugatuck",
    "holland",
    "royale",
    "pictured",
    "rocks",
}
SOCIAL_DOMAINS = [
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "reddit.com",
]
REAL_PLACE_TOKENS = {
    "renovation",
    "renovated",
    "reopen",
    "reopened",
    "landmark",
    "iconic",
    "historic",
    "architecture",
    "building",
    "district",
    "riverwalk",
    "waterfront",
    "lighthouse",
    "bridge",
    "aerial",
    "viewpoint",
    "skyline",
}
TREND_TERM_STOPWORDS = {
    "worldatlas",
    "express",
    "thoughtful",
    "their",
    "will",
    "that",
    "next",
    "smoother",
    "timeless",
    "northern",
    "winter",
    "awesome",
    "mitten",
    "travel",
    "trendy",
    "spots",
    "spot",
    "places",
    "best",
    "top",
}


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_job(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_text(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split())


def token_set(s: str) -> set[str]:
    return {x for x in normalize_text(s).split() if x}


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in items:
        line = " ".join(str(raw).split()).strip()
        if not line:
            continue
        key = normalize_text(line)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def parse_pub_date(raw: str) -> Optional[dt.datetime]:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        return email.utils.parsedate_to_datetime(txt).astimezone()
    except Exception:
        pass
    try:
        val = dt.datetime.fromisoformat(txt.replace("Z", "+00:00"))
        if val.tzinfo is None:
            val = val.replace(tzinfo=dt.timezone.utc)
        return val.astimezone()
    except Exception:
        return None


def days_since(ts: Optional[dt.datetime], now: Optional[dt.datetime] = None) -> float:
    if ts is None:
        return 999.0
    here = (now or dt.datetime.now().astimezone())
    delta = here - ts
    return max(0.0, delta.total_seconds() / 86400.0)


def load_strategy_keywords() -> list[str]:
    if not STRATEGY_PATH.exists():
        return []
    try:
        data = json.loads(STRATEGY_PATH.read_text(encoding="utf-8-sig"))
        rules = data.get("rules") or {}
        kws = rules.get("preferred_keywords") or []
        return [k.strip() for k in kws if isinstance(k, str) and k.strip()]
    except Exception:
        return []


def load_job_keywords(job: dict) -> list[str]:
    inputs = job.get("inputs") or {}
    out: list[str] = []
    direct = inputs.get("keywords")
    if isinstance(direct, list):
        for item in direct:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    query = inputs.get("query")
    if isinstance(query, str) and query.strip():
        for token in re.split(r"[^a-zA-Z0-9]+", query):
            token = token.strip()
            if len(token) >= 3:
                out.append(token)
    return dedupe_keep_order(out)[:14]


def load_job_query(job: dict) -> str:
    inputs = job.get("inputs") or {}
    q = inputs.get("query")
    if isinstance(q, str):
        return q.strip()
    return ""


def _fetch_rss(url: str) -> ET.Element:
    req = Request(url, headers={"User-Agent": "gemini-op-trend-spotter/2.0"})
    with urlopen(req, timeout=25) as resp:
        xml_text = resp.read().decode("utf-8", errors="ignore")
    return ET.fromstring(xml_text)


def _signal_base(
    title: str,
    source: str,
    query: str,
    *,
    pub_date: Optional[str] = None,
    score: float = 0.0,
    comments: float = 0.0,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "title": " ".join(str(title).split()).strip(),
        "source": source,
        "query": query,
        "pub_date": str(pub_date or "").strip(),
        "raw_score": float(score or 0.0),
        "raw_comments": float(comments or 0.0),
    }
    if extras:
        out.update(extras)
    return out


def fetch_google_trends_us() -> List[Dict[str, Any]]:
    root = _fetch_rss("https://trends.google.com/trending/rss?geo=US")
    out: List[Dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        out.append(
            _signal_base(
                title=title,
                source="google_trends_rss",
                query="google trends us",
                pub_date=item.findtext("pubDate") or "",
            )
        )
    return out


def fetch_google_news_queries(queries: List[str], max_per_query: int = 8) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for qraw in queries[:10]:
        q = quote_plus(qraw)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        root = _fetch_rss(url)
        for item in root.findall(".//item")[:max_per_query]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            out.append(
                _signal_base(
                    title=title,
                    source="google_news_rss",
                    query=qraw,
                    pub_date=item.findtext("pubDate") or "",
                    extras={"publisher": (item.findtext("source") or "").strip()},
                )
            )
    return out


def fetch_google_news_site_probes(
    queries: List[str],
    domains: List[str],
    max_per_probe: int = 3,
    max_queries: int = 4,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    trimmed_queries = [q for q in queries if isinstance(q, str) and q.strip()][:max_queries]
    trimmed_domains = [d for d in domains if isinstance(d, str) and d.strip()][:8]
    for domain in trimmed_domains:
        for qraw in trimmed_queries:
            probe = f"site:{domain} {qraw}"
            q = quote_plus(probe)
            url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
            root = _fetch_rss(url)
            for item in root.findall(".//item")[:max_per_probe]:
                title = (item.findtext("title") or "").strip()
                if not title:
                    continue
                out.append(
                    _signal_base(
                        title=title,
                        source="google_news_site_probe",
                        query=probe,
                        pub_date=item.findtext("pubDate") or "",
                        extras={
                            "publisher": (item.findtext("source") or "").strip(),
                            "site_domain": domain,
                        },
                    )
                )
    return out


def fetch_youtube_queries(queries: List[str], max_per_query: int = 8) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for qraw in queries[:8]:
        q = quote_plus(qraw)
        url = f"https://www.youtube.com/feeds/videos.xml?search_query={q}"
        root = _fetch_rss(url)
        for entry in root.findall(f".//{atom_ns}entry")[:max_per_query]:
            title = (entry.findtext(f"{atom_ns}title") or "").strip()
            if not title:
                continue
            pub_date = (entry.findtext(f"{atom_ns}published") or "").strip()
            channel = (entry.findtext(f"{atom_ns}author/{atom_ns}name") or "").strip()
            out.append(
                _signal_base(
                    title=title,
                    source="youtube_rss_search",
                    query=qraw,
                    pub_date=pub_date,
                    extras={"channel": channel},
                )
            )
    return out


def fetch_pinterest_probe(keywords: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for kw in keywords[:4]:
        probe = f"site:pinterest.com {kw} trend"
        q = quote_plus(probe)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        root = _fetch_rss(url)
        for item in root.findall(".//item")[:4]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            out.append(
                _signal_base(
                    title=title,
                    source="news_pinterest_probe",
                    query=probe,
                    pub_date=item.findtext("pubDate") or "",
                    extras={"publisher": (item.findtext("source") or "").strip()},
                )
            )
    return out


def fetch_reddit_queries(queries: List[str], max_per_query: int = 10) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for qraw in queries[:6]:
        q = quote_plus(qraw)
        url = f"https://www.reddit.com/search.json?q={q}&sort=top&t=year&limit={max_per_query}"
        req = Request(url, headers={"User-Agent": "gemini-op-trend-spotter/2.0"})
        with urlopen(req, timeout=25) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="ignore"))
        children = (((body.get("data") or {}).get("children") or []) if isinstance(body, dict) else [])
        for node in children:
            data = node.get("data") or {}
            title = str(data.get("title") or "").strip()
            if not title:
                continue
            created_utc = data.get("created_utc")
            created_iso = ""
            if isinstance(created_utc, (int, float)):
                created_iso = dt.datetime.fromtimestamp(float(created_utc), tz=dt.timezone.utc).isoformat()
            out.append(
                _signal_base(
                    title=title,
                    source="reddit_search_json",
                    query=qraw,
                    pub_date=created_iso,
                    score=float(data.get("score") or 0.0),
                    comments=float(data.get("num_comments") or 0.0),
                    extras={"subreddit": str(data.get("subreddit") or "")},
                )
            )
    return out


def keyword_score(text: str, keywords: List[str], query: str) -> float:
    low = normalize_text(text)
    score = 0.0
    for k in keywords:
        kk = normalize_text(k)
        if not kk:
            continue
        if kk in low:
            score += 1.2 if len(kk.split()) > 1 else 0.8
    qk = normalize_text(query)
    if qk and qk in low:
        score += 1.8
    for hint in TREND_TOKEN_HINTS:
        if hint in low:
            score += 0.3
    return score


def relevance_overlap(text: str, keywords: List[str], query: str) -> float:
    anchors = set()
    for row in keywords + [query]:
        for tok in re.findall(r"[a-z0-9]+", row.lower()):
            if len(tok) < 3:
                continue
            if tok in RELEVANCE_STOPWORDS:
                continue
            anchors.add(tok)
    if not anchors:
        return 0.0
    tt = token_set(text)
    if not tt:
        return 0.0
    return float(len(tt & anchors)) / float(len(anchors))


def freshness_score(signal: Dict[str, Any]) -> float:
    pub_date = parse_pub_date(str(signal.get("pub_date") or ""))
    age_days = days_since(pub_date)
    if age_days >= 45:
        return 0.0
    # Non-linear decay keeps last 72h highly weighted.
    return max(0.0, 1.0 - (age_days / 30.0))


def engagement_score(signal: Dict[str, Any]) -> float:
    base_score = float(signal.get("raw_score") or 0.0)
    comments = float(signal.get("raw_comments") or 0.0)
    if base_score <= 0 and comments <= 0:
        return 0.0
    val = math.log10(max(1.0, base_score) + 1.0) + 0.4 * math.log10(max(1.0, comments) + 1.0)
    return min(2.2, val)


def compute_signal_score(signal: Dict[str, Any], keywords: List[str], query: str) -> float:
    title = str(signal.get("title") or "")
    src = str(signal.get("source") or "")
    src_w = SOURCE_WEIGHTS.get(src, 0.7)
    k_score = keyword_score(title, keywords=keywords, query=query)
    f_score = freshness_score(signal)
    e_score = engagement_score(signal)
    rel = relevance_overlap(title, keywords=keywords, query=query)
    intent_bonus = 0.0
    q_tokens = token_set(query)
    title_tokens = token_set(title)
    travel_intent = bool(q_tokens & TRAVEL_INTENT_TOKENS)
    nightlife_intent = bool(q_tokens & NIGHTLIFE_INTENT_TOKENS)
    if travel_intent:
        if title_tokens & TRAVEL_CONTENT_TOKENS:
            intent_bonus += 0.9
        if not (title_tokens & (TRAVEL_CONTENT_TOKENS | LOCATION_HINT_TOKENS)):
            intent_bonus -= 1.1
        if title_tokens & HARD_NEWS_NOISE_TOKENS:
            intent_bonus -= 1.6
    if nightlife_intent:
        if title_tokens & NIGHTLIFE_CONTENT_TOKENS:
            intent_bonus += 1.1
        if not (title_tokens & (NIGHTLIFE_CONTENT_TOKENS | LOCATION_HINT_TOKENS)):
            intent_bonus -= 1.2
        if title_tokens & NIGHTLIFE_NOISE_TOKENS:
            intent_bonus -= 0.9
        if title_tokens & HARD_NEWS_NOISE_TOKENS:
            intent_bonus -= 1.2
    if title_tokens & REAL_PLACE_TOKENS:
        intent_bonus += 0.35
    if title_tokens & LOCATION_HINT_TOKENS:
        intent_bonus += 0.25
    return round((src_w * 0.9) + (k_score * 0.7) + (f_score * 0.9) + (e_score * 0.5) + (rel * 1.4) + intent_bonus, 5)


def collapse_signals(signals: List[Dict[str, Any]], keywords: List[str], query: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in signals:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        key = normalize_text(title)
        if not key:
            continue
        score = compute_signal_score(row, keywords=keywords, query=query)
        if query.strip() and score < 1.25:
            continue
        row2 = dict(row)
        row2["signal_score"] = score
        slot = grouped.get(key)
        if slot is None:
            grouped[key] = {
                "title": title,
                "signal_score": score,
                "sources": [str(row.get("source") or "")],
                "queries": [str(row.get("query") or "")],
                "evidence_count": 1,
                "evidence": [row2],
            }
            continue
        slot["signal_score"] = max(float(slot.get("signal_score") or 0.0), score)
        slot["evidence_count"] = int(slot.get("evidence_count") or 0) + 1
        slot["sources"] = dedupe_keep_order(list(slot.get("sources") or []) + [str(row.get("source") or "")])
        slot["queries"] = dedupe_keep_order(list(slot.get("queries") or []) + [str(row.get("query") or "")])
        slot["evidence"] = list(slot.get("evidence") or []) + [row2]

    ranked = sorted(
        grouped.values(),
        key=lambda x: (float(x.get("signal_score") or 0.0), int(x.get("evidence_count") or 0), len(str(x.get("title") or ""))),
        reverse=True,
    )
    return ranked


def build_queries(job_query: str, keywords: List[str]) -> List[str]:
    q: List[str] = []
    if job_query:
        q.append(job_query)
        q.extend(
            [
                f"{job_query} trend 2026",
                f"{job_query} reddit",
                f"{job_query} tiktok trend",
                f"{job_query} instagram reels",
                f"{job_query} youtube shorts",
                f"{job_query} etsy",
                f"{job_query} gifts",
                f"{job_query} newly renovated",
                f"{job_query} iconic landmark",
                f"{job_query} aerial view",
            ]
        )
    if keywords:
        base = " ".join(keywords[:4])
        q.extend(
            [
                f"{base} trends 2026",
                f"{base} reddit",
                f"{base} travel trend",
                f"{base} sticker trend",
                f"{base} shirt trend",
                f"{base} newly renovated",
                f"{base} iconic landmark",
                f"{base} aerial",
            ]
        )
    low = (job_query or "").lower()
    if "michigan" in low:
        q.extend(
            [
                "trendy spots in michigan 2026",
                "best places to visit in michigan 2026",
                "michigan hidden gems 2026",
                "michigan travel trends reddit",
                "michigan destination stickers 2026",
                "michigan newly renovated building 2026",
                "michigan iconic landmark 2026",
                "michigan downtown reopening 2026",
                "michigan rooftop bar opening 2026",
                "michigan aerial landmark view",
            ]
        )
    return dedupe_keep_order(q)[:20]


def extract_michigan_spots(lines: List[str]) -> List[str]:
    out: List[str] = []
    low_map = {s.lower(): s for s in KNOWN_MI_SPOTS}
    for ln in lines:
        low = ln.lower()
        for k, canon in low_map.items():
            if k in low and canon not in out:
                out.append(canon)
        for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:Michigan|MI)\b", ln):
            spot = m.strip()
            toks = set(re.findall(r"[a-z0-9]+", spot.lower()))
            if any(t in GENERIC_SPOT_TOKENS for t in toks):
                continue
            if spot and spot not in out:
                out.append(spot)
    return out[:12]


def gather_signals(queries: List[str], keywords: List[str]) -> tuple[List[Dict[str, Any]], List[str], Dict[str, str]]:
    raw: List[Dict[str, Any]] = []
    sources: List[str] = []
    errors: Dict[str, str] = {}

    try:
        chunk = fetch_google_trends_us()
        raw.extend(chunk)
        if chunk:
            sources.append("google_trends_rss")
    except Exception as e:
        errors["google_trends_rss"] = str(e)

    if keywords:
        try:
            chunk = fetch_pinterest_probe(keywords)
            raw.extend(chunk)
            if chunk:
                sources.append("news_pinterest_probe")
        except Exception as e:
            errors["news_pinterest_probe"] = str(e)

    if queries:
        try:
            chunk = fetch_google_news_site_probes(queries=queries, domains=SOCIAL_DOMAINS)
            raw.extend(chunk)
            if chunk:
                sources.append("google_news_site_probe")
        except Exception as e:
            errors["google_news_site_probe"] = str(e)
        try:
            chunk = fetch_google_news_queries(queries)
            raw.extend(chunk)
            if chunk:
                sources.append("google_news_rss")
        except Exception as e:
            errors["google_news_rss"] = str(e)
        try:
            chunk = fetch_youtube_queries(queries)
            raw.extend(chunk)
            if chunk:
                sources.append("youtube_rss_search")
        except Exception as e:
            errors["youtube_rss_search"] = str(e)
        try:
            chunk = fetch_reddit_queries(queries)
            raw.extend(chunk)
            if chunk:
                sources.append("reddit_search_json")
        except Exception as e:
            errors["reddit_search_json"] = str(e)

    return raw, dedupe_keep_order(sources), errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Trend spotter skill (deep live web fetch)")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_job(job_path)
    job_id = str(job.get("id") or job_path.stem)

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out = INBOX_DIR / f"report_trends_{now_stamp()}.md"

    strategy_keywords = load_strategy_keywords()
    job_keywords = load_job_keywords(job)
    job_query = load_job_query(job)
    combined_keywords = dedupe_keep_order(strategy_keywords + job_keywords)[:24]
    queries = build_queries(job_query=job_query, keywords=combined_keywords)
    raw_signals, sources, errors = gather_signals(queries=queries, keywords=combined_keywords)
    if not raw_signals:
        raise SystemExit("Trend fetch failed: no live trends available from configured sources.")

    ranked = collapse_signals(raw_signals, keywords=combined_keywords, query=job_query)
    ranked = ranked[:24]
    ranked_filtered = [r for r in ranked if float(r.get("signal_score") or 0.0) >= 1.8]
    ranked_hot = ranked_filtered if ranked_filtered else ranked
    hot_trends = [str(row.get("title") or "").strip() for row in ranked_hot[:12] if str(row.get("title") or "").strip()]
    source_breakdown: Dict[str, int] = {}
    social_hits: List[Dict[str, Any]] = []
    social_sources = {"google_news_site_probe", "youtube_rss_search", "reddit_search_json", "news_pinterest_probe"}
    for row in ranked[:16]:
        src = str((row.get("sources") or ["unknown"])[0] if isinstance(row.get("sources"), list) else "unknown")
        source_breakdown[src] = int(source_breakdown.get(src) or 0) + 1
        row_sources = row.get("sources") if isinstance(row.get("sources"), list) else []
        if any(str(s) in social_sources for s in row_sources):
            social_hits.append(
                {
                    "title": str(row.get("title") or ""),
                    "signal_score": float(row.get("signal_score") or 0.0),
                    "sources": row_sources,
                }
            )

    mi_spots: List[str] = []
    if "michigan" in (job_query or "").lower():
        mi_spots = extract_michigan_spots(hot_trends)

    lines = [
        "# Trend Spotter Report (Live)",
        "",
        f"job_id: {job_id}",
        f"generated_at: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"query: {job_query or 'none'}",
        f"strategy_keywords: {', '.join(strategy_keywords) if strategy_keywords else 'none'}",
        f"job_keywords: {', '.join(job_keywords) if job_keywords else 'none'}",
        f"sources: {', '.join(sources) if sources else 'none'}",
        "",
        "## Hot Trends",
    ]
    for row in ranked_hot[:12]:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        lines.append(
            f"- {title} (signal={float(row.get('signal_score') or 0.0):.2f}; evidence={int(row.get('evidence_count') or 0)})"
        )

    lines.extend(["", "## Query Set"])
    lines.extend([f"- {q}" for q in queries[:12]])

    if mi_spots:
        lines.extend(["", "## Michigan Spot Leads"])
        lines.extend([f"- {s}" for s in mi_spots])
    if errors:
        lines.extend(["", "## Fetch Notes"])
        for k, v in errors.items():
            lines.append(f"- {k}: {v}")

    out.write_text("\n".join(lines), encoding="utf-8")
    json_out = out.with_suffix(".json")
    payload: Dict[str, object] = {
        "job_id": job_id,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "query": job_query,
        "strategy_keywords": strategy_keywords,
        "job_keywords": job_keywords,
        "sources": sources,
        "queries": queries,
        "errors": errors,
        "hot_trends": hot_trends,
        "ranked_trends": ranked[:16],
        "social_hits": social_hits[:16],
        "source_breakdown": source_breakdown,
        "signal_count": len(raw_signals),
        "michigan_spot_leads": mi_spots,
    }
    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Trend analysis complete")


if __name__ == "__main__":
    main()
