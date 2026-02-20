from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageFilter, ImageStat


def alpha_ratio(img: Image.Image) -> float:
    rgba = img.convert("RGBA")
    alpha = rgba.split()[-1]
    hist = alpha.histogram()
    total = float(sum(hist)) or 1.0
    opaque = float(sum(hist[1:]))
    return opaque / total


def edge_density(img: Image.Image, threshold: int = 32) -> float:
    rgba = img.convert("RGBA")
    alpha = rgba.split()[-1]
    gray = alpha if "A" in rgba.mode else rgba.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    hist = edges.histogram()
    total = float(sum(hist)) or 1.0
    strong = float(sum(hist[threshold:]))
    return strong / total


def unique_color_count(img: Image.Image) -> int:
    rgba = img.convert("RGBA")
    small = rgba.resize((min(512, rgba.width), min(512, rgba.height)), Image.Resampling.BILINEAR)
    colors = small.getcolors(maxcolors=512 * 512)
    if colors is None:
        return 512 * 512
    return len(colors)


def lineart_quality_flags(metrics: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    a = float(metrics.get("alpha_ratio") or 0.0)
    e = float(metrics.get("edge_density") or 0.0)
    c = int(metrics.get("unique_colors") or 0)
    if a < 0.005:
        flags.append("too_sparse")
    if a > 0.75:
        flags.append("too_dense")
    if e < 0.006:
        flags.append("low_edge_definition")
    if c > 256:
        flags.append("too_many_colors_for_lineart")
    return flags


def analyze_image(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        gray = rgba.split()[-1]
        stat = ImageStat.Stat(gray)
        metrics: Dict[str, Any] = {
            "path": str(path),
            "width_px": rgba.width,
            "height_px": rgba.height,
            "file_size_mb": round(path.stat().st_size / (1024.0 * 1024.0), 4),
            "alpha_ratio": round(alpha_ratio(rgba), 6),
            "edge_density": round(edge_density(rgba), 6),
            "unique_colors": int(unique_color_count(rgba)),
            "grayscale_mean": round(float(stat.mean[0]), 4),
            "grayscale_stddev": round(float(stat.stddev[0]), 4),
        }
    metrics["flags"] = lineart_quality_flags(metrics)
    metrics["status"] = "pass" if not metrics["flags"] else "warn"
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze PNG line-art quality metrics.")
    ap.add_argument("--image", required=True, help="Path to PNG image.")
    ap.add_argument("--json-out", default="", help="Optional output path for JSON report.")
    args = ap.parse_args()

    path = Path(args.image).resolve()
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "analysis": analyze_image(path),
    }
    if str(args.json_out).strip():
        out = Path(args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
