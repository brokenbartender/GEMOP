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
SCRIPT = REPO_ROOT / "scripts" / "marketplace_image_check.py"


def make_test_png(path: Path, w: int, h: int) -> None:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((w // 4, h // 4, (w * 3) // 4, (h * 3) // 4), outline=(0, 0, 0, 255), width=max(4, w // 300))
    img.save(path, format="PNG")


class MarketplaceImageCheckTests(unittest.TestCase):
    def test_redbubble_tshirt_passes_for_4500x5400(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_marketcheck_pass_") as td:
            root = Path(td).resolve()
            image = root / "ok.png"
            out = root / "report.json"
            make_test_png(image, 4500, 5400)

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "--image",
                    os.fspath(image),
                    "--market",
                    "redbubble",
                    "--product",
                    "tshirt",
                    "--json-out",
                    os.fspath(out),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["status"], "pass")

    def test_redbubble_tshirt_fails_for_small_image(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_marketcheck_fail_") as td:
            root = Path(td).resolve()
            image = root / "small.png"
            out = root / "report.json"
            make_test_png(image, 1000, 1000)

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "--image",
                    os.fspath(image),
                    "--market",
                    "redbubble",
                    "--product",
                    "tshirt",
                    "--json-out",
                    os.fspath(out),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertNotEqual(cp.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
