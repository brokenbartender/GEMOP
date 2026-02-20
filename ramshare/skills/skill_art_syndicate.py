from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import quote, quote_plus, unquote_plus
from urllib.request import Request, urlopen


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
DRAFTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "drafts"
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
REJECTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "rejected"
SKILLS_DIR = REPO_ROOT / "ramshare" / "skills"
SCRIPTS_DIR = REPO_ROOT / "scripts"
IP_TERMS_PATH = REPO_ROOT / "data" / "redbubble" / "ip_risk_terms.txt"
STYLE_PROFILE_PATH = REPO_ROOT / "data" / "redbubble" / "style_profile.json"
CATALOG_CACHE_PATH = REPO_ROOT / "data" / "redbubble" / "shop_catalog_cache.json"
DEFAULT_BANNED_TERMS = ["Disney", "Marvel", "Nike", "Star Wars"]
MORAL_RISK_TERMS = ["hate", "violent", "racist", "nsfw", "explicit", "terror"]
DEFAULT_THEME = "trendy spots in michigan 2026"
SPOT_STOP = {
    "michigan",
    "trends",
    "travel",
    "guide",
    "best",
    "visit",
    "things",
    "places",
    "spot",
    "spots",
    "reddit",
    "news",
    "2026",
    "top",
    "official",
    "guide",
    "restaurant",
    "northern",
    "kids",
    "activities",
    "your",
    "visual",
}
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
    "field",
    "trips",
}
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
    "Holland",
]
TREND_TERM_STOP = {
    "worldatlas",
    "express",
    "awesome",
    "mitten",
    "thoughtful",
    "their",
    "will",
    "that",
    "next",
    "smoother",
    "timeless",
    "winter",
    "best",
    "top",
    "travel",
    "trendy",
    "spots",
    "michigan",
    "guide",
}
TREND_TERM_ALLOWED = {
    "camping",
    "beach",
    "vacation",
    "visit",
    "visiting",
    "destination",
    "destinations",
    "travel",
    "trip",
    "roadtrip",
    "road",
    "hidden",
    "gems",
    "gift",
    "gifts",
    "sticker",
    "stickers",
    "line",
    "icon",
    "minimal",
    "bars",
    "bar",
    "nightlife",
    "cocktail",
    "club",
    "brewery",
    "pub",
    "lounge",
}
TREND_TERM_LOCATION_TOKENS = {
    "mackinac",
    "island",
    "sleeping",
    "bear",
    "dunes",
    "pictured",
    "rocks",
    "tahquamenon",
    "falls",
    "traverse",
    "grand",
    "rapids",
    "annarbor",
    "detroit",
    "riverwalk",
    "royale",
    "saugatuck",
    "holland",
}
BAD_SPOT_TOKENS = {
    "timeless",
    "best",
    "top",
    "new",
    "awesome",
    "northern",
    "official",
    "guide",
    "your",
}
ARCHITECTURE_KEYWORDS = {
    "victorian",
    "art deco",
    "modernist",
    "gothic",
    "bridge",
    "lighthouse",
    "waterfront",
    "riverwalk",
    "marina",
    "downtown",
    "main street",
    "historic district",
    "facade",
    "sandstone",
    "cliffs",
    "dunes",
    "falls",
    "ferry dock",
    "boardwalk",
    "neon",
    "brewery",
    "cocktail",
    "pub",
    "speakeasy",
    "hotel",
    "theater",
    "museum",
    "library",
    "station",
    "tower",
    "hall",
    "stadium",
    "casino",
    "market",
    "square",
    "cathedral",
    "church",
    "campus",
    "harbor",
    "pier",
    "boardwalk",
}
LANDMARK_SUFFIXES = {
    "bridge",
    "tower",
    "hall",
    "hotel",
    "theater",
    "museum",
    "library",
    "station",
    "market",
    "harbor",
    "pier",
    "lighthouse",
    "brewery",
    "pub",
    "bar",
    "club",
    "district",
    "park",
}
LOCATION_SCORECARD_CATEGORIES = [
    "real_location_verified",
    "architecture_cues_present",
    "location_name_fidelity",
    "style_consistency",
    "novelty_guard",
]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def token_set(text: str) -> set[str]:
    return {x for x in normalize_text(text).split() if x}


def text_similarity(a: str, b: str) -> float:
    ta = token_set(a)
    tb = token_set(b)
    if not ta or not tb:
        return 0.0
    jac = float(len(ta & tb)) / float(len(ta | tb))
    seq = SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()
    return max(jac, seq)


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
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


def http_json(url: str, timeout: int = 20) -> Any:
    req = Request(url, headers={"User-Agent": "gemini-op-art-syndicate/2.0"})
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    return json.loads(body)


def infer_cues_from_spot_name(spot: str) -> List[str]:
    low = normalize_text(spot)
    cues: List[str] = []
    if "falls" in low:
        cues.extend(["waterfall", "forest trail"])
    if "dunes" in low:
        cues.extend(["dunes", "lakeshore"])
    if "riverwalk" in low:
        cues.extend(["riverwalk", "waterfront"])
    if "island" in low:
        cues.extend(["ferry dock", "waterfront"])
    if "city" in low or "rapids" in low or "arbor" in low:
        cues.extend(["downtown", "main street"])
    if "rocks" in low:
        cues.extend(["sandstone cliffs", "waterfront"])
    return dedupe_keep_order(cues)[:4]


def extract_architecture_cues(text: str) -> List[str]:
    low = (text or "").lower()
    out: List[str] = []
    for kw in ARCHITECTURE_KEYWORDS:
        if kw in low:
            out.append(kw)
    return dedupe_keep_order(out)[:8]


def geojson_shape_stats(geojson_obj: Any) -> Dict[str, Any]:
    if not isinstance(geojson_obj, dict):
        return {"has_geometry_outline": False, "geometry_type": "", "geometry_point_count": 0}
    gtype = str(geojson_obj.get("type") or "")
    coords = geojson_obj.get("coordinates")
    point_count = 0

    def _walk(node: Any) -> None:
        nonlocal point_count
        if isinstance(node, list):
            if len(node) == 2 and all(isinstance(x, (int, float)) for x in node):
                point_count += 1
                return
            for child in node:
                _walk(child)

    _walk(coords)
    return {
        "has_geometry_outline": bool(gtype in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"} and point_count >= 3),
        "geometry_type": gtype,
        "geometry_point_count": int(point_count),
    }


def lookup_real_location(spot: str, query: str) -> Dict[str, Any]:
    # Nominatim provides free geocoding for "is this a real location?" checks.
    q = f"{spot}, Michigan, USA" if "michigan" in normalize_text(query) else f"{spot}, USA"
    url = (
        "https://nominatim.openstreetmap.org/search"
        f"?format=jsonv2&limit=5&polygon_geojson=1&addressdetails=1&extratags=1&namedetails=1&q={quote_plus(q)}"
    )
    try:
        rows = http_json(url)
    except Exception as e:
        return {"spot": spot, "verified": False, "error": str(e), "architecture_cues": infer_cues_from_spot_name(spot)}
    if not isinstance(rows, list) or not rows:
        return {"spot": spot, "verified": False, "architecture_cues": infer_cues_from_spot_name(spot)}

    best = None
    best_score = -1.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        disp = str(row.get("display_name") or "")
        imp = float(row.get("importance") or 0.0)
        score = imp
        dlow = disp.lower()
        if "michigan" in dlow:
            score += 0.9
        if normalize_text(spot) in normalize_text(disp):
            score += 0.7
        if score > best_score:
            best_score = score
            best = row
    if not isinstance(best, dict):
        return {"spot": spot, "verified": False, "architecture_cues": infer_cues_from_spot_name(spot)}

    title_options = [f"{spot}, Michigan", spot]
    wiki_extract = ""
    for title in title_options:
        t = quote(title.replace(" ", "_"), safe="")
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{t}"
        try:
            wiki = http_json(wiki_url, timeout=18)
        except Exception:
            continue
        if isinstance(wiki, dict) and str(wiki.get("extract") or "").strip():
            wiki_extract = str(wiki.get("extract") or "")
            break

    row_text = " ".join(
        [
            str(best.get("display_name") or ""),
            str(best.get("class") or ""),
            str(best.get("type") or ""),
            json.dumps(best.get("extratags") or {}, ensure_ascii=True),
            json.dumps(best.get("namedetails") or {}, ensure_ascii=True),
        ]
    )
    geo_stats = geojson_shape_stats(best.get("geojson"))
    cues = dedupe_keep_order(extract_architecture_cues(wiki_extract) + extract_architecture_cues(row_text) + infer_cues_from_spot_name(spot))[
        :8
    ]
    if bool(geo_stats.get("has_geometry_outline")):
        cues = dedupe_keep_order(cues + ["aerial outline", "map-accurate proportions"])[:8]
    dlow = str(best.get("display_name") or "").lower()
    verified = bool(best_score >= 0.65 and ("usa" in dlow or "united states" in dlow))
    return {
        "spot": spot,
        "verified": verified,
        "display_name": str(best.get("display_name") or ""),
        "lat": str(best.get("lat") or ""),
        "lon": str(best.get("lon") or ""),
        "class": str(best.get("class") or ""),
        "type": str(best.get("type") or ""),
        "osm_id": str(best.get("osm_id") or ""),
        "osm_type": str(best.get("osm_type") or ""),
        "importance": float(best.get("importance") or 0.0),
        "boundingbox": best.get("boundingbox") if isinstance(best.get("boundingbox"), list) else [],
        "geojson": best.get("geojson") if isinstance(best.get("geojson"), dict) else {},
        "has_geometry_outline": bool(geo_stats.get("has_geometry_outline")),
        "geometry_type": str(geo_stats.get("geometry_type") or ""),
        "geometry_point_count": int(geo_stats.get("geometry_point_count") or 0),
        "architecture_cues": cues,
        "wiki_extract": wiki_extract[:700],
    }


def build_location_briefs(spots: List[str], query: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for spot in dedupe_keep_order(spots)[:16]:
        out.append(lookup_real_location(spot, query=query))
    return out


def load_banned_terms() -> List[str]:
    if not IP_TERMS_PATH.exists():
        return list(DEFAULT_BANNED_TERMS)
    out: List[str] = []
    for raw in IP_TERMS_PATH.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out if out else list(DEFAULT_BANNED_TERMS)


def run_python(script: Path, args: List[str], env: Dict[str, str] | None = None) -> Tuple[int, str]:
    cp = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env or dict(os.environ),
    )
    out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    return cp.returncode, out


def run_skill(skill_script: Path, job_payload: Dict[str, Any], env: Dict[str, str] | None = None) -> Tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        tf.write(json.dumps(job_payload, indent=2))
        job_path = Path(tf.name)
    try:
        return run_python(skill_script, [str(job_path)], env=env)
    finally:
        try:
            job_path.unlink(missing_ok=True)
        except Exception:
            pass


def latest_new_file(folder: Path, pattern: str, before: set[str]) -> Path | None:
    if not folder.exists():
        return None
    for p in sorted(folder.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True):
        if str(p.resolve()) not in before:
            return p
    return None


def catalog_scan(shop_url: str = "") -> Dict[str, Any]:
    args = []
    if shop_url.strip():
        args.extend(["--shop-url", shop_url.strip()])
    rc, out = run_python(SCRIPTS_DIR / "rb_catalog_scan.py", args)
    if rc != 0:
        return {"ok": False, "error": out}
    try:
        payload = json.loads(out)
    except Exception:
        payload = {"ok": False, "error": out}
    payload["catalog"] = load_json(CATALOG_CACHE_PATH, fallback={})
    return payload


def _looks_like_specific_landmark(name: str) -> bool:
    norm = normalize_text(name)
    toks = norm.split()
    if not toks:
        return False
    if any(t in SPOT_STOP or t in GENERIC_SPOT_TOKENS for t in toks):
        return False
    if len(toks) == 1 and toks[0] not in TREND_TERM_LOCATION_TOKENS:
        return False
    if len(name.strip()) < 5:
        return False
    if toks[-1] in LANDMARK_SUFFIXES:
        return True
    joined = "".join(toks)
    if joined in TREND_TERM_LOCATION_TOKENS:
        return True
    if any(tok in TREND_TERM_LOCATION_TOKENS for tok in toks):
        return True
    return len(toks) >= 2 and toks[0] not in BAD_SPOT_TOKENS


def _extract_named_landmarks(line: str) -> List[str]:
    out: List[str] = []
    # Capitalized place names, allowing short connectors like "of" and "the".
    pattern = r"\b([A-Z][A-Za-z0-9'&.-]*(?:\s+(?:[A-Z][A-Za-z0-9'&.-]*|of|the|and)){0,5})\b"
    for m in re.findall(pattern, line):
        cand = " ".join(str(m).split()).strip(" ,.-")
        if not cand:
            continue
        if _looks_like_specific_landmark(cand):
            out.append(cand)
    return dedupe_keep_order(out)


def extract_spot_candidates(trend_json: Dict[str, Any]) -> List[str]:
    spots = trend_json.get("michigan_spot_leads") if isinstance(trend_json.get("michigan_spot_leads"), list) else []
    out: List[str] = []
    for s in spots:
        if not isinstance(s, str) or not s.strip():
            continue
        cand = s.strip()
        low = normalize_text(cand)
        if not low:
            continue
        toks = low.split()
        if toks and toks[0] in BAD_SPOT_TOKENS:
            continue
        if any(tok in SPOT_STOP for tok in toks):
            continue
        if any(tok in GENERIC_SPOT_TOKENS for tok in toks):
            continue
        if len(toks) == 1 and toks[0] not in TREND_TERM_LOCATION_TOKENS:
            continue
        out.append(cand)

    lines: List[str] = []
    hot = trend_json.get("hot_trends") if isinstance(trend_json.get("hot_trends"), list) else []
    lines.extend([str(x) for x in hot if isinstance(x, str)])
    ranked = trend_json.get("ranked_trends") if isinstance(trend_json.get("ranked_trends"), list) else []
    for row in ranked[:20]:
        if isinstance(row, dict):
            title = str(row.get("title") or "").strip()
            if title:
                lines.append(title)
    social_hits = trend_json.get("social_hits") if isinstance(trend_json.get("social_hits"), list) else []
    for row in social_hits[:20]:
        if isinstance(row, dict):
            title = str(row.get("title") or "").strip()
            if title:
                lines.append(title)

    for row in lines:
        if not isinstance(row, str):
            continue
        row_low = row.lower()
        has_michigan_context = "michigan" in row_low or " ann arbor" in row_low or " grand rapids" in row_low
        for spot in KNOWN_MI_SPOTS:
            if spot.lower() in row_low:
                out.append(spot)
        for cand in _extract_named_landmarks(row):
            if _looks_like_specific_landmark(cand):
                out.append(cand)
        if not has_michigan_context:
            continue
        for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*(?:,)?\s*(?:Michigan|MI)\b", row):
            low = normalize_text(m)
            if not low:
                continue
            if any(tok in SPOT_STOP for tok in low.split()):
                continue
            low_toks = low.split()
            if low_toks and low_toks[0] in BAD_SPOT_TOKENS:
                continue
            if len(low.split()) == 1 and len(low) < 6:
                continue
            if len(low_toks) == 1 and low_toks[0] not in TREND_TERM_LOCATION_TOKENS:
                continue
            if len(m) >= 4:
                out.append(m.strip())
    cleaned = []
    for s in dedupe_keep_order(out):
        toks = token_set(s)
        if not toks:
            continue
        if any(t in GENERIC_SPOT_TOKENS for t in toks):
            continue
        if len(toks) == 1 and len(next(iter(toks))) < 6:
            continue
        if not _looks_like_specific_landmark(s):
            continue
        cleaned.append(s)
    if not cleaned:
        cleaned = list(KNOWN_MI_SPOTS)
    return cleaned[:16]


def extract_trend_terms(trend_json: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    freq: Dict[str, int] = {}
    ranked = trend_json.get("ranked_trends") if isinstance(trend_json.get("ranked_trends"), list) else []
    for row in ranked[:12]:
        title = str((row or {}).get("title") or "").strip() if isinstance(row, dict) else ""
        if not title:
            continue
        for tok in re.findall(r"[a-z0-9]+", title.lower()):
            if len(tok) < 4:
                continue
            if tok in SPOT_STOP or tok in GENERIC_SPOT_TOKENS:
                continue
            if tok in TREND_TERM_STOP:
                continue
            out.append(tok)
            freq[tok] = int(freq.get(tok) or 0) + 1

    hot = trend_json.get("hot_trends") if isinstance(trend_json.get("hot_trends"), list) else []
    for row in hot[:10]:
        if not isinstance(row, str):
            continue
        for tok in re.findall(r"[a-z0-9]+", row.lower()):
            if len(tok) < 4:
                continue
            if tok in SPOT_STOP or tok in GENERIC_SPOT_TOKENS:
                continue
            if tok in TREND_TERM_STOP:
                continue
            out.append(tok)
            freq[tok] = int(freq.get(tok) or 0) + 1

    deduped = dedupe_keep_order(out)
    deduped.sort(key=lambda x: (int(freq.get(x) or 0), len(x)), reverse=True)

    filtered: List[str] = []
    for tok in deduped:
        if tok.isdigit():
            continue
        compact = tok.replace(" ", "")
        if tok in TREND_TERM_ALLOWED or compact in TREND_TERM_LOCATION_TOKENS:
            filtered.append(tok)
    if not filtered:
        filtered = deduped
    return filtered[:14]


def attempt_redbubble_best_selling_tags(query: str) -> List[str]:
    q = quote_plus(query)
    url = f"https://www.redbubble.com/shop/?query={q}&ref=search_box"
    req = Request(url, headers={"User-Agent": "gemini-op-art-syndicate/1.0"})
    try:
        with urlopen(req, timeout=18) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    tags: List[str] = []
    for m in re.findall(r"/shop/\?query=([a-zA-Z0-9%+\-]+)", html):
        decoded = unquote_plus(m)
        t = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", decoded.lower())).strip()
        if len(t) >= 3:
            tags.append(t)
    return dedupe_keep_order(tags)[:20]


def run_trend_hunter(query: str) -> Dict[str, Any]:
    before = {str(p.resolve()) for p in (REPO_ROOT / "ramshare" / "evidence" / "inbox").glob("report_trends_*.json")}
    q_tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3]
    dynamic_keywords = dedupe_keep_order(
        q_tokens
        + [
            "line art",
            "sticker",
            "landmark",
            "iconic",
            "renovated",
            "aerial",
            "architecture",
        ]
    )[:16]
    trend_job = {
        "id": f"art-syndicate-trend-{now_stamp()}",
        "task_type": "trend_spotter",
        "target_profile": "research",
        "inputs": {
            "query": query,
            "keywords": dynamic_keywords,
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    rc, out = run_skill(SKILLS_DIR / "skill_trend_spotter.py", trend_job)
    report = latest_new_file(REPO_ROOT / "ramshare" / "evidence" / "inbox", "report_trends_*.json", before=before)
    trend_json = load_json(report, fallback={}) if report else {}
    rb_tags = attempt_redbubble_best_selling_tags(query if query.strip() else "michigan travel")
    if rb_tags:
        hot = trend_json.get("hot_trends") if isinstance(trend_json.get("hot_trends"), list) else []
        trend_json["hot_trends"] = dedupe_keep_order([str(x) for x in hot] + [f"Redbubble tag: {t}" for t in rb_tags])
    return {
        "ok": rc == 0,
        "stdout": out,
        "report_path": str(report) if report else "",
        "trend_json": trend_json,
        "redbubble_tags": rb_tags,
    }


def build_concepts(location_briefs: List[Dict[str, Any]], query: str, trend_terms: List[str]) -> List[str]:
    out: List[str] = []
    qtokens = token_set(query)
    nightlife_mode = bool(qtokens & {"bar", "bars", "nightlife", "cocktail", "club", "brewery", "pub", "lounge"})
    verified = [b for b in location_briefs if bool(b.get("verified"))]
    ordered_spots = [str(b.get("spot") or "").strip() for b in verified if str(b.get("spot") or "").strip()]
    if not ordered_spots:
        ordered_spots = [str(b.get("spot") or "").strip() for b in location_briefs if str(b.get("spot") or "").strip()]
    for spot in KNOWN_MI_SPOTS:
        if spot not in ordered_spots:
            ordered_spots.append(spot)

    brief_map = {str(b.get("spot") or ""): b for b in location_briefs}
    for spot in ordered_spots[:16]:
        toks = token_set(spot)
        if any(t in GENERIC_SPOT_TOKENS for t in toks):
            continue
        brief = brief_map.get(spot, {})
        cues = brief.get("architecture_cues")
        cue_list = [str(x).strip() for x in (cues if isinstance(cues, list) else []) if str(x).strip()]
        has_geo = bool(brief.get("has_geometry_outline"))
        out.append(f"{spot} Michigan minimal line sigil")
        out.append(f"{spot} destination line icon minimal emblem")
        out.append(f"{spot} map marker monoline travel symbol")
        out.append(f"{spot} recognizable landmark faithful line drawing")
        if has_geo:
            out.append(f"{spot} aerial map-outline minimalist line art")
            out.append(f"{spot} map-accurate proportions monoline illustration")
        if nightlife_mode:
            out.append(f"{spot} nightlife venue minimalist line emblem")
            out.append(f"{spot} cocktail bar neon monoline icon")
            out.append(f"{spot} pub crawl map minimalist sigil")
        for cue in cue_list[:2]:
            out.append(f"{spot} {cue} minimalist line architecture icon")
        for term in trend_terms[:6]:
            out.append(f"{spot} {term} minimalist line graphic")
    if not out:
        out = [
            "Michigan hidden gem travel minimal line sigil",
            "Michigan roadtrip landmark monoline badge",
            "Great Lakes destination minimalist line emblem",
        ]
    query_norm = normalize_text(query)
    if "michigan" in query_norm and all("michigan" not in normalize_text(x) for x in out):
        out = [f"Michigan {x}" for x in out]
    return dedupe_keep_order(out)[:30]


def similarity_to_catalog(text: str, catalog_titles: List[str]) -> Dict[str, Any]:
    best = ""
    score = 0.0
    for t in catalog_titles:
        s = text_similarity(text, t)
        if s > score:
            score = s
            best = t
    return {"best_title": best, "score": round(score, 4)}


def choose_candidate(
    concepts: List[str],
    catalog_titles: List[str],
    used: set[str],
    *,
    query: str,
    location_brief_map: Dict[str, Dict[str, Any]],
    threshold: float = 0.75,
) -> Dict[str, Any]:
    best: Dict[str, Any] = {}
    qtokens = token_set(query)
    nightlife_mode = bool(qtokens & {"bar", "bars", "nightlife", "cocktail", "club", "brewery", "pub", "lounge"})
    nightlife_tokens = {"bar", "bars", "nightlife", "cocktail", "club", "brewery", "pub", "lounge", "taproom"}
    for c in concepts:
        key = normalize_text(c)
        if key in used:
            continue
        matched_spot = ""
        matched_brief: Dict[str, Any] = {}
        for spot in location_brief_map.keys():
            if spot and spot.lower() in c.lower():
                matched_spot = spot
                matched_brief = location_brief_map.get(spot) or {}
                break
        if matched_spot and not bool(matched_brief.get("verified")):
            continue
        dup = similarity_to_catalog(c, catalog_titles)
        penalty = float(dup["score"])
        novelty = 1.0 - penalty
        toks = token_set(c)
        quality_bonus = 0.0
        if any(spot.lower() in c.lower() for spot in KNOWN_MI_SPOTS):
            quality_bonus += 0.2
        if "minimal line sigil" in c.lower():
            quality_bonus += 0.2
        if "travel badge" in c.lower():
            quality_bonus -= 0.2
        if nightlife_mode:
            ctoks = token_set(c)
            if ctoks & nightlife_tokens:
                quality_bonus += 0.45
            else:
                quality_bonus -= 0.75
        if any(t in GENERIC_SPOT_TOKENS for t in toks):
            quality_bonus -= 0.35
        if len(toks) <= 2:
            quality_bonus -= 0.1
        cue_list = matched_brief.get("architecture_cues")
        cues = [str(x).strip().lower() for x in (cue_list if isinstance(cue_list, list) else []) if str(x).strip()]
        if matched_spot and cues:
            if any(any(tok in ctok for tok in token_set(c)) for ctok in cues):
                quality_bonus += 0.35
            else:
                quality_bonus -= 0.2
        if bool(matched_brief.get("has_geometry_outline")):
            if any(x in normalize_text(c) for x in ("aerial", "outline", "map-accurate", "landmark", "proportions")):
                quality_bonus += 0.4
            else:
                quality_bonus -= 0.25
        last_tok = normalize_text(matched_spot).split()[-1] if matched_spot else ""
        if last_tok in LANDMARK_SUFFIXES:
            quality_bonus += 0.15
        score = novelty + quality_bonus
        row = {
            "concept": c,
            "novelty_score": round(novelty, 4),
            "quality_bonus": round(quality_bonus, 4),
            "duplicate_ref": dup,
            "location_spot": matched_spot,
            "location_verified": bool(matched_brief.get("verified")),
            "location_cues": cues,
            "selection_score": round(score, 4),
        }
        is_dup = float(dup["score"]) >= threshold
        row["rejected_duplicate"] = is_dup
        if is_dup:
            continue
        if not best or float(row["selection_score"]) > float(best.get("selection_score") or -1.0):
            best = row
    if not best:
        return {}
    used.add(normalize_text(str(best.get("concept") or "")))
    return best


def run_product_drafter(
    concept: str,
    feedback: str,
    revision: int,
    trend_terms: List[str],
    location_brief: Dict[str, Any],
) -> Tuple[Path | None, str]:
    before = {str(p.resolve()) for p in DRAFTS_DIR.glob("draft_*.json")}
    cues = location_brief.get("architecture_cues") if isinstance(location_brief.get("architecture_cues"), list) else []
    cue_terms = [str(x).strip() for x in cues if isinstance(x, str) and str(x).strip()]
    draft_terms = dedupe_keep_order(trend_terms + cue_terms)[:10]
    job = {
        "id": f"art-syndicate-draft-{now_stamp()}",
        "task_type": "product_drafter",
        "target_profile": "research",
        "inputs": {
            "concept": concept,
            "feedback": feedback,
            "revision": revision,
            "image_backend": "local_lineart",
            "trend_terms": draft_terms,
            "location_brief": location_brief if isinstance(location_brief, dict) else {},
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    rc, out = run_skill(SKILLS_DIR / "skill_product_drafter.py", job)
    if rc != 0:
        return (None, out)
    draft = latest_new_file(DRAFTS_DIR, "draft_*.json", before=before)
    return (draft, out)


def run_listing_generator(draft_path: Path) -> Tuple[Path | None, str]:
    before = {str(p.resolve()) for p in STAGING_DIR.glob("listing_*.json")}
    before_rej = {str(p.resolve()) for p in REJECTED_DIR.glob("rejected_*.json")}
    job = {
        "id": f"art-syndicate-listing-{now_stamp()}",
        "task_type": "listing_generator",
        "target_profile": "research",
        "inputs": {"draft_path": str(draft_path)},
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    rc, out = run_skill(SKILLS_DIR / "skill_listing_generator.py", job)
    if rc != 0:
        return (None, out)
    listing = latest_new_file(STAGING_DIR, "listing_*.json", before=before)
    if listing:
        return (listing, out)
    reject = latest_new_file(REJECTED_DIR, "rejected_*.json", before=before_rej)
    if reject:
        return (None, out + f"\nlisting_rejected:{reject}")
    return (None, out)


def run_uploader(listing_path: Path) -> Tuple[Path | None, str]:
    before = {str(p.resolve()) for p in (REPO_ROOT / "ramshare" / "evidence" / "posted").glob("live_*.json")}
    job = {
        "id": f"art-syndicate-upload-{now_stamp()}",
        "task_type": "uploader",
        "target_profile": "ops",
        "inputs": {"listing_path": str(listing_path)},
        "policy": {"risk": "medium", "estimated_spend_usd": 0},
    }
    env = dict(os.environ)
    env["GEMINI_PROFILE"] = "ops"
    rc, out = run_skill(SKILLS_DIR / "skill_uploader.py", job, env=env)
    if rc != 0:
        return (None, out)
    receipt = latest_new_file(REPO_ROOT / "ramshare" / "evidence" / "posted", "live_*.json", before=before)
    return (receipt, out)


def council_review(
    draft_path: Path,
    catalog_titles: List[str],
    banned_terms: List[str],
    candidate_concept: str,
    location_brief: Dict[str, Any],
) -> Dict[str, Any]:
    draft = load_json(draft_path, fallback={})
    title = str(draft.get("title") or candidate_concept).strip()
    prompt = str(draft.get("mock_image_prompt") or "").strip()
    tags = draft.get("tags") if isinstance(draft.get("tags"), list) else []
    tags = [str(x).strip() for x in tags if str(x).strip()]
    quality = draft.get("quality_outputs") if isinstance(draft.get("quality_outputs"), dict) else {}
    analysis = load_json(Path(str(quality.get("analysis_json") or "")), fallback={})
    preflight = load_json(Path(str(quality.get("preflight_json") or "")), fallback={})

    flags = ((analysis.get("analysis") or {}).get("flags") or []) if isinstance(analysis.get("analysis"), dict) else []
    pre_status = str(preflight.get("status") or "").strip().lower()
    if not pre_status:
        results = preflight.get("results") if isinstance(preflight.get("results"), list) else []
        if results and isinstance(results[0], dict):
            pre_status = str(results[0].get("status") or "").strip().lower()
    lead_dup = similarity_to_catalog(candidate_concept + " " + title, catalog_titles)

    compliance_hits = []
    hay = " ".join([candidate_concept, title, prompt, " ".join(tags)]).lower()
    for term in banned_terms + MORAL_RISK_TERMS:
        if str(term).lower() in hay:
            compliance_hits.append(term)
    compliance_pass = (not compliance_hits) and float(lead_dup["score"]) < 0.62
    compliance_score = 1.0
    if compliance_hits:
        compliance_score -= 0.6
    if float(lead_dup["score"]) >= 0.62:
        compliance_score -= 0.5
    compliance_score = max(0.0, compliance_score)

    has_hard_flag = any(str(f) not in ("low_edge_definition",) for f in flags)
    creative_pass = (not has_hard_flag) and (pre_status in ("pass", "warn"))
    creative_score = 1.0
    if len(flags) > 0:
        penalty = 0.08 if all(str(f) == "low_edge_definition" for f in flags) else min(0.6, len(flags) * 0.22)
        creative_score -= penalty
    if pre_status not in ("pass", "warn"):
        creative_score -= 0.5
    creative_score = max(0.0, creative_score)

    hype_score = 0.3
    if 24 <= len(title) <= 70:
        hype_score += 0.3
    if len(tags) >= 8:
        hype_score += 0.3
    if "michigan" in normalize_text(title + " " + " ".join(tags)):
        hype_score += 0.1
    hype_score = min(1.0, hype_score)
    hype_pass = hype_score >= 0.75

    manager_score = 1.0
    if not str(draft.get("asset_path") or "").strip():
        manager_score -= 0.5
    if pre_status not in ("pass", "warn"):
        manager_score -= 0.25
    manager_score = max(0.0, manager_score)
    manager_pass = manager_score >= 0.75

    # Hard 10/10 location-faithfulness scorecard requested by user.
    spot = str(location_brief.get("spot") or "").strip()
    cues = location_brief.get("architecture_cues") if isinstance(location_brief.get("architecture_cues"), list) else []
    cues = [str(x).strip().lower() for x in cues if isinstance(x, str) and str(x).strip()]
    title_prompt_tags = normalize_text(" ".join([title, prompt, " ".join(tags), candidate_concept]))
    cue_hit = False
    for cue in cues:
        if normalize_text(cue) in title_prompt_tags:
            cue_hit = True
            break
    location_name_hit = bool(spot and normalize_text(spot) in title_prompt_tags)
    strict_scorecard = {
        "real_location_verified": 10 if bool(location_brief.get("verified")) else 0,
        "architecture_cues_present": 10 if (bool(cues) and cue_hit) else 0,
        "location_name_fidelity": 10 if location_name_hit else 0,
        "style_consistency": 10 if (creative_pass and creative_score >= 0.85 and pre_status == "pass") else 0,
        "novelty_guard": 10 if float(lead_dup["score"]) < 0.72 else 0,
    }
    strict_pass = all(int(strict_scorecard.get(k, 0)) == 10 for k in LOCATION_SCORECARD_CATEGORIES)

    role_rows = [
        {
            "role": "Trend Hunter",
            "pass": True,
            "score": round(max(0.0, 1.0 - float(lead_dup["score"])), 3),
            "notes": [f"duplicate_similarity={lead_dup['score']}"],
        },
        {
            "role": "Creative Director",
            "pass": creative_pass,
            "score": round(creative_score, 3),
            "notes": [f"flags={flags}", f"preflight={pre_status}"],
        },
        {
            "role": "Compliance Officer",
            "pass": compliance_pass,
            "score": round(compliance_score, 3),
            "notes": [f"hits={compliance_hits}", f"best_catalog_match={lead_dup['best_title']}"],
        },
        {
            "role": "Hype Man",
            "pass": hype_pass,
            "score": round(hype_score, 3),
            "notes": [f"title_len={len(title)}", f"tag_count={len(tags)}"],
        },
        {
            "role": "Shop Manager",
            "pass": manager_pass,
            "score": round(manager_score, 3),
            "notes": [f"asset_path={draft.get('asset_path','')}", f"preflight={pre_status}"],
        },
    ]
    avg_score = sum(float(r["score"]) for r in role_rows) / float(len(role_rows))
    approved = all(bool(r["pass"]) for r in role_rows) and avg_score >= 0.78 and strict_pass

    feedback_parts: List[str] = []
    if not creative_pass:
        feedback_parts.append("Increase line clarity and reduce artifacts; keep clean center composition.")
    if not compliance_pass:
        if compliance_hits:
            feedback_parts.append("Remove all risky terms and avoid any brand/protected references.")
        if float(lead_dup["score"]) >= 0.62:
            feedback_parts.append("Shift to a more novel Michigan spot concept; avoid overlap with existing listings.")
    if not hype_pass:
        feedback_parts.append("Improve title specificity and add stronger location-focused tags.")
    if not manager_pass:
        feedback_parts.append("Ensure Redbubble preflight passes for tshirt and keep asset print-ready.")
    if not strict_pass:
        for cat, value in strict_scorecard.items():
            if int(value) != 10:
                if cat == "real_location_verified":
                    feedback_parts.append("Use only a real, verified location and regenerate.")
                elif cat == "architecture_cues_present":
                    feedback_parts.append("Inject location-specific architectural cues into prompt/title/tags.")
                elif cat == "location_name_fidelity":
                    feedback_parts.append("Keep exact location name present across concept, title, and tags.")
                elif cat == "style_consistency":
                    feedback_parts.append("Improve linework clarity until preflight passes with strong style consistency.")
                elif cat == "novelty_guard":
                    feedback_parts.append("Shift to a more novel execution with lower duplicate similarity.")

    return {
        "approved": approved,
        "avg_score": round(avg_score, 4),
        "strict_scorecard": strict_scorecard,
        "strict_pass": strict_pass,
        "location_brief": {
            "spot": spot,
            "verified": bool(location_brief.get("verified")),
            "display_name": str(location_brief.get("display_name") or ""),
            "has_geometry_outline": bool(location_brief.get("has_geometry_outline")),
            "geometry_type": str(location_brief.get("geometry_type") or ""),
            "architecture_cues": cues,
        },
        "roles": role_rows,
        "feedback": " ".join(feedback_parts).strip(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Art Syndicate: trend->generate->council review->fix loop for Redbubble.")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()

    job = load_json(Path(args.job_file), fallback={})
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    query = str(inputs.get("query") or inputs.get("theme") or DEFAULT_THEME).strip()
    max_revisions = int(inputs.get("max_revisions") or 4)
    max_candidates = int(inputs.get("max_candidates") or 6)
    build_packet = bool(inputs.get("build_upload_packet", True))
    shop_url = str(inputs.get("shop_url") or "").strip()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    banned_terms = load_banned_terms()

    catalog_info = catalog_scan(shop_url=shop_url)
    catalog = catalog_info.get("catalog") if isinstance(catalog_info.get("catalog"), dict) else {}
    catalog_titles = catalog.get("titles") if isinstance(catalog.get("titles"), list) else []
    catalog_titles = [str(x).strip() for x in catalog_titles if isinstance(x, str) and x.strip()]

    trend = run_trend_hunter(query=query)
    trend_json = trend.get("trend_json") if isinstance(trend.get("trend_json"), dict) else {}
    trend_terms = extract_trend_terms(trend_json)
    trend_terms = dedupe_keep_order(trend_terms + trend.get("redbubble_tags", []))[:16]
    spots = extract_spot_candidates(trend_json)
    if len(spots) < 8:
        spots = dedupe_keep_order(spots + KNOWN_MI_SPOTS)[:16]
    location_briefs = build_location_briefs(spots=spots, query=query)
    location_brief_map = {str(b.get("spot") or ""): b for b in location_briefs if str(b.get("spot") or "")}
    concepts = build_concepts(location_briefs=location_briefs, query=query, trend_terms=trend_terms)

    used: set[str] = set()
    trace_rows: List[Dict[str, Any]] = []
    winner: Dict[str, Any] = {}

    for _ in range(max(1, max_candidates)):
        selected = choose_candidate(
            concepts=concepts,
            catalog_titles=catalog_titles,
            used=used,
            query=query,
            location_brief_map=location_brief_map,
            threshold=0.75,
        )
        if not selected:
            break
        concept = str(selected.get("concept") or "").strip()
        matched_spot = str(selected.get("location_spot") or "").strip()
        matched_brief = location_brief_map.get(matched_spot) or {}
        feedback = ""
        for revision in range(max(1, max_revisions)):
            draft_path, draft_log = run_product_drafter(
                concept=concept,
                feedback=feedback,
                revision=revision,
                trend_terms=trend_terms,
                location_brief=matched_brief,
            )
            row: Dict[str, Any] = {
                "concept": concept,
                "revision": revision,
                "draft_path": str(draft_path) if draft_path else "",
                "selection": selected,
                "draft_log": draft_log,
            }
            if draft_path is None:
                row["status"] = "draft_failed"
                trace_rows.append(row)
                break

            review = council_review(
                draft_path=draft_path,
                catalog_titles=catalog_titles,
                banned_terms=banned_terms,
                candidate_concept=concept,
                location_brief=matched_brief,
            )
            row["council_review"] = review
            if bool(review.get("approved")):
                listing_path, listing_log = run_listing_generator(draft_path=draft_path)
                row["listing_path"] = str(listing_path) if listing_path else ""
                row["listing_log"] = listing_log
                if listing_path is None:
                    row["status"] = "listing_failed_or_rejected"
                    trace_rows.append(row)
                    break
                upload_receipt = None
                upload_log = ""
                if build_packet:
                    upload_receipt, upload_log = run_uploader(listing_path=listing_path)
                row["upload_receipt"] = str(upload_receipt) if upload_receipt else ""
                row["upload_log"] = upload_log
                row["status"] = "approved"
                trace_rows.append(row)
                winner = row
                break

            feedback = str(review.get("feedback") or "").strip()
            row["status"] = "disapproved_needs_revision"
            row["next_feedback"] = feedback
            trace_rows.append(row)

        if winner:
            break

    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "catalog_scan": {
            "ok": bool(catalog_info.get("ok", True)),
            "catalog_path": str(CATALOG_CACHE_PATH),
            "live_scan": (catalog.get("live_scan") if isinstance(catalog, dict) else {}),
            "title_count": len(catalog_titles),
        },
        "trend_hunter": {
            "report_path": trend.get("report_path", ""),
            "hot_trends": trend_json.get("hot_trends", []),
            "ranked_trends": trend_json.get("ranked_trends", []),
            "social_hits": trend_json.get("social_hits", []),
            "source_breakdown": trend_json.get("source_breakdown", {}),
            "michigan_spot_leads": trend_json.get("michigan_spot_leads", []),
            "redbubble_best_selling_tag_hints": trend.get("redbubble_tags", []),
            "trend_terms": trend_terms,
        },
        "location_briefs": location_briefs,
        "candidates": concepts[:max_candidates],
        "trace": trace_rows,
        "winner": winner,
        "approved": bool(winner),
    }
    out = REPORTS_DIR / f"art_syndicate_{now_stamp()}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": bool(winner), "report": str(out), "approved": bool(winner)}, indent=2))


if __name__ == "__main__":
    main()
