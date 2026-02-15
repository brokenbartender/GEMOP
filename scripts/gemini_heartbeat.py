import os
import sys
import json
import time
import psutil
import pathlib
import datetime as dt
import subprocess

REPO_ROOT = pathlib.Path(__file__).parent.parent
CONTEXT_FILE = REPO_ROOT / "ramshare/state/universal_context.json"
KILL_SWITCH = REPO_ROOT / ".gemini/kill.flag"
LOG_FILE = REPO_ROOT / "agent_runner_debug.log"

STALL_THRESHOLD_SECONDS = 900 # 15 minutes

def log_message(message):
    """Appends a message to the debug log."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now().isoformat()}] [VIGILANCE] {message}\n")

def get_latest_job(jobs_root):
    """Finds the most recently modified job directory."""
    jobs_dir = jobs_root / ".agent-jobs"
    if not jobs_dir.exists():
        return None
    
    subdirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
    if not subdirs:
        return None
        
    latest_job = max(subdirs, key=lambda d: d.stat().st_mtime)
    return latest_job

def get_orchestrator_pid(job_dir):
    """Finds the PID of the orchestrator running for a specific job."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if "gemini_orchestrator.ps1" in cmdline and str(job_dir) in cmdline:
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def check_for_stall(latest_job):
    """Checks if the latest mission has stalled."""
    if not latest_job:
        return

    log_path = latest_job / "triad_orchestrator.log"
    if not log_path.exists():
        return # Not started yet, not a stall.

    last_modified_time = log_path.stat().st_mtime
    time_since_modified = time.time() - last_modified_time

    if time_since_modified > STALL_THRESHOLD_SECONDS:
        log_message(f"STALL DETECTED in {latest_job.name}! Last log update was {time_since_modified:.0f}s ago.")
        
        # --- HARD RESET PROTOCOL ---
        orchestrator_pid = get_orchestrator_pid(latest_job)
        if orchestrator_pid:
            try:
                p = psutil.Process(orchestrator_pid)
                p.kill()
                log_message(f"Killed stalled orchestrator (PID: {orchestrator_pid}).")
            except psutil.NoSuchProcess:
                log_message(f"Stalled orchestrator (PID: {orchestrator_pid}) already gone.")

        # Re-trigger the mission via the Deputy
        log_message("Requesting Deputy to re-launch the mission.")
        try:
            # We need to get the original prompt to relaunch
            original_prompt = "Default relaunch prompt: Audit and fix system." # Fallback
            prompt_file = latest_job / "state/prompt1.txt" # Assume agent1 prompt is good enough
            if prompt_file.exists():
                original_prompt = prompt_file.read_text(encoding='utf-8').splitlines()[0]

            subprocess.Popen([
                "python", str(REPO_ROOT / "scripts/chat_bridge.py"),
                "new", "Commander",
                f"VIGILANCE ALERT: Mission stalled. Relaunching. GOAL: {original_prompt} [SPAWN_TEAM: architect, engineer, tester]"
            ], cwd=str(REPO_ROOT))
        except Exception as e:
            log_message(f"Failed to request relaunch: {e}")
        
        # Finally, archive the failed job to prevent a loop
        archive_dir = REPO_ROOT / ".agent-jobs/_ARCHIVED_STALLED"
        archive_dir.mkdir(exist_ok=True)
        os.rename(latest_job, archive_dir / f"{latest_job.name}_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}")
        log_message(f"Archived stalled job {latest_job.name}.")


def update_universal_context():
    context = {
        "ts": dt.datetime.now().isoformat(),
        "active_pids": [],
        "system_load": {"cpu": 0, "ram": 0},
    }

    if psutil:
        context["system_load"]["cpu"] = psutil.cpu_percent()
        context["system_load"]["ram"] = psutil.virtual_memory().percent
    
    CONTEXT_FILE.parent.mkdir(exist_ok=True)
    CONTEXT_FILE.write_text(json.dumps(context, indent=2))


def main():
    while not KILL_SWITCH.exists():
        try:
            update_universal_context()
            latest_job = get_latest_job(REPO_ROOT)
            check_for_stall(latest_job)
        except Exception as e:
            log_message(f"Heartbeat error: {e}")
        time.sleep(30) # Check every 30 seconds

if __name__ == "__main__":
    log_message("Vigilance Sentinel Activated.")
    main()
