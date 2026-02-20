import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
REVIEWED_DIR = REPO_ROOT / "ramshare" / "evidence" / "reviewed"
REJECTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "rejected"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_json_if_exists(path_str: Any) -> Dict[str, Any]:
    if not isinstance(path_str, str) or not path_str.strip():
        return {}
    p = Path(path_str)
    if not p.exists():
        return {}
    try:
        return load_json(p)
    except Exception:
        return {}


def evaluate_draft(draft: Dict[str, Any]) -> Tuple[str, int, List[str]]:
    notes: List[str] = []
    score = 100

    title = str(draft.get("title") or "").strip()
    prompt = str(draft.get("mock_image_prompt") or "").strip()
    concept = str(draft.get("concept") or "").strip()
    tags = draft.get("tags")
    tag_count = len(tags) if isinstance(tags, list) else 0
    asset_path = str(draft.get("asset_path") or "").strip()
    quality_outputs = draft.get("quality_outputs") if isinstance(draft.get("quality_outputs"), dict) else {}

    if len(title) < 8 or len(title) > 80:
        score -= 25
        notes.append("Title length outside target range (8-80 chars).")
    if tag_count < 3:
        score -= 25
        notes.append("Need at least 3 tags for discoverability.")
    if len(prompt) < 60:
        score -= 20
        notes.append("Image prompt is too short; add clearer visual direction.")
    if concept and concept.lower() not in prompt.lower() and concept.lower() not in title.lower():
        score -= 20
        notes.append("Prompt/title should more explicitly match the concept.")

    low_prompt = prompt.lower()
    for bad in ("blurry", "watermark", "low resolution", "copyrighted logo"):
        if f"no {bad}" in low_prompt:
            continue
        if bad in low_prompt:
            score -= 30
            notes.append(f"Prompt includes disallowed quality token: '{bad}'.")

    if not asset_path:
        score -= 35
        notes.append("Missing generated asset path.")
    else:
        p = Path(asset_path)
        if not p.exists():
            score -= 35
            notes.append("Generated asset file does not exist.")
        else:
            try:
                with Image.open(p) as img:
                    w, h = img.size
                if w < 4200 or h < 5100:
                    score -= 30
                    notes.append(f"Asset resolution too small for apparel ({w}x{h}).")
            except Exception:
                score -= 20
                notes.append("Unable to read generated asset metadata.")

    preflight = read_json_if_exists(quality_outputs.get("preflight_json") if isinstance(quality_outputs, dict) else None)
    if preflight:
        results = preflight.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            status = str((first or {}).get("status") or "")
            if status != "pass":
                score -= 30
                notes.append(f"Marketplace preflight status={status}.")

    analysis = read_json_if_exists(quality_outputs.get("analysis_json") if isinstance(quality_outputs, dict) else None)
    if analysis:
        a = analysis.get("analysis") if isinstance(analysis.get("analysis"), dict) else {}
        flags = a.get("flags") if isinstance(a.get("flags"), list) else []
        if flags:
            score -= min(20, 8 * len(flags))
            notes.append(f"Line-art quality flags: {', '.join(str(x) for x in flags)}")

    decision = "pass" if score >= 75 else "refine"
    if not notes:
        notes.append("Draft meets baseline quality bar.")
    return decision, max(score, 0), notes


def pick_draft_path(job: Dict[str, Any]) -> Path:
    inputs = job.get("inputs") or {}
    draft_path = inputs.get("draft_path") or job.get("draft_path") or job.get("input_data")
    if not isinstance(draft_path, str) or not draft_path.strip():
        raise SystemExit("Missing draft_path in art_director job")
    return Path(draft_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Art Director skill: critique draft quality before listing")
    ap.add_argument("job_file", help="Path to art_director job json")
    args = ap.parse_args()

    job = load_json(Path(args.job_file))
    draft_path = pick_draft_path(job)
    if not draft_path.exists():
        raise SystemExit(f"Draft file not found: {draft_path}")

    draft = load_json(draft_path)
    revision = int(draft.get("revision") or 0)
    decision, score, notes = evaluate_draft(draft)

    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    if decision == "pass":
        out = REVIEWED_DIR / f"reviewed_{now_stamp()}.json"
        reviewed = {
            "status": "reviewed_pass",
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "source_draft_path": str(draft_path),
            "title": draft.get("title"),
            "concept": draft.get("concept"),
            "mock_image_prompt": draft.get("mock_image_prompt"),
            "tags": draft.get("tags"),
            "price_point": draft.get("price_point", 24.99),
            "asset_path": draft.get("asset_path", ""),
            "quality_outputs": draft.get("quality_outputs") if isinstance(draft.get("quality_outputs"), dict) else {},
            "image_backend_used": draft.get("image_backend_used", ""),
            "revision": revision,
            "art_director_review": {"score": score, "decision": decision, "notes": notes},
        }
        out.write_text(json.dumps(reviewed, indent=2), encoding="utf-8")
        print(f"Art Director PASS: {out}")
        return

    if revision >= 2:
        out = REJECTED_DIR / f"art_reject_{now_stamp()}.json"
        payload = {
            "status": "rejected",
            "reason": "max_revision_reached",
            "source_draft_path": str(draft_path),
            "title": draft.get("title"),
            "art_director_review": {"score": score, "decision": decision, "notes": notes},
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Art Director REJECT: {out}")
        return

    feedback = "; ".join(notes)
    concept = str(draft.get("concept") or draft.get("title") or "Retro Sci-Fi")
    out = INBOX_DIR / f"job.auto_redraft_{now_stamp()}.json"
    redraft_job = {
        "id": f"auto-redraft-{now_stamp()}",
        "task_type": "product_drafter",
        "target_profile": "research",
        "inputs": {
            "trend": concept,
            "feedback": feedback,
            "revision": revision + 1,
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    out.write_text(json.dumps(redraft_job, indent=2), encoding="utf-8")
    print(f"Art Director REFINE: queued {out}")


if __name__ == "__main__":
    main()
