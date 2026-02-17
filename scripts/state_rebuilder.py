from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def safe_read_text(path: Path, max_bytes: int = 200_000) -> str:
    try:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
        for enc in ("utf-8-sig", "utf-16", "utf-8"):
            try:
                return raw.decode(enc, errors="ignore").replace("\x00", "")
            except Exception:
                continue
    except Exception:
        return ""
    return ""


def build_world_state(run_dir: Path, round_n: int) -> str:
    state_dir = run_dir / "state"
    anchor = safe_read_text(state_dir / "mission_anchor.md", max_bytes=120_000).strip()
    digest = safe_read_text(state_dir / f"round{round_n}_digest.md", max_bytes=120_000).strip()
    sup = safe_read_text(state_dir / f"supervisor_round{round_n}.json", max_bytes=120_000).strip()

    # Bus status snapshot
    bus_state = safe_read_text(run_dir / "bus" / "state.json", max_bytes=120_000).strip()
    bus_status = ""
    if bus_state:
        try:
            obj = json.loads(bus_state)
            dec = obj.get("decisions", {}) or {}
            unresolved = {k: v.get("status") for k, v in dec.items() if not str(v.get("status", "")).startswith("resolved_")}
            bus_status = json.dumps({"quorum": obj.get("quorum"), "unresolved_decisions": unresolved}, indent=2)
        except Exception:
            bus_status = ""

    lines: list[str] = []
    lines.append("# World State (Rebuilt)")
    lines.append("")
    lines.append(f"generated_at: {time.time()}")
    lines.append(f"run_id: {run_dir.name}")
    lines.append(f"round: {round_n}")
    lines.append("")
    if anchor:
        lines.append("## Mission Anchor")
        lines.append(anchor)
        lines.append("")
    if digest:
        lines.append("## Latest Digest")
        lines.append(digest)
        lines.append("")
    if bus_status:
        lines.append("## Bus Snapshot")
        lines.append("```json")
        lines.append(bus_status.strip())
        lines.append("```")
        lines.append("")
    if sup:
        lines.append("## Supervisor (Raw, Truncated)")
        # Keep only the tail; this is for recovery, not full audit.
        tail = sup[-20_000:] if len(sup) > 20_000 else sup
        lines.append("```json")
        lines.append(tail.strip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild drift-resistant world state artifact for long/blackout runs.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=1)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    out = build_world_state(run_dir, round_n)
    (state_dir / "world_state.md").write_text(out, encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(state_dir / "world_state.md"), "round": round_n}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

