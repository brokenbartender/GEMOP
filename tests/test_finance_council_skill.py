import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_finance_council.py"


FAKE_YFINANCE = """\
import pandas as pd

class _Ticker:
    def __init__(self, symbol):
        self.symbol = str(symbol).upper()

    def history(self, period="9mo", interval="1d", auto_adjust=True):
        n = 120
        base = 180.0 if self.symbol == "NVDA" else 240.0
        idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=n, freq="D")
        close = pd.Series([base + (i * 0.15) for i in range(n)], index=idx)
        return pd.DataFrame({"Close": close, "High": close + 1.0, "Low": close - 1.0}, index=idx)

    @property
    def info(self):
        if self.symbol == "NVDA":
            return {
                "forwardPE": 30.0,
                "revenueGrowth": 0.20,
                "earningsGrowth": 0.22,
                "debtToEquity": 35.0,
                "profitMargins": 0.23,
            }
        return {
            "forwardPE": 0.0,
            "revenueGrowth": 0.02,
            "earningsGrowth": 0.02,
            "debtToEquity": 0.0,
            "profitMargins": 0.05,
        }

    @property
    def news(self):
        if self.symbol == "NVDA":
            return [{"title": "NVIDIA beats earnings and raises guidance"} for _ in range(5)]
        return [{"title": "Index fund flows remain stable"} for _ in range(3)]

def Ticker(symbol):
    return _Ticker(symbol)
"""


class FinanceCouncilSkillTests(unittest.TestCase):
    def test_generates_council_report_and_paper_jobs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_finance_council_") as td:
            root = Path(td)
            (root / "ramshare" / "evidence" / "inbox").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "evidence" / "reports").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "strategy").mkdir(parents=True, exist_ok=True)

            job_path = root / "ramshare" / "evidence" / "inbox" / "job.finance_council_test.json"
            payload = {
                "id": "finance-council-test-001",
                "task_type": "finance_council",
                "target_profile": "fidelity",
                "inputs": {
                    "account_id": "Z39213144",
                    "emit_paper_jobs": True,
                    "max_paper_jobs": 2,
                    "max_symbols": 4,
                    "positions": [
                        {"symbol": "NVDA", "quantity": 0.133, "price": 180.15, "current_value": 25.00, "cost_basis": 23.96},
                        {"symbol": "FXAIX", "quantity": 0.245, "price": 241.22, "current_value": 58.63, "cost_basis": 59.10},
                    ],
                },
            }
            job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            profile_latest = root / "ramshare" / "strategy" / "fidelity_profile_latest.json"
            profile_latest.write_text(
                json.dumps(
                    {
                        "lead_summary": {
                            "positive_catalyst_count": 4,
                            "negative_risk_count": 1,
                        },
                        "online_leads": [
                            {
                                "title": "NVDA beats earnings estimates and raises outlook",
                                "query": "NVDA earnings guidance analyst revisions",
                                "signal_label": "positive_catalyst",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            fake_mod_dir = root / "fake_modules"
            fake_mod_dir.mkdir(parents=True, exist_ok=True)
            (fake_mod_dir / "yfinance.py").write_text(FAKE_YFINANCE, encoding="utf-8")

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)
            env["PYTHONPATH"] = str(fake_mod_dir)

            cp = subprocess.run(
                [sys.executable, str(SKILL), str(job_path)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            self.assertIn("Finance council generated:", cp.stdout)

            latest = root / "ramshare" / "strategy" / "finance_council_latest.json"
            self.assertTrue(latest.exists())
            report = json.loads(latest.read_text(encoding="utf-8"))
            self.assertIn("council", report)
            self.assertGreaterEqual(len(report["council"]), 1)
            self.assertIn("horizon_plan", report)
            self.assertIn("tomorrow_orders", report)

            first = report["council"][0]
            self.assertIn("agents", first)
            self.assertIn("technical_analyst", first["agents"])
            self.assertIn("risk_manager", first["agents"])
            self.assertIn("execution_trader", first["agents"])
            self.assertIn("chief_of_staff", first["agents"])

            valid = {
                "SPY",
                "QQQ",
                "IWM",
                "XLK",
                "SMH",
                "SOXX",
                "AAPL",
                "MSFT",
                "NVDA",
                "AMD",
                "META",
                "AMZN",
                "FXAIX",
            }
            for row in report.get("opportunity_council", []):
                self.assertIn(str(row.get("symbol")), valid)

            emitted = list((root / "ramshare" / "evidence" / "inbox").glob("job.finance_council_trade_*.json"))
            self.assertGreaterEqual(len(emitted), 1)


if __name__ == "__main__":
    unittest.main()
