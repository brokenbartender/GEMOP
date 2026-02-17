from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_powershell(args: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None, timeout_s: int = 180) -> subprocess.CompletedProcess[str]:
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + args
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), text=True, capture_output=True, env=e, timeout=timeout_s)


class OrchestratorSkillInjectionTests(unittest.TestCase):
    def test_prompt_includes_selected_skill_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_inject_") as td:
            root = Path(td).resolve()

            # Minimal external skills tree.
            codex_skills = root / "codex" / "skills"
            gemini_skills = root / "gemini" / "skills"
            (codex_skills / "unicorn-debugger").mkdir(parents=True, exist_ok=True)
            (gemini_skills).mkdir(parents=True, exist_ok=True)

            marker = "UNICORN_DEBUGGER_MARKER_123"
            (codex_skills / "unicorn-debugger" / "SKILL.md").write_text(
                f"# unicorn-debugger\nUse this when debugging unicorn-related failures.\n{marker}\n",
                encoding="utf-8",
            )

            run_dir = root / "run"
            env = {
                "GEMINI_OP_MOCK_MODE": "1",
                "GEMINI_OP_REPO_ROOT": str(REPO_ROOT),
                "GEMINI_OP_SKILLS_DIR_CODEX": str(codex_skills),
                "GEMINI_OP_SKILLS_DIR_GEMINI": str(gemini_skills),
                "GEMINI_OP_SKILLS_PREFER": "codex",
            }

            cp = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "please use unicorn debugger to fix the bug",
                    "-Agents",
                    "1",
                    "-MaxRounds",
                    "1",
                    "-MaxParallel",
                    "1",
                ],
                env=env,
                timeout_s=180,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr[-4000:])

            prompt1 = run_dir / "prompt1.txt"
            self.assertTrue(prompt1.exists(), msg=f"missing {prompt1}")
            txt = prompt1.read_text(encoding="utf-8", errors="ignore")
            self.assertIn("[SKILLS - AUTO-SELECTED PLAYBOOKS]", txt)
            self.assertIn(marker, txt)

