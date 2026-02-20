from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rb_lineart_generator.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class RbLineartGeneratorTests(unittest.TestCase):
    def test_generator_outputs_png(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_lineart_") as td:
            root = Path(td).resolve()
            out = root / "lineart.png"
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "--concept",
                    "Michigan heritage sigil",
                    "--prompt",
                    "minimal line art",
                    "--width",
                    "1200",
                    "--height",
                    "1400",
                    "--out",
                    os.fspath(out),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            self.assertTrue(out.exists())
            with Image.open(out) as img:
                self.assertEqual(img.size, (1200, 1400))

    def test_generator_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_lineart_det_") as td:
            root = Path(td).resolve()
            out1 = root / "a.png"
            out2 = root / "b.png"
            args = [
                os.fspath(Path(sys.executable)),
                os.fspath(SCRIPT),
                "--concept",
                "deterministic sigil",
                "--prompt",
                "determinism check",
                "--width",
                "1000",
                "--height",
                "1200",
            ]
            cp1 = subprocess.run(args + ["--out", os.fspath(out1)], cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=60)
            cp2 = subprocess.run(args + ["--out", os.fspath(out2)], cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=60)
            self.assertEqual(cp1.returncode, 0, msg=cp1.stderr or cp1.stdout)
            self.assertEqual(cp2.returncode, 0, msg=cp2.stderr or cp2.stdout)
            self.assertEqual(sha256_file(out1), sha256_file(out2))

    def test_generator_accepts_style_profile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_lineart_style_") as td:
            root = Path(td).resolve()
            out = root / "styled.png"
            profile = root / "style_profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "style_name": "test_style",
                        "generator_overrides": {
                            "style": "sigil_hybrid",
                            "ring_count_range": [6, 6],
                            "rays_range": [20, 20],
                            "nodes_range": [30, 30],
                            "overlay_lines_range": [12, 12],
                            "overlay_arcs_range": [10, 10],
                            "stroke_px_range": [3, 3],
                            "center_jitter_px": 5,
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "--concept",
                    "style profile check",
                    "--prompt",
                    "styled output",
                    "--width",
                    "1100",
                    "--height",
                    "1300",
                    "--style",
                    "hybrid",
                    "--style-profile",
                    os.fspath(profile),
                    "--out",
                    os.fspath(out),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            self.assertTrue(out.exists())
            with Image.open(out) as img:
                self.assertEqual(img.size, (1100, 1300))


if __name__ == "__main__":
    unittest.main()
