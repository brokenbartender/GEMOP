from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
AGENTIC_DIR = Path(r"C:\Users\codym\agentic-console")
CONTROL_SCRIPT = AGENTIC_DIR / "scripts" / "a2a_control.py"
STATE_SCRIPT = AGENTIC_DIR / "scripts" / "a2a_system_state.py"
BUDGET_SCRIPT = REPO_ROOT / "scripts" / "gemini_budget.py"
CHRONOBIO_SCRIPT = REPO_ROOT / "scripts" / "chronobio_consolidation.py"
STOP_FLAG = REPO_ROOT / "ramshare" / "state" / "STOP"
IN_CONSOLIDATION_FLAG = REPO_ROOT / "ramshare" / "state" / "chronobio" / "IN_CONSOLIDATION.flag"


def run_json(cmd: List[str]) -> Dict:
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace", stderr=subprocess.STDOUT)
    return json.loads(out)


def check_requirements() -> List[str]:
    problems: List[str] = []
    for exe in ("python", "git"):
        if shutil.which(exe) is None:
            problems.append(f"missing_executable:{exe}")
    if not (REPO_ROOT / ".git").exists():
        problems.append("missing_git_repo")
    if not BUDGET_SCRIPT.exists():
        problems.append("missing_budget_script")
    if not CHRONOBIO_SCRIPT.exists():
        problems.append("missing_chronobio_script")
    return problems


def check_runtime_flags() -> List[str]:
    problems: List[str] = []
    if STOP_FLAG.exists():
        problems.append("stop_flag_present")
    if IN_CONSOLIDATION_FLAG.exists():
        problems.append("consolidation_in_progress")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini preflight checks (fail-closed)")
    ap.add_argument("--prompt", default="", help="Prompt text for budget estimate")
    ap.add_argument("--context", type=int, default=128000)
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    result = {"capabilities": None, "system_state": None, "budget": None, "problems": []}
    result["problems"].extend(check_requirements())
    result["problems"].extend(check_runtime_flags())

    if CONTROL_SCRIPT.exists():
        try:
            result["capabilities"] = run_json([sys.executable, str(CONTROL_SCRIPT), "--describe-tools"])
        except Exception as e:
            result["problems"].append(f"capabilities_check_failed:{e}")
    if STATE_SCRIPT.exists():
        try:
            result["system_state"] = run_json([sys.executable, str(STATE_SCRIPT)])
        except Exception as e:
            result["problems"].append(f"system_state_check_failed:{e}")
    if BUDGET_SCRIPT.exists():
        try:
            result["budget"] = run_json(
                [sys.executable, str(BUDGET_SCRIPT), "--context", str(args.context), "--prompt", args.prompt]
            )
        except Exception as e:
            result["problems"].append(f"budget_check_failed:{e}")

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    if result["problems"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
