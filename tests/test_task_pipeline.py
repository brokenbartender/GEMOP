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
