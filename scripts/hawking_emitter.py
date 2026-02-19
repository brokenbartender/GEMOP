from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _tail_text(path: Path, max_lines: int = 3, max_chars: int = 360) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    if not lines:
        return ""
    txt = " | ".join(lines[-max_lines:])
    return txt[-max_chars:]


def _build_summary(reason: str, error: str, agent: int, round_num: int, pid: int | None, log_tail: str) -> str:
    chunks = []
    if reason:
        chunks.append(reason.strip())
    if error:
        chunks.append(f"error={error.strip()}")
    if agent > 0:
        chunks.append(f"agent={agent}")
    if round_num > 0:
        chunks.append(f"round={round_num}")
    if pid is not None:
        chunks.append(f"pid={pid}")
    if log_tail:
        chunks.append(f"log_tail={log_tail}")
    out = "; ".join(chunks).strip()
    return out[:420]


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _emit_bus(run_dir: Path, summary: str) -> None:
    bus_state = run_dir / "bus" / "state.json"
    if not bus_state.exists():
        return
    bus = Path(__file__).with_name("council_bus.py")
    if not bus.exists():
        return
    try:
        subprocess.run(
            [
                sys.executable,
                str(bus),
                "send",
                "--run-dir",
                str(run_dir),
                "--sender",
                "hawking_emitter",
                "--receiver",
                "council",
                "--intent",
                "radiation",
                "--message",
                summary,
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        pass


def emit_radiation(
    run_dir: Path,
    *,
    source: str = "iolaus",
    reason: str = "",
    agent: int = 0,
    round_num: int = 0,
    pid: int | None = None,
    error: str = "",
    emit_bus: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    orch_log = run_dir / "triad_orchestrator.log"
    log_tail = _tail_text(orch_log)
    summary = _build_summary(reason, error, agent, round_num, pid, log_tail)

    row: dict[str, Any] = {
        "ts": time.time(),
        "source": str(source or "unknown"),
        "reason": str(reason or ""),
        "agent": int(agent or 0),
        "round": int(round_num or 0),
        "pid": int(pid) if pid is not None else None,
        "error": str(error or ""),
        "summary": summary,
    }
    if extra:
        row["extra"] = dict(extra)

    _append_jsonl(state_dir / "hawking_radiation.jsonl", row)
    (state_dir / "hawking_latest.json").write_text(json.dumps(row, indent=2), encoding="utf-8")

    if emit_bus:
        _emit_bus(run_dir, summary)
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit Hawking micro-summary from a terminated/failing process.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--source", default="iolaus")
    ap.add_argument("--reason", default="")
    ap.add_argument("--agent", type=int, default=0)
    ap.add_argument("--round", dest="round_num", type=int, default=0)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--error", default="")
    ap.add_argument("--no-bus", action="store_true")
    args = ap.parse_args()

    row = emit_radiation(
        Path(args.run_dir),
        source=args.source,
        reason=args.reason,
        agent=args.agent,
        round_num=args.round_num,
        pid=args.pid,
        error=args.error,
        emit_bus=not bool(args.no_bus),
    )
    print(json.dumps(row, separators=(",", ":")))


if __name__ == "__main__":
    main()
