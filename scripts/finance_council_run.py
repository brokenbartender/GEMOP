from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_finance_council.py"
FIDELITY_INTAKE = REPO_ROOT / "scripts" / "fidelity_intake.py"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_job(payload: Dict[str, Any]) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    path = INBOX_DIR / f"job.finance_council_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_subprocess(cmd: list[str]) -> int:
    cp = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ))
    if cp.stdout.strip():
        print(cp.stdout.strip())
    if cp.returncode != 0 and cp.stderr.strip():
        print(cp.stderr.strip())
    return cp.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Create and optionally run a finance_council job.")
    ap.add_argument("--account-id", default="unknown")
    ap.add_argument("--account-value", type=float, default=0.0)
    ap.add_argument("--max-symbols", type=int, default=6)
    ap.add_argument("--max-risk-per-trade-pct", type=float, default=2.0)
    ap.add_argument("--emit-paper-jobs", action="store_true")
    ap.add_argument("--max-paper-jobs", type=int, default=2)
    ap.add_argument("--launch-council", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--council-rounds", type=int, default=2)
    ap.add_argument("--run-now", action="store_true")
    ap.add_argument("--csv", default="", help="Optional: ingest Fidelity CSV snapshot before running")
    args = ap.parse_args()

    if args.csv:
        intake_cmd = [
            sys.executable,
            str(FIDELITY_INTAKE),
            "csv",
            "--path",
            str(args.csv),
            "--account-id",
            str(args.account_id),
            "--account-value",
            str(args.account_value),
        ]
        rc = run_subprocess(intake_cmd)
        if rc != 0:
            return rc

    payload = {
        "id": f"finance-council-{now_stamp()}",
        "task_type": "finance_council",
        "target_profile": "fidelity",
        "inputs": {
            "account_id": str(args.account_id),
            "account_value": float(args.account_value),
            "max_symbols": int(args.max_symbols),
            "max_risk_per_trade_pct": float(args.max_risk_per_trade_pct) / 100.0,
            "emit_paper_jobs": bool(args.emit_paper_jobs),
            "max_paper_jobs": int(args.max_paper_jobs),
            "launch_council": bool(args.launch_council),
            "online": bool(args.online),
            "council_rounds": int(args.council_rounds),
        },
        "policy": {
            "risk": "high",
            "estimated_spend_usd": 0,
        },
    }
    job_path = write_job(payload)
    print(f"Finance council job created: {job_path}")

    if not args.run_now:
        return 0
    if not SKILL.exists():
        print(f"ERROR: missing skill script: {SKILL}")
        return 1
    return run_subprocess([sys.executable, str(SKILL), str(job_path)])


if __name__ == "__main__":
    raise SystemExit(main())

