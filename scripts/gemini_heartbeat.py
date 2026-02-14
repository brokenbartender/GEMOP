import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
try:
    import psutil
except ImportError:
    psutil = None


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
CRASH_LOG = REPO_ROOT / "ramshare" / "evidence" / "crash_log.md"
KILL_SWITCH = REPO_ROOT / "STOP_ALL_AGENTS.flag"
DISPATCHER = REPO_ROOT / "scripts" / "GEMINI_dispatcher.py"
ACCOUNTANT = REPO_ROOT / "ramshare" / "skills" / "skill_accountant.py"
UNIVERSAL_CONTEXT_PATH = REPO_ROOT / "ramshare" / "state" / "universal_context.json"
LESSONS_PATH = REPO_ROOT / "ramshare" / "learning" / "memory" / "lessons.md"
TASK_PATH = Path(r"C:\Users\codym\.Gemini\current_task.json")


def update_universal_context() -> None:
    context = {
        "ts": dt.datetime.now().isoformat(),
        "active_pids": [],
        "current_task": "Unknown",
        "system_load": {"cpu": 0, "ram": 0},
        "lessons_summary": "No recent lessons."
    }

    # 1. Active PIDs (excluding CLI/Shell)
    if psutil:
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Basic filter to find agentic processes
                cmdline = " ".join(proc.info['cmdline'] or [])
                if ("gemini" in cmdline or "python" in cmdline) and proc.info['pid'] != current_pid:
                    if "gemini-heartbeat" not in cmdline and "powershell" not in cmdline:
                        context["active_pids"].append({"pid": proc.info['pid'], "name": proc.info['name']})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        context["system_load"]["cpu"] = psutil.cpu_percent()
        context["system_load"]["ram"] = psutil.virtual_memory().percent

    # 2. Current Task
    if TASK_PATH.exists():
        try:
            task_data = json.loads(TASK_PATH.read_text(encoding="utf-8"))
            context["current_task"] = task_data.get("task", "Idle")
        except: pass

    # 3. Lessons Learned Summary
    if LESSONS_PATH.exists():
        try:
            lines = LESSONS_PATH.read_text(encoding="utf-8").splitlines()
            lessons = [l for l in lines if l.strip().startswith("- ")]
            if lessons:
                context["lessons_summary"] = " | ".join(lessons[-3:]) # Last 3 lessons
        except: pass

    UNIVERSAL_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSAL_CONTEXT_PATH.write_text(json.dumps(context, indent=2), encoding="utf-8")


def log_crash(message: str) -> None:
    CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not CRASH_LOG.exists():
        CRASH_LOG.write_text("# Crash Log\n\n", encoding="utf-8")
    now_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with CRASH_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- {now_iso} {message}\n")


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def make_manager_job() -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = INBOX_DIR / f"job.heartbeat_manager_{ts}.json"
    payload = {
        "id": f"heartbeat-manager-{ts}",
        "task_type": "manager",
        "target_profile": "research",
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_dispatcher_drain(max_passes: int) -> None:
    for _ in range(max_passes):
        proc = run_cmd([sys.executable, str(DISPATCHER)])
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.returncode != 0:
            err = proc.stderr.strip() or "dispatcher returned non-zero exit"
            log_crash(f"dispatcher_error: {err}")
            return
        if "No jobs found." in (proc.stdout or ""):
            return


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Heartbeat daemon: accountant + manager dispatch loop")
    ap.add_argument("--interval-seconds", type=int, default=900, help="Sleep interval between cycles (default 900 = 15 min)")
    ap.add_argument("--stop-sleep-seconds", type=int, default=60, help="Sleep while kill switch is enabled")
    ap.add_argument("--drain-passes", type=int, default=6, help="Max dispatcher passes per cycle")
    ap.add_argument("--default-daily-limit-usd", type=float, default=5.0)
    ap.add_argument("--once", action="store_true", help="Run one cycle only (for testing)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    while True:
        try:
            update_universal_context()
            if KILL_SWITCH.exists():
                print(f"Heartbeat paused: kill switch present at {KILL_SWITCH}")
                if args.once:
                    return
                time.sleep(max(args.stop_sleep_seconds, 1))
                continue

            acct = run_cmd(
                [
                    sys.executable,
                    str(ACCOUNTANT),
                    "--default-daily-limit-usd",
                    str(args.default_daily_limit_usd),
                ]
            )
            if acct.stdout.strip():
                print(acct.stdout.strip())
            if acct.returncode == 3:
                print("Heartbeat stopping: accountant triggered emergency stop.")
                return
            if acct.returncode != 0:
                log_crash(f"accountant_error: {acct.stderr.strip() or 'non-zero exit'}")
                if args.once:
                    return
                time.sleep(max(args.interval_seconds, 1))
                continue

            make_manager_job()
            run_dispatcher_drain(max(args.drain_passes, 1))

        except Exception as e:
            log_crash(f"heartbeat_exception: {e}")

        if args.once:
            return
        time.sleep(max(args.interval_seconds, 1))


if __name__ == "__main__":
    main()
