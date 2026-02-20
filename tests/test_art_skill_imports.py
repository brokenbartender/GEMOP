from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def import_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ArtSkillImportTests(unittest.TestCase):
    def test_key_art_skill_modules_import(self) -> None:
        targets = [
            REPO_ROOT / "ramshare" / "skills" / "skill_art_syndicate.py",
            REPO_ROOT / "ramshare" / "skills" / "skill_product_drafter.py",
            REPO_ROOT / "ramshare" / "skills" / "skill_art_director.py",
            REPO_ROOT / "ramshare" / "skills" / "skill_listing_generator.py",
            REPO_ROOT / "ramshare" / "skills" / "skill_librarian.py",
            REPO_ROOT / "ramshare" / "skills" / "skill_strategist.py",
        ]
        for path in targets:
            self.assertTrue(path.exists(), msg=f"missing file: {path}")
            _ = import_from_path(path)


if __name__ == "__main__":
    unittest.main()
