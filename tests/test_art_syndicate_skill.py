from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = REPO_ROOT / "ramshare" / "skills" / "skill_art_syndicate.py"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ArtSyndicateSkillTests(unittest.TestCase):
    def test_choose_candidate_avoids_high_similarity(self) -> None:
        mod = load_module(MOD_PATH)
        concepts = [
            "Detroit Riverwalk minimal line sigil",
            "Sleeping Bear Dunes travel badge monoline emblem",
        ]
        catalog = ["Detroit Riverwalk | Minimal Line Art"]
        chosen = mod.choose_candidate(
            concepts=concepts,
            catalog_titles=catalog,
            used=set(),
            query="trendy spots in michigan 2026",
            location_brief_map={
                "Detroit Riverwalk": {"spot": "Detroit Riverwalk", "verified": True, "architecture_cues": ["riverwalk", "waterfront"]},
                "Sleeping Bear Dunes": {"spot": "Sleeping Bear Dunes", "verified": True, "architecture_cues": ["dunes", "lakeshore"]},
            },
            threshold=0.6,
        )
        self.assertTrue(chosen)
        self.assertIn("Sleeping Bear Dunes", str(chosen.get("concept") or ""))

    def test_council_review_passes_clean_draft(self) -> None:
        mod = load_module(MOD_PATH)
        with tempfile.TemporaryDirectory(prefix="gemop_art_syn_") as td:
            root = Path(td).resolve()
            analysis = root / "analysis.json"
            preflight = root / "preflight.json"
            draft = root / "draft.json"
            analysis.write_text(json.dumps({"analysis": {"flags": []}}, indent=2), encoding="utf-8")
            preflight.write_text(json.dumps({"status": "pass"}, indent=2), encoding="utf-8")
            draft.write_text(
                json.dumps(
                    {
                        "title": "Sleeping Bear Dunes | Minimal Line Art",
                        "mock_image_prompt": "clean line art michigan travel",
                        "tags": [
                            "sleeping bear dunes",
                            "michigan",
                            "travel",
                            "line art",
                            "minimalist",
                            "gift idea",
                            "lakeshore",
                            "badge",
                        ],
                        "asset_path": str(root / "asset.png"),
                        "quality_outputs": {
                            "analysis_json": str(analysis),
                            "preflight_json": str(preflight),
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            review = mod.council_review(
                draft_path=draft,
                catalog_titles=["Detroit Riverwalk | Minimal Line Art"],
                banned_terms=["Disney", "Marvel"],
                candidate_concept="Sleeping Bear Dunes Michigan minimal line sigil",
                location_brief={"spot": "Sleeping Bear Dunes", "verified": True, "architecture_cues": ["dunes", "lakeshore"]},
            )
            self.assertTrue(bool(review.get("approved")))


if __name__ == "__main__":
    unittest.main()
