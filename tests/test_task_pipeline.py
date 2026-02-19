from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TaskPipelineTests(unittest.TestCase):
    def test_task_pipeline_writes_round_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_tp_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)

            contract_cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "task_contract.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--prompt",
                    "Build a cohesive multi-agent pipeline. Must include verification.",
                    "--pattern",
                    "debate",
                    "--round",
                    "2",
                    "--max-rounds",
                    "3",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(contract_cp.returncode, 0, msg=contract_cp.stderr or contract_cp.stdout)

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "task_pipeline.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "2",
                    "--pattern",
                    "debate",
                    "--prompt",
                    "Build a cohesive multi-agent pipeline. Must include verification.",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("stage"), "planner_executor")
            self.assertTrue(out.get("prompt_addendum"))

            self.assertTrue((run_dir / "state" / "task_pipeline_round2.json").exists())
            self.assertTrue((run_dir / "state" / "task_pipeline_round2.md").exists())
            self.assertTrue((run_dir / "state" / "task_pipeline_latest.json").exists())

    def test_task_pipeline_rank_mode_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_tp_rank_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)

            # Two agents with different supervisor/output quality.
            (run_dir / "round2_agent1.md").write_text(
                "```json DECISION_JSON\n{\"summary\":\"a\",\"files\":[\"scripts/x.py\"],\"commands\":[\"python -m pytest -q tests\"],\"risks\":[],\"confidence\":0.7}\n```\n```diff\ndiff --git a/scripts/x.py b/scripts/x.py\n--- a/scripts/x.py\n+++ b/scripts/x.py\n@@ -1 +1 @@\n-print('a')\n+print('b')\n```\nCOMPLETED\n",
                encoding="utf-8",
            )
            (run_dir / "round2_agent2.md").write_text("No decision json here.\n", encoding="utf-8")
            (state / "supervisor_round2.json").write_text(
                json.dumps(
                    {
                        "verdicts": [
                            {"agent": 1, "score": 82, "status": "OK"},
                            {"agent": 2, "score": 84, "status": "WARN"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "task_pipeline.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "2",
                    "--rank",
                    "--agent-count",
                    "2",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("ok"))
            self.assertEqual(int(out.get("top_agent") or 0), 1)
            self.assertTrue((state / "task_rank_round2.json").exists())

    def test_task_pipeline_fails_without_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_tp_fail_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "task_pipeline.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "1",
                    "--pattern",
                    "debate",
                    "--prompt",
                    "x",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertNotEqual(cp.returncode, 0)
            out = json.loads(cp.stdout)
            self.assertFalse(out.get("ok"))


if __name__ == "__main__":
    unittest.main()
