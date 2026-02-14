import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Uploader skill (mock publish)")
    ap.add_argument("job_file", help="Path to uploader job json")
    args = ap.parse_args()

    profile = os.environ.get("GEMINI_PROFILE", "")
    if profile.lower() != "ops":
        print(f"WARNING: uploader running outside ops profile (GEMINI_PROFILE={profile or 'unset'})")

    job_path = Path(args.job_file)
    job = load_json(job_path)
    inputs = job.get("inputs") or {}
    listing_path_str = (
        inputs.get("listing_path")
        or job.get("listing_path")
        or job.get("input_data")
    )
    if not isinstance(listing_path_str, str) or not listing_path_str.strip():
        raise SystemExit("Missing listing_path in job (expected inputs.listing_path or input_data)")

    listing_path = Path(listing_path_str)
    if not listing_path.exists():
        raise SystemExit(f"Listing file not found: {listing_path}")

    _listing = load_json(listing_path)

    POSTED_DIR.mkdir(parents=True, exist_ok=True)
    out = POSTED_DIR / f"live_{now_stamp()}.json"
    receipt = {
        "status": "live",
        "platform": "mock_store",
        "url": f"http://mock-store.com/item/{now_stamp()}",
        "source_listing_path": str(listing_path),
        "published_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("SUCCESS: Published to Mock Store")


if __name__ == "__main__":
    main()

