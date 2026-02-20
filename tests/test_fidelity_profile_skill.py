from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_fidelity_profile.py"


class FidelityProfileSkillTests(unittest.TestCase):
    def test_generates_profile_report_offline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_fidelity_profile_") as td:
            root = Path(td).resolve()
            inbox = root / "ramshare" / "evidence" / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            job_path = inbox / "job.fidelity_profile_test.json"
            job = {
                "id": "fidelity-profile-test-001",
                "task_type": "fidelity_profile",
                "target_profile": "fidelity",
                "inputs": {
                    "account_id": "Z39213144",
                    "account_value": 90.72,
                    "offline": True,
                    "positions": [
                        {"symbol": "FXAIX", "quantity": 0.245, "current_value": 58.63, "cost_basis": 59.10},
                        {"symbol": "NVDA", "quantity": 0.133, "current_value": 25.00, "cost_basis": 23.96},
                        {"symbol": "SCHD", "quantity": 0.224, "current_value": 6.00, "cost_basis": 6.00},
                    ],
                },
            }
            job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)

            cp = subprocess.run(
                [os.fspath(Path(sys.executable)), os.fspath(SKILL), os.fspath(job_path)],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)
            self.assertIn("Fidelity profile generated:", cp.stdout)

            reports_dir = root / "ramshare" / "evidence" / "reports"
            reports = list(reports_dir.glob("fidelity_profile_*.json"))
            self.assertTrue(reports, msg=f"no profile reports in {reports_dir}")

            payload = json.loads(reports[-1].read_text(encoding="utf-8"))
            self.assertEqual(payload.get("account_id"), "Z39213144")
            self.assertIn("portfolio", payload)
            self.assertIn("recommendations", payload)
            self.assertTrue(isinstance(payload.get("recommendations"), list))
            self.assertIn("research_diagnostics", payload)
            self.assertIn("event_watchlist", payload)

    def test_parses_positions_from_raw_text(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_fidelity_profile_text_") as td:
            root = Path(td).resolve()
            inbox = root / "ramshare" / "evidence" / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            job_path = inbox / "job.fidelity_profile_text.json"
            raw_text = (
                "Account Value: $90.72\n"
                "FXAIX FIDELITY 500 INDEX FUND 0.245 $241.22 $59.10 $58.63\n"
                "NVDA NVIDIA CORPORATION 0.133 $180.15 $23.96 $25.00\n"
                "SCHD SCHWAB US DIVIDEND ETF 0.224 $26.79 $6.00 $6.00\n"
            )
            job = {
                "id": "fidelity-profile-test-raw-text",
                "task_type": "fidelity_profile",
                "target_profile": "fidelity",
                "inputs": {
                    "account_id": "Z39213144",
                    "offline": True,
                    "raw_text": raw_text,
                    "search_depth": "deep",
                },
            }
            job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)

            cp = subprocess.run(
                [os.fspath(Path(sys.executable)), os.fspath(SKILL), os.fspath(job_path)],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)

            reports_dir = root / "ramshare" / "evidence" / "reports"
            reports = list(reports_dir.glob("fidelity_profile_*.json"))
            self.assertTrue(reports, msg=f"no profile reports in {reports_dir}")
            payload = json.loads(reports[-1].read_text(encoding="utf-8"))
            positions = payload.get("portfolio", {}).get("positions", [])
            self.assertGreaterEqual(len(positions), 3)
            self.assertAlmostEqual(float(payload.get("portfolio", {}).get("metrics", {}).get("account_value", 0.0)), 90.72, places=2)


if __name__ == "__main__":
    unittest.main()
