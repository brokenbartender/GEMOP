from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def run(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    t0 = time.time()
    # Windows default encoding (cp1252) can choke on undefined bytes from subprocess output.
    # Be permissive: never fail the pipeline due to decode errors.
    p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", errors="replace")
    return {
        "cmd": cmd,
        "rc": int(p.returncode),
        "duration_s": round(time.time() - t0, 3),
        "stdout_tail": (p.stdout or "")[-8000:],
        "stderr_tail": (p.stderr or "")[-8000:],
    }


def repo_root_from_env_or_file() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a lightweight verification pipeline and write a JSON report.")
    ap.add_argument("--repo-root", default="", help="Repo root (defaults to GEMINI_OP_REPO_ROOT or scripts/..)")
    ap.add_argument("--run-dir", default="", help="Council run dir; if provided, writes into <run>/state/")
    ap.add_argument("--strict", action="store_true", help="Fail closed on any non-zero check.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_env_or_file()
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None
    out_path = (run_dir / "state" / "verify_report.json") if run_dir else (repo_root / "state" / "verify_report.json")

    checks: list[dict[str, Any]] = []
    ok = True

    # 1) Python parse/bytecode check for core folders.
    checks.append(run([sys.executable, "-m", "compileall", "-q", "scripts", "mcp", "work"], cwd=repo_root))

    # 2) Git whitespace / conflict marker check (best-effort).
    if (repo_root / ".git").exists():
        git_check = run(["git", "diff", "--check"], cwd=repo_root)
        # Windows/dev UX: `git diff --check` returns rc=2 for "new blank line at EOF",
        # which is usually harmless and often introduced by editors. Treat it as non-fatal.
        if int(git_check.get("rc") or 0) != 0:
            out = str(git_check.get("stdout_tail") or "")
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if lines and all(ln.endswith("new blank line at EOF.") for ln in lines):
                git_check["ignored_new_blank_line_at_eof"] = True
                git_check["rc"] = 0
        checks.append(git_check)

    # 3) Secret scan on current diff (useful after auto-apply).
    if (repo_root / "scripts" / "scan_secrets.py").exists():
        checks.append(run([sys.executable, "scripts/scan_secrets.py", "--diff"], cwd=repo_root))

    # 4) Optional: validate local tool-contract scaffolding (if present).
    # Keep this lightweight; it's meant to catch obvious import/path issues.
    if (repo_root / "scripts" / "validate_tool_contracts.py").exists():
        checks.append(run([sys.executable, "scripts/validate_tool_contracts.py"], cwd=repo_root))

    ok = all(int(c.get("rc") or 0) == 0 for c in checks)
    report = {
        "ok": bool(ok),
        "generated_at": time.time(),
        "repo_root": str(repo_root),
        "run_dir": str(run_dir) if run_dir else "",
        "checks": checks,
    }
    write_report(out_path, report)

    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
