from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rb_style_train.py"


def make_lineart(path: Path, *, w: int, h: int, variant: int) -> None:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    stroke = max(2, w // 420)
    cx, cy = w // 2, h // 2
    r = min(w, h) // 4
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(0, 0, 0, 255), width=stroke)
    if variant % 2 == 0:
        draw.line((cx - r, cy, cx + r, cy), fill=(0, 0, 0, 255), width=stroke)
        draw.line((cx, cy - r, cx, cy + r), fill=(0, 0, 0, 255), width=stroke)
    else:
        draw.line((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 255), width=stroke)
        draw.line((cx - r, cy + r, cx + r, cy - r), fill=(0, 0, 0, 255), width=stroke)
    img.save(path, format="PNG")


class RbStyleTrainTests(unittest.TestCase):
    def test_trainer_builds_style_profile_from_zip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_rb_style_") as td:
            root = Path(td).resolve()
            src_dir = root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            for i in range(4):
                make_lineart(src_dir / f"michigan_symbol_{i}.png", w=1200, h=1400, variant=i)

            zip_path = root / "art.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in sorted(src_dir.glob("*.png")):
                    zf.write(p, arcname=f"set/{p.name}")

            out_profile = root / "style_profile.json"
            extract_dir = root / "extract"
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "--zip",
                    os.fspath(zip_path),
                    "--extract-dir",
                    os.fspath(extract_dir),
                    "--out-profile",
                    os.fspath(out_profile),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=120,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            self.assertTrue(out_profile.exists())
            payload = json.loads(out_profile.read_text(encoding="utf-8"))
            self.assertIn("generator_overrides", payload)
            self.assertIn("prompt_modifiers", payload)
            self.assertGreaterEqual(int(payload.get("source", {}).get("image_count", 0)), 4)


if __name__ == "__main__":
    unittest.main()
