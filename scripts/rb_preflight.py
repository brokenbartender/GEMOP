from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from analyze_png_lineart import analyze_image
from marketplace_image_check import check_image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STANDARDS_PATH = REPO_ROOT / "data" / "marketplace_image_standards.json"


def preflight(image: Path, standards_path: Path, product: str) -> Dict[str, Any]:
    market_report = check_image(image, standards_path=standards_path, market="redbubble", product=product)
    quality_report = analyze_image(image)
    status = "pass"
    if market_report.get("status") != "pass":
        status = "fail"
    elif quality_report.get("status") not in ("pass",):
        status = "warn"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "image": str(image),
        "product": product,
        "marketplace_check": market_report,
        "lineart_quality": quality_report,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Redbubble preflight checks on a single image.")
    ap.add_argument("--image", required=True)
    ap.add_argument("--product", default="tshirt")
    ap.add_argument("--standards", default=str(DEFAULT_STANDARDS_PATH))
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    report = preflight(
        image=Path(args.image).resolve(),
        standards_path=Path(args.standards).resolve(),
        product=str(args.product).strip().lower(),
    )
    if str(args.json_out).strip():
        out = Path(args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in ("pass", "warn") else 2


if __name__ == "__main__":
    raise SystemExit(main())
