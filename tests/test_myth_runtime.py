from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MythRuntimeTests(unittest.TestCase):
    def test_myth_runtime_dispatch_writes_round_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_myth_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)
            (run_dir / "state" / "world_state.md").write_text("historical context for wormhole creation", encoding="utf-8")

            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "myth_runtime.py"),
                    "--repo-root",
                    os.fspath(REPO_ROOT),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--query",
                    "event horizon alignment",
                    "--round",
                    "2",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertTrue(out.get("ok"))
            self.assertTrue((run_dir / "state" / "myth_runtime_round2.json").exists())
            self.assertTrue((run_dir / "state" / "hubble_drift.json").exists())
            self.assertTrue((run_dir / "state" / "wormholes.jsonl").exists())
            self.assertTrue((run_dir / "state" / "dark_matter_profile.json").exists())


if __name__ == "__main__":
    unittest.main()
