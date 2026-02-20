from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = REPO_ROOT / "ramshare" / "skills" / "skill_trend_spotter.py"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TrendSpotterUtilsTests(unittest.TestCase):
    def test_extract_michigan_spots(self) -> None:
        mod = load_module(MOD_PATH)
        rows = [
            "Best things to do in Mackinac Island Michigan for 2026",
            "Reddit travel: Sleeping Bear Dunes guide",
            "Detroit Riverwalk events 2026",
        ]
        spots = mod.extract_michigan_spots(rows)
        joined = " | ".join(spots)
        self.assertIn("Mackinac Island", joined)
        self.assertIn("Sleeping Bear Dunes", joined)


if __name__ == "__main__":
    unittest.main()
