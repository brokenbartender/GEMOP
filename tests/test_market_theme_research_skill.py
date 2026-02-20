from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_market_theme_research.py"


FAKE_YFINANCE = """\
import pandas as pd

class _Ticker:
    def __init__(self, symbol):
        self.symbol = str(symbol).upper()

    def history(self, period="9mo", interval="1d", auto_adjust=True):
        known = {"BBAI", "SOUN", "PLTR", "NVDA"}
        if self.symbol not in known:
            return pd.DataFrame()
        n = 120
        base = {
            "BBAI": 6.0,
            "SOUN": 15.0,
            "PLTR": 24.0,
            "NVDA": 180.0,
        }[self.symbol]
        idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=n, freq="D")
        close = pd.Series([base + (i * 0.03) for i in range(n)], index=idx)
        vol = pd.Series([900000 + (i * 1000) for i in range(n)], index=idx)
        return pd.DataFrame({"Close": close, "High": close + 0.2, "Low": close - 0.2, "Volume": vol}, index=idx)

    @property
    def info(self):
        return {"marketCap": 2000000000}

def Ticker(symbol):
    return _Ticker(symbol)
"""


class MarketThemeResearchSkillTests(unittest.TestCase):
    def test_generates_theme_candidates_and_excludes_held_symbols(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_theme_skill_") as td:
            root = Path(td)
            (root / "ramshare" / "evidence").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "evidence" / "inbox").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "evidence" / "reports").mkdir(parents=True, exist_ok=True)
            (root / "ramshare" / "strategy").mkdir(parents=True, exist_ok=True)

            snapshot = {
                "positions": [
                    {"symbol": "NVDA", "quantity": 0.2, "current_value": 36.0},
                ]
            }
            (root / "ramshare" / "evidence" / "portfolio_snapshot.json").write_text(
                json.dumps(snapshot, indent=2),
                encoding="utf-8",
            )

            job = {
                "id": "market-theme-test-001",
                "task_type": "market_theme_research",
                "target_profile": "fidelity",
                "inputs": {
                    "account_id": "Z39213144",
                    "theme": "best ai micro investments for this week",
                    "offline": True,
                    "max_candidates": 6,
                    "seed_leads": [
                        {
                            "query": "theme",
                            "title": "BigBear.ai lands defense win (NASDAQ:BBAI) - Reuters",
                            "url": "https://example.com/1",
                            "published": "Wed, 18 Feb 2026 14:00:00 GMT",
                            "source_name": "Reuters",
                            "signal_score": 2,
                            "signal_label": "positive_catalyst",
                            "source_trust_score": 3,
                            "recency_score": 2,
                        },
                        {
                            "query": "theme",
                            "title": "SoundHound AI momentum builds into week (NASDAQ:SOUN) - CNBC",
                            "url": "https://example.com/2",
                            "published": "Wed, 18 Feb 2026 15:00:00 GMT",
                            "source_name": "CNBC",
                            "signal_score": 2,
                            "signal_label": "positive_catalyst",
                            "source_trust_score": 3,
                            "recency_score": 2,
                        },
                    ],
                },
            }
            job_path = root / "ramshare" / "evidence" / "inbox" / "job.market_theme_test.json"
            job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

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
            self.assertEqual(cp.returncode, 0, msg=cp.stderr or cp.stdout)

            latest = root / "ramshare" / "strategy" / "market_theme_latest.json"
            self.assertTrue(latest.exists())
            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("theme"), "best ai micro investments for this week")
            self.assertIn("top_candidates", payload)
            symbols = {str(x.get("symbol")) for x in payload.get("top_candidates", [])}
            self.assertIn("BBAI", symbols)
            self.assertIn("SOUN", symbols)
            self.assertNotIn("NVDA", symbols)


if __name__ == "__main__":
    unittest.main()
