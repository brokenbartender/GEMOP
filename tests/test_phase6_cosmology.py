from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PhaseVICosmologyTests(unittest.TestCase):
    def test_event_horizon_split_and_state_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_phase6_") as td:
            run_dir = Path(td).resolve()
            dense_prompt = "\n\n".join(
                [
                    "Architecture migration task with strict constraints.",
                    "Must preserve security boundaries and never break tests.",
                    "Required files: scripts/triad_orchestrator.ps1, scripts/agent_runner_v2.py, scripts/iolaus_cauterize.py.",
                    "Add event horizon and hawking protocols with exact behavior and verification gates.",
                ]
                * 12
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "event_horizon.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--prompt",
                    dense_prompt,
                    "--context-radius",
                    "256",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("split_required"), msg=cp.stdout)
            self.assertGreaterEqual(len(out.get("shards") or []), 2)

            state_path = run_dir / "state" / "event_horizon.json"
            self.assertTrue(state_path.exists(), msg=f"missing {state_path}")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state.get("split_required"))

    def test_hawking_emitter_writes_micro_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_phase6_") as td:
            run_dir = Path(td).resolve()
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "hawking_emitter.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--source",
                    "test",
                    "--reason",
                    "dependency_missing",
                    "--agent",
                    "2",
                    "--round",
                    "1",
                    "--pid",
                    "999999",
                    "--no-bus",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            row = json.loads(cp.stdout)
            self.assertIn("dependency_missing", row.get("summary", ""))

            radiation_path = run_dir / "state" / "hawking_radiation.jsonl"
            self.assertTrue(radiation_path.exists(), msg=f"missing {radiation_path}")
            lines = [ln for ln in radiation_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 1)

    def test_iolaus_lyapunov_triggers_hawking_radiation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_phase6_") as td:
            run_dir = Path(td).resolve()
            state_dir = run_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "pids.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {"agent": 1, "round": 1, "pid": 999999},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "iolaus_cauterize.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--agent",
                    "1",
                    "--round",
                    "1",
                    "--lyapunov",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)

            radiation_path = state_dir / "hawking_radiation.jsonl"
            self.assertTrue(radiation_path.exists(), msg=f"missing {radiation_path}")
            rows = [json.loads(ln) for ln in radiation_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(rows), 1)
            self.assertTrue(any(r.get("reason") == "lyapunov_divergence" for r in rows))


if __name__ == "__main__":
    unittest.main()
