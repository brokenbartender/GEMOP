from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def select_prompt(run_dir: Path, default_prompt: str, round_n: int) -> dict[str, Any]:
    state_dir = run_dir / "state"
    eh = _read_json(state_dir / "event_horizon.json")
    shards = eh.get("shards") if isinstance(eh.get("shards"), list) else []
    split_required = bool(eh.get("split_required")) and len(shards) >= 2
    total = len(shards) if split_required else 1

    if split_required:
        idx = max(0, min(int(round_n) - 1, total - 1))
        prompt = str(shards[idx] or "")
    else:
        idx = 0
        prompt = default_prompt

    schedule = {
        "schema_version": 1,
        "updated_at": time.time(),
        "split_required": split_required,
        "shard_total": total,
        "selected_shard_index": idx,
        "selected_round": int(round_n),
    }
    _write_json(state_dir / "event_horizon_schedule.json", schedule)

    return {
        "prompt": prompt,
        "split_required": split_required,
        "shard_index": idx,
        "shard_total": total,
        "schedule_path": str(state_dir / "event_horizon_schedule.json"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Select current event-horizon shard prompt for a run round.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--default-prompt", default="")
    args = ap.parse_args()

    out = select_prompt(Path(args.run_dir).resolve(), str(args.default_prompt or ""), int(args.round))
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
