from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TaskContractTests(unittest.TestCase):
    def test_task_contract_writes_state_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_tc_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)

            prompt = (
                "Implement scripts/task_contract.py and scripts/task_pipeline.py.\n"
                "You must avoid duplicate logic.\n"
                "Required: include tests and verification commands.\n"
                "- Update scripts/triad_orchestrator.ps1\n"
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "task_contract.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--prompt",
                    prompt,
                    "--pattern",
                    "debate",
                    "--round",
                    "1",
                    "--max-rounds",
                    "3",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("ok"))
            self.assertTrue((run_dir / "state" / "task_contract.json").exists())
            self.assertTrue((run_dir / "state" / "task_contract.md").exists())
            self.assertTrue((run_dir / "state" / "task_contract_round1.json").exists())

            payload = json.loads((run_dir / "state" / "task_contract.json").read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("schema_version", -1)), 1)
            self.assertTrue(payload.get("constraints"))
            self.assertTrue(payload.get("deliverables"))
            self.assertTrue(payload.get("verification"))


if __name__ == "__main__":
    unittest.main()
