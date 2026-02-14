import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
STATE_DIR = REPO_ROOT / "ramshare" / "state"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"
STRATEGY_PATH = STATE_DIR / "strategy.json"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_strategy(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"updated_at": "", "rules": {}, "evidence": []}
    try:
        return load_json(path)
    except Exception:
        return {"updated_at": "", "rules": {}, "evidence": []}


def score_units_sold(title: str) -> int:
    raw = sum(ord(ch) for ch in title)
    return raw % 60


def decide_rules(title: str, units_sold: int) -> Dict[str, Any]:
    title_low = title.lower()
    preferred_palette = "neon" if units_sold >= 30 else "vintage"
    preferred_keywords: List[str] = []
    avoid_keywords: List[str] = []

    if "retro" in title_low:
        preferred_keywords.append("retro")
    if "cat" in title_low:
        preferred_keywords.append("cat")
    if units_sold < 10:
        avoid_keywords.append("generic")
    if units_sold >= 30:
        preferred_keywords.append("high-contrast")

    return {
        "preferred_palette": preferred_palette,
        "preferred_keywords": sorted(set(preferred_keywords)),
        "avoid_keywords": sorted(set(avoid_keywords)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Strategist skill: derive feedback rules from posted listings")
    ap.add_argument("job_file", help="Path to strategist job json")
    args = ap.parse_args()

    job = load_json(Path(args.job_file))
    inputs = job.get("inputs") or {}
    receipt_path_str = inputs.get("live_receipt_path") or job.get("live_receipt_path") or job.get("input_data")
    if not isinstance(receipt_path_str, str) or not receipt_path_str.strip():
        raise SystemExit("Missing live_receipt_path in strategist job")

    receipt_path = Path(receipt_path_str)
    if not receipt_path.exists():
        raise SystemExit(f"Live receipt not found: {receipt_path}")
    receipt = load_json(receipt_path)

    listing_path = Path(str(receipt.get("source_listing_path") or ""))
    title = "Unknown Listing"
    if listing_path.exists():
        listing = load_json(listing_path)
        title = str(listing.get("title") or title)

    units = score_units_sold(title)
    rules = decide_rules(title, units)

    strategy = load_strategy(STRATEGY_PATH)
    strategy["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    strategy["rules"] = rules
    evidence = strategy.get("evidence") or []
    evidence.append(
        {
            "ts": strategy["updated_at"],
            "title": title,
            "units_sold_mock": units,
            "live_receipt_path": str(receipt_path),
        }
    )
    strategy["evidence"] = evidence[-200:]
    STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_PATH.write_text(json.dumps(strategy, indent=2), encoding="utf-8")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORTS_DIR / f"strategy_{now_stamp()}.md"
    lines = [
        "# Strategist Update (Mock)",
        "",
        f"- title: {title}",
        f"- units_sold_mock: {units}",
        f"- preferred_palette: {rules['preferred_palette']}",
        f"- preferred_keywords: {', '.join(rules['preferred_keywords']) or 'none'}",
        f"- avoid_keywords: {', '.join(rules['avoid_keywords']) or 'none'}",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Strategist updated strategy: {STRATEGY_PATH}")


if __name__ == "__main__":
    main()
