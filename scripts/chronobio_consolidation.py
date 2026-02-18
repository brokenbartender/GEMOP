from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
STATE_DIR = REPO_ROOT / "ramshare" / "state" / "chronobio"
RUNS_DIR = STATE_DIR / "runs"
WINDOWS_PATH = STATE_DIR / "windows.json"
IN_FLAG = STATE_DIR / "IN_CONSOLIDATION.flag"
STOP_FLAG = REPO_ROOT / "ramshare" / "state" / "STOP"

SELF_LEARNER = REPO_ROOT / "scripts" / "agent_self_learning.py"
COUNCIL_LEARNER = REPO_ROOT / "scripts" / "council_reflection_learner.py"
MEMORY_SCRIPT = REPO_ROOT / "scripts" / "gemini_memory.py"
MEMORY_INGEST_PS1 = REPO_ROOT / "scripts" / "memory-ingest.ps1"
MEMORY_URL = "http://localhost:3013/mcp"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def today_hhmm(ts: Optional[dt.datetime] = None) -> str:
    ts = ts or dt.datetime.now().astimezone()
    return ts.strftime("%H:%M")


def run_cmd(args: List[str], cwd: Optional[Path] = None) -> Dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "cmd": args,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-4000:],
        "ok": proc.returncode == 0,
    }


def port_open(host: str, port: int, timeout: float = 0.8) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def ensure_defaults() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if not WINDOWS_PATH.exists():
        payload = {
            "version": 1,
            "timezone": "local",
            "windows": ["02:00-04:00", "14:00-14:10"],
        }
        WINDOWS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_windows() -> Dict[str, Any]:
    ensure_defaults()
    try:
        return json.loads(WINDOWS_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"version": 1, "timezone": "local", "windows": []}


def in_window(now_hm: str, windows: List[str]) -> bool:
    for w in windows:
        if "-" not in w:
            continue
        start, end = [x.strip() for x in w.split("-", 1)]
        if start <= now_hm <= end:
            return True
    return False


def latest_run_dir() -> Optional[Path]:
    jobs_root = REPO_ROOT / ".agent-jobs"
    if not jobs_root.exists():
        return None
    runs = [p for p in jobs_root.iterdir() if p.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def latest_distilled_note() -> Optional[Path]:
    notes_dir = REPO_ROOT / "ramshare" / "notes" / "distilled"
    if not notes_dir.exists():
        return None
    md = list(notes_dir.rglob("*.md"))
    if not md:
        return None
    md.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return md[0]


def write_flag(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def clear_flag(path: Path) -> None:
    if path.exists():
        path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 21 chronobiology consolidation runner")
    ap.add_argument("--run-dir", default="", help="Agent run dir; defaults to latest .agent-jobs run")
    ap.add_argument("--threshold", type=int, default=70)
    ap.add_argument("--memory-compact", type=int, default=300)
    ap.add_argument("--window", choices=["auto", "now"], default="auto")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan", action="store_true")
    args = ap.parse_args()

    ensure_defaults()
    windows = load_windows()
    now_hm = today_hhmm()
    allowed = args.window == "now" or in_window(now_hm, list(windows.get("windows", [])))

    run_dir = Path(args.run_dir).resolve() if args.run_dir else latest_run_dir()
    report: Dict[str, Any] = {
        "ts": now_iso(),
        "repo_root": str(REPO_ROOT),
        "window_mode": args.window,
        "now_hhmm": now_hm,
        "allowed_window": allowed,
        "dry_run": bool(args.dry_run),
        "run_dir": str(run_dir) if run_dir else None,
        "steps": [],
    }

    if args.plan:
        report["steps"] = [
            {"step": "set_flags", "ok": True, "note": "Set IN_CONSOLIDATION + STOP"},
            {"step": "score_run", "ok": True, "note": "agent_self_learning close-loop"},
            {"step": "council_reflect", "ok": True, "note": "council_reflection_learner"},
            {"step": "memory_compact", "ok": True, "note": "GEMINI_memory --compact"},
            {"step": "ingest_note", "ok": True, "note": "memory-ingest.ps1 latest distilled note"},
            {"step": "clear_flags", "ok": True, "note": "Clear IN_CONSOLIDATION + STOP"},
        ]
        print(json.dumps(report, indent=2))
        return

    if args.window == "auto" and not allowed:
        report["blocked"] = "outside_consolidation_window"
        print(json.dumps(report, indent=2))
        return

    if args.dry_run:
        print(json.dumps(report, indent=2))
        return

    write_flag(IN_FLAG, f"{now_iso()} start\n")
    write_flag(STOP_FLAG, f"{now_iso()} chronobio consolidation\n")
    report["steps"].append({"step": "set_flags", "ok": True})

    try:
        if run_dir and SELF_LEARNER.exists():
            step = run_cmd(
                ["python", str(SELF_LEARNER), "close-loop", "--run-dir", str(run_dir), "--threshold", str(args.threshold)]
            )
            step["step"] = "score_run"
            report["steps"].append(step)
        else:
            report["steps"].append({"step": "score_run", "ok": False, "reason": "missing_run_or_script"})

        bus_path = (run_dir / "bus" / "messages.jsonl") if run_dir else None
        if run_dir and bus_path and bus_path.exists() and COUNCIL_LEARNER.exists():
            step = run_cmd(["python", str(COUNCIL_LEARNER), "--run-dir", str(run_dir)])
            step["step"] = "council_reflect"
            report["steps"].append(step)
        else:
            report["steps"].append({"step": "council_reflect", "ok": True, "skipped": True})

        if MEMORY_SCRIPT.exists():
            step = run_cmd(["python", str(MEMORY_SCRIPT), "--compact", str(args.memory_compact)])
            step["step"] = "memory_compact"
            report["steps"].append(step)
        else:
            report["steps"].append({"step": "memory_compact", "ok": False, "reason": "missing_script"})

        note = latest_distilled_note()
        if note and MEMORY_INGEST_PS1.exists() and port_open("127.0.0.1", 3013):
            step = run_cmd(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(MEMORY_INGEST_PS1),
                    "-DistilledNotePath",
                    str(note),
                    "-MemoryUrl",
                    MEMORY_URL,
                ]
            )
            step["step"] = "ingest_note"
            step["note_path"] = str(note)
            report["steps"].append(step)
        else:
            report["steps"].append(
                {
                    "step": "ingest_note",
                    "ok": True,
                    "skipped": True,
                    "reason": "no_note_or_memory_server_unavailable",
                }
            )

    finally:
        clear_flag(STOP_FLAG)
        clear_flag(IN_FLAG)
        report["steps"].append({"step": "clear_flags", "ok": True})

    ok = all(bool(s.get("ok", False)) for s in report["steps"] if not s.get("skipped"))
    report["ok"] = ok
    out = RUNS_DIR / f"chronobio-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(out)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
