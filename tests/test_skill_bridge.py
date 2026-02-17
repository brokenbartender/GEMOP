from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_py(args: list[str], *, env: dict[str, str] | None = None, timeout_s: int = 120) -> subprocess.CompletedProcess[str]:
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=e,
        timeout=timeout_s,
    )


class SkillBridgeTests(unittest.TestCase):
    def test_select_picks_relevant_skill_from_configured_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_skills_") as td:
            root = Path(td).resolve()
            codex_skills = root / "codex" / "skills"
            gemini_skills = root / "gemini" / "skills"
            (codex_skills / "playwright" ).mkdir(parents=True, exist_ok=True)
            (gemini_skills / "pdf").mkdir(parents=True, exist_ok=True)

            (codex_skills / "playwright" / "SKILL.md").write_text(
                "# playwright\nAutomate a real browser for UI-flow debugging.\n",
                encoding="utf-8",
            )
            (gemini_skills / "pdf" / "SKILL.md").write_text(
                "# pdf\nWork with PDF rendering and extraction.\n",
                encoding="utf-8",
            )

            run_dir = root / "run"
            out_md = run_dir / "state" / "skills_selected.md"
            out_json = run_dir / "state" / "skills_selected.json"

            env = {
                "GEMINI_OP_REPO_ROOT": str(REPO_ROOT),
                "GEMINI_OP_SKILLS_DIR_CODEX": str(codex_skills),
                "GEMINI_OP_SKILLS_DIR_GEMINI": str(gemini_skills),
                "GEMINI_OP_SKILLS_PREFER": "codex",
            }

            cp = run_py(
                [
                    os.fspath(Path(sys.executable)),
                    str(REPO_ROOT / "scripts" / "skill_bridge.py"),
                    "select",
                    "--task",
                    "please do UI testing with playwright",
                    "--max-skills",
                    "5",
                    "--max-chars",
                    "20000",
                    "--out-md",
                    os.fspath(out_md),
                    "--out-json",
                    os.fspath(out_json),
                    "--force-index",
                ],
                env=env,
                timeout_s=120,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr[-4000:])
            self.assertTrue(out_md.exists(), msg=f"missing {out_md}")
            self.assertTrue(out_json.exists(), msg=f"missing {out_json}")
            md = out_md.read_text(encoding="utf-8", errors="ignore")
            self.assertIn("## playwright", md)

            data = json.loads(out_json.read_text(encoding="utf-8"))
            selected = [s["name"] for s in data.get("selected") or []]
            self.assertIn("playwright", selected)
