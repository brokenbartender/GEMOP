from __future__ import annotations

import json
import os
import time
from typing import Dict, Any

from mcp.server import FastMCP

app = FastMCP("notify")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOG_PATH = os.path.join(DATA_DIR, "notifications.log")


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _log_event(event: Dict[str, Any]) -> None:
    _ensure_dirs()
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


@app.tool()
def notify(message: str, level: str = "info") -> Dict[str, Any]:
    """Record a notification event."""
    event = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
    }
    _log_event(event)
    return {"ok": True, "event": event}


if __name__ == "__main__":
    app.run()
