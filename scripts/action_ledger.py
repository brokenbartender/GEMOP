from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class ActionRecord:
    action_id: str
    kind: str
    ts: float
    details: Dict[str, Any]


def ledger_path(run_dir: Path) -> Path:
    return run_dir / "state" / "actions.jsonl"


def append_action(run_dir: Path, *, action_id: str, kind: str, details: Dict[str, Any] | None = None) -> None:
    p = ledger_path(run_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": 1,
        "ts": time.time(),
        "action_id": str(action_id),
        "kind": str(kind),
        "details": details or {},
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def iter_actions(run_dir: Path) -> Iterable[ActionRecord]:
    p = ledger_path(run_dir)
    if not p.exists():
        return []
    out: list[ActionRecord] = []
    try:
        for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = (ln or "").strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            aid = str(obj.get("action_id") or "").strip()
            kind = str(obj.get("kind") or "").strip()
            ts = float(obj.get("ts") or 0.0)
            det = obj.get("details") if isinstance(obj.get("details"), dict) else {}
            if aid and kind:
                out.append(ActionRecord(action_id=aid, kind=kind, ts=ts, details=dict(det)))
    except Exception:
        return []
    return out


def has_action(run_dir: Path, *, action_id: str, kind: str | None = None) -> bool:
    aid = str(action_id or "").strip()
    if not aid:
        return False
    k = str(kind or "").strip() if kind is not None else ""
    for r in iter_actions(run_dir):
        if r.action_id != aid:
            continue
        if k and r.kind != k:
            continue
        return True
    return False

