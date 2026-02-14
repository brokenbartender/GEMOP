import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
REJECTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "rejected"
BANNED_TERMS = ["Disney", "Marvel", "Nike", "Star Wars"]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def flatten_tags(tags: Any) -> List[str]:
    if not isinstance(tags, list):
        return []
    out: List[str] = []
    for t in tags:
        if isinstance(t, str):
            out.append(t)
    return out


def find_banned_hits(title: str, tags: Iterable[str]) -> List[str]:
    text = f"{title} " + " ".join(tags)
    low = text.lower()
    hits: List[str] = []
    for term in BANNED_TERMS:
        if term.lower() in low:
            hits.append(term)
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description="Listing generator with trademark safety gate")
    ap.add_argument("job_file", help="Path to listing_generator job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_json(job_path)

    inputs = job.get("inputs") or {}
    draft_path_str = (
        inputs.get("draft_path")
        or job.get("draft_path")
        or job.get("input_data")
    )
    if not isinstance(draft_path_str, str) or not draft_path_str.strip():
        raise SystemExit("Missing draft_path in job (expected inputs.draft_path or input_data)")

    draft_path = Path(draft_path_str)
    if not draft_path.exists():
        raise SystemExit(f"Draft file not found: {draft_path}")

    draft = load_json(draft_path)
    title = str(draft.get("title") or "").strip()
    tags = flatten_tags(draft.get("tags"))

    hits = find_banned_hits(title, tags)
    if hits:
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        out = REJECTED_DIR / f"rejected_{now_stamp()}.json"
        payload = {
            "status": "rejected",
            "reason": "banned_term_detected",
            "hits": hits,
            "draft_path": str(draft_path),
            "title": title,
            "tags": tags,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Listing rejected: {out}")
        return

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    out = STAGING_DIR / f"listing_{now_stamp()}.json"
    seo = f"Elevate your style with this {title}. Perfect gift-ready design with a clean, bold look."

    listing = {
        "status": "staged",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_draft_path": str(draft_path),
        "title": title,
        "mock_image_prompt": draft.get("mock_image_prompt"),
        "tags": tags,
        "price_point": draft.get("price_point", 24.99),
        "seo_description": seo,
    }
    out.write_text(json.dumps(listing, indent=2), encoding="utf-8")
    print(f"Listing staged: {out}")


if __name__ == "__main__":
    main()

