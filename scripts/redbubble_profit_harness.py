from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
SKILL_PRODUCT = REPO_ROOT / "ramshare" / "skills" / "skill_product_drafter.py"
SKILL_ART = REPO_ROOT / "ramshare" / "skills" / "skill_art_director.py"
SKILL_LISTING = REPO_ROOT / "ramshare" / "skills" / "skill_listing_generator.py"
SKILL_UPLOADER = REPO_ROOT / "ramshare" / "skills" / "skill_uploader.py"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
REVIEWED_DIR = REPO_ROOT / "ramshare" / "evidence" / "reviewed"
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def run_py(script: Path, job_payload: Dict[str, Any], env: Dict[str, str]) -> Tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        tf.write(json.dumps(job_payload, indent=2))
        job_path = tf.name
    try:
        cp = subprocess.run(
            [sys.executable, str(script), job_path],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            env=env,
        )
        out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
        return cp.returncode, out
    finally:
        try:
            Path(job_path).unlink(missing_ok=True)
        except Exception:
            pass


def latest_file(dir_path: Path, pattern: str) -> Optional[Path]:
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def concept_variants(theme: str, count: int) -> List[str]:
    base = theme.strip() or "minimal geometric symbol"
    suffixes = [
        "minimal line sigil",
        "bold emblem linework",
        "clean monoline crest",
        "high-contrast icon set",
        "geometric heritage seal",
        "vintage badge line art",
        "gift-ready minimalist mark",
        "symbolic abstract stamp",
    ]
    out = []
    for i in range(max(1, count)):
        sfx = suffixes[i % len(suffixes)]
        out.append(f"{base} {sfx}")
    return out


def compute_sellability_score(reviewed: Dict[str, Any], listing: Dict[str, Any]) -> float:
    review = reviewed.get("art_director_review")
    if not isinstance(review, dict):
        review = {}
    score = float(review.get("score") or 0.0)
    tags = listing.get("tags") if isinstance(listing.get("tags"), list) else []
    tcount = len(tags)
    score += min(12.0, float(tcount))
    title = str(listing.get("title") or "")
    if 18 <= len(title) <= 64:
        score += 6.0
    desc = str(listing.get("seo_description") or "")
    if len(desc) >= 90:
        score += 4.0
    if "line" in title.lower() or "minimal" in title.lower():
        score += 2.0
    return round(score, 2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rigorous sellability harness for Redbubble free pipeline.")
    ap.add_argument("--theme", required=True)
    ap.add_argument("--variants", type=int, default=6)
    ap.add_argument("--approve-upload", action="store_true")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    start = dt.datetime.now()
    env = dict(os.environ)
    env["GEMINI_OP_FREE_MODE"] = "1"
    env["GEMINI_OP_ALLOW_PAID_ART"] = "0"
    env["GEMINI_OP_ART_BACKEND"] = "local_lineart"

    leaderboard: List[Dict[str, Any]] = []

    for idx, concept in enumerate(concept_variants(args.theme, args.variants), start=1):
        before_draft = latest_file(REPO_ROOT / "ramshare" / "evidence" / "drafts", "draft_*.json")
        product_job = {
            "id": f"profit-draft-{idx}-{now_stamp()}",
            "task_type": "product_drafter",
            "target_profile": "research",
            "inputs": {"concept": concept, "image_backend": "local_lineart"},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        rc1, out1 = run_py(SKILL_PRODUCT, product_job, env=env)
        if rc1 != 0:
            leaderboard.append({"concept": concept, "status": "draft_failed", "error": out1})
            continue
        draft = latest_file(REPO_ROOT / "ramshare" / "evidence" / "drafts", "draft_*.json")
        if draft is None or draft == before_draft:
            leaderboard.append({"concept": concept, "status": "draft_missing"})
            continue

        before_reviewed = latest_file(REVIEWED_DIR, "reviewed_*.json")
        art_job = {
            "id": f"profit-art-{idx}-{now_stamp()}",
            "task_type": "art_director",
            "target_profile": "research",
            "inputs": {"draft_path": str(draft)},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        rc2, out2 = run_py(SKILL_ART, art_job, env=env)
        reviewed = latest_file(REVIEWED_DIR, "reviewed_*.json")
        if rc2 != 0 or reviewed is None or reviewed == before_reviewed:
            leaderboard.append({"concept": concept, "status": "review_refined_or_failed", "detail": out2, "draft_path": str(draft)})
            continue

        before_listing = latest_file(STAGING_DIR, "listing_*.json")
        listing_job = {
            "id": f"profit-listing-{idx}-{now_stamp()}",
            "task_type": "listing_generator",
            "target_profile": "research",
            "inputs": {"draft_path": str(reviewed)},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        rc3, out3 = run_py(SKILL_LISTING, listing_job, env=env)
        listing = latest_file(STAGING_DIR, "listing_*.json")
        if rc3 != 0 or listing is None or listing == before_listing:
            leaderboard.append({"concept": concept, "status": "listing_failed", "detail": out3, "reviewed_path": str(reviewed)})
            continue

        reviewed_obj = load_json(reviewed)
        listing_obj = load_json(listing)
        score = compute_sellability_score(reviewed_obj, listing_obj)
        leaderboard.append(
            {
                "concept": concept,
                "status": "pass",
                "sellability_score": score,
                "draft_path": str(draft),
                "reviewed_path": str(reviewed),
                "listing_path": str(listing),
            }
        )

    pass_rows = [r for r in leaderboard if r.get("status") == "pass"]
    pass_rows = sorted(pass_rows, key=lambda x: float(x.get("sellability_score") or 0.0), reverse=True)
    winner = pass_rows[0] if pass_rows else None

    upload_receipt = ""
    upload_output = ""
    if winner and args.approve_upload:
        listing_path = Path(str(winner.get("listing_path")))
        before_live = latest_file(POSTED_DIR, "live_*.json")
        upload_job = {
            "id": f"profit-upload-{now_stamp()}",
            "task_type": "uploader",
            "target_profile": "ops",
            "requires_human_approval": True,
            "approval_token": f"FIRST_UPLOAD_APPROVED_{now_stamp()}",
            "inputs": {"listing_path": str(listing_path)},
            "policy": {"risk": "medium", "estimated_spend_usd": 0},
        }
        env_ops = dict(env)
        env_ops["GEMINI_PROFILE"] = "ops"
        rc4, out4 = run_py(SKILL_UPLOADER, upload_job, env=env_ops)
        upload_output = out4
        after_live = latest_file(POSTED_DIR, "live_*.json")
        if rc4 == 0 and after_live is not None and after_live != before_live:
            upload_receipt = str(after_live)

    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "theme": args.theme,
        "variants": int(args.variants),
        "duration_sec": round((dt.datetime.now() - start).total_seconds(), 3),
        "leaderboard": leaderboard,
        "winner": winner,
        "upload_approved": bool(args.approve_upload),
        "upload_receipt": upload_receipt,
        "upload_output": upload_output,
    }
    out_json = REPORTS_DIR / f"rb_profit_harness_{now_stamp()}.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nReport: {out_json}")
    return 0 if winner else 2


if __name__ == "__main__":
    raise SystemExit(main())
