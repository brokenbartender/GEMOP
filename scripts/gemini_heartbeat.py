import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
CRASH_LOG = REPO_ROOT / "ramshare" / "evidence" / "crash_log.md"
KILL_SWITCH = REPO_ROOT / "STOP_ALL_AGENTS.flag"
DISPATCHER = REPO_ROOT / "scripts" / "GEMINI_dispatcher.py"
ACCOUNTANT = REPO_ROOT / "ramshare" / "skills" / "skill_accountant.py"


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
