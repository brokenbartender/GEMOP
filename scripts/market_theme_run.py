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
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_market_theme_research.py"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_job(payload: Dict[str, Any]) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = INBOX_DIR / f"job.market_theme_{now_stamp()}.json"
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
    ap = argparse.ArgumentParser(description="Queue or run theme-driven market research.")
    ap.add_argument("--theme", required=True, help="Any finance theme, e.g. 'best ai micro investments for this week'")
    ap.add_argument("--account-id", default="unknown")
    ap.add_argument("--search-depth", default="deep", choices=["standard", "deep"])
    ap.add_argument("--max-candidates", type=int, default=10)
    ap.add_argument("--max-items-per-query", type=int, default=8)
    ap.add_argument("--timeout-s", type=int, default=12)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--run-now", action="store_true")
    args = ap.parse_args()

    payload = {
        "id": f"market-theme-{now_stamp()}",
        "task_type": "market_theme_research",
        "target_profile": "fidelity",
        "inputs": {
            "account_id": str(args.account_id),
            "theme": str(args.theme),
            "search_depth": str(args.search_depth),
            "max_candidates": int(args.max_candidates),
            "max_items_per_query": int(args.max_items_per_query),
            "timeout_s": int(args.timeout_s),
            "offline": bool(args.offline),
        },
        "policy": {
            "risk": "high",
            "estimated_spend_usd": 0,
        },
    }
    job_path = write_job(payload)
    print(f"Market theme job created: {job_path}")

    if not args.run_now:
        return 0
    if not SKILL.exists():
        print(f"ERROR: missing skill script: {SKILL}")
        return 1
    return run_subprocess([sys.executable, str(SKILL), str(job_path)])


if __name__ == "__main__":
    raise SystemExit(main())

