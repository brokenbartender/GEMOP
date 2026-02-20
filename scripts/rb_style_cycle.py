from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rb_style_train import (
    DEFAULT_EXTRACT_DIR,
    DEFAULT_PROFILE_OUT,
    analyze_style_image,
    extract_images_from_zip,
    list_images,
    summarize_metrics,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LINEART_SCRIPT = REPO_ROOT / "scripts" / "rb_lineart_generator.py"
REPORT_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
CALIBRATION_DIR = REPO_ROOT / "data" / "redbubble" / "style_calibration"
DEFAULT_THEMES = [
    "trendy bar downtown detroit michigan",
    "hidden coffee shop ann arbor michigan",
    "sleeping bear dunes scenic overlook",
    "pictured rocks kayak cove michigan",
    "mackinac island ferry dock",
    "tahquamenon falls waterfall trail",
    "grand rapids riverwalk nightlife",
    "lakeshore campground at sunset",
]
METRIC_WEIGHTS = {
    "alpha_ratio": 1.4,
    "edge_density": 1.3,
    "bbox_fill_ratio": 1.2,
    "symmetry_x": 1.0,
    "symmetry_y": 1.0,
    "component_count": 1.5,
    "stroke_to_fill_ratio": 1.4,
}
STYLE_CHOICES = ["sigil", "symbol", "sigil_hybrid"]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback or {}


def clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _clean_range(raw: Any, default: Tuple[int, int], lo: int, hi: int) -> List[int]:
    if isinstance(raw, Sequence) and len(raw) == 2:
        try:
            a = clamp_int(int(raw[0]), lo, hi)
            b = clamp_int(int(raw[1]), lo, hi)
            return [min(a, b), max(a, b)]
        except Exception:
            pass
    a, b = default
    return [clamp_int(a, lo, hi), clamp_int(b, lo, hi)]


def sanitize_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    style = str(raw.get("style") or "sigil").strip().lower()
    if style not in STYLE_CHOICES:
        style = "sigil"
    return {
        "style": style,
        "ring_count_range": _clean_range(raw.get("ring_count_range"), (4, 7), 2, 12),
        "rays_range": _clean_range(raw.get("rays_range"), (12, 20), 4, 36),
        "nodes_range": _clean_range(raw.get("nodes_range"), (18, 34), 4, 80),
        "stroke_px_range": _clean_range(raw.get("stroke_px_range"), (2, 5), 1, 20),
        "overlay_lines_range": _clean_range(raw.get("overlay_lines_range"), (10, 20), 0, 64),
        "overlay_arcs_range": _clean_range(raw.get("overlay_arcs_range"), (8, 16), 0, 64),
        "center_jitter_px": clamp_int(int(raw.get("center_jitter_px") or 0), 0, 48),
    }


def mutate_range(base: Sequence[int], *, rng: random.Random, lo: int, hi: int, scale: float) -> List[int]:
    a = int(base[0])
    b = int(base[1])
    center = (a + b) / 2.0
    width = max(1.0, (b - a) / 2.0)
    center += rng.uniform(-1.0, 1.0) * width * max(0.25, scale)
    width *= 1.0 + rng.uniform(-0.35, 0.35) * max(0.25, scale)
    width = max(1.0, width)
    left = clamp_int(int(round(center - width)), lo, hi)
    right = clamp_int(int(round(center + width)), lo, hi)
    if left > right:
        left, right = right, left
    return [left, right]


def mutate_overrides(base: Dict[str, Any], *, rng: random.Random, scale: float) -> Dict[str, Any]:
    cur = sanitize_overrides(base)
    out = dict(cur)
    if rng.random() < 0.12 * max(0.4, scale):
        out["style"] = rng.choice(STYLE_CHOICES)
    out["ring_count_range"] = mutate_range(cur["ring_count_range"], rng=rng, lo=2, hi=12, scale=scale)
    out["rays_range"] = mutate_range(cur["rays_range"], rng=rng, lo=4, hi=36, scale=scale)
    out["nodes_range"] = mutate_range(cur["nodes_range"], rng=rng, lo=4, hi=80, scale=scale)
    out["stroke_px_range"] = mutate_range(cur["stroke_px_range"], rng=rng, lo=1, hi=20, scale=scale)
    out["overlay_lines_range"] = mutate_range(cur["overlay_lines_range"], rng=rng, lo=0, hi=64, scale=scale)
    out["overlay_arcs_range"] = mutate_range(cur["overlay_arcs_range"], rng=rng, lo=0, hi=64, scale=scale)
    jitter = int(cur.get("center_jitter_px") or 0)
    jitter += int(round(rng.uniform(-8.0, 8.0) * max(0.3, scale)))
    out["center_jitter_px"] = clamp_int(jitter, 0, 48)
    return sanitize_overrides(out)


def metric_norm(ref: Dict[str, Dict[str, float]], key: str) -> float:
    slot = ref.get(key) or {}
    p10 = float(slot.get("p10") or 0.0)
    p90 = float(slot.get("p90") or 0.0)
    span = abs(p90 - p10)
    if span > 1e-6:
        return span
    med = abs(float(slot.get("median") or 0.0))
    return max(1e-3, med * 0.25, 1e-3)


def metric_median(summary: Dict[str, Dict[str, float]], key: str) -> float:
    return float((summary.get(key) or {}).get("median") or 0.0)


def style_distance(ref: Dict[str, Dict[str, float]], got: Dict[str, Dict[str, float]]) -> float:
    total_w = 0.0
    total = 0.0
    for key, weight in METRIC_WEIGHTS.items():
        rv = metric_median(ref, key)
        gv = metric_median(got, key)
        norm = metric_norm(ref, key)
        d = abs(gv - rv) / max(norm, 1e-6)
        total += d * float(weight)
        total_w += float(weight)
    if total_w <= 0:
        return 999.0
    return total / total_w


def diversity_score(rows: Sequence[Dict[str, Any]]) -> float:
    if len(rows) <= 1:
        return 0.0
    keys = ["alpha_ratio", "edge_density", "component_count", "stroke_to_fill_ratio"]
    score = 0.0
    used = 0
    for key in keys:
        vals = [float(r.get(key) or 0.0) for r in rows if isinstance(r.get(key), (int, float))]
        if len(vals) <= 1:
            continue
        vmin = min(vals)
        vmax = max(vals)
        mean = sum(vals) / float(len(vals))
        scale = max(1e-6, abs(mean), 0.01)
        score += min(1.0, (vmax - vmin) / scale)
        used += 1
    if used == 0:
        return 0.0
    return score / float(used)


def ensure_reference_summary(
    profile: Dict[str, Any],
    *,
    zip_path: Path | None,
    dataset_dir: Path | None,
    extract_dir: Path,
    max_images: int,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Any]]:
    if zip_path is None and dataset_dir is None:
        summary = profile.get("metrics_summary")
        if isinstance(summary, dict) and summary:
            return summary, {"source_mode": "profile_metrics"}
        raise SystemExit("No reference source found. Provide --zip or --dataset-dir, or ensure style profile has metrics_summary.")

    if zip_path is not None:
        if not zip_path.exists():
            raise SystemExit(f"Reference ZIP not found: {zip_path}")
        images = extract_images_from_zip(zip_path, extract_dir=extract_dir, max_images=max_images)
        mode = "zip"
    else:
        assert dataset_dir is not None
        if not dataset_dir.exists():
            raise SystemExit(f"Dataset directory not found: {dataset_dir}")
        images = list_images(dataset_dir, max_images=max_images)
        mode = "dataset"

    if not images:
        raise SystemExit("No reference images found.")
    rows = [analyze_style_image(p) for p in images]
    summary = summarize_metrics(rows)
    return summary, {"source_mode": mode, "image_count": len(rows), "sample_paths": [str(p) for p in images[:12]]}


def call_lineart_generator(
    *,
    concept: str,
    prompt: str,
    out_path: Path,
    profile_path: Path,
    style: str,
    width: int,
    height: int,
) -> None:
    cmd = [
        sys.executable,
        str(LINEART_SCRIPT),
        "--concept",
        concept,
        "--prompt",
        prompt,
        "--style",
        style,
        "--width",
        str(width),
        "--height",
        str(height),
        "--out",
        str(out_path),
        "--style-profile",
        str(profile_path),
    ]
    cp = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
    if cp.returncode != 0:
        out = "\n".join(x for x in [cp.stdout.strip(), cp.stderr.strip()] if x).strip()
        raise RuntimeError(f"lineart generation failed: {out}")


def evaluate_overrides(
    *,
    base_profile: Dict[str, Any],
    overrides: Dict[str, Any],
    ref_summary: Dict[str, Dict[str, float]],
    themes: Sequence[str],
    width: int,
    height: int,
    work_dir: Path,
) -> Dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_profile = dict(base_profile)
    temp_profile["generator_overrides"] = sanitize_overrides(overrides)
    temp_profile_path = work_dir / "candidate_profile.json"
    temp_profile_path.write_text(json.dumps(temp_profile, indent=2), encoding="utf-8")

    rows: List[Dict[str, Any]] = []
    for idx, theme in enumerate(themes):
        image_path = work_dir / f"sample_{idx:02d}.png"
        prompt = (
            f"Minimal black-and-white linework representation of {theme}; "
            "transparent background, clean strokes, print-ready composition."
        )
        call_lineart_generator(
            concept=theme,
            prompt=prompt,
            out_path=image_path,
            profile_path=temp_profile_path,
            style=str(overrides.get("style") or "sigil"),
            width=width,
            height=height,
        )
        row = analyze_style_image(image_path)
        rows.append(row)

    summary = summarize_metrics(rows)
    distance = style_distance(ref_summary, summary)
    diversity = diversity_score(rows)
    warn_count = sum(1 for r in rows if isinstance(r.get("flags"), list) and len(r.get("flags") or []) > 0)
    score = 100.0 - (distance * 26.0) + (diversity * 8.0) - (warn_count * 1.5)
    return {
        "score": round(score, 6),
        "distance": round(distance, 6),
        "diversity": round(diversity, 6),
        "warn_count": int(warn_count),
        "sample_count": len(rows),
        "overrides": sanitize_overrides(overrides),
        "summary": summary,
    }


def parse_themes(raw: str, file_path: str) -> List[str]:
    if str(file_path).strip():
        path = Path(file_path).resolve()
        if not path.exists():
            raise SystemExit(f"Themes file not found: {path}")
        out = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
        if out:
            return out
    if str(raw).strip():
        rows = [x.strip() for x in raw.split(",")]
        rows = [x for x in rows if x]
        if rows:
            return rows
    return list(DEFAULT_THEMES)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run style calibration cycles for Redbubble line-art generation.")
    ap.add_argument("--style-profile", default=str(DEFAULT_PROFILE_OUT))
    ap.add_argument("--zip", default="", help="Reference ZIP with your artwork.")
    ap.add_argument("--dataset-dir", default="", help="Reference artwork folder.")
    ap.add_argument("--extract-dir", default=str(DEFAULT_EXTRACT_DIR))
    ap.add_argument("--cycles", type=int, default=6, help="Calibration cycles.")
    ap.add_argument("--candidates-per-cycle", type=int, default=4)
    ap.add_argument("--max-images", type=int, default=320)
    ap.add_argument("--themes", default="", help="Comma-separated theme prompts for variety test.")
    ap.add_argument("--themes-file", default="", help="One prompt per line.")
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--height", type=int, default=1800)
    ap.add_argument("--seed", type=int, default=20260219)
    ap.add_argument("--apply", action="store_true", help="Write best overrides back into style profile.")
    args = ap.parse_args()

    rng = random.Random(int(args.seed))
    style_profile_path = Path(args.style_profile).resolve()
    if not style_profile_path.exists():
        raise SystemExit(f"Style profile not found: {style_profile_path}")

    zip_path = Path(args.zip).resolve() if str(args.zip).strip() else None
    dataset_dir = Path(args.dataset_dir).resolve() if str(args.dataset_dir).strip() else None
    extract_dir = Path(args.extract_dir).resolve()
    themes = parse_themes(args.themes, args.themes_file)

    profile = load_json(style_profile_path, fallback={})
    if not profile:
        raise SystemExit("Style profile JSON is empty or unreadable.")

    ref_summary, ref_meta = ensure_reference_summary(
        profile,
        zip_path=zip_path,
        dataset_dir=dataset_dir,
        extract_dir=extract_dir,
        max_images=int(args.max_images),
    )

    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = CALIBRATION_DIR / f"cycle_{now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    base_overrides = sanitize_overrides(profile.get("generator_overrides") if isinstance(profile.get("generator_overrides"), dict) else {})
    best = evaluate_overrides(
        base_profile=profile,
        overrides=base_overrides,
        ref_summary=ref_summary,
        themes=themes,
        width=int(args.width),
        height=int(args.height),
        work_dir=run_dir / "base",
    )
    history: List[Dict[str, Any]] = [{"cycle": 0, "best": best}]
    global_best = dict(best)

    for cycle_idx in range(1, max(1, int(args.cycles)) + 1):
        cycle_rows: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = [sanitize_overrides(global_best.get("overrides") or base_overrides)]
        scale = max(0.2, 1.0 - (float(cycle_idx - 1) / max(1.0, float(args.cycles))))
        for _ in range(max(1, int(args.candidates_per_cycle) - 1)):
            candidates.append(mutate_overrides(candidates[0], rng=rng, scale=scale))

        best_cycle = None
        for idx, cand in enumerate(candidates):
            eval_row = evaluate_overrides(
                base_profile=profile,
                overrides=cand,
                ref_summary=ref_summary,
                themes=themes,
                width=int(args.width),
                height=int(args.height),
                work_dir=run_dir / f"cycle_{cycle_idx:02d}" / f"cand_{idx:02d}",
            )
            eval_row["candidate_index"] = idx
            cycle_rows.append(eval_row)
            if best_cycle is None or float(eval_row["score"]) > float(best_cycle["score"]):
                best_cycle = eval_row

        assert best_cycle is not None
        improved = float(best_cycle["score"]) > float(global_best["score"])
        if improved:
            global_best = dict(best_cycle)
        history.append(
            {
                "cycle": cycle_idx,
                "scale": round(scale, 6),
                "best": best_cycle,
                "improved_global": bool(improved),
            }
        )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "style_profile_path": str(style_profile_path),
        "ref_meta": ref_meta,
        "themes": themes,
        "cycles": int(args.cycles),
        "candidates_per_cycle": int(args.candidates_per_cycle),
        "width": int(args.width),
        "height": int(args.height),
        "seed": int(args.seed),
        "baseline": best,
        "global_best": global_best,
        "history": history,
    }
    report_path = REPORT_DIR / f"rb_style_cycle_{now_stamp()}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.apply:
        updated = dict(profile)
        updated["generator_overrides"] = dict(global_best.get("overrides") or base_overrides)
        updated["style_cycle"] = {
            "last_run_at": datetime.now().isoformat(timespec="seconds"),
            "report_path": str(report_path),
            "baseline_score": float(best["score"]),
            "best_score": float(global_best["score"]),
            "best_distance": float(global_best["distance"]),
            "best_diversity": float(global_best["diversity"]),
            "themes": themes,
            "cycles": int(args.cycles),
        }
        style_profile_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")

    # Keep only report + profile metadata; generated candidate images are intermediate.
    try:
        shutil.rmtree(run_dir)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "ok": True,
                "report": str(report_path),
                "applied": bool(args.apply),
                "baseline_score": float(best["score"]),
                "best_score": float(global_best["score"]),
                "best_distance": float(global_best["distance"]),
                "themes_tested": len(themes),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
