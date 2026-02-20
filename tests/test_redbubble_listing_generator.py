from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "ramshare" / "skills" / "skill_listing_generator.py"


def make_png(path: Path, w: int = 1200, h: int = 1200) -> None:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((w // 4, h // 4, (w * 3) // 4, (h * 3) // 4), outline=(0, 0, 0, 255), width=max(3, w // 200))
    img.save(path, format="PNG")


class RedbubbleListingGeneratorTests(unittest.TestCase):
    def test_generates_rich_listing_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_rb_listing_") as td:
            root = Path(td).resolve()
            (root / "ramshare" / "evidence" / "staging").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "evidence" / "rejected").mkdir(parents=True, exist_ok=True)
            (root / "data" / "redbubble").mkdir(parents=True, exist_ok=True)

            # Minimal shop profile and ban list.
            (root / "data" / "redbubble" / "shop_profile.json").write_text(
                json.dumps(
                    {
                        "seo": {
                            "title": {"min_chars": 24, "max_chars": 70, "patterns": ["{theme} | Minimal Line Art"]},
                            "tags": {"min_count": 8, "max_count": 15, "core": ["minimal line art", "michigan", "gift idea"]},
                            "description_blocks": ["High-resolution transparent artwork."],
                            "cta": ["Save this design to your favorites."]
                        },
                        "products": {
                            "enabled": ["sticker", "classic_tshirt"],
                            "default_markup_pct": {"sticker": 35, "classic_tshirt": 25}
                        },
                        "upload_policy": {"manual_publish_required": True, "safe_daily_upload_cap": 8, "safe_hourly_upload_cap": 3},
                        "social": {"hashtags": ["#minimalart", "#lineart"]}
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (root / "data" / "redbubble" / "ip_risk_terms.txt").write_text("Disney\nMarvel\n", encoding="utf-8")

            asset = root / "asset.png"
            make_png(asset)
            draft = root / "draft.json"
            draft.write_text(
                json.dumps(
                    {
                        "title": "Detroit Riverline",
                        "concept": "Detroit river skyline minimal line art",
                        "tags": ["detroit", "line art", "skyline"],
                        "asset_path": str(asset),
                        "price_point": 24.99
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            reviewed = root / "reviewed.json"
            reviewed.write_text(
                json.dumps(
                    {
                        "status": "reviewed_pass",
                        "source_draft_path": str(draft),
                        "title": "Detroit Riverline",
                        "concept": "Detroit river skyline minimal line art",
                        "tags": ["detroit", "line art", "skyline"],
                        "asset_path": str(asset),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            job = root / "job.json"
            job.write_text(
                json.dumps(
                    {
                        "id": "listing-job",
                        "task_type": "listing_generator",
                        "target_profile": "research",
                        "inputs": {"draft_path": str(reviewed)},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)
            cp = subprocess.run(
                [os.fspath(Path(sys.executable)), os.fspath(SCRIPT), os.fspath(job)],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            files = sorted((root / "ramshare" / "evidence" / "staging").glob("listing_*.json"))
            self.assertTrue(files, msg="no staged listing produced")
            payload = json.loads(files[-1].read_text(encoding="utf-8"))
            self.assertIn("social_posts", payload)
            self.assertIn("upload_settings", payload)
            self.assertGreaterEqual(len(payload.get("tags", [])), 8)
            self.assertLessEqual(len(payload.get("tags", [])), 15)


if __name__ == "__main__":
    unittest.main()
