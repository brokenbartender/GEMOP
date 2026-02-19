from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase6ContractValidationTests(unittest.TestCase):
    def _run_validator(self, run_dir: Path, round_n: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                os.fspath(Path(sys.executable)),
                os.fspath(REPO_ROOT / "scripts" / "validate_phase6_contracts.py"),
                "--run-dir",
                os.fspath(run_dir),
                "--round",
                str(round_n),
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=30,
        )

    def _run_contract_pipeline_builders(self, run_dir: Path, round_n: int, prompt: str) -> None:
        cp_task = subprocess.run(
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
                str(round_n),
                "--max-rounds",
                "3",
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(cp_task.returncode, 0, msg=cp_task.stderr or cp_task.stdout)

        cp_pipeline = subprocess.run(
            [
                os.fspath(Path(sys.executable)),
                os.fspath(REPO_ROOT / "scripts" / "task_pipeline.py"),
                "--run-dir",
                os.fspath(run_dir),
                "--round",
                str(round_n),
                "--pattern",
                "debate",
                "--prompt",
                prompt,
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(cp_pipeline.returncode, 0, msg=cp_pipeline.stderr or cp_pipeline.stdout)

    def test_validator_passes_with_valid_contracts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_p6_valid_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)
            prompt = "validate contracts"

            # Generate valid artifacts through real scripts.
            cp1 = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "myth_runtime.py"),
                    "--repo-root",
                    os.fspath(REPO_ROOT),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--query",
                    prompt,
                    "--round",
                    "1",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(cp1.returncode, 0, msg=cp1.stderr)
            self._run_contract_pipeline_builders(run_dir, 1, prompt)

            cp = self._run_validator(run_dir, 1)
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("ok"))

    def test_validator_fails_on_bad_dark_matter_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_p6_invalid_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)

            # Minimal invalid payloads.
            (state / "dark_matter_profile.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": 1.0,
                        "query": "x",
                        "weights": {"safety": 0.2},
                        "directives": [],
                    }
                ),
                encoding="utf-8",
            )
            (state / "myth_runtime_round1.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": 1.0,
                        "round": 1,
                        "query": "x",
                        "ok": True,
                        "results": [],
                    }
                ),
                encoding="utf-8",
            )

            cp = self._run_validator(run_dir, 1)
            self.assertNotEqual(cp.returncode, 0, msg="expected validator failure")
            out = json.loads(cp.stdout)
            self.assertFalse(out.get("ok"))
            self.assertTrue(any(str(e).startswith("dark_matter.weights") or str(e).startswith("myth_runtime.results") for e in out.get("errors", [])))


if __name__ == "__main__":
    unittest.main()
