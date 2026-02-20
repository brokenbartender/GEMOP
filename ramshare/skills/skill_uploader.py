import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"
UPLOAD_PACKET_SCRIPT = REPO_ROOT / "scripts" / "rb_upload_packet.py"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def mode() -> str:
    # manual_packet (default) keeps account-safe behavior: prepare everything, human clicks publish.
    return str(os.environ.get("REDBUBBLE_UPLOAD_MODE", "manual_packet")).strip().lower()


def run_cmd(args: list[str]) -> tuple[int, str]:
    cp = subprocess.run(args, text=True, capture_output=True, cwd=str(REPO_ROOT))
    out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    return cp.returncode, out


def build_packet(listing_path: Path) -> Dict[str, Any]:
    rc, out = run_cmd([sys.executable, str(UPLOAD_PACKET_SCRIPT), "--listing", str(listing_path)])
    if rc != 0:
        raise RuntimeError(f"Upload packet build failed: {out}")
    try:
        return json.loads(out)
    except Exception:
        # Fallback: parse by finding first/last json braces in mixed logs.
        start = out.find("{")
        end = out.rfind("}")
        if start >= 0 and end > start:
            return json.loads(out[start : end + 1])
        raise RuntimeError(f"Upload packet returned non-JSON output: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Uploader skill (manual-safe Redbubble packet by default)")
    ap.add_argument("job_file", help="Path to uploader job json")
    args = ap.parse_args()

    profile = os.environ.get("GEMINI_PROFILE", "")
    if profile.lower() != "ops":
        print(f"WARNING: uploader running outside ops profile (GEMINI_PROFILE={profile or 'unset'})")

    job_path = Path(args.job_file)
    job = load_json(job_path)
    inputs = job.get("inputs") or {}
    listing_path_str = inputs.get("listing_path") or job.get("listing_path") or job.get("input_data")
    if not isinstance(listing_path_str, str) or not listing_path_str.strip():
        raise SystemExit("Missing listing_path in job (expected inputs.listing_path or input_data)")

    listing_path = Path(listing_path_str)
    if not listing_path.exists():
        raise SystemExit(f"Listing file not found: {listing_path}")
    listing = load_json(listing_path)

    POSTED_DIR.mkdir(parents=True, exist_ok=True)
    out = POSTED_DIR / f"live_{now_stamp()}.json"

    active_mode = mode()
    if active_mode == "mock":
        receipt = {
            "status": "live",
            "platform": "mock_store",
            "url": f"http://mock-store.com/item/{now_stamp()}",
            "source_listing_path": str(listing_path),
            "published_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print("SUCCESS: Published to Mock Store")
        return

    packet = build_packet(listing_path=listing_path)
    receipt = {
        "status": "awaiting_manual_publish",
        "platform": "redbubble_manual_packet",
        "source_listing_path": str(listing_path),
        "title": listing.get("title", ""),
        "packet": packet,
        "published_at": dt.datetime.now().isoformat(timespec="seconds"),
        "next_action": "Open manual_steps.md from packet and click Publish in Redbubble UI.",
    }
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"SUCCESS: Upload packet ready for manual publish ({packet.get('packet_dir', '')})")


if __name__ == "__main__":
    main()
