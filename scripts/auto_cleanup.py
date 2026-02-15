import os
import shutil
import time
from pathlib import Path
import logging

# --- Configuration ---
REPO_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = REPO_ROOT / ".agent-jobs"
ARCHIVE_DIR = REPO_ROOT / "compressed_archives"
LOG_FILE = REPO_ROOT / "logs/cleanup.log"
AGE_THRESHOLD_HOURS = 48

# Setup Logging
os.makedirs(REPO_ROOT / "logs", exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def cleanup_jobs(dry_run=False):
    if not JOBS_DIR.exists():
        print(f"Jobs directory not found: {JOBS_DIR}")
        return

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    now = time.time()
    threshold_sec = AGE_THRESHOLD_HOURS * 3600
    
    # Get all job folders, excluding 'latest'
    jobs = [d for d in JOBS_DIR.iterdir() if d.is_dir() and d.name != "latest"]
    if not jobs:
        print("No jobs found to clean.")
        return

    # Identify the newest job to EXEMPT it
    newest_job = max(jobs, key=lambda p: p.stat().st_mtime)
    
    count = 0
    for job in jobs:
        if job == newest_job:
            continue
            
        mtime = job.stat().st_mtime
        age_sec = now - mtime
        
        if age_sec > threshold_sec:
            dest = ARCHIVE_DIR / job.name
            msg = f"{'[DRY RUN] ' if dry_run else ''}Moving {job.name} to archives (Age: {int(age_sec/3600)}h)"
            print(msg)
            logging.info(msg)
            
            if not dry_run:
                try:
                    shutil.move(str(job), str(dest))
                    count += 1
                except Exception as e:
                    err = f"Failed to move {job.name}: {e}"
                    print(err)
                    logging.error(err)
                    
    print(f"Cleanup complete. Total moved: {count}")

if __name__ == "__main__":
    import sys
    is_dry = "--dry-run" in sys.argv
    cleanup_jobs(dry_run=is_dry)
