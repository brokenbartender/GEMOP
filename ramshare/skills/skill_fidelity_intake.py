from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
INTAKE_SCRIPT = REPO_ROOT / "scripts" / "fidelity_intake.py"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: skill_fidelity_intake.py <job_file>")

    job_path = Path(sys.argv[1]).resolve()
    job = load_json(job_path)
    inputs = job.get("inputs") if isinstance(job.get("inputs"), dict) else {}

    mode = str(inputs.get("mode") or "csv").lower().strip()
    cmd = [sys.executable, str(INTAKE_SCRIPT), mode]

    account_id = str(inputs.get("account_id") or "")
    account_value = inputs.get("account_value")
    source_path = str(inputs.get("source_path") or "")

    if mode in {"csv", "raw", "json"}:
        if not source_path:
            raise SystemExit("fidelity_intake requires inputs.source_path for csv/raw/json modes")
        cmd += ["--path", source_path]
    elif mode != "playwright":
        raise SystemExit(f"unsupported fidelity_intake mode: {mode}")

    if account_id:
        cmd += ["--account-id", account_id]
    if account_value is not None:
        cmd += ["--account-value", str(account_value)]

    search_depth = str(inputs.get("search_depth") or "deep")
    if search_depth in {"standard", "deep"}:
        cmd += ["--search-depth", search_depth]
    cmd += ["--min-source-trust-score", str(int(inputs.get("min_source_trust_score", 0)))]

    if bool(inputs.get("offline", False)):
        cmd += ["--offline"]
    if bool(inputs.get("run_profile", False)):
        cmd += ["--run-profile"]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ))
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip())
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()

