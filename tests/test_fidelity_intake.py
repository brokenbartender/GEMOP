from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "fidelity_intake.py"


class FidelityIntakeTests(unittest.TestCase):
    def test_csv_mode_writes_snapshot_and_profile_job(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_fidelity_intake_csv_") as td:
            root = Path(td).resolve()
            src = root / "positions.csv"
            src.write_text(
                "Symbol,Description,Quantity,Price,Cost Basis,Current Value\n"
                "FXAIX,Fidelity 500 Index Fund,0.245,241.22,59.10,58.63\n"
                "NVDA,NVIDIA Corp,0.133,180.15,23.96,25.00\n"
                "SCHD,Schwab US Dividend ETF,0.224,26.79,6.00,6.00\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "csv",
                    "--path",
                    os.fspath(src),
                    "--account-id",
                    "Z39213144",
                    "--account-value",
                    "90.72",
                    "--offline",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)

            snapshot = root / "ramshare" / "evidence" / "portfolio_snapshot.json"
            self.assertTrue(snapshot.exists(), msg="snapshot not created")
            snap = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(int(snap.get("positions_count", 0)), 3)

            inbox = root / "ramshare" / "evidence" / "inbox"
            jobs = list(inbox.glob("job.fidelity_profile_*.json"))
            self.assertTrue(jobs, msg="profile job not created")
            payload = json.loads(jobs[-1].read_text(encoding="utf-8"))
            self.assertEqual(payload.get("task_type"), "fidelity_profile")
            self.assertEqual(payload.get("inputs", {}).get("account_id"), "Z39213144")

    def test_json_mode_ingests_aggregator_like_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_fidelity_intake_json_") as td:
            root = Path(td).resolve()
            src = root / "aggregator.json"
            src.write_text(
                json.dumps(
                    {
                        "account_value": 90.72,
                        "positions": [
                            {"ticker": "FXAIX", "qty": 0.245, "last_price": 241.22, "cost": 59.10, "market_value": 58.63},
                            {"ticker": "NVDA", "qty": 0.133, "last_price": 180.15, "cost": 23.96, "market_value": 25.00},
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)
            cp = subprocess.run(
                [
                    os.fspath(Path(sys.executable)),
                    os.fspath(SCRIPT),
                    "json",
                    "--path",
                    os.fspath(src),
                    "--account-id",
                    "Z39213144",
                    "--offline",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=30,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)

            snapshot = root / "ramshare" / "evidence" / "portfolio_snapshot.json"
            self.assertTrue(snapshot.exists(), msg="snapshot not created")
            snap = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(int(snap.get("positions_count", 0)), 2)


if __name__ == "__main__":
    unittest.main()

