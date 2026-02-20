from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set
from urllib.parse import unquote, urljoin, urlparse


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
SHOP_PROFILE_PATH = REPO_ROOT / "data" / "redbubble" / "shop_profile.json"
SEED_CATALOG_PATH = REPO_ROOT / "data" / "redbubble" / "shop_catalog_seed.json"
OUT_CATALOG_PATH = REPO_ROOT / "data" / "redbubble" / "shop_catalog_cache.json"
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
PROCESSED_DIR = REPO_ROOT / "ramshare" / "evidence" / "processed"
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"
PACKETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "upload_packets"
DEFAULT_SHOP_URL = "https://www.redbubble.com/people/BrokenArrowMI/shop?asc=u"


def normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def title_case_from_slug(text: str) -> str:
    tokens = [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 2]
    if not tokens:
        return ""
    return " ".join(t.capitalize() for t in tokens)


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for item in items:
        s = " ".join(str(item).split()).strip()
        if not s:
            continue
        k = normalize_text(s)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def load_json(path: Path, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback or {}


def infer_shop_url() -> str:
    profile = load_json(SHOP_PROFILE_PATH, fallback={})
    shop = profile.get("shop") if isinstance(profile.get("shop"), dict) else {}
    handle = str(shop.get("handle") or "").strip()
    if handle:
        return f"https://www.redbubble.com/people/{handle}/shop?asc=u"
    return DEFAULT_SHOP_URL


def collect_titles_from_local() -> List[str]:
    titles: List[str] = []
    for p in sorted(STAGING_DIR.glob("listing_*.json")):
        obj = load_json(p, fallback={})
        t = str(obj.get("title") or "").strip()
        if t:
            titles.append(t)
    for p in sorted(PROCESSED_DIR.glob("listing_*.json")):
        obj = load_json(p, fallback={})
        t = str(obj.get("title") or "").strip()
        if t:
            titles.append(t)
    for p in sorted(PACKETS_DIR.glob("**/upload_manifest.json")):
        obj = load_json(p, fallback={})
        t = str(obj.get("title") or "").strip()
        if t:
            titles.append(t)
    for p in sorted(POSTED_DIR.glob("live_*.json")):
        rec = load_json(p, fallback={})
        source_listing = Path(str(rec.get("source_listing_path") or "").strip())
        if source_listing.exists():
            lst = load_json(source_listing, fallback={})
            t = str(lst.get("title") or "").strip()
            if t:
                titles.append(t)
    seed = load_json(SEED_CATALOG_PATH, fallback={})
    seed_titles = seed.get("titles") if isinstance(seed.get("titles"), list) else []
    for t in seed_titles:
        if isinstance(t, str) and t.strip():
            titles.append(t.strip())
    return dedupe_keep_order(titles)


def parse_redbubble_title_from_href(href: str) -> str:
    full = href
    try:
        parsed = urlparse(href)
        full = parsed.path or href
    except Exception:
        pass
    m = re.search(r"/i/[^/]+/([^/?#]+)/\d+", full)
    if not m:
        return ""
    slug = unquote(m.group(1))
    return title_case_from_slug(slug)


def scan_live_redbubble_titles(shop_url: str, max_items: int = 240) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        return {"status": "error", "error": f"playwright_unavailable: {e}", "titles": []}

    titles: List[str] = []
    href_titles: List[str] = []
    blocked_reason = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(shop_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5500)
            title = (page.title() or "").strip()
            html = page.content()
            if "just a moment" in title.lower() or "security verification" in html.lower():
                blocked_reason = "cloudflare_challenge"
            link_nodes = page.query_selector_all("a[href*='/i/']")[:max_items]
            for node in link_nodes:
                href = str(node.get_attribute("href") or "").strip()
                txt = str(node.inner_text() or "").strip()
                if txt and len(normalize_text(txt).split()) >= 2:
                    titles.append(txt)
                if href:
                    full = urljoin(shop_url, href)
                    t = parse_redbubble_title_from_href(full)
                    if t:
                        href_titles.append(t)
            for href in re.findall(r'href="([^"]+)"', html):
                if "/i/" not in href:
                    continue
                t = parse_redbubble_title_from_href(urljoin(shop_url, href))
                if t:
                    href_titles.append(t)
        finally:
            browser.close()
    combined = dedupe_keep_order(titles + href_titles)
    if blocked_reason and not combined:
        return {"status": "blocked", "error": blocked_reason, "titles": []}
    return {"status": "ok", "error": "", "titles": combined}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Redbubble shop catalog cache for duplicate prevention.")
    ap.add_argument("--shop-url", default="")
    ap.add_argument("--out", default=str(OUT_CATALOG_PATH))
    ap.add_argument("--max-items", type=int, default=240)
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args()

    shop_url = str(args.shop_url).strip() or infer_shop_url()
    local_titles = collect_titles_from_local()
    live = {"status": "skipped", "error": "", "titles": []}
    if not bool(args.no_live):
        live = scan_live_redbubble_titles(shop_url=shop_url, max_items=max(40, int(args.max_items)))

    merged = dedupe_keep_order(local_titles + list(live.get("titles") or []))
    payload: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "shop_url": shop_url,
        "live_scan": {
            "status": str(live.get("status") or "unknown"),
            "error": str(live.get("error") or ""),
            "count": len(list(live.get("titles") or [])),
        },
        "local_count": len(local_titles),
        "total_count": len(merged),
        "titles": merged,
    }
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "catalog_path": str(out), "total_count": len(merged), "live_scan": payload["live_scan"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
