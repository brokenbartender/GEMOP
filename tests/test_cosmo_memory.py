from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CosmoMemoryTests(unittest.TestCase):
    def test_hubble_drift_writes_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_hubble_") as td:
            run_dir = Path(td).resolve()
            (run_dir / "state").mkdir(parents=True, exist_ok=True)
            (run_dir / "state" / "world_state.md").write_text(
                "Legacy architecture notes with old retrieval assumptions.",
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "hubble_drift.py"),
                    "--repo-root",
                    os.fspath(REPO_ROOT),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--query",
                    "retrieval architecture",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertIn("avg_velocity", out)
            self.assertTrue((run_dir / "state" / "hubble_drift.json").exists())

    def test_wormhole_indexer_generates_nodes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_wormhole_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)
            source = state / "world_state.md"
            source.write_text("Historical run summary about event horizon and prompt splitting.", encoding="utf-8")
            (state / "hubble_drift.json").write_text(
                json.dumps(
                    {
                        "receding_entries": [
                            {
                                "path": str(source),
                                "distance": 0.9,
                                "velocity": 1.7,
                                "age_hours": 48,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "wormhole_indexer.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--query",
                    "event horizon",
                    "--max-nodes",
                    "5",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertGreaterEqual(int(out.get("count", 0)), 1)
            self.assertTrue((state / "wormholes.jsonl").exists())
            self.assertTrue((state / "wormholes.md").exists())

    def test_dark_matter_profile_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_darkmatter_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)
            (state / "supervisor_round1.json").write_text(
                json.dumps(
                    {
                        "verdicts": [
                            {"agent": 1, "mistakes": ["hallucination_risk", "delegation_ping_pong_risk"]},
                            {"agent": 2, "mistakes": ["security_injection_risk"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "dark_matter_halo.py"),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--query",
                    "stabilize alignment",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            out = json.loads(cp.stdout)
            self.assertIn("weights", out)
            self.assertTrue((state / "dark_matter_profile.json").exists())
            self.assertTrue((state / "dark_matter_profile.md").exists())

    def test_retrieval_pack_includes_wormhole_section(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_retrieval_") as td:
            run_dir = Path(td).resolve()
            state = run_dir / "state"
            state.mkdir(parents=True, exist_ok=True)
            (state / "wormholes.jsonl").write_text(
                json.dumps(
                    {
                        "anchor_id": "wormhole_abc",
                        "source_path": "C:/tmp/old.md",
                        "summary": "event horizon split summary",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(REPO_ROOT / "scripts" / "retrieval_pack.py"),
                    "--repo-root",
                    os.fspath(REPO_ROOT),
                    "--run-dir",
                    os.fspath(run_dir),
                    "--round",
                    "1",
                    "--query",
                    "event horizon",
                    "--max-per-section",
                    "10",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            payload = json.loads((state / "retrieval_pack_round1.json").read_text(encoding="utf-8"))
            sections = payload.get("sections", [])
            sec_ids = [s.get("id") for s in sections if isinstance(s, dict)]
            self.assertIn("wormholes", sec_ids)


if __name__ == "__main__":
    unittest.main()
