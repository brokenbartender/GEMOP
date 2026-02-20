from __future__ import annotations

import importlib.util
import random
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = REPO_ROOT / "scripts" / "rb_style_cycle.py"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RbStyleCycleTests(unittest.TestCase):
    def test_style_distance_zero_when_identical(self) -> None:
        mod = load_module(MOD_PATH)
        summary = {
            "alpha_ratio": {"median": 0.08, "p10": 0.05, "p90": 0.12},
            "edge_density": {"median": 0.012, "p10": 0.009, "p90": 0.016},
            "bbox_fill_ratio": {"median": 0.48, "p10": 0.41, "p90": 0.55},
            "symmetry_x": {"median": 0.72, "p10": 0.61, "p90": 0.81},
            "symmetry_y": {"median": 0.70, "p10": 0.60, "p90": 0.80},
            "component_count": {"median": 22.0, "p10": 18.0, "p90": 29.0},
            "stroke_to_fill_ratio": {"median": 0.14, "p10": 0.10, "p90": 0.19},
        }
        dist = mod.style_distance(summary, summary)
        self.assertLessEqual(float(dist), 1e-9)

    def test_mutate_overrides_stays_in_bounds(self) -> None:
        mod = load_module(MOD_PATH)
        base = {
            "style": "sigil_hybrid",
            "ring_count_range": [4, 7],
            "rays_range": [12, 20],
            "nodes_range": [18, 34],
            "stroke_px_range": [2, 5],
            "overlay_lines_range": [10, 20],
            "overlay_arcs_range": [8, 16],
            "center_jitter_px": 10,
        }
        rng = random.Random(11)
        out = mod.mutate_overrides(base, rng=rng, scale=0.8)
        self.assertIn(out["style"], mod.STYLE_CHOICES)
        self.assertGreaterEqual(out["ring_count_range"][0], 2)
        self.assertLessEqual(out["ring_count_range"][1], 12)
        self.assertGreaterEqual(out["rays_range"][0], 4)
        self.assertLessEqual(out["rays_range"][1], 36)
        self.assertGreaterEqual(out["nodes_range"][0], 4)
        self.assertLessEqual(out["nodes_range"][1], 80)
        self.assertGreaterEqual(out["stroke_px_range"][0], 1)
        self.assertLessEqual(out["stroke_px_range"][1], 20)
        self.assertGreaterEqual(out["overlay_lines_range"][0], 0)
        self.assertLessEqual(out["overlay_lines_range"][1], 64)
        self.assertGreaterEqual(out["overlay_arcs_range"][0], 0)
        self.assertLessEqual(out["overlay_arcs_range"][1], 64)
        self.assertGreaterEqual(int(out["center_jitter_px"]), 0)
        self.assertLessEqual(int(out["center_jitter_px"]), 48)


if __name__ == "__main__":
    unittest.main()

