from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageOps

from analyze_png_lineart import analyze_image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_OUT = REPO_ROOT / "data" / "redbubble" / "style_profile.json"
DEFAULT_EXTRACT_DIR = REPO_ROOT / "data" / "redbubble" / "style_dataset" / "extracted"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
TOKEN_STOP = {
    "and",
    "art",
    "design",
    "draft",
    "final",
    "file",
    "img",
    "image",
    "line",
    "minimal",
    "new",
    "png",
    "rgb",
    "scan",
    "sketch",
    "style",
    "the",
    "v1",
    "v2",
    "v3",
}


def clamp_float(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def slug(text: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "art"


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def list_images(dataset_dir: Path, max_images: int) -> List[Path]:
    files = [p for p in sorted(dataset_dir.rglob("*")) if p.is_file() and is_image_path(p)]
    return files[: max(1, int(max_images))]


def extract_images_from_zip(zip_path: Path, extract_dir: Path, max_images: int) -> List[Path]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    out: List[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.infolist() if not m.is_dir() and is_image_path(Path(m.filename))]
        for idx, member in enumerate(members[: max(1, int(max_images))], start=1):
            name = Path(member.filename)
            stem = slug(name.stem)[:48]
            ext = name.suffix.lower() if name.suffix.lower() in IMAGE_EXTS else ".png"
            target = extract_dir / f"{idx:04d}_{stem}{ext}"
            with zf.open(member, "r") as src:
                target.write_bytes(src.read())
            out.append(target)
    return out


def quantiles(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0, "p10": 0.0, "p90": 0.0}
    arr = sorted(float(v) for v in values)

    def q(p: float) -> float:
        if len(arr) == 1:
            return arr[0]
        idx = (len(arr) - 1) * p
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return arr[lo]
        w = idx - lo
        return arr[lo] * (1.0 - w) + arr[hi] * w

    return {
        "min": arr[0],
        "max": arr[-1],
        "mean": sum(arr) / float(len(arr)),
        "median": q(0.5),
        "p10": q(0.1),
        "p90": q(0.9),
    }


def _component_count(alpha_img: Image.Image, size: int = 192) -> int:
    alpha = alpha_img.resize((size, size), Image.Resampling.BILINEAR)
    pix = alpha.load()
    visited = [[False] * size for _ in range(size)]
    components = 0

    for y in range(size):
        for x in range(size):
            if visited[y][x]:
                continue
            visited[y][x] = True
            if pix[x, y] <= 8:
                continue
            components += 1
            q: deque[Tuple[int, int]] = deque()
            q.append((x, y))
            while q:
                cx, cy = q.popleft()
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= size or ny >= size:
                        continue
                    if visited[ny][nx]:
                        continue
                    visited[ny][nx] = True
                    if pix[nx, ny] > 8:
                        q.append((nx, ny))
    return components


def symmetry_score(alpha_img: Image.Image, axis: str = "x", size: int = 256) -> float:
    alpha = alpha_img.resize((size, size), Image.Resampling.BILINEAR)
    if axis == "x":
        mirrored = ImageOps.mirror(alpha)
    else:
        mirrored = ImageOps.flip(alpha)
    diff = ImageChops.difference(alpha, mirrored)
    mean = float(sum(diff.histogram()[i] * i for i in range(256))) / float(size * size)
    return float(clamp_float(1.0 - (mean / 255.0), 0.0, 1.0))


def bbox_fill_ratio(alpha_img: Image.Image) -> float:
    bbox = alpha_img.getbbox()
    if bbox is None:
        return 0.0
    x0, y0, x1, y1 = bbox
    area = max(1, (x1 - x0) * (y1 - y0))
    total = max(1, alpha_img.width * alpha_img.height)
    return float(area) / float(total)


def tokenize_path(path: Path) -> List[str]:
    raw = re.split(r"[^a-z0-9]+", path.stem.lower())
    out: List[str] = []
    for t in raw:
        if len(t) < 3:
            continue
        if t.isdigit():
            continue
        if t in TOKEN_STOP:
            continue
        out.append(t)
    return out


def analyze_style_image(path: Path) -> Dict[str, Any]:
    base = analyze_image(path)
    if isinstance(base.get("analysis"), dict):
        metrics = dict(base.get("analysis") or {})
    else:
        metrics = dict(base)
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        alpha = rgba.split()[-1]
        width, height = rgba.size
        occ = float(metrics.get("alpha_ratio") or 0.0)
        edge_density = float(metrics.get("edge_density") or 0.0)
        stroke_to_fill = edge_density / max(occ, 1e-6)
        metrics.update(
            {
                "width_px": int(width),
                "height_px": int(height),
                "aspect_ratio": round(float(width) / float(height), 6) if height else 0.0,
                "bbox_fill_ratio": round(bbox_fill_ratio(alpha), 6),
                "symmetry_x": round(symmetry_score(alpha, axis="x"), 6),
                "symmetry_y": round(symmetry_score(alpha, axis="y"), 6),
                "component_count": int(_component_count(alpha)),
                "stroke_to_fill_ratio": round(float(stroke_to_fill), 6),
            }
        )
    return metrics


def summarize_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    keys = [
        "alpha_ratio",
        "edge_density",
        "unique_colors",
        "grayscale_mean",
        "grayscale_stddev",
        "aspect_ratio",
        "bbox_fill_ratio",
        "symmetry_x",
        "symmetry_y",
        "component_count",
        "stroke_to_fill_ratio",
        "width_px",
        "height_px",
    ]
    out: Dict[str, Dict[str, float]] = {}
    for key in keys:
        vals: List[float] = []
        for row in rows:
            v = row.get(key)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        q = quantiles(vals)
        out[key] = {k: round(v, 6) for k, v in q.items()}
    return out


def derive_prompt_modifiers(summary: Dict[str, Dict[str, float]], tokens: Sequence[str]) -> List[str]:
    modifiers: List[str] = [
        "minimal black and white line art",
        "transparent background",
        "clean vector-like strokes",
    ]
    alpha_med = float((summary.get("alpha_ratio") or {}).get("median") or 0.0)
    sym = (
        float((summary.get("symmetry_x") or {}).get("median") or 0.0)
        + float((summary.get("symmetry_y") or {}).get("median") or 0.0)
    ) / 2.0
    colors = float((summary.get("unique_colors") or {}).get("median") or 0.0)
    comp = float((summary.get("component_count") or {}).get("median") or 0.0)
    bbox = float((summary.get("bbox_fill_ratio") or {}).get("median") or 0.0)

    if colors <= 12:
        modifiers.append("strict monochrome output")
    if sym >= 0.72:
        modifiers.append("balanced symmetry and radial harmony")
    if alpha_med <= 0.2:
        modifiers.append("generous negative space")
    if bbox <= 0.55:
        modifiers.append("centered composition with wide safe margins")
    if comp >= 12:
        modifiers.append("dense decorative micro-details")

    motif_tokens = [t for t in tokens if len(t) >= 3][:5]
    if motif_tokens:
        modifiers.append("motif hints: " + ", ".join(motif_tokens))
    return modifiers


def derive_generator_overrides(summary: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    edge = float((summary.get("edge_density") or {}).get("median") or 0.01)
    alpha = float((summary.get("alpha_ratio") or {}).get("median") or 0.1)
    sym = (
        float((summary.get("symmetry_x") or {}).get("median") or 0.0)
        + float((summary.get("symmetry_y") or {}).get("median") or 0.0)
    ) / 2.0
    comp = float((summary.get("component_count") or {}).get("median") or 8.0)
    stroke_fill = float((summary.get("stroke_to_fill_ratio") or {}).get("median") or 0.12)

    rings_mid = clamp_int(int(round(4 + (edge * 40))), 3, 9)
    rays_mid = clamp_int(int(round(12 + (sym * 10))), 10, 24)
    nodes_mid = clamp_int(int(round(16 + comp)), 14, 42)
    lines_mid = clamp_int(int(round(8 + (comp * 0.7))), 6, 30)
    arcs_mid = clamp_int(int(round(6 + (edge * 150))), 4, 24)
    stroke_mid = clamp_int(int(round(2 + (stroke_fill * 40))), 2, 8)
    jitter = clamp_int(int(round((1.0 - sym) * 24)), 2, 18)

    overlay_enabled = edge >= 0.010
    style = "sigil_hybrid" if overlay_enabled else "sigil"
    if alpha < 0.06:
        style = "symbol"

    return {
        "style": style,
        "ring_count_range": [max(3, rings_mid - 1), min(10, rings_mid + 1)],
        "rays_range": [max(8, rays_mid - 3), min(28, rays_mid + 3)],
        "nodes_range": [max(10, nodes_mid - 5), min(48, nodes_mid + 5)],
        "stroke_px_range": [max(2, stroke_mid - 1), min(10, stroke_mid + 1)],
        "overlay_lines_range": [0, 0] if not overlay_enabled else [max(6, lines_mid - 4), min(36, lines_mid + 4)],
        "overlay_arcs_range": [0, 0] if not overlay_enabled else [max(4, arcs_mid - 3), min(28, arcs_mid + 3)],
        "center_jitter_px": jitter,
    }


def build_profile(
    image_paths: Sequence[Path],
    *,
    zip_path: Path | None,
    dataset_dir: Path | None,
) -> Dict[str, Any]:
    analyzed: List[Dict[str, Any]] = []
    token_counter: Counter[str] = Counter()
    for p in image_paths:
        try:
            metrics = analyze_style_image(p)
            metrics["path"] = str(p)
            analyzed.append(metrics)
            token_counter.update(tokenize_path(p))
        except Exception:
            continue
    if not analyzed:
        raise RuntimeError("No readable images were analyzed.")

    summary = summarize_metrics(analyzed)
    tokens = [t for t, _ in token_counter.most_common(20)]
    prompt_modifiers = derive_prompt_modifiers(summary, tokens=tokens)
    generator_overrides = derive_generator_overrides(summary)

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "style_name": "brokenarrowmi_lineart_profile_v1",
        "source": {
            "zip_path": str(zip_path) if zip_path else "",
            "dataset_dir": str(dataset_dir) if dataset_dir else "",
            "image_count": len(analyzed),
            "samples": [str(x["path"]) for x in analyzed[:12]],
        },
        "top_tokens": tokens,
        "prompt_modifiers": prompt_modifiers,
        "generator_overrides": generator_overrides,
        "metrics_summary": summary,
        "qa_targets": {
            "alpha_ratio_range": [
                float((summary.get("alpha_ratio") or {}).get("p10") or 0.0),
                float((summary.get("alpha_ratio") or {}).get("p90") or 0.0),
            ],
            "edge_density_range": [
                float((summary.get("edge_density") or {}).get("p10") or 0.0),
                float((summary.get("edge_density") or {}).get("p90") or 0.0),
            ],
            "unique_colors_max": float((summary.get("unique_colors") or {}).get("p90") or 0.0),
            "symmetry_floor": float(
                min(
                    (summary.get("symmetry_x") or {}).get("p10") or 0.0,
                    (summary.get("symmetry_y") or {}).get("p10") or 0.0,
                )
            ),
        },
        "notes": [
            "Generated from existing shop artwork to drive consistent style output.",
            "Use with scripts/rb_lineart_generator.py via --style-profile.",
            "Product drafter auto-loads this file when present.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Train a reusable Redbubble style profile from local artwork.")
    ap.add_argument("--zip", default="", help="Path to a ZIP containing reference artwork.")
    ap.add_argument("--dataset-dir", default="", help="Path to a folder containing reference artwork.")
    ap.add_argument("--extract-dir", default=str(DEFAULT_EXTRACT_DIR), help="Where ZIP images are extracted.")
    ap.add_argument("--out-profile", default=str(DEFAULT_PROFILE_OUT), help="Output style profile JSON path.")
    ap.add_argument("--max-images", type=int, default=400)
    args = ap.parse_args()

    zip_path = Path(args.zip).resolve() if str(args.zip).strip() else None
    dataset_dir = Path(args.dataset_dir).resolve() if str(args.dataset_dir).strip() else None
    extract_dir = Path(args.extract_dir).resolve()
    out_profile = Path(args.out_profile).resolve()

    if zip_path is None and dataset_dir is None:
        raise SystemExit("Provide --zip or --dataset-dir.")

    if zip_path is not None:
        if not zip_path.exists():
            raise SystemExit(f"ZIP not found: {zip_path}")
        image_paths = extract_images_from_zip(zip_path=zip_path, extract_dir=extract_dir, max_images=int(args.max_images))
        dataset_for_profile = extract_dir
    else:
        assert dataset_dir is not None
        if not dataset_dir.exists():
            raise SystemExit(f"Dataset directory not found: {dataset_dir}")
        image_paths = list_images(dataset_dir=dataset_dir, max_images=int(args.max_images))
        dataset_for_profile = dataset_dir

    if not image_paths:
        raise SystemExit("No images found to train style profile.")

    profile = build_profile(image_paths, zip_path=zip_path, dataset_dir=dataset_for_profile)
    out_profile.parent.mkdir(parents=True, exist_ok=True)
    out_profile.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    summary = {
        "ok": True,
        "profile_path": str(out_profile),
        "image_count": int((profile.get("source") or {}).get("image_count") or 0),
        "style_name": str(profile.get("style_name") or ""),
        "dataset_dir": str(dataset_for_profile),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
