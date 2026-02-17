from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        # Windows PowerShell's `Set-Content -Encoding UTF8` writes a UTF-8 BOM by default,
        # which breaks naive json.loads() on some files (pids.json/run.json).
        return json.loads(path.read_bytes().decode("utf-8-sig"))
    except Exception:
        return None


def pid_alive(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    try:
        os.kill(pid_i, 0)  # type: ignore[arg-type]
        return True
    except Exception:
        pass
    if platform.system().lower().startswith("win"):
        try:
            cp = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_i}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            out = (cp.stdout or "").strip()
            if not out or out.lower().startswith("info:"):
                return False
            return str(pid_i) in out
        except Exception:
            return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a concise run status summary for a council RunDir.")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state = run_dir / "state"
    out: dict[str, Any] = {
        "run_dir": str(run_dir),
        "has_stop": (state / "STOP").exists(),
    }

    for name in ("learning-summary.json",):
        p = run_dir / name
        if p.exists():
            out[name] = str(p)

    for name in ("quota.json", "concurrency.json", "verify_report.json", "pids.json", "run.json"):
        p = state / name
        if p.exists():
            out[name] = read_json(p)

    # Derive live PIDs (best-effort).
    pids_obj = out.get("pids.json")
    if isinstance(pids_obj, dict):
        entries = pids_obj.get("entries")
        if isinstance(entries, list):
            live = []
            for e in entries:
                if not isinstance(e, dict):
                    continue
                try:
                    pid = int(e.get("pid") or 0)
                except Exception:
                    pid = 0
                if pid and pid_alive(pid):
                    live.append(e)
            out["live_pids"] = live

    # Local slot locks snapshot.
    slots = state / "local_slots"
    if slots.exists():
        out["local_slots"] = sorted([p.name for p in slots.glob("slot*.lock")])

    # Patch apply report for round2 (most common).
    for p in sorted(state.glob("patch_apply_round*.json")):
        out.setdefault("patch_apply_reports", []).append(read_json(p))

    # Decisions summary.
    decs = []
    for p in sorted(state.glob("decisions_round*.json")):
        decs.append(read_json(p))
    if decs:
        out["decisions"] = decs

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
