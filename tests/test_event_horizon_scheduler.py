from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class EventHorizonSchedulerTests(unittest.TestCase):
    def test_selects_shards_by_round(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_ehs_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)
            (state / "event_horizon.json").write_text(
                json.dumps(
                    {
                        "split_required": True,
                        "shards": ["shard-a", "shard-b", "shard-c"],
                    }
                ),
                encoding="utf-8",
            )

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "event_horizon_scheduler.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "2",
                    "--default-prompt",
                    "fallback",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("split_required"))
            self.assertEqual(out.get("prompt"), "shard-b")
            self.assertEqual(int(out.get("shard_index", -1)), 1)
            self.assertTrue((state / "event_horizon_schedule.json").exists())

    def test_falls_back_without_split(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_ehs_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "event_horizon_scheduler.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "1",
                    "--default-prompt",
                    "fallback",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertFalse(out.get("split_required"))
            self.assertEqual(out.get("prompt"), "fallback")


if __name__ == "__main__":
    unittest.main()
