from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Grant an approval for a pending action in a run directory.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--action-id", required=True)
    ap.add_argument("--kind", default="patch_apply")
    ap.add_argument("--actor", default="human")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    approvals = state_dir / "approvals.jsonl"

    row = {
        "schema_version": 1,
        "ts": time.time(),
        "action_id": str(args.action_id),
        "kind": str(args.kind),
        "actor": str(args.actor),
        "note": str(args.note or ""),
    }
    append_jsonl(approvals, row)
    print(json.dumps({"ok": True, "approvals": str(approvals), "action_id": str(args.action_id)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

