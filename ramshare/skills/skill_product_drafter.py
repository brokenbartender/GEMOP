import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from base64 import b64decode
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
DRAFTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "drafts"
ASSETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "assets"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gemini_governance  # type: ignore


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_job(path: Path) -> Dict[str, Any]:
    # Tolerate UTF-8 BOM from editors generating JSON files.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pick_concept(job: Dict[str, Any]) -> str:
    # Accept multiple shapes to keep early pipeline flexible.
    if isinstance(job.get("input_data"), str) and job["input_data"].strip():
        return job["input_data"].strip()
    inputs = job.get("inputs") or {}
    for k in ("trend", "keyword", "concept"):
        v = inputs.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    if isinstance(inputs.get("keywords"), list) and inputs["keywords"]:
        first = inputs["keywords"][0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return "Retro Sci-Fi"


def pick_feedback(job: Dict[str, Any]) -> str:
    inputs = job.get("inputs") or {}
    v = inputs.get("feedback")
    if isinstance(v, str):
        return v.strip()
    return ""


def pick_revision(job: Dict[str, Any]) -> int:
    inputs = job.get("inputs") or {}
    try:
        return int(inputs.get("revision") or 0)
    except Exception:
        return 0


def slug(s: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in s)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "concept"


def image_cost_estimate_usd() -> float:
    try:
        return float(os.environ.get("DALLE_ESTIMATED_COST_USD", "0.08"))
    except Exception:
        return 0.08


def generate_real_image(prompt: str, out_path: Path) -> None:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise SystemExit(f"Missing dependency 'openai'. Install it in .venv. Details: {e}")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Product Drafter requires a real API key for Path B.")

    est = image_cost_estimate_usd()
    allowed = gemini_governance.enforce(
        budget_path=gemini_governance.default_budget_path(),
        kill_switch_path=gemini_governance.default_kill_switch_path(),
        audit_path=gemini_governance.default_audit_log_path(),
        action="generate product image (dall-e-3)",
        details=f"estimated_spend=${est:.2f}",
        estimated_spend_usd=est,
        write_audit=True,
    )
    if not allowed:
        raise SystemExit("Budget/Kill-switch gate blocked image generation.")

    client = OpenAI(api_key=api_key)
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
        )
    except Exception as e:
        gemini_governance.audit_log_append(
            gemini_governance.default_audit_log_path(),
            action="image generation failed (dall-e-3)",
            details=str(e),
            severity="CRITICAL",
        )
        raise SystemExit(f"Image generation failed: {e}")

    data0 = resp.data[0]
    if getattr(data0, "b64_json", None):
        out_path.write_bytes(b64decode(data0.b64_json))
    elif getattr(data0, "url", None):
        with urllib.request.urlopen(data0.url, timeout=60) as r:  # nosec - URL from API response
            out_path.write_bytes(r.read())
    else:
        raise SystemExit("Image API returned no usable image payload.")

    gemini_governance.record_spend(
        gemini_governance.default_budget_path(),
        amount_usd=est,
        reason="dall-e image generation",
        meta={"model": "dall-e-3", "asset_path": str(out_path)},
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Product drafter skill (live image generation)")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_job(job_path)
    job_id = str(job.get("id") or job_path.stem)
    concept = pick_concept(job)
    feedback = pick_feedback(job)
    revision = pick_revision(job)

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFTS_DIR / f"draft_{now_stamp()}.json"
    image_out = ASSETS_DIR / f"asset_{now_stamp()}.png"

    title = f"{concept} Tee"
    image_prompt = (
        f"Create a high-contrast POD t-shirt design for '{concept}'. "
        "Style: clean vector look, center composition, transparent background, "
        "print-ready, no copyrighted logos."
    )
    if feedback:
        image_prompt = image_prompt + f" Refinement guidance: {feedback}"
    generate_real_image(image_prompt, image_out)

    tags = [
        slug(concept),
        "pod",
        "tshirt",
        "gift-idea",
        "retro-style",
    ]

    draft = {
        "job_id": job_id,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "concept": concept,
        "revision": revision,
        "feedback_applied": feedback,
        "title": title,
        "mock_image_prompt": image_prompt,
        "asset_path": str(image_out),
        "tags": tags,
        "price_point": 24.99,
    }

    out.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    print(f"Product Draft generated: {out}")


if __name__ == "__main__":
    main()
