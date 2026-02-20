from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
STYLE_PROFILE_PATH = REPO_ROOT / "data" / "redbubble" / "style_profile.json"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
ASSETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "assets"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def load_style_profile(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def style_targets(profile: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    qa = profile.get("qa_targets") if isinstance(profile.get("qa_targets"), dict) else {}
    edge = qa.get("edge_density_range") if isinstance(qa.get("edge_density_range"), list) and len(qa.get("edge_density_range")) == 2 else [0.03, 0.16]
    alpha = qa.get("alpha_ratio_range") if isinstance(qa.get("alpha_ratio_range"), list) and len(qa.get("alpha_ratio_range")) == 2 else [0.015, 0.18]
    # Guard against bad profile ranges.
    edge_lo, edge_hi = float(edge[0]), float(edge[1])
    alpha_lo, alpha_hi = float(alpha[0]), float(alpha[1])
    if edge_hi <= edge_lo:
        edge_lo, edge_hi = 0.03, 0.16
    if alpha_hi <= alpha_lo or alpha_lo >= 0.8:
        alpha_lo, alpha_hi = 0.015, 0.18
    return {
        "edge_density": (edge_lo, edge_hi),
        "alpha_ratio": (alpha_lo, alpha_hi),
    }


def source_edge_map(src_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 80, 210, apertureSize=3, L2gradient=True)
    return edges


def apply_component_filter(mask: np.ndarray, min_area: int) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return mask
    out = np.zeros_like(mask)
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= min_area:
            out[labels == i] = 255
    return out


def connected_component_stats(mask: np.ndarray) -> Tuple[int, float]:
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return 0, 0.0
    areas = stats[1:, cv2.CC_STAT_AREA]
    comp_count = int(len(areas))
    small = int(np.count_nonzero(areas < 22))
    small_ratio = float(small) / float(max(1, comp_count))
    return comp_count, small_ratio


def contour_line_mask(gray: np.ndarray, p: Dict[str, int], stroke_width: int) -> np.ndarray:
    block = int(p.get("contour_block_size", 13))
    if block % 2 == 0:
        block += 1
    block = max(5, min(41, block))
    bias = int(p.get("contour_bias", 5))
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        bias,
    )
    th = cv2.medianBlur(th, 3)
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(gray)
    min_perim = float(int(p.get("contour_min_perim", 90)))
    eps_pct = float(int(p.get("contour_eps_pct", 2))) / 100.0
    for cnt in cnts:
        perim = float(cv2.arcLength(cnt, True))
        if perim < min_perim:
            continue
        eps = max(0.2, eps_pct * perim)
        approx = cv2.approxPolyDP(cnt, eps, True)
        if len(approx) < 2:
            continue
        cv2.polylines(out, [approx], isClosed=True, color=255, thickness=max(1, stroke_width - 1))
    return out


def hough_line_mask(edges: np.ndarray, p: Dict[str, int]) -> np.ndarray:
    out = np.zeros_like(edges)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=int(p["hough_threshold"]),
        minLineLength=int(p["hough_min_length"]),
        maxLineGap=int(p["hough_max_gap"]),
    )
    if lines is None:
        return out
    max_lines = int(p.get("hough_max_lines", 1400))
    len_floor = float(int(p.get("hough_len_floor", 20)))
    stroke = int(max(1, p.get("stroke_width", 1)))
    kept: List[Tuple[float, Tuple[int, int, int, int]]] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        ln = float(np.hypot(float(x2 - x1), float(y2 - y1)))
        if ln < len_floor:
            continue
        kept.append((ln, (x1, y1, x2, y2)))
    kept.sort(key=lambda x: x[0], reverse=True)
    for _, seg in kept[:max_lines]:
        x1, y1, x2, y2 = seg
        cv2.line(out, (x1, y1), (x2, y2), 255, stroke)
    return out


def stylize_photo(src_bgr: np.ndarray, p: Dict[str, int]) -> np.ndarray:
    gray = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY)
    if int(p["bilateral_d"]) > 0:
        gray = cv2.bilateralFilter(gray, int(p["bilateral_d"]), int(p["bilateral_sigma"]), int(p["bilateral_sigma"]))
    if int(p["gauss_ksize"]) > 0:
        k = int(p["gauss_ksize"])
        if k % 2 == 0:
            k += 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    edges = cv2.Canny(gray, int(p["canny_low"]), int(p["canny_high"]), apertureSize=3, L2gradient=True)

    if int(p["dilate_iter"]) > 0:
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=int(p["dilate_iter"]))
    if int(p["erode_iter"]) > 0:
        edges = cv2.erode(edges, np.ones((3, 3), np.uint8), iterations=int(p["erode_iter"]))

    edges = apply_component_filter(edges, int(p["min_component_area"]))

    mode = int(p.get("line_mode", 1))
    mode = max(0, min(2, mode))
    out = np.zeros_like(edges)
    if mode in (0, 1):
        out = cv2.bitwise_or(out, edges)

    if int(p["hough_enable"]) == 1 or mode in (1, 2):
        out = cv2.bitwise_or(out, hough_line_mask(edges, p))

    if int(p.get("contour_enable", 0)) == 1:
        out = cv2.bitwise_or(out, contour_line_mask(gray, p, int(max(1, p.get("stroke_width", 1)))))

    if int(p.get("close_iter", 0)) > 0:
        out = cv2.morphologyEx(
            out,
            cv2.MORPH_CLOSE,
            np.ones((3, 3), np.uint8),
            iterations=int(p.get("close_iter", 0)),
        )
    out = apply_component_filter(out, int(p["min_component_area"]))
    return out


def edge_overlap_score(source_edges: np.ndarray, candidate_edges: np.ndarray) -> float:
    a = (source_edges > 0).astype(np.uint8)
    b = (candidate_edges > 0).astype(np.uint8)
    inter = float(np.sum((a == 1) & (b == 1)))
    union = float(np.sum((a == 1) | (b == 1)))
    if union <= 0.0:
        return 0.0
    return inter / union


def metric_distance(value: float, lo: float, hi: float) -> float:
    if lo <= value <= hi:
        return 0.0
    if value < lo:
        return (lo - value) / max(1e-6, lo)
    return (value - hi) / max(1e-6, hi)


def candidate_metrics(alpha: np.ndarray) -> Dict[str, float]:
    area = float(alpha.shape[0] * alpha.shape[1]) or 1.0
    alpha_ratio = float(np.count_nonzero(alpha)) / area
    # Approx edge density from alpha edges.
    edges = cv2.Canny(alpha, 60, 180, apertureSize=3, L2gradient=True)
    edge_density = float(np.count_nonzero(edges)) / area
    comp_count, small_ratio = connected_component_stats(alpha)
    return {
        "alpha_ratio": alpha_ratio,
        "edge_density": edge_density,
        "component_count": float(comp_count),
        "small_component_ratio": small_ratio,
    }


def score_candidate(
    *,
    source_edges: np.ndarray,
    candidate_alpha: np.ndarray,
    targets: Dict[str, Tuple[float, float]],
    fill_ratio: float,
) -> Dict[str, float]:
    overlap = edge_overlap_score(source_edges, candidate_alpha)
    m = candidate_metrics(candidate_alpha)
    edge_lo, edge_hi = targets["edge_density"]
    alpha_lo, alpha_hi = targets["alpha_ratio"]
    edge_penalty = metric_distance(m["edge_density"], edge_lo, edge_hi)
    alpha_penalty = metric_distance(m["alpha_ratio"], alpha_lo, alpha_hi)
    comp_penalty = 0.0
    if m["component_count"] < 16:
        comp_penalty = (16.0 - m["component_count"]) / 16.0
    elif m["component_count"] > 240:
        comp_penalty = (m["component_count"] - 240.0) / 240.0
    style_score = clamp(1.0 - (0.6 * edge_penalty + 0.4 * alpha_penalty), 0.0, 1.0)
    simplicity_score = clamp(1.0 - (0.72 * m["small_component_ratio"] + 0.28 * comp_penalty), 0.0, 1.0)
    fill_score = clamp(1.0 - (abs(fill_ratio - 0.8) / 0.22), 0.0, 1.0)
    # Weight fidelity highest for recognizable architecture while suppressing scratch noise.
    total = (0.56 * overlap) + (0.24 * style_score) + (0.12 * simplicity_score) + (0.08 * fill_score)
    return {
        "total_score": total,
        "fidelity_score": overlap,
        "style_score": style_score,
        "simplicity_score": simplicity_score,
        "fill_score": fill_score,
        "alpha_ratio": m["alpha_ratio"],
        "edge_density": m["edge_density"],
        "component_count": m["component_count"],
        "small_component_ratio": m["small_component_ratio"],
    }


def place_on_canvas(alpha: np.ndarray, width: int, height: int, fill_ratio: float, stroke_boost: int) -> Image.Image:
    h, w = alpha.shape[:2]
    alpha = apply_component_filter(alpha, max(22, int((h * w) * 0.000006)))
    row_counts = np.count_nonzero(alpha > 0, axis=1)
    strong_thresh = max(10, int(0.004 * w))
    strong_rows = np.where(row_counts >= strong_thresh)[0]
    if len(strong_rows) > 0:
        y0s = max(0, int(strong_rows[0]) - 14)
        y1s = min(h, int(strong_rows[-1]) + 15)
        alpha = alpha[y0s:y1s, :]
        h, w = alpha.shape[:2]
    ys, xs = np.where(alpha > 0)
    if len(xs) > 0 and len(ys) > 0:
        x0 = max(0, int(np.min(xs)) - 8)
        x1 = min(w, int(np.max(xs)) + 9)
        y0 = max(0, int(np.min(ys)) - 8)
        y1 = min(h, int(np.max(ys)) + 9)
        alpha = alpha[y0:y1, x0:x1]
        h, w = alpha.shape[:2]
    target_w = int(width * clamp(fill_ratio, 0.45, 0.9))
    target_h = int(height * clamp(fill_ratio, 0.45, 0.9))
    scale = min(target_w / max(1, w), target_h / max(1, h))
    out_w = max(1, int(w * scale))
    out_h = max(1, int(h * scale))
    resized_alpha = cv2.resize(alpha, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
    _, resized_alpha = cv2.threshold(resized_alpha, 48, 255, cv2.THRESH_BINARY)
    if stroke_boost > 1:
        k = np.ones((stroke_boost, stroke_boost), np.uint8)
        resized_alpha = cv2.dilate(resized_alpha, k, iterations=1)
    # Final speck cleanup to avoid "etch-a-sketch" noise on print exports.
    resized_alpha = apply_component_filter(resized_alpha, max(8, int(2 * (stroke_boost ** 2))))

    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    x0 = (width - out_w) // 2
    y0 = (height - out_h) // 2
    canvas[y0 : y0 + out_h, x0 : x0 + out_w, 3] = resized_alpha
    # Black strokes.
    canvas[y0 : y0 + out_h, x0 : x0 + out_w, 0] = 0
    canvas[y0 : y0 + out_h, x0 : x0 + out_w, 1] = 0
    canvas[y0 : y0 + out_h, x0 : x0 + out_w, 2] = 0
    return Image.fromarray(canvas)


def random_params(rng: random.Random, base: Dict[str, int] | None = None, local: bool = False) -> Dict[str, int]:
    b = base or {}
    jitter = 8 if local else 28

    def pick(name: str, lo: int, hi: int, odd: bool = False) -> int:
        if name in b:
            v = int(b[name]) + rng.randint(-jitter, jitter)
            v = max(lo, min(hi, v))
        else:
            v = rng.randint(lo, hi)
        if odd and v % 2 == 0:
            v += 1
            if v > hi:
                v -= 2
        return v

    low = pick("canny_low", 55, 170)
    high = pick("canny_high", max(low + 36, 96), 255)
    mode = pick("line_mode", 1, 2)
    return {
        "canny_low": low,
        "canny_high": high,
        "bilateral_d": pick("bilateral_d", 0, 7),
        "bilateral_sigma": pick("bilateral_sigma", 28, 120),
        "gauss_ksize": pick("gauss_ksize", 0, 5, odd=True),
        "dilate_iter": pick("dilate_iter", 0, 1),
        "erode_iter": pick("erode_iter", 0, 1),
        "min_component_area": pick("min_component_area", 24, 320),
        "hough_enable": pick("hough_enable", 0, 1),
        "hough_threshold": pick("hough_threshold", 60, 180),
        "hough_min_length": pick("hough_min_length", 24, 260),
        "hough_max_gap": pick("hough_max_gap", 3, 22),
        "hough_max_lines": pick("hough_max_lines", 500, 1800),
        "hough_len_floor": pick("hough_len_floor", 20, 60),
        "stroke_width": pick("stroke_width", 1, 4),
        "line_mode": mode,
        "contour_enable": pick("contour_enable", 0, 1),
        "contour_block_size": pick("contour_block_size", 7, 25, odd=True),
        "contour_bias": pick("contour_bias", 2, 12),
        "contour_min_perim": pick("contour_min_perim", 50, 420),
        "contour_eps_pct": pick("contour_eps_pct", 1, 6),
        "close_iter": pick("close_iter", 0, 1),
        "fill_ratio": pick("fill_ratio", 64, 86),
    }


def run_search(
    *,
    src_path: Path,
    out_path: Path,
    report_path: Path,
    style_profile_path: Path,
    width: int,
    height: int,
    cycles: int,
    seed: int,
) -> Dict[str, Any]:
    profile = load_style_profile(style_profile_path)
    targets = style_targets(profile)
    rng = random.Random(seed)

    src_bgr = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
    if src_bgr is None:
        raise SystemExit(f"Unable to read image: {src_path}")
    source_edges = source_edge_map(src_bgr)

    best: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []

    global_tries = max(8, cycles * 5)
    local_tries = max(10, cycles * 6)

    for i in range(global_tries):
        params = random_params(rng)
        alpha = stylize_photo(src_bgr, params)
        score = score_candidate(
            source_edges=source_edges,
            candidate_alpha=alpha,
            targets=targets,
            fill_ratio=float(params["fill_ratio"]) / 100.0,
        )
        row = {
            "iter": i + 1,
            "phase": "global",
            "params": params,
            **score,
        }
        rows.append(row)
        if not best or float(row["total_score"]) > float(best.get("total_score", -1.0)):
            best = row

    base_params = dict(best.get("params") or {})
    for i in range(local_tries):
        params = random_params(rng, base=base_params, local=True)
        alpha = stylize_photo(src_bgr, params)
        score = score_candidate(
            source_edges=source_edges,
            candidate_alpha=alpha,
            targets=targets,
            fill_ratio=float(params["fill_ratio"]) / 100.0,
        )
        row = {
            "iter": i + 1,
            "phase": "local",
            "params": params,
            **score,
        }
        rows.append(row)
        if float(row["total_score"]) > float(best.get("total_score", -1.0)):
            best = row
            base_params = dict(params)

    best_alpha = stylize_photo(src_bgr, best["params"])
    img = place_on_canvas(
        best_alpha,
        width=width,
        height=height,
        fill_ratio=float(best["params"]["fill_ratio"]) / 100.0,
        stroke_boost=max(1, int(best["params"].get("stroke_width", 1))),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    preview_path = out_path.with_name(f"{out_path.stem}_preview.png")
    preview = Image.new("RGBA", img.size, (255, 255, 255, 255))
    preview.alpha_composite(img)
    preview.convert("RGB").save(preview_path, format="PNG")

    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_image": str(src_path),
        "output_image": str(out_path),
        "preview_image": str(preview_path),
        "style_profile": str(style_profile_path),
        "canvas": {"width": width, "height": height, "transparent": True},
        "cycles": cycles,
        "seed": seed,
        "best": best,
        "targets": targets,
        "top_candidates": sorted(rows, key=lambda r: float(r["total_score"]), reverse=True)[:12],
        "try_count": len(rows),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert a real photo into Redbubble-ready minimal line art style with iterative tuning.")
    ap.add_argument("--image", required=True, help="Source photo path.")
    ap.add_argument("--out", default="", help="Output PNG path (defaults into ramshare/evidence/assets).")
    ap.add_argument("--report", default="", help="JSON report path (defaults into ramshare/evidence/reports).")
    ap.add_argument("--style-profile", default=str(STYLE_PROFILE_PATH))
    ap.add_argument("--width", type=int, default=4500)
    ap.add_argument("--height", type=int, default=5400)
    ap.add_argument("--cycles", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src_path = Path(args.image).resolve()
    stamp = now_stamp()
    out_path = Path(args.out).resolve() if str(args.out).strip() else (ASSETS_DIR / f"asset_photo_style_{stamp}.png")
    report_path = Path(args.report).resolve() if str(args.report).strip() else (REPORTS_DIR / f"photo_style_{stamp}.json")

    report = run_search(
        src_path=src_path,
        out_path=out_path,
        report_path=report_path,
        style_profile_path=Path(args.style_profile).resolve(),
        width=max(512, int(args.width)),
        height=max(512, int(args.height)),
        cycles=max(1, int(args.cycles)),
        seed=int(args.seed),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output_image": str(out_path),
                "preview_image": str(report.get("preview_image") or ""),
                "report": str(report_path),
                "best": report.get("best", {}),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
