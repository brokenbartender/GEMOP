from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
PACKETS_DIR = REPO_ROOT / "ramshare" / "evidence" / "upload_packets"
STICKERIZE_SCRIPT = REPO_ROOT / "scripts" / "rb_stickerize.py"
PREFLIGHT_SCRIPT = REPO_ROOT / "scripts" / "rb_preflight.py"


def slug(s: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(s))
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "listing"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_cmd(args: list[str]) -> tuple[int, str]:
    cp = subprocess.run(args, text=True, capture_output=True, cwd=str(REPO_ROOT))
    out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    return cp.returncode, out


def write_manual_steps(packet_dir: Path, listing: Dict[str, Any], manifest_path: Path) -> Path:
    steps = [
        "# Redbubble Manual Publish Steps",
        "",
        "1. Open your Redbubble dashboard and start a new upload.",
        "2. Upload `artwork_master.png` as the main design.",
        "3. Use `artwork_sticker.png` for sticker-specific replacement if needed.",
        "4. Paste title from `upload_manifest.json` -> `title`.",
        "5. Paste description from `upload_manifest.json` -> `description`.",
        "6. Paste tags from `upload_manifest.json` -> `tags_csv`.",
        "7. Apply product toggles and markups from `upload_manifest.json` -> `upload_settings`.",
        "8. Confirm mature content setting from `upload_settings.mature_default`.",
        "9. Final visual QA in product previews, then click Publish.",
        "",
        "Safety notes:",
        "- Do not use stealth automation or bypass site controls.",
        "- Keep uploads within safe pacing caps in `upload_settings`.",
        "",
        f"Source listing: {listing.get('source_input_path', '')}",
        f"Manifest: {manifest_path}",
    ]
    out = packet_dir / "manual_steps.md"
    out.write_text("\n".join(steps).strip() + "\n", encoding="utf-8")
    return out


def write_social_copy(packet_dir: Path, listing: Dict[str, Any]) -> Path:
    posts = listing.get("social_posts") if isinstance(listing.get("social_posts"), dict) else {}
    lines = ["# Social Copy", ""]
    for platform in ("instagram", "pinterest", "x"):
        txt = str(posts.get(platform) or "").strip()
        if not txt:
            continue
        lines.append(f"## {platform.capitalize()}")
        lines.append(txt)
        lines.append("")
    out = packet_dir / "social_posts.md"
    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out


def build_packet(listing_path: Path) -> Dict[str, Any]:
    listing = load_json(listing_path)
    title = str(listing.get("title") or "listing")
    packet_dir = PACKETS_DIR / f"{now_stamp()}_{slug(title)[:48]}"
    packet_dir.mkdir(parents=True, exist_ok=True)

    asset_path = Path(str(listing.get("asset_path") or ""))
    if not asset_path.exists():
        raise FileNotFoundError(f"Listing asset not found: {asset_path}")

    master = packet_dir / "artwork_master.png"
    shutil.copyfile(asset_path, master)

    sticker = packet_dir / "artwork_sticker.png"
    rc, out = run_cmd(
        [
            sys.executable,
            str(STICKERIZE_SCRIPT),
            "--input",
            str(master),
            "--output",
            str(sticker),
            "--canvas-px",
            "5000",
            "--padding-pct",
            "0.08",
        ]
    )
    if rc != 0:
        raise RuntimeError(f"Stickerize failed: {out}")

    preflight_master = packet_dir / "preflight_master.json"
    rc1, out1 = run_cmd(
        [
            sys.executable,
            str(PREFLIGHT_SCRIPT),
            "--image",
            str(master),
            "--product",
            "tshirt",
            "--json-out",
            str(preflight_master),
        ]
    )
    preflight_sticker = packet_dir / "preflight_sticker.json"
    rc2, out2 = run_cmd(
        [
            sys.executable,
            str(PREFLIGHT_SCRIPT),
            "--image",
            str(sticker),
            "--product",
            "sticker",
            "--json-out",
            str(preflight_sticker),
        ]
    )

    tags = listing.get("tags") if isinstance(listing.get("tags"), list) else []
    tags_csv = ", ".join(str(x).strip() for x in tags if str(x).strip())
    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "listing_path": str(listing_path),
        "title": listing.get("title"),
        "description": listing.get("seo_description"),
        "tags": tags,
        "tags_csv": tags_csv,
        "price_point": listing.get("price_point"),
        "upload_settings": listing.get("upload_settings", {}),
        "files": {
            "master_artwork": str(master),
            "sticker_artwork": str(sticker),
            "preflight_master": str(preflight_master),
            "preflight_sticker": str(preflight_sticker),
        },
        "checks": {
            "master_preflight_rc": rc1,
            "sticker_preflight_rc": rc2,
            "master_preflight_log": out1,
            "sticker_preflight_log": out2,
        },
        "social_posts": listing.get("social_posts", {}),
    }
    manifest_path = packet_dir / "upload_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    manual_steps = write_manual_steps(packet_dir=packet_dir, listing=listing, manifest_path=manifest_path)
    social_copy = write_social_copy(packet_dir=packet_dir, listing=listing)

    return {
        "packet_dir": str(packet_dir),
        "manifest_path": str(manifest_path),
        "manual_steps": str(manual_steps),
        "social_copy": str(social_copy),
        "status": "ready" if rc1 == 0 and rc2 == 0 else "ready_with_warnings",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build manual-safe Redbubble upload packet from a staged listing.")
    ap.add_argument("--listing", required=True)
    args = ap.parse_args()

    result = build_packet(Path(args.listing).resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
