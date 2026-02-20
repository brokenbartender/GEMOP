from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rb_upload_packet.py"


def make_png(path: Path, w: int = 4500, h: int = 5400) -> None:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((w // 4, h // 4, (w * 3) // 4, (h * 3) // 4), outline=(0, 0, 0, 255), width=max(4, w // 350))
    img.save(path, format="PNG")


class RbUploadPacketTests(unittest.TestCase):
    def test_packet_builds_expected_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_rb_packet_") as td:
            root = Path(td).resolve()
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "data").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "evidence").mkdir(parents=True, exist_ok=True)

            # Copy required scripts/data so rb_upload_packet can run in isolated temp root.
            for rel in (
                "scripts/rb_stickerize.py",
                "scripts/rb_preflight.py",
                "scripts/analyze_png_lineart.py",
                "scripts/marketplace_image_check.py",
            ):
                src = REPO_ROOT / rel
                dst = root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            shutil.copy2(REPO_ROOT / "data" / "marketplace_image_standards.json", root / "data" / "marketplace_image_standards.json")

            asset = root / "asset.png"
            make_png(asset)
            listing = root / "listing.json"
            listing.write_text(
                json.dumps(
                    {
                        "title": "Detroit Skyline | Minimal Line Art",
                        "seo_description": "High-resolution minimal line-art design.",
                        "tags": ["detroit", "minimal line art", "michigan"],
                        "price_point": 24.99,
                        "asset_path": str(asset),
                        "upload_settings": {"enabled_products": ["sticker", "classic_tshirt"]},
                        "social_posts": {"instagram": "Test post"},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)
            cp = subprocess.run(
                [os.fspath(Path(sys.executable)), os.fspath(SCRIPT), "--listing", os.fspath(listing)],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=120,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            payload = json.loads(cp.stdout)
            packet_dir = Path(payload["packet_dir"])
            self.assertTrue((packet_dir / "upload_manifest.json").exists())
            self.assertTrue((packet_dir / "manual_steps.md").exists())
            self.assertTrue((packet_dir / "social_posts.md").exists())
            self.assertTrue((packet_dir / "artwork_master.png").exists())
            self.assertTrue((packet_dir / "artwork_sticker.png").exists())


if __name__ == "__main__":
    unittest.main()
