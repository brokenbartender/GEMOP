import argparse
import datetime as dt
import json
from pathlib import Path
from typing import List
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
STRATEGY_PATH = REPO_ROOT / "ramshare" / "state" / "strategy.json"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_job(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_strategy_keywords() -> list[str]:
    if not STRATEGY_PATH.exists():
        return []
    try:
        data = json.loads(STRATEGY_PATH.read_text(encoding="utf-8-sig"))
        rules = data.get("rules") or {}
        kws = rules.get("preferred_keywords") or []
        return [k for k in kws if isinstance(k, str) and k.strip()]
    except Exception:
        return []


def fetch_google_trends_us() -> List[str]:
    req = Request(
        "https://trends.google.com/trending/rss?geo=US",
        headers={"User-Agent": "gemini-op-trend-spotter/1.0"},
    )
    with urlopen(req, timeout=20) as resp:
        xml_text = resp.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_text)
    out: List[str] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if title:
            out.append(title)
    return out


def fetch_pinterest_like_queries(keywords: List[str]) -> List[str]:
    """
    Lightweight web pull via search RSS for strategy keywords.
    """
    out: List[str] = []
    for kw in keywords[:3]:
        q = quote_plus(f"site:pinterest.com trends {kw}")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        req = Request(url, headers={"User-Agent": "gemini-op-trend-spotter/1.0"})
        with urlopen(req, timeout=20) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[:3]:
            title = (item.findtext("title") or "").strip()
            if title:
                out.append(title)
    return out


def rank_trends(raw_trends: List[str], keywords: List[str], limit: int = 8) -> List[str]:
    if not raw_trends:
        return []
    kws = [k.lower() for k in keywords if k.strip()]

    def score(text: str) -> int:
        low = text.lower()
        return sum(3 for k in kws if k in low)

    seen = set()
    deduped: List[str] = []
    for t in raw_trends:
        key = t.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(t.strip())

    ranked = sorted(deduped, key=lambda t: (score(t), len(t)), reverse=True)
    return ranked[:limit]


def main() -> None:
    ap = argparse.ArgumentParser(description="Trend spotter skill (live web fetch)")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_job(job_path)
    job_id = str(job.get("id") or job_path.stem)

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out = INBOX_DIR / f"report_trends_{now_stamp()}.md"

    strategy_keywords = load_strategy_keywords()
    live_trends: List[str] = []
    sources: List[str] = []

    try:
        live_trends.extend(fetch_google_trends_us())
        sources.append("Google Trends US RSS")
    except Exception:
        pass

    if strategy_keywords:
        try:
            live_trends.extend(fetch_pinterest_like_queries(strategy_keywords))
            sources.append("Google News RSS (Pinterest keyword search)")
        except Exception:
            pass

    trends = rank_trends(live_trends, strategy_keywords, limit=8)
    if not trends:
        raise SystemExit("Trend fetch failed: no live trends available from configured sources.")

    lines = [
        "# Trend Spotter Report (Live)",
        "",
        f"- job_id: {job_id}",
        f"- generated_at: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- strategy_keywords: {', '.join(strategy_keywords) if strategy_keywords else 'none'}",
        f"- sources: {', '.join(sources) if sources else 'none'}",
        "",
        "## Hot Trends",
    ]
    lines.extend([f"- {t}" for t in trends])
    lines.extend([
        "",
        "## Notes",
        "- Live web-derived trend report.",
    ])

    out.write_text("\n".join(lines), encoding="utf-8")
    print("Trend analysis complete")


if __name__ == "__main__":
    main()
