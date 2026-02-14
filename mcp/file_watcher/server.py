from __future__ import annotations

import hashlib
import json
import os
import time
from fnmatch import fnmatch
from typing import Any, Dict, List

from mcp.server import FastMCP

app = FastMCP("file-watcher")


def _iter_files(root: str, pattern: str | None = None) -> List[str]:
    files: List[str] = []
    for base, _, names in os.walk(root):
        for name in names:
            path = os.path.join(base, name)
            if pattern and not fnmatch(path, pattern):
                continue
            files.append(path)
    return files


def _snapshot(root: str, pattern: str | None = None) -> Dict[str, Any]:
    items = []
    for path in _iter_files(root, pattern):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        items.append({
            "path": path,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        })
    digest = hashlib.sha256(
        json.dumps(items, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "root": root,
        "pattern": pattern or "*",
        "timestamp": time.time(),
        "digest": digest,
        "items": items,
    }


@app.tool()
def list_recent_files(path: str, limit: int = 20, pattern: str | None = None) -> List[Dict[str, Any]]:
    """List most recently modified files under a path."""
    files = []
    for file_path in _iter_files(path, pattern):
        try:
            stat = os.stat(file_path)
        except OSError:
            continue
        files.append({
            "path": file_path,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files[: max(1, int(limit))]


@app.tool()
def snapshot(path: str, pattern: str | None = None) -> Dict[str, Any]:
    """Create a snapshot of files (path, mtime, size)."""
    return _snapshot(path, pattern)


@app.tool()
def diff(previous: Dict[str, Any]) -> Dict[str, Any]:
    """Diff a previous snapshot against current state."""
    root = previous.get("root")
    pattern = previous.get("pattern")
    if not root:
        raise ValueError("previous snapshot missing root")
    current = _snapshot(root, pattern if pattern != "*" else None)

    prev_items = {i["path"]: i for i in previous.get("items", [])}
    curr_items = {i["path"]: i for i in current.get("items", [])}

    added = [v for k, v in curr_items.items() if k not in prev_items]
    removed = [v for k, v in prev_items.items() if k not in curr_items]
    changed = []
    for path, curr in curr_items.items():
        prev = prev_items.get(path)
        if not prev:
            continue
        if prev.get("mtime") != curr.get("mtime") or prev.get("size") != curr.get("size"):
            changed.append({"before": prev, "after": curr})

    return {
        "root": root,
        "pattern": pattern,
        "previous_digest": previous.get("digest"),
        "current_digest": current.get("digest"),
        "added": added,
        "removed": removed,
        "changed": changed,
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    app.run()
