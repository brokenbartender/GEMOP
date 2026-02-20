from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STANDARDS_PATH = REPO_ROOT / "data" / "marketplace_image_standards.json"


def load_standards(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Standards file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def image_metadata(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    file_bytes = path.stat().st_size
    with Image.open(path) as img:
        mode = img.mode
        width, height = img.size
        fmt = (img.format or "").lower()
        has_alpha = "A" in mode
    return {
        "path": str(path),
        "format": fmt,
        "mode": mode,
        "width_px": int(width),
        "height_px": int(height),
        "long_side_px": int(max(width, height)),
        "short_side_px": int(min(width, height)),
        "aspect_ratio": round(float(width) / float(height), 6) if height else 0.0,
        "has_alpha": bool(has_alpha),
        "file_size_mb": round(file_bytes / (1024.0 * 1024.0), 4),
    }


def add_check(checks: List[Dict[str, str]], cid: str, ok: bool, message: str) -> None:
    checks.append(
        {
            "id": cid,
            "status": "pass" if ok else "fail",
            "message": message,
        }
    )


def evaluate_against_market(
    metadata: Dict[str, Any],
    standards: Dict[str, Any],
    market: str,
    product: str,
) -> Dict[str, Any]:
    markets = (standards.get("markets") or {}) if isinstance(standards, dict) else {}
    mcfg = markets.get(market) if isinstance(markets, dict) else None
    if not isinstance(mcfg, dict):
        raise KeyError(f"Unknown market in standards: {market}")

    general = mcfg.get("general") or {}
    products = mcfg.get("products") or {}
    pcfg = products.get(product) if isinstance(products, dict) else None
    if not isinstance(pcfg, dict):
        pcfg = {}

    checks: List[Dict[str, str]] = []
    width = int(metadata.get("width_px") or 0)
    height = int(metadata.get("height_px") or 0)
    long_side = int(metadata.get("long_side_px") or 0)
    ratio = float(metadata.get("aspect_ratio") or 0.0)
    file_size_mb = float(metadata.get("file_size_mb") or 0.0)
    has_alpha = bool(metadata.get("has_alpha"))

    max_file_mb = float(general.get("max_file_mb") or 0.0)
    if max_file_mb > 0:
        add_check(
            checks,
            "max_file_mb",
            file_size_mb <= max_file_mb,
            f"size_mb={file_size_mb} limit_mb={max_file_mb}",
        )

    max_side = int(general.get("max_side_px") or 0)
    if max_side > 0:
        add_check(
            checks,
            "max_side_px",
            long_side <= max_side,
            f"long_side_px={long_side} limit_px={max_side}",
        )

    min_w = int(pcfg.get("min_width_px") or 0)
    if min_w > 0:
        add_check(checks, "min_width_px", width >= min_w, f"width_px={width} min_width_px={min_w}")

    min_h = int(pcfg.get("min_height_px") or 0)
    if min_h > 0:
        add_check(checks, "min_height_px", height >= min_h, f"height_px={height} min_height_px={min_h}")

    rec_w = int(pcfg.get("recommended_width_px") or 0)
    if rec_w > 0:
        add_check(
            checks,
            "recommended_width_px",
            width >= rec_w,
            f"width_px={width} recommended_width_px={rec_w}",
        )

    rec_h = int(pcfg.get("recommended_height_px") or 0)
    if rec_h > 0:
        add_check(
            checks,
            "recommended_height_px",
            height >= rec_h,
            f"height_px={height} recommended_height_px={rec_h}",
        )

    ratio_range = pcfg.get("aspect_ratio_range") if isinstance(pcfg, dict) else None
    if isinstance(ratio_range, Iterable):
        vals = list(ratio_range)
        if len(vals) == 2:
            lo = float(vals[0])
            hi = float(vals[1])
            add_check(
                checks,
                "aspect_ratio_range",
                lo <= ratio <= hi,
                f"aspect_ratio={ratio} range=[{lo},{hi}]",
            )

    alpha_required_for = general.get("transparency_required_for")
    if isinstance(alpha_required_for, list):
        must_alpha = product.lower() in {str(x).lower() for x in alpha_required_for}
        if must_alpha:
            add_check(
                checks,
                "alpha_required",
                has_alpha,
                f"has_alpha={has_alpha} product={product}",
            )

    failed = [c for c in checks if c["status"] == "fail"]
    status = "pass" if not failed else "fail"
    return {
        "status": status,
        "market": market,
        "product": product,
        "metadata": metadata,
        "checks": checks,
    }


def check_image(path: Path, standards_path: Path, market: str, product: str) -> Dict[str, Any]:
    standards = load_standards(standards_path)
    meta = image_metadata(path)
    return evaluate_against_market(meta, standards, market=market, product=product)


def run_cli(images: List[Path], standards_path: Path, market: str, product: str, json_out: Path | None) -> int:
    results: List[Dict[str, Any]] = []
    exit_code = 0
    for image in images:
        try:
            result = check_image(image, standards_path=standards_path, market=market, product=product)
        except Exception as e:
            result = {
                "status": "fail",
                "market": market,
                "product": product,
                "metadata": {"path": str(image)},
                "checks": [{"id": "runtime_error", "status": "fail", "message": str(e)}],
            }
        results.append(result)
        if result.get("status") != "pass":
            exit_code = 2

    payload: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "standards_path": str(standards_path),
        "market": market,
        "product": product,
        "results": results,
    }

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description="Check image assets against marketplace standards.")
    ap.add_argument("--image", action="append", required=True, help="Path to image (repeatable).")
    ap.add_argument("--market", default="redbubble")
    ap.add_argument("--product", default="tshirt")
    ap.add_argument("--standards", default=str(DEFAULT_STANDARDS_PATH))
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    images = [Path(p).resolve() for p in args.image]
    standards_path = Path(args.standards).resolve()
    json_out = Path(args.json_out).resolve() if str(args.json_out).strip() else None
    return run_cli(images, standards_path=standards_path, market=str(args.market), product=str(args.product), json_out=json_out)


if __name__ == "__main__":
    raise SystemExit(main())
