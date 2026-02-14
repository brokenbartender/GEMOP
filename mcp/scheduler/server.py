from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Dict, Any, List

from mcp.server import FastMCP

app = FastMCP("scheduler")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOG_PATH = os.path.join(DATA_DIR, "scheduler.log")

_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _log_event(event: Dict[str, Any]) -> None:
    _ensure_dirs()
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return
    delay = max(0.0, float(job.get("delay_seconds", 0)))
    time.sleep(delay)
    event = {
        "type": "scheduled_job",
        "job_id": job_id,
        "payload": job.get("payload"),
        "scheduled_at": job.get("created_at"),
        "fired_at": time.time(),
    }
    _log_event(event)
    with _lock:
        _jobs.pop(job_id, None)


@app.tool()
def schedule_once(delay_seconds: float, payload: Any) -> Dict[str, Any]:
    """Schedule a one-shot job. The job writes to scheduler.log when it fires."""
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "delay_seconds": float(delay_seconds),
        "payload": payload,
        "created_at": time.time(),
    }
    with _lock:
        _jobs[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return job


@app.tool()
def list_jobs() -> List[Dict[str, Any]]:
    """List pending jobs."""
    with _lock:
        return list(_jobs.values())


if __name__ == "__main__":
    app.run()
