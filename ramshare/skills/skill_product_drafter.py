import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from base64 import b64decode
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
DRAFTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "drafts"
ASSETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "assets"
SCRIPTS_DIR = REPO_ROOT / "scripts"
LINEART_SCRIPT = SCRIPTS_DIR / "rb_lineart_generator.py"
PHOTO_STYLE_SCRIPT = SCRIPTS_DIR / "rb_photo_to_style.py"
CHECK_SCRIPT = SCRIPTS_DIR / "marketplace_image_check.py"
ANALYZE_SCRIPT = SCRIPTS_DIR / "analyze_png_lineart.py"
STYLE_PROFILE_PATH = REPO_ROOT / "data" / "redbubble" / "style_profile.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gemini_governance  # type: ignore


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def load_job(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pick_concept(job: Dict[str, Any]) -> str:
    if isinstance(job.get("input_data"), str) and job["input_data"].strip():
        return job["input_data"].strip()
    inputs = job.get("inputs") or {}
    for key in ("trend", "keyword", "concept", "theme"):
        v = inputs.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    if isinstance(inputs.get("keywords"), list) and inputs["keywords"]:
        first = inputs["keywords"][0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return "Minimal Geometric Symbol"


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


def pick_backend(job: Dict[str, Any]) -> str:
    inputs = job.get("inputs") or {}
    raw = inputs.get("image_backend") or os.environ.get("GEMINI_OP_ART_BACKEND") or "local_lineart"
    return str(raw).strip().lower()


def pick_location_brief(job: Dict[str, Any]) -> Dict[str, Any]:
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    brief = inputs.get("location_brief")
    if isinstance(brief, dict):
        return brief
    return {}


def pick_reference_image(job: Dict[str, Any]) -> str:
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    raw = inputs.get("reference_image_path") or inputs.get("reference_image") or ""
    if isinstance(raw, str):
        return raw.strip()
    return ""


def is_free_mode() -> bool:
    raw = os.environ.get("GEMINI_OP_FREE_MODE", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def allow_paid_art() -> bool:
    raw = os.environ.get("GEMINI_OP_ALLOW_PAID_ART", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


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


def style_profile_enabled() -> bool:
    raw = os.environ.get("GEMINI_OP_DISABLE_STYLE_PROFILE", "0").strip().lower()
    return raw not in ("1", "true", "yes", "on")


def resolve_style_profile_path() -> Path:
    raw = os.environ.get("GEMINI_OP_RB_STYLE_PROFILE", "").strip()
    if raw:
        return Path(raw).resolve()
    return STYLE_PROFILE_PATH


def load_style_profile(path: Path) -> Dict[str, Any]:
    if not path.exists() or not style_profile_enabled():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def style_prompt_guidance(profile: Dict[str, Any]) -> str:
    parts: List[str] = []
    mods = profile.get("prompt_modifiers") if isinstance(profile.get("prompt_modifiers"), list) else []
    for m in mods[:4]:
        if isinstance(m, str) and m.strip():
            parts.append(m.strip().rstrip("."))
    return ". ".join(parts).strip()


def style_token_tags(profile: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    tokens = profile.get("top_tokens") if isinstance(profile.get("top_tokens"), list) else []
    for t in tokens[:6]:
        if isinstance(t, str) and len(t.strip()) >= 3:
            out.append(t.strip().lower())
    return out


def style_render_mode(profile: Dict[str, Any]) -> str:
    over = profile.get("generator_overrides") if isinstance(profile.get("generator_overrides"), dict) else {}
    style = str(over.get("style") or "").strip().lower()
    if not style:
        return "sigil"
    if any(k in style for k in ("hybrid", "glyph", "complex")):
        return "hybrid"
    if style in ("sigil", "seal", "symbol"):
        return style
    return "sigil"


def call_script(args: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ))
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if err:
            output = f"{output}\n{err}".strip()
    return proc.returncode, output


def generate_local_lineart(
    concept: str,
    prompt: str,
    out_path: Path,
    *,
    style_profile_path: Path | None = None,
    style_mode: str = "sigil",
    location_brief: Dict[str, Any] | None = None,
) -> str:
    if not LINEART_SCRIPT.exists():
        raise SystemExit(f"Missing free generator script: {LINEART_SCRIPT}")
    cmd = [
        sys.executable,
        str(LINEART_SCRIPT),
        "--concept",
        concept,
        "--prompt",
        prompt,
        "--style",
        style_mode,
        "--width",
        "4500",
        "--height",
        "5400",
        "--out",
        str(out_path),
    ]
    tmp_location_json: Path | None = None
    if isinstance(location_brief, dict) and location_brief:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
                tf.write(json.dumps(location_brief, indent=2))
                tmp_location_json = Path(tf.name).resolve()
            cmd.extend(["--location-brief-json", str(tmp_location_json)])
        except Exception:
            tmp_location_json = None
    if style_profile_path is not None and style_profile_path.exists():
        cmd.extend(["--style-profile", str(style_profile_path)])
    try:
        rc, out = call_script(cmd)
        if rc != 0:
            raise SystemExit(f"Local line-art generation failed: {out}")
    finally:
        if tmp_location_json is not None:
            try:
                tmp_location_json.unlink(missing_ok=True)
            except Exception:
                pass
    return "local_lineart"


def generate_photo_stylized_lineart(
    reference_image: Path,
    out_path: Path,
    *,
    style_profile_path: Path | None = None,
    seed: int = 42,
    cycles: int = 14,
) -> str:
    if not PHOTO_STYLE_SCRIPT.exists():
        raise SystemExit(f"Missing photo style script: {PHOTO_STYLE_SCRIPT}")
    report_path = out_path.with_suffix(".photo_style.json")
    cmd = [
        sys.executable,
        str(PHOTO_STYLE_SCRIPT),
        "--image",
        str(reference_image),
        "--out",
        str(out_path),
        "--report",
        str(report_path),
        "--cycles",
        str(max(4, int(cycles))),
        "--seed",
        str(int(seed)),
    ]
    if style_profile_path is not None and style_profile_path.exists():
        cmd.extend(["--style-profile", str(style_profile_path)])
    rc, out = call_script(cmd)
    if rc != 0:
        raise SystemExit(f"Photo style conversion failed: {out}")
    return "photo_style_lineart"


def generate_sdwebui_image(prompt: str, out_path: Path) -> str:
    base_url = os.environ.get("SD_WEBUI_URL", "http://127.0.0.1:7860").rstrip("/")
    endpoint = f"{base_url}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "negative_prompt": "watermark, logo, text, signature, blurry, low quality",
        "width": 1024,
        "height": 1024,
        "steps": 28,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=75) as resp:  # nosec B310 - explicit local endpoint only
        body = json.loads(resp.read().decode("utf-8", errors="ignore"))
    images = body.get("images") if isinstance(body, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError("SD WebUI returned no images")

    raw = images[0]
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("SD WebUI image payload is empty")
    if "," in raw:
        raw = raw.split(",", 1)[1]
    out_path.write_bytes(b64decode(raw))

    # Normalize to marketplace-friendly print size.
    img = Image.open(out_path).convert("RGBA")
    img = img.resize((4500, 5400), Image.Resampling.LANCZOS)
    img.save(out_path, format="PNG")
    return "sdwebui"


def generate_real_image(prompt: str, out_path: Path) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise SystemExit(f"Missing dependency 'openai'. Install it in .venv. Details: {e}")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Product Drafter requires a real API key for paid backend.")

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
        with urllib.request.urlopen(data0.url, timeout=60) as r:  # nosec B310 - provider URL response
            out_path.write_bytes(r.read())
    else:
        raise SystemExit("Image API returned no usable image payload.")

    img = Image.open(out_path).convert("RGBA")
    img = img.resize((4500, 5400), Image.Resampling.LANCZOS)
    img.save(out_path, format="PNG")

    gemini_governance.record_spend(
        gemini_governance.default_budget_path(),
        amount_usd=est,
        reason="dall-e image generation",
        meta={"model": "dall-e-3", "asset_path": str(out_path)},
    )
    return "openai_dalle3"


def run_quality_checks(image_path: Path) -> Dict[str, str]:
    outputs: Dict[str, str] = {}
    if ANALYZE_SCRIPT.exists():
        analyze_path = image_path.with_suffix(".analysis.json")
        cmd = [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--image",
            str(image_path),
            "--json-out",
            str(analyze_path),
        ]
        rc, out = call_script(cmd)
        if rc == 0 and analyze_path.exists():
            outputs["analysis_json"] = str(analyze_path)
        elif out:
            outputs["analysis_error"] = out

    if CHECK_SCRIPT.exists():
        check_path = image_path.with_suffix(".preflight.json")
        cmd = [
            sys.executable,
            str(CHECK_SCRIPT),
            "--image",
            str(image_path),
            "--market",
            "redbubble",
            "--product",
            "tshirt",
            "--json-out",
            str(check_path),
        ]
        rc, out = call_script(cmd)
        if check_path.exists():
            outputs["preflight_json"] = str(check_path)
        if rc != 0 and out:
            outputs["preflight_error"] = out
    return outputs


def make_tags(concept: str) -> List[str]:
    stop = {
        "and",
        "the",
        "for",
        "with",
        "this",
        "that",
        "spots",
        "spot",
    }
    raw_tokens = [tok.strip("-_ ").lower() for tok in slug(concept).split("-")]
    tokens = [t for t in raw_tokens if len(t) >= 3 and t not in stop and not t.isdigit()]
    phrase_tokens = [x for x in re.findall(r"[a-z0-9]+", concept.lower()) if len(x) >= 3]
    phrases: List[str] = []
    for idx in range(0, max(0, len(phrase_tokens) - 1)):
        if phrase_tokens[idx] in stop or phrase_tokens[idx + 1] in stop:
            continue
        bg = f"{phrase_tokens[idx]} {phrase_tokens[idx + 1]}"
        if len(bg) >= 7:
            phrases.append(bg)
    fixed = [
        "line-art",
        "minimalist",
        "black-and-white",
        "symbolic",
        "print-ready",
        "transparent-background",
        "high-contrast",
    ]
    seen = set()
    out: List[str] = []
    for token in tokens + phrases + fixed:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out[:15]


def main() -> None:
    ap = argparse.ArgumentParser(description="Product drafter skill (free-first image generation)")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = load_job(job_path)
    job_id = str(job.get("id") or job_path.stem)
    concept = pick_concept(job)
    feedback = pick_feedback(job)
    revision = pick_revision(job)
    requested_backend = pick_backend(job)
    location_brief = pick_location_brief(job)
    reference_image_path = pick_reference_image(job)
    reference_image = Path(reference_image_path).resolve() if reference_image_path else Path("")
    style_profile_path = resolve_style_profile_path()
    style_profile = load_style_profile(style_profile_path)
    style_guidance = style_prompt_guidance(style_profile)
    style_mode = style_render_mode(style_profile)
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}
    trend_terms = inputs.get("trend_terms") if isinstance(inputs.get("trend_terms"), list) else []
    trend_terms = [str(x).strip().lower() for x in trend_terms if isinstance(x, str) and str(x).strip()]
    trend_terms = list(dict.fromkeys(trend_terms))[:8]

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFTS_DIR / f"draft_{now_stamp()}.json"
    image_out = ASSETS_DIR / f"asset_{now_stamp()}.png"

    title = f"{concept} Tee"
    image_prompt = (
        f"Create a high-contrast POD t-shirt design for '{concept}'. "
        "Style: clean vector line-art, center composition, transparent background, "
        "print-ready at 4500x5400, bold readable strokes, no copyrighted logos, no celebrity likeness."
    )
    if isinstance(location_brief, dict) and location_brief:
        spot = str(location_brief.get("spot") or "").strip()
        cues = location_brief.get("architecture_cues") if isinstance(location_brief.get("architecture_cues"), list) else []
        cues = [str(x).strip() for x in cues if isinstance(x, str) and str(x).strip()][:5]
        if spot and bool(location_brief.get("verified")):
            image_prompt = image_prompt + f" Keep '{spot}' real and recognizable from the real-world location."
        if cues:
            image_prompt = image_prompt + f" Include recognizable cues: {', '.join(cues)}."
        if bool(location_brief.get("has_geometry_outline")):
            image_prompt = image_prompt + " Use an aerial map-outline with accurate proportions from real geography."
            style_mode = "landmark"
        elif any(x in concept.lower() for x in ("aerial", "outline", "map-accurate", "landmark")):
            style_mode = "landmark"
    if feedback:
        image_prompt = image_prompt + f" Refinement guidance: {feedback}"
    if style_guidance:
        image_prompt = image_prompt + f" Style profile anchors: {style_guidance}."
    if trend_terms:
        image_prompt = image_prompt + f" Trend anchors: {', '.join(trend_terms[:5])}."

    free_mode = is_free_mode()
    backend_used = "local_lineart"
    backend_errors: List[str] = []

    if reference_image_path and reference_image.exists():
        backend_used = generate_photo_stylized_lineart(
            reference_image=reference_image,
            out_path=image_out,
            style_profile_path=style_profile_path if style_profile else None,
            seed=42 + max(0, int(revision)),
            cycles=14,
        )
    elif requested_backend in ("sdwebui", "stable-diffusion"):
        try:
            backend_used = generate_sdwebui_image(image_prompt, image_out)
        except Exception as e:
            backend_errors.append(f"sdwebui fallback: {e}")
            backend_used = generate_local_lineart(
                concept,
                image_prompt,
                image_out,
                style_profile_path=style_profile_path if style_profile else None,
                style_mode=style_mode,
                location_brief=location_brief,
            )
    elif requested_backend in ("openai", "dalle", "dall-e-3"):
        if free_mode and not allow_paid_art():
            backend_errors.append("paid backend requested but blocked in free mode")
            backend_used = generate_local_lineart(
                concept,
                image_prompt,
                image_out,
                style_profile_path=style_profile_path if style_profile else None,
                style_mode=style_mode,
                location_brief=location_brief,
            )
        else:
            backend_used = generate_real_image(image_prompt, image_out)
    else:
        backend_used = generate_local_lineart(
            concept,
            image_prompt,
            image_out,
            style_profile_path=style_profile_path if style_profile else None,
            style_mode=style_mode,
            location_brief=location_brief,
        )

    quality_outputs = run_quality_checks(image_out)
    tags = make_tags(concept)
    tags = list(dict.fromkeys(tags + trend_terms + style_token_tags(style_profile)))[:15]

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
        "image_backend_requested": requested_backend,
        "image_backend_used": backend_used,
        "free_mode": free_mode,
        "backend_warnings": backend_errors,
        "quality_outputs": quality_outputs,
        "style_profile_used": str(style_profile_path) if style_profile else "",
        "style_profile_name": str(style_profile.get("style_name") or "") if style_profile else "",
        "style_render_mode": style_mode,
        "trend_terms": trend_terms,
        "location_brief": location_brief if isinstance(location_brief, dict) else {},
        "source_reference_image": str(reference_image) if reference_image_path else "",
    }

    out.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    print(f"Product Draft generated: {out}")


if __name__ == "__main__":
    main()
