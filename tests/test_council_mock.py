from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_powershell(args: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None, timeout_s: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + args
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), text=True, capture_output=True, env=e, timeout=timeout_s)


class CouncilMockTests(unittest.TestCase):
    def test_mock_council_basic_and_resume(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_run_") as td:
            run_dir = Path(td).resolve()
            env = {"GEMINI_OP_MOCK_MODE": "1"}
            cp = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "test prompt",
                    "-Agents",
                    "3",
                    "-MaxRounds",
                    "1",
                    "-MaxParallel",
                    "2",
                ],
                env=env,
                timeout_s=120,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr[-4000:])

            for i in (1, 2, 3):
                p = run_dir / f"round1_agent{i}.md"
                self.assertTrue(p.exists(), msg=f"missing {p}")
                txt = p.read_text(encoding="utf-8", errors="ignore")
                self.assertIn("\nCOMPLETED\n", txt)

            # Resume should skip already-completed outputs.
            cp2 = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "test prompt",
                    "-Agents",
                    "3",
                    "-MaxRounds",
                    "1",
                    "-MaxParallel",
                    "2",
                    "-Resume",
                ],
                env=env,
                timeout_s=120,
            )
            self.assertEqual(cp2.returncode, 0, msg=cp2.stderr[-4000:])
            log = (run_dir / "triad_orchestrator.log").read_text(encoding="utf-8", errors="ignore")
            self.assertIn("resume_skip", log)

    def test_stop_file_stops_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_run_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)
            (run_dir / "state" / "STOP").write_text("STOP\n", encoding="utf-8")
            env = {"GEMINI_OP_MOCK_MODE": "1"}
            cp = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "test prompt",
                    "-Agents",
                    "3",
                    "-MaxRounds",
                    "1",
                ],
                env=env,
                timeout_s=60,
            )
            # Orchestrator may exit 0 or non-zero; require the STOPPED artifact.
            stopped = run_dir / "state" / "STOPPED.md"
            self.assertTrue(stopped.exists(), msg=f"expected {stopped} to exist; rc={cp.returncode} stderr={cp.stderr[-2000:]}")

    def test_timeout_kills_subprocess(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_run_") as td:
            run_dir = Path(td).resolve()
            scn = {
                "default": {"behavior": "sleep", "sleep_s": 5},
            }
            scn_path = run_dir / "scenario.json"
            scn_path.parent.mkdir(parents=True, exist_ok=True)
            scn_path.write_text(json.dumps(scn), encoding="utf-8")

            env = {
                "GEMINI_OP_MOCK_MODE": "1",
                "GEMINI_OP_FORCE_SUBPROCESS": "1",
                "GEMINI_OP_MOCK_SCENARIO": str(scn_path),
            }
            cp = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "timeout test",
                    "-Agents",
                    "2",
                    "-MaxRounds",
                    "1",
                    "-MaxParallel",
                    "2",
                    "-AgentTimeoutSec",
                    "1",
                ],
                env=env,
                timeout_s=60,
            )
            # May still exit 0; assert timeout was recorded.
            log = (run_dir / "triad_orchestrator.log").read_text(encoding="utf-8", errors="ignore")
            self.assertIn("agent_timeout", log)

    def test_patch_apply_requires_decision_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_run_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            (state / "decisions").mkdir(parents=True, exist_ok=True)

            # Decision claims it will touch a different file than the diff actually touches.
            (state / "decisions" / "round2_agent1.json").write_text(
                json.dumps({"files": ["docs/Other.md"], "summary": "noop", "commands": [], "risks": []}),
                encoding="utf-8",
            )

            out = run_dir / "round2_agent1.md"
            out.write_text(
                "\n".join(
                    [
                        "## Proposed patch",
                        "```diff",
                        "--- /dev/null",
                        "+++ b/docs/NewThing.md",
                        "@@",
                        "+hello",
                        "```",
                        "COMPLETED",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "council_patch_apply.py"),
                    "--repo-root",
                    os.fspath(REPO_ROOT),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "2",
                    "--agent",
                    "1",
                    "--require-decision-files",
                    "--dry-run",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertNotEqual(cp.returncode, 0, msg="expected failure when touched files not declared in DECISION_JSON")


if __name__ == "__main__":
    unittest.main()
