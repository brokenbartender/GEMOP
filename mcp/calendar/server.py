from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP

app = FastMCP("calendar")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STORE_PATH = os.path.join(DATA_DIR, "calendar.json")


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_store() -> List[Dict[str, Any]]:
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []


def _save_store(events: List[Dict[str, Any]]) -> None:
    _ensure_dirs()
    with open(STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(events, handle)


@app.tool()
def add_event(title: str, start_ts: float, end_ts: float, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add a calendar event (epoch seconds)."""
    event = {
        "id": str(uuid.uuid4()),
        "title": title,
        "start_ts": float(start_ts),
        "end_ts": float(end_ts),
        "metadata": metadata or {},
        "created_at": time.time(),
    }
    events = _load_store()
    events.append(event)
    _save_store(events)
    return event


@app.tool()
def list_events(start_ts: Optional[float] = None, end_ts: Optional[float] = None) -> List[Dict[str, Any]]:
    """List events filtered by optional time range (epoch seconds)."""
    events = _load_store()
    if start_ts is None and end_ts is None:
        return events
    out = []
    for ev in events:
        if start_ts is not None and ev.get("end_ts", 0) < start_ts:
            continue
        if end_ts is not None and ev.get("start_ts", 0) > end_ts:
            continue
        out.append(ev)
    return out


@app.tool()
def delete_event(event_id: str) -> Dict[str, Any]:
    """Delete an event by id."""
    events = _load_store()
    remaining = [e for e in events if e.get("id") != event_id]
    deleted = len(remaining) != len(events)
    if deleted:
        _save_store(remaining)
    return {"ok": deleted, "id": event_id}


if __name__ == "__main__":
    app.run()
