from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw


def stable_seed(*parts: str) -> int:
    base = "|".join(parts).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(base).hexdigest()
    return int(digest[:16], 16)


def random_point(rng: random.Random, width: int, height: int) -> tuple[int, int]:
    return rng.randint(0, width - 1), rng.randint(0, height - 1)


def _int_range(raw: Any, default: Tuple[int, int], lo: int, hi: int) -> Tuple[int, int]:
    if isinstance(raw, Iterable):
        vals = list(raw)
        if len(vals) == 2 and isinstance(vals[0], (int, float)) and isinstance(vals[1], (int, float)):
            a = max(lo, min(hi, int(vals[0])))
            b = max(lo, min(hi, int(vals[1])))
            return (min(a, b), max(a, b))
    return default


def load_style_profile(path: str) -> Dict[str, Any]:
    p = Path(path).resolve()
    payload = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return {}
    return payload


def style_config(style_profile: Dict[str, Any]) -> Dict[str, Any]:
    over = style_profile.get("generator_overrides") if isinstance(style_profile.get("generator_overrides"), dict) else {}
    cfg = {
        "style": str(over.get("style") or "sigil"),
        "ring_count_range": _int_range(over.get("ring_count_range"), (4, 7), 2, 12),
        "rays_range": _int_range(over.get("rays_range"), (12, 20), 4, 36),
        "nodes_range": _int_range(over.get("nodes_range"), (18, 34), 4, 80),
        "stroke_px_range": _int_range(over.get("stroke_px_range"), (2, 5), 1, 20),
        "overlay_lines_range": _int_range(over.get("overlay_lines_range"), (10, 20), 0, 64),
        "overlay_arcs_range": _int_range(over.get("overlay_arcs_range"), (8, 16), 0, 64),
        "center_jitter_px": max(0, min(48, int(over.get("center_jitter_px") or 0))),
    }
    return cfg


def load_location_brief(path: str) -> Dict[str, Any]:
    p = Path(path).resolve()
    payload = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return {}
    return payload


def _iter_geo_paths(geojson_obj: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    gtype = str(geojson_obj.get("type") or "")
    coords = geojson_obj.get("coordinates")
    out: List[List[Tuple[float, float]]] = []

    def to_pairs(path: Any) -> List[Tuple[float, float]]:
        pts: List[Tuple[float, float]] = []
        if isinstance(path, list):
            for row in path:
                if isinstance(row, list) and len(row) >= 2 and isinstance(row[0], (int, float)) and isinstance(row[1], (int, float)):
                    pts.append((float(row[0]), float(row[1])))
        return pts

    if gtype == "Polygon" and isinstance(coords, list):
        for ring in coords:
            pts = to_pairs(ring)
            if len(pts) >= 2:
                out.append(pts)
    elif gtype == "MultiPolygon" and isinstance(coords, list):
        for poly in coords:
            if isinstance(poly, list):
                for ring in poly:
                    pts = to_pairs(ring)
                    if len(pts) >= 2:
                        out.append(pts)
    elif gtype == "LineString":
        pts = to_pairs(coords)
        if len(pts) >= 2:
            out.append(pts)
    elif gtype == "MultiLineString" and isinstance(coords, list):
        for line in coords:
            pts = to_pairs(line)
            if len(pts) >= 2:
                out.append(pts)
    elif gtype == "Point":
        pts = to_pairs([coords] if isinstance(coords, list) else [])
        if pts:
            out.append(pts)
    return out


def _decimate_path(path: List[Tuple[float, float]], max_points: int = 1200) -> List[Tuple[float, float]]:
    if len(path) <= max_points:
        return path
    step = max(1, int(len(path) / max_points))
    out = [path[i] for i in range(0, len(path), step)]
    if out[-1] != path[-1]:
        out.append(path[-1])
    return out


def _project_path(
    path: List[Tuple[float, float]],
    *,
    width: int,
    height: int,
    bbox: Tuple[float, float, float, float],
    pad_x: float,
    pad_y: float,
    scale: float,
) -> List[Tuple[float, float]]:
    min_x, _, min_y, _ = bbox
    out: List[Tuple[float, float]] = []
    for lon, lat in path:
        px = pad_x + ((lon - min_x) * scale)
        py = height - (pad_y + ((lat - min_y) * scale))
        out.append((px, py))
    return out


def draw_location_geometry(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    height: int,
    location_brief: Dict[str, Any],
    rng: random.Random,
    stroke: int,
) -> bool:
    geojson_obj = location_brief.get("geojson")
    if not isinstance(geojson_obj, dict):
        return False
    paths = _iter_geo_paths(geojson_obj)
    if not paths:
        return False

    xs: List[float] = []
    ys: List[float] = []
    for p in paths:
        for lon, lat in p:
            xs.append(lon)
            ys.append(lat)
    if not xs or not ys:
        return False
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1e-8, max_x - min_x)
    span_y = max(1e-8, max_y - min_y)

    # Keep true map proportions by using a uniform scale.
    pad = 0.14
    avail_w = width * (1.0 - (2.0 * pad))
    avail_h = height * (1.0 - (2.0 * pad))
    scale = min(avail_w / span_x, avail_h / span_y)
    pad_x = (width - (span_x * scale)) / 2.0
    pad_y = (height - (span_y * scale)) / 2.0

    drawn = 0
    for p in paths:
        q = _decimate_path(p, max_points=1400)
        projected = _project_path(
            q,
            width=width,
            height=height,
            bbox=(min_x, max_x, min_y, max_y),
            pad_x=pad_x,
            pad_y=pad_y,
            scale=scale,
        )
        if len(projected) <= 1:
            continue
        # Tiny deterministic jitter to keep hand-drawn feel while preserving geometry.
        jitter_px = 1.2
        stylized = [(x + rng.uniform(-jitter_px, jitter_px), y + rng.uniform(-jitter_px, jitter_px)) for x, y in projected]
        draw.line(stylized, fill=(0, 0, 0, 255), width=stroke)
        # Close polygons where needed.
        if projected[0] != projected[-1] and len(projected) >= 3 and str(geojson_obj.get("type") or "") in {"Polygon", "MultiPolygon"}:
            draw.line([stylized[-1], stylized[0]], fill=(0, 0, 0, 255), width=stroke)
        drawn += 1

    if drawn == 0:
        return False

    # Subtle map badge ring around geometry footprint for print-ready framing.
    ring_pad = int(min(width, height) * 0.1)
    draw.ellipse((ring_pad, ring_pad, width - ring_pad, height - ring_pad), outline=(0, 0, 0, 180), width=max(1, stroke - 1))
    return True


def draw_sigil_style(draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random, cfg: Dict[str, Any]) -> None:
    cx = width // 2
    cy = height // 2
    jitter = int(cfg.get("center_jitter_px") or 0)
    if jitter > 0:
        cx += rng.randint(-jitter, jitter)
        cy += rng.randint(-jitter, jitter)
    ring_lo, ring_hi = cfg.get("ring_count_range", (4, 7))
    ring_count = rng.randint(int(ring_lo), int(ring_hi))
    min_side = min(width, height)
    base_radius = int(min_side * 0.09)
    radius_step = int(min_side * 0.055)
    stroke_lo, stroke_hi = cfg.get("stroke_px_range", (2, 5))
    stroke = max(1, rng.randint(int(stroke_lo), int(stroke_hi)))

    for i in range(ring_count):
        r = base_radius + (i * radius_step)
        box = (cx - r, cy - r, cx + r, cy + r)
        draw.ellipse(box, outline=(0, 0, 0, 255), width=stroke)

    rays_lo, rays_hi = cfg.get("rays_range", (12, 20))
    rays = rng.randint(int(rays_lo), int(rays_hi))
    max_r = base_radius + ((ring_count - 1) * radius_step)
    for i in range(rays):
        angle = (360.0 / float(rays)) * i + rng.uniform(-3.0, 3.0)
        rad = angle * 3.1415926535 / 180.0
        x2 = int(cx + (max_r * 1.15) * math.cos(rad))
        y2 = int(cy + (max_r * 1.15) * math.sin(rad))
        draw.line([(cx, cy), (x2, y2)], fill=(0, 0, 0, 255), width=max(2, stroke - 1))

    nodes_lo, nodes_hi = cfg.get("nodes_range", (18, 34))
    nodes = rng.randint(int(nodes_lo), int(nodes_hi))
    for _ in range(nodes):
        x = rng.randint(cx - int(max_r * 1.1), cx + int(max_r * 1.1))
        y = rng.randint(cy - int(max_r * 1.1), cy + int(max_r * 1.1))
        r = rng.randint(max(2, stroke - 1), stroke + 2)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(0, 0, 0, 255))


def draw_geometric_overlay(draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random, cfg: Dict[str, Any]) -> None:
    min_side = min(width, height)
    stroke_lo, stroke_hi = cfg.get("stroke_px_range", (2, 4))
    stroke = max(1, rng.randint(max(1, int(stroke_lo - 1)), int(stroke_hi)))

    # Diagonal/chord lines
    lines_lo, lines_hi = cfg.get("overlay_lines_range", (10, 20))
    for _ in range(rng.randint(int(lines_lo), int(lines_hi))):
        p1 = random_point(rng, width, height)
        p2 = random_point(rng, width, height)
        draw.line([p1, p2], fill=(0, 0, 0, 230), width=stroke)

    # Arc fragments
    arcs_lo, arcs_hi = cfg.get("overlay_arcs_range", (8, 16))
    for _ in range(rng.randint(int(arcs_lo), int(arcs_hi))):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        r = rng.randint(int(min_side * 0.06), int(min_side * 0.22))
        box = (x - r, y - r, x + r, y + r)
        start = rng.uniform(0, 360)
        end = start + rng.uniform(35, 165)
        draw.arc(box, start=start, end=end, fill=(0, 0, 0, 230), width=stroke)


def render_lineart(
    concept: str,
    prompt: str,
    style: str,
    width: int,
    height: int,
    style_profile: Dict[str, Any] | None = None,
    location_brief: Dict[str, Any] | None = None,
) -> Image.Image:
    profile = style_profile or {}
    brief = location_brief or {}
    cfg = style_config(profile)
    style_final = str(style or cfg.get("style") or "sigil").strip().lower()
    if style_final in ("map", "aerial", "landmark"):
        style_final = "landmark"
    profile_sig = json.dumps(cfg, sort_keys=True)
    location_sig = ""
    if isinstance(brief, dict) and brief:
        location_sig = json.dumps(
            {
                "spot": str(brief.get("spot") or ""),
                "display_name": str(brief.get("display_name") or ""),
                "geometry_type": str(brief.get("geometry_type") or ""),
                "geojson": brief.get("geojson") if isinstance(brief.get("geojson"), dict) else {},
            },
            sort_keys=True,
        )
    seed = stable_seed(concept, prompt, style_final, profile_sig, location_sig, str(width), str(height))
    rng = random.Random(seed)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    stroke_lo, stroke_hi = cfg.get("stroke_px_range", (2, 5))
    stroke = max(1, rng.randint(int(stroke_lo), int(stroke_hi)))

    drew_geo = False
    if isinstance(brief, dict) and brief and bool(brief.get("has_geometry_outline")):
        drew_geo = draw_location_geometry(
            draw,
            width=width,
            height=height,
            location_brief=brief,
            rng=rng,
            stroke=max(2, stroke),
        )

    if drew_geo and style_final in ("landmark", "hybrid", "sigil", "seal", "symbol"):
        # Layer light geometry accents for artistic style without losing fidelity.
        draw_geometric_overlay(draw, width, height, rng, {**cfg, "overlay_lines_range": (4, 9), "overlay_arcs_range": (2, 6)})
    elif style_final in ("sigil", "seal", "symbol"):
        draw_sigil_style(draw, width, height, rng, cfg)
    else:
        draw_sigil_style(draw, width, height, rng, cfg)
        draw_geometric_overlay(draw, width, height, rng, cfg)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic transparent line-art for POD.")
    ap.add_argument("--concept", required=True)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--style", default="sigil")
    ap.add_argument("--width", type=int, default=4500)
    ap.add_argument("--height", type=int, default=5400)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta-out", default="")
    ap.add_argument("--style-profile", default="")
    ap.add_argument("--location-brief-json", default="")
    args = ap.parse_args()

    width = max(512, int(args.width))
    height = max(512, int(args.height))
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    style_profile: Dict[str, Any] = {}
    if str(args.style_profile).strip():
        try:
            style_profile = load_style_profile(str(args.style_profile).strip())
        except Exception:
            style_profile = {}
    location_brief: Dict[str, Any] = {}
    if str(args.location_brief_json).strip():
        try:
            location_brief = load_location_brief(str(args.location_brief_json).strip())
        except Exception:
            location_brief = {}

    img = render_lineart(
        concept=str(args.concept).strip(),
        prompt=str(args.prompt).strip(),
        style=str(args.style).strip().lower(),
        width=width,
        height=height,
        style_profile=style_profile,
        location_brief=location_brief,
    )
    img.save(out_path, format="PNG")

    payload: Dict[str, str] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "concept": str(args.concept),
        "style": str(args.style),
        "out": str(out_path),
        "style_profile": str(args.style_profile or ""),
        "location_brief_json": str(args.location_brief_json or ""),
    }
    if str(args.meta_out).strip():
        meta_path = Path(args.meta_out).resolve()
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
