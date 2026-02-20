import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "finance_council_run.py"


class FinanceCouncilRunnerTests(unittest.TestCase):
    def test_creates_job_in_queue(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_finance_council_runner_") as td:
            root = Path(td)
            (root / "ramshare" / "evidence" / "inbox").mkdir(parents=True, exist_ok=True)

            env = dict(os.environ)
            env["GEMINI_OP_REPO_ROOT"] = str(root)

            cp = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--account-id",
                    "Z39213144",
                    "--max-symbols",
                    "5",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(cp.returncode, 0, msg=cp.stderr)
            self.assertIn("Finance council job created:", cp.stdout)

            jobs = list((root / "ramshare" / "evidence" / "inbox").glob("job.finance_council_*.json"))
            self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()

