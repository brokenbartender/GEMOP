from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_powershell(args: list[str], *, env: dict[str, str] | None = None, timeout_s: int = 180) -> subprocess.CompletedProcess[str]:
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + args
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, env=e, timeout=timeout_s)


class HawkingFailpathTests(unittest.TestCase):
    def test_fail_threshold_emits_hawking_radiation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gemop_hawk_fail_") as td:
            run_dir = Path(td).resolve()
            env = {"GEMINI_OP_MOCK_MODE": "1"}
            cp = run_powershell(
                [
                    str(REPO_ROOT / "scripts" / "triad_orchestrator.ps1"),
                    "-RepoRoot",
                    str(REPO_ROOT),
                    "-RunDir",
                    str(run_dir),
                    "-Prompt",
                    "trigger fail threshold emission",
                    "-Agents",
                    "1",
                    "-MaxRounds",
                    "1",
                    "-MaxParallel",
                    "1",
                    "-FailClosedOnThreshold",
                    "-Threshold",
                    "99",
                ],
                env=env,
                timeout_s=180,
            )
            self.assertNotEqual(cp.returncode, 0, msg="expected threshold failure return code")
            radiation = run_dir / "state" / "hawking_radiation.jsonl"
            self.assertTrue(radiation.exists(), msg=f"missing {radiation}")
            rows = [json.loads(ln) for ln in radiation.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(any(str(r.get("reason")) == "fail_threshold" for r in rows))


if __name__ == "__main__":
    unittest.main()
