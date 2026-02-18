from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict


A2A_SCHEMA_V1 = "a2a.v1"
A2A_SCHEMA_V2 = "a2a.v2"
ACK_SCHEMA_VERSION = "a2a.ack.v1"


def repo_root() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT", "") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
INBOX_DIR = REPO_ROOT / "ramshare" / "state" / "a2a" / "inbox"
WAL_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "wal_receive.jsonl"
IDEMPOTENCY_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "receive_idempotency.json"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _load_idempotency() -> Dict[str, float]:
    if not IDEMPOTENCY_PATH.exists():
        return {}
    try:
        data = json.loads(IDEMPOTENCY_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _save_idempotency(data: Dict[str, float]) -> None:
    _atomic_write_text(IDEMPOTENCY_PATH, json.dumps(data, indent=2))


def _mark_or_reject_task(task_id: str, ttl_sec: int = 14 * 24 * 3600) -> bool:
    now = time.time()
    data = _load_idempotency()
    data = {k: v for k, v in data.items() if (now - float(v)) < ttl_sec}
    if task_id in data:
        _save_idempotency(data)
        return False
    data[task_id] = now
    _save_idempotency(data)
    return True


def _required_secret() -> str:
    # Prefer GEMINI_OP_A2A_SHARED_SECRET; fall back to AGENTIC_A2A_SHARED_SECRET for compatibility.
    s = (os.environ.get("GEMINI_OP_A2A_SHARED_SECRET", "") or "").strip()
    if s:
        return s
    return (os.environ.get("AGENTIC_A2A_SHARED_SECRET", "") or "").strip()


def _validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    version = str(payload.get("schema_version", "") or "").strip() or A2A_SCHEMA_V1
    if version not in (A2A_SCHEMA_V1, A2A_SCHEMA_V2):
        raise SystemExit(f"invalid schema_version: {version}")
    payload["schema_version"] = version

    payload.setdefault("intent", "chat")
    payload["intent"] = str(payload.get("intent") or "chat").strip() or "chat"

    if "task_id" not in payload or not str(payload.get("task_id") or "").strip():
        payload["task_id"] = str(uuid.uuid4())
    if "timestamp" not in payload:
        payload["timestamp"] = time.time()

    if payload.get("action_payload") is not None and version == A2A_SCHEMA_V1:
        payload["schema_version"] = A2A_SCHEMA_V2
        version = A2A_SCHEMA_V2

    ap = payload.get("action_payload")
    if version == A2A_SCHEMA_V2 and ap is not None:
        if not isinstance(ap, dict):
            raise SystemExit("action_payload must be an object")
        tool = ap.get("tool")
        params = ap.get("params")
        if not isinstance(tool, str) or not tool.strip():
            raise SystemExit("action_payload.tool must be a non-empty string")
        if params is None:
            ap["params"] = {}
        elif not isinstance(params, dict):
            raise SystemExit("action_payload.params must be an object")

    required = _required_secret()
    provided = str(payload.get("shared_secret") or "").strip()
    if required and (provided != required):
        raise SystemExit("shared_secret mismatch")

    return payload


def _ack(status: str, *, task_id: str, detail: str = "") -> Dict[str, Any]:
    return {
        "ok": status in ("queued", "duplicate_ignored"),
        "task_id": task_id,
        "ack": {
            "ack_contract_version": ACK_SCHEMA_VERSION,
            "ack_status": status,
            "ack_observed": status in ("queued", "duplicate_ignored", "received", "accepted"),
            "detail": detail,
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Receive A2A payload (stdin or file) and enqueue into inbox.")
    ap.add_argument("--payload-file", default="", help="Path to JSON payload file")
    ap.add_argument("--stdin", action="store_true", help="Read JSON payload from stdin")
    ap.add_argument("--inbox-dir", default=str(INBOX_DIR), help="Override inbox directory")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    inbox_dir = Path(args.inbox_dir).expanduser().resolve()
    if args.stdin:
        raw = (os.sys.stdin.read() or "").strip()
        if not raw:
            raise SystemExit("no stdin payload provided")
        payload = json.loads(raw)
    else:
        if not args.payload_file:
            raise SystemExit("one of --stdin or --payload-file is required")
        p = Path(args.payload_file).expanduser().resolve()
        if not p.exists():
            raise SystemExit(f"payload file not found: {p}")
        payload = json.loads(p.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise SystemExit("payload must be a JSON object")
    payload = _validate_payload(payload)
    task_id = str(payload.get("task_id"))

    _append_jsonl(WAL_PATH, {"ts": time.time(), "event": "received", "task_id": task_id, "intent": payload.get("intent")})

    if not _mark_or_reject_task(task_id):
        out = _ack("duplicate_ignored", task_id=task_id)
        print(json.dumps(out))
        return 0

    inbox_dir.mkdir(parents=True, exist_ok=True)
    out_path = inbox_dir / f"{int(time.time() * 1000)}_{task_id}.json"
    _atomic_write_text(out_path, json.dumps(payload, indent=2))
    _append_jsonl(WAL_PATH, {"ts": time.time(), "event": "queued", "task_id": task_id, "path": str(out_path)})

    out = _ack("queued", task_id=task_id)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

