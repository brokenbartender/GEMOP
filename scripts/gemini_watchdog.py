from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "watchdog.jsonl"
NOTIFY_LOG_PATH = REPO_ROOT / "mcp" / "data" / "notifications.log"
STATUS_PATH = REPO_ROOT / "ramshare" / "state" / "watchdog_status.json"
STOP_FILES = [
    REPO_ROOT / "STOP_ALL_AGENTS.flag",
    REPO_ROOT / "ramshare" / "state" / "STOP",
    REPO_ROOT / "ramshare" / "state" / "chronobio" / "IN_CONSOLIDATION.flag",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def audit(event: str, ok: bool, details: Dict[str, Any]) -> None:
    append_jsonl(
        AUDIT_PATH,
        {"ts": now_iso(), "event": event, "ok": ok, "details": details},
    )


def notify(message: str, level: str = "warning") -> None:
    append_jsonl(
        NOTIFY_LOG_PATH,
        {"timestamp": time.time(), "level": level, "message": message},
    )


def is_stopped() -> bool:
    return any(p.exists() for p in STOP_FILES)


def port_open(port: int, timeout_sec: float = 0.8) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_sec)
    try:
        s.connect(("127.0.0.1", int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def sidecar_window_present(patterns: List[str]) -> bool:
    try:
        import win32gui
    except Exception:
        return False
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    found = False

    def _cb(hwnd: int, _: Any) -> bool:
        nonlocal found
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return True
        if any(rx.search(title) for rx in compiled):
            found = True
            return False
        return True

    win32gui.EnumWindows(_cb, None)
    return found


def expected_targets(profile: str) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    if profile in {"browser", "research", "fidelity", "full"}:
        targets.append({"id": "memory", "type": "port", "port": 3013})
    if profile in {"research", "full"}:
        targets.append({"id": "semantic-search", "type": "port", "port": 3014})
    if profile in {"browser", "full"}:
        targets.append({"id": "playwright", "type": "port", "port": 8931})
    if profile in {"sidecar-operator"}:
        targets.append(
            {
                "id": "sidecar-window",
                "type": "sidecar",
                "patterns": ["remote desktop", "mstsc", "vmconnect"],
            }
        )
    return targets


def run_ps(script_path: Path, args: List[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def restart_daemons(profile: str) -> bool:
    proc = run_ps(REPO_ROOT / "start-daemons.ps1", ["-Profile", profile])
    ok = proc.returncode == 0
    audit(
        "restart_daemons",
        ok,
        {
            "profile": profile,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-600:],
            "stderr_tail": (proc.stderr or "")[-600:],
        },
    )
    if not ok:
        notify(f"[watchdog] restart-daemons failed profile={profile}", level="error")
    return ok


def restart_sidecar() -> bool:
    proc = run_ps(REPO_ROOT / "scripts" / "start-sidecar.ps1", [])
    ok = proc.returncode == 0
    audit(
        "restart_sidecar",
        ok,
        {
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-600:],
            "stderr_tail": (proc.stderr or "")[-600:],
        },
    )
    if not ok:
        notify("[watchdog] sidecar restart failed", level="error")
    return ok


def write_status(payload: Dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Gemini-op self-healing watchdog")
    ap.add_argument("--profile", default="sidecar-operator")
    ap.add_argument("--interval-seconds", type=int, default=20)
    ap.add_argument("--failure-threshold", type=int, default=2)
    ap.add_argument("--restart-cooldown-seconds", type=int, default=45)
    ap.add_argument("--auto-restart-sidecar", action="store_true")
    ap.add_argument("--once", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    profile = str(args.profile)
    targets = expected_targets(profile)
    if not targets:
        notify(f"[watchdog] no targets configured for profile={profile}", level="info")

    fail_counts: Dict[str, int] = {t["id"]: 0 for t in targets}
    previous_state: Dict[str, bool] = {t["id"]: True for t in targets}
    last_restart_at = 0.0

    notify(f"[watchdog] started profile={profile}", level="info")
    audit("watchdog_started", True, {"profile": profile, "targets": [t["id"] for t in targets]})

    while True:
        stopped = is_stopped()
        cycle: Dict[str, Any] = {
            "ts": now_iso(),
            "profile": profile,
            "stopped": stopped,
            "targets": {},
        }

        if stopped:
            write_status(cycle)
            if args.once:
                return
            time.sleep(max(1, args.interval_seconds))
            continue

        unhealthy_ids: List[str] = []
        for t in targets:
            tid = str(t["id"])
            healthy = True
            if t["type"] == "port":
                healthy = port_open(int(t["port"]))
            elif t["type"] == "sidecar":
                healthy = sidecar_window_present([str(x) for x in t["patterns"]])

            if healthy:
                fail_counts[tid] = 0
            else:
                fail_counts[tid] = fail_counts.get(tid, 0) + 1
                unhealthy_ids.append(tid)

            cycle["targets"][tid] = {
                "healthy": healthy,
                "fail_count": fail_counts[tid],
                "meta": t,
            }

            prev = previous_state.get(tid, True)
            if prev != healthy:
                level = "warning" if not healthy else "info"
                state_txt = "DOWN" if not healthy else "RECOVERED"
                notify(f"[watchdog] {tid} {state_txt} profile={profile}", level=level)
                audit("target_state_change", True, {"target": tid, "healthy": healthy, "profile": profile})
                previous_state[tid] = healthy

        should_restart = any(fail_counts[tid] >= max(1, args.failure_threshold) for tid in unhealthy_ids)
        restart_due = (time.time() - last_restart_at) >= max(5, args.restart_cooldown_seconds)
        if should_restart and restart_due:
            if any(t["id"] in {"memory", "semantic-search", "playwright"} for t in targets):
                restart_daemons(profile)
            if args.auto_restart_sidecar and any(t["id"] == "sidecar-window" for t in targets):
                if fail_counts.get("sidecar-window", 0) >= max(1, args.failure_threshold):
                    restart_sidecar()
            last_restart_at = time.time()

        write_status(cycle)
        if args.once:
            return
        time.sleep(max(1, args.interval_seconds))


if __name__ == "__main__":
    main()
