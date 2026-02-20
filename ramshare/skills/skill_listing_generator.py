import argparse
import datetime as dt
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
REJECTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "rejected"
PROCESSED_DIR = REPO_ROOT / "ramshare" / "evidence" / "processed"
PACKETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "upload_packets"
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"
IP_TERMS_PATH = REPO_ROOT / "data" / "redbubble" / "ip_risk_terms.txt"
SHOP_PROFILE_PATH = REPO_ROOT / "data" / "redbubble" / "shop_profile.json"
CATALOG_CACHE_PATH = REPO_ROOT / "data" / "redbubble" / "shop_catalog_cache.json"
DEFAULT_BANNED_TERMS = ["Disney", "Marvel", "Nike", "Star Wars"]
DUPLICATE_STOP_TOKENS = {
    "minimal",
    "line",
    "art",
    "travel",
    "badge",
    "monoline",
    "michigan",
    "clean",
    "design",
    "tee",
    "gift",
}
TITLE_STOPWORDS = {"the", "and", "for", "with", "from", "your", "this", "that", "line", "art", "minimal"}
TAG_STOPWORDS = {"the", "and", "for", "with", "from", "your", "this", "that", "best", "top"}


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_shop_profile() -> Dict[str, Any]:
    if not SHOP_PROFILE_PATH.exists():
        return {}
    try:
        return load_json(SHOP_PROFILE_PATH)
    except Exception:
        return {}


def load_banned_terms() -> List[str]:
    if not IP_TERMS_PATH.exists():
        return list(DEFAULT_BANNED_TERMS)
    out: List[str] = []
    for raw in IP_TERMS_PATH.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    if not out:
        return list(DEFAULT_BANNED_TERMS)
    return out


def flatten_tags(tags: Any) -> List[str]:
    if not isinstance(tags, list):
        return []
    out: List[str] = []
    for t in tags:
        if isinstance(t, str):
            out.append(t.strip())
    return [x for x in out if x]


def normalize_token(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", s.lower())).strip()


def title_case_slug(s: str) -> str:
    cleaned = normalize_token(s)
    if not cleaned:
        return "Minimal Line Art"
    return " ".join(x.capitalize() for x in cleaned.split())


def extract_theme(seed: str) -> str:
    cleaned = normalize_token(seed)
    stop = {
        "minimal",
        "line",
        "art",
        "design",
        "graphic",
        "for",
        "gift",
        "gifts",
        "tee",
        "shirt",
        "symbol",
        "symbols",
    }
    tokens = [t for t in cleaned.split() if len(t) >= 3 and t not in stop]
    if not tokens:
        return title_case_slug(seed)
    return " ".join(x.capitalize() for x in tokens[:4])


def trim_title(text: str, min_len: int, max_len: int) -> str:
    t = " ".join(text.split()).strip()
    if len(t) <= max_len and len(t) >= min_len:
        return t
    if len(t) > max_len:
        t = t[:max_len].rstrip(" -|,:")
    if len(t) < min_len:
        t = (t + " Minimal Line Art").strip()
        if len(t) > max_len:
            t = t[:max_len].rstrip(" -|,:")
    return t


def title_tokens(text: str) -> List[str]:
    out: List[str] = []
    for tok in normalize_token(text).split():
        if not tok or tok in TITLE_STOPWORDS:
            continue
        out.append(tok)
    return out


def build_title_variants(concept: str, theme: str, patterns: List[str]) -> List[str]:
    base = title_case_slug(concept)
    raw_patterns = patterns if patterns else ["{theme} | Minimal Line Art", "{theme} Minimal Line Badge", "{theme} Travel Line Art"]
    out: List[str] = []
    for p in raw_patterns[:5]:
        out.append(str(p).replace("{theme}", theme).replace("{concept}", base))
    out.extend(
        [
            f"{theme} | Minimal Line Art",
            f"{theme} Travel Badge | Monoline",
            f"{theme} Michigan Line Art Gift",
        ]
    )
    return dedupe_keep_order(out)


def choose_best_title(candidates: List[str], trend_terms: List[str], min_chars: int, max_chars: int) -> str:
    if not candidates:
        return trim_title("Minimal Line Art", min_chars, max_chars)
    scored: List[tuple[float, str]] = []
    trend_token_set = set()
    for tt in trend_terms:
        trend_token_set.update(title_tokens(tt))
    for raw in candidates:
        t = trim_title(raw, min_len=min_chars, max_len=max_chars)
        toks = set(title_tokens(t))
        if not toks:
            score = 0.0
        else:
            overlap = float(len(toks & trend_token_set)) / float(len(toks | trend_token_set)) if trend_token_set else 0.0
            score = overlap * 2.0
            if 26 <= len(t) <= 62:
                score += 1.0
            if "|" in t:
                score += 0.25
            if any(x in normalize_token(t) for x in ("michigan", "travel", "badge", "line")):
                score += 0.35
        scored.append((score, t))
    scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    return scored[0][1]


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        x = " ".join(str(item).strip().split())
        if not x:
            continue
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def build_tags(seed_tags: List[str], theme: str, profile: Dict[str, Any], trend_terms: List[str]) -> List[str]:
    seo = profile.get("seo") if isinstance(profile.get("seo"), dict) else {}
    tags_cfg = seo.get("tags") if isinstance(seo.get("tags"), dict) else {}
    min_count = int(tags_cfg.get("min_count") or 8)
    max_count = int(tags_cfg.get("max_count") or 15)
    core = tags_cfg.get("core") if isinstance(tags_cfg.get("core"), list) else []

    theme_tokens = [x for x in normalize_token(theme).split() if len(x) >= 3]
    theme_phrases = []
    if theme_tokens:
        theme_phrases.append(" ".join(theme_tokens[:2]))
        theme_phrases.append(" ".join(theme_tokens[:3]))
        theme_phrases.extend(theme_tokens[:4])

    candidates = dedupe_keep_order(
        seed_tags + [str(x) for x in core] + trend_terms + theme_phrases + ["minimal line art", "black and white"]
    )
    # Remove very short or noisy tags.
    cleaned = []
    for c in candidates:
        nc = normalize_token(c)
        if len(nc) < 3:
            continue
        if len(nc.split()) > 4:
            continue
        if nc in TAG_STOPWORDS:
            continue
        if nc.isdigit():
            continue
        if re.fullmatch(r"(19|20)\d{2}", nc):
            continue
        if nc in {"line", "art", "minimal", "design"}:
            continue
        cleaned.append(c)

    out = dedupe_keep_order(cleaned)[:max_count]
    while len(out) < min_count:
        out.append(f"{theme} art".strip())
        out = dedupe_keep_order(out)[:max_count]
        if len(out) >= min_count:
            break
        out.append("gift idea")
        out = dedupe_keep_order(out)[:max_count]
        if len(out) >= min_count:
            break
        out.append("michigan")
        out = dedupe_keep_order(out)[:max_count]
    return out[:max_count]


def build_description(theme: str, profile: Dict[str, Any], tags: List[str]) -> str:
    seo = profile.get("seo") if isinstance(profile.get("seo"), dict) else {}
    blocks = seo.get("description_blocks") if isinstance(seo.get("description_blocks"), list) else []
    cta = seo.get("cta") if isinstance(seo.get("cta"), list) else []
    tag_tail = ", ".join(tags[:5]) if tags else ""
    text_parts: List[str] = [f"{theme} in a clean minimal line-art style."]
    text_parts.extend([str(x).strip() for x in blocks if isinstance(x, str) and x.strip()])
    if cta:
        text_parts.append(str(cta[0]).strip())
    if tag_tail:
        text_parts.append(f"Keywords: {tag_tail}.")
    return " ".join(text_parts).strip()


def build_social_posts(title: str, theme: str, profile: Dict[str, Any]) -> Dict[str, str]:
    social = profile.get("social") if isinstance(profile.get("social"), dict) else {}
    hashtags = social.get("hashtags") if isinstance(social.get("hashtags"), list) else []
    tags = " ".join(str(x).strip() for x in hashtags if isinstance(x, str) and x.strip())
    ig = f"New drop: {title}. Clean minimal line-art inspired by {theme.lower()}. {tags}".strip()
    pin = f"{title} - Minimal line-art gift idea inspired by {theme.lower()}. Save for later."
    xpost = f"{title} now live. Minimal line-art, high-res transparent design. {tags}".strip()
    return {"instagram": ig, "pinterest": pin, "x": xpost}


def build_upload_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    products = profile.get("products") if isinstance(profile.get("products"), dict) else {}
    upload_policy = profile.get("upload_policy") if isinstance(profile.get("upload_policy"), dict) else {}
    enabled = products.get("enabled") if isinstance(products.get("enabled"), list) else []
    markup = products.get("default_markup_pct") if isinstance(products.get("default_markup_pct"), dict) else {}
    return {
        "enabled_products": enabled,
        "markup_pct": markup,
        "manual_publish_required": bool(upload_policy.get("manual_publish_required", True)),
        "safe_daily_upload_cap": int(upload_policy.get("safe_daily_upload_cap") or 8),
        "safe_hourly_upload_cap": int(upload_policy.get("safe_hourly_upload_cap") or 3),
        "mature_default": bool(upload_policy.get("mature_default", False)),
    }


def seo_score(title: str, tags: List[str], description: str, trend_terms: List[str]) -> float:
    score = 0.0
    title_len = len(title)
    if 24 <= title_len <= 70:
        score += 2.0
    elif 18 <= title_len <= 80:
        score += 1.0
    tag_count = len(tags)
    if 10 <= tag_count <= 15:
        score += 2.0
    elif 8 <= tag_count <= 15:
        score += 1.5
    if len(description) >= 120:
        score += 1.5
    trend_tokens = set()
    for t in trend_terms:
        trend_tokens.update(title_tokens(t))
    title_tag_tokens = set(title_tokens(title + " " + " ".join(tags)))
    if trend_tokens:
        overlap = float(len(trend_tokens & title_tag_tokens)) / float(len(trend_tokens))
        score += overlap * 2.0
    if "michigan" in normalize_token(title + " " + " ".join(tags)):
        score += 0.6
    return round(min(7.0, score), 4)


def find_banned_hits(text_fields: Iterable[str], banned_terms: Iterable[str]) -> List[str]:
    text = " ".join(text_fields).lower()
    hits: List[str] = []
    for term in banned_terms:
        if term.lower() in text:
            hits.append(term)
    return dedupe_keep_order(hits)


def token_set(s: str) -> set[str]:
    out = set()
    for x in normalize_token(s).split():
        if not x:
            continue
        if x in DUPLICATE_STOP_TOKENS:
            continue
        if x.isdigit():
            continue
        out.add(x)
    return out


def text_similarity(a: str, b: str) -> float:
    ta = token_set(a)
    tb = token_set(b)
    if not ta or not tb:
        return 0.0
    jac = float(len(ta & tb)) / float(len(ta | tb))
    seq = SequenceMatcher(None, normalize_token(a), normalize_token(b)).ratio()
    # Prevent boilerplate title scaffolding from dominating duplicate detection.
    return max(jac, min(seq * 0.6, jac + 0.2))


def load_existing_titles() -> List[str]:
    out: List[str] = []
    if CATALOG_CACHE_PATH.exists():
        try:
            cache = load_json(CATALOG_CACHE_PATH)
            titles = cache.get("titles") if isinstance(cache.get("titles"), list) else []
            for t in titles:
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
        except Exception:
            pass
    for p in sorted(STAGING_DIR.glob("listing_*.json")):
        obj = load_json(p)
        t = str(obj.get("title") or "").strip()
        if t:
            out.append(t)
    for p in sorted(PROCESSED_DIR.glob("listing_*.json")):
        obj = load_json(p)
        t = str(obj.get("title") or "").strip()
        if t:
            out.append(t)
    for p in sorted(PACKETS_DIR.glob("**/upload_manifest.json")):
        obj = load_json(p)
        t = str(obj.get("title") or "").strip()
        if t:
            out.append(t)
    for p in sorted(POSTED_DIR.glob("live_*.json")):
        rec = load_json(p)
        src = Path(str(rec.get("source_listing_path") or "").strip())
        if src.exists():
            lst = load_json(src)
            t = str(lst.get("title") or "").strip()
            if t:
                out.append(t)
    return dedupe_keep_order(out)


def find_duplicate_title(candidate: str, existing_titles: List[str], threshold: float = 0.62) -> Dict[str, Any]:
    best_title = ""
    best_score = 0.0
    for t in existing_titles:
        s = text_similarity(candidate, t)
        if s > best_score:
            best_score = s
            best_title = t
    return {
        "is_duplicate": bool(best_score >= threshold),
        "best_match_title": best_title,
        "best_match_score": round(best_score, 4),
        "threshold": threshold,
    }


def resolve_source_payload(input_path: Path) -> Dict[str, Any]:
    payload = load_json(input_path)
    # listing_generator often receives a reviewed file; if source draft exists, merge in asset metadata.
    src_draft_path = payload.get("source_draft_path")
    if isinstance(src_draft_path, str) and src_draft_path.strip():
        p = Path(src_draft_path)
        if p.exists():
            try:
                draft_payload = load_json(p)
                merged = dict(draft_payload)
                merged.update(payload)
                merged["source_draft_path"] = str(p)
                return merged
            except Exception:
                return payload
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Listing generator with SEO + compliance + upload metadata")
    ap.add_argument("job_file", help="Path to listing_generator job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_json(job_path)

    inputs = job.get("inputs") or {}
    src_path_str = inputs.get("draft_path") or job.get("draft_path") or job.get("input_data")
    if not isinstance(src_path_str, str) or not src_path_str.strip():
        raise SystemExit("Missing draft_path in job (expected inputs.draft_path or input_data)")

    src_path = Path(src_path_str)
    if not src_path.exists():
        raise SystemExit(f"Source file not found: {src_path}")

    payload = resolve_source_payload(src_path)
    profile = load_shop_profile()
    banned_terms = load_banned_terms()
    existing_titles = load_existing_titles()
    trend_terms = payload.get("trend_terms") if isinstance(payload.get("trend_terms"), list) else []
    trend_terms = [str(x).strip() for x in trend_terms if isinstance(x, str) and str(x).strip()]
    trend_terms = dedupe_keep_order(trend_terms)[:10]

    seed_title = str(payload.get("title") or "").strip()
    concept = str(payload.get("concept") or seed_title or "Minimal Line Art").strip()
    theme = extract_theme(concept)

    seo = profile.get("seo") if isinstance(profile.get("seo"), dict) else {}
    title_cfg = seo.get("title") if isinstance(seo.get("title"), dict) else {}
    patterns = title_cfg.get("patterns") if isinstance(title_cfg.get("patterns"), list) else []
    min_chars = int(title_cfg.get("min_chars") or 24)
    max_chars = int(title_cfg.get("max_chars") or 70)
    title_candidates = build_title_variants(concept=concept, theme=theme, patterns=patterns)
    title = choose_best_title(title_candidates, trend_terms=trend_terms, min_chars=min_chars, max_chars=max_chars)

    seed_tags = flatten_tags(payload.get("tags"))
    tags = build_tags(seed_tags, theme=theme, profile=profile, trend_terms=trend_terms)
    description = build_description(theme=theme, profile=profile, tags=tags)
    social_posts = build_social_posts(title=title, theme=theme, profile=profile)
    upload_settings = build_upload_settings(profile=profile)
    listing_seo_score = seo_score(title=title, tags=tags, description=description, trend_terms=trend_terms)

    hits = find_banned_hits(
        [title, description, " ".join(tags), " ".join(social_posts.values())],
        banned_terms=banned_terms,
    )
    dup = find_duplicate_title(title, existing_titles)
    if hits:
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        out = REJECTED_DIR / f"rejected_{now_stamp()}.json"
        reject_payload = {
            "status": "rejected",
            "reason": "banned_term_detected",
            "hits": hits,
            "source_path": str(src_path),
            "title": title,
            "tags": tags,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        out.write_text(json.dumps(reject_payload, indent=2), encoding="utf-8")
        print(f"Listing rejected: {out}")
        return
    if bool(dup.get("is_duplicate")):
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        out = REJECTED_DIR / f"rejected_{now_stamp()}.json"
        reject_payload = {
            "status": "rejected",
            "reason": "duplicate_like_existing_listing",
            "duplicate_check": dup,
            "source_path": str(src_path),
            "title": title,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        out.write_text(json.dumps(reject_payload, indent=2), encoding="utf-8")
        print(f"Listing rejected: {out}")
        return

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    out = STAGING_DIR / f"listing_{now_stamp()}.json"
    listing = {
        "status": "staged",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_input_path": str(src_path),
        "source_draft_path": str(payload.get("source_draft_path") or ""),
        "asset_path": str(payload.get("asset_path") or ""),
        "quality_outputs": payload.get("quality_outputs") if isinstance(payload.get("quality_outputs"), dict) else {},
        "title": title,
        "theme": theme,
        "concept": concept,
        "mock_image_prompt": payload.get("mock_image_prompt"),
        "tags": tags,
        "price_point": payload.get("price_point", 24.99),
        "seo_description": description,
        "social_posts": social_posts,
        "upload_settings": upload_settings,
        "shop_profile_path": str(SHOP_PROFILE_PATH),
        "duplicate_check": dup,
        "trend_terms": trend_terms,
        "seo_score": listing_seo_score,
    }
    out.write_text(json.dumps(listing, indent=2), encoding="utf-8")
    print(f"Listing staged: {out}")


if __name__ == "__main__":
    main()
