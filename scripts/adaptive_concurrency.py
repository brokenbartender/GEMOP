from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

def get_cpu_load() -> float:
    if psutil:
        return psutil.cpu_percent(interval=1)
    return 0.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def p95(nums: list[float]) -> float:
    if not nums:
        return 0.0
    xs = sorted(nums)
    idx = int(round(0.95 * (len(xs) - 1)))
    return float(xs[max(0, min(len(xs) - 1, idx))])


def main() -> int:
    ap = argparse.ArgumentParser(description="Recommend safe max_parallel/max_local_concurrency based on run metrics.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--current-max-parallel", type=int, default=3)
    ap.add_argument("--current-max-local", type=int, default=2)
    ap.add_argument("--out", default="", help="Output JSON path (default: <run>/state/concurrency.json)")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state = run_dir / "state"
    metrics_path = state / "agent_metrics.jsonl"
    rows = read_jsonl(metrics_path)

    durations: list[float] = []
    slot_waits: list[float] = []
    overloads = 0
    for r in rows:
        try:
            d = float(r.get("duration_s") or 0)
            if d > 0:
                durations.append(d)
        except Exception:
            pass
        try:
            w = float(r.get("local_slot_wait_s") or 0)
            if w > 0:
                slot_waits.append(w)
        except Exception:
            pass
        try:
            if str(r.get("ok")).lower() in ("false", "0") and "LOCAL_OVERLOAD" in str(r.get("error") or ""):
                overloads += 1
        except Exception:
            pass

    d95 = p95(durations)
    w95 = p95(slot_waits)

    max_parallel = max(1, int(args.current_max_parallel))
    max_local = max(1, int(args.current_max_local))
    reasons: list[str] = []

    # --- THERMAL-AWARE THROTTLING ---
    cpu_load = get_cpu_load()
    if cpu_load >= 90.0:
        max_parallel = 1
        reasons.append(f"CPU_LOAD={cpu_load}% >= 90% -> thermal failsafe throttle to 1")

    # Conservative: only reduce based on evidence of slowness/queueing.
    if w95 >= 30 and max_parallel > 1:
        max_parallel = max(1, max_parallel - 1)
        reasons.append(f"local_slot_wait_p95={w95}>=30s -> reduce max_parallel")
    if d95 >= 240:
        max_parallel = max(1, max_parallel - 1)
        reasons.append(f"duration_p95={d95}>=240s -> reduce max_parallel")
    if w95 >= 60:
        max_local = max(1, max_local - 1)
        reasons.append(f"local_slot_wait_p95={w95}>=60s -> reduce max_local_concurrency")

    out_path = Path(args.out).resolve() if args.out else (state / "concurrency.json")
    payload = {
        "generated_at": time.time(),
        "current": {"max_parallel": int(args.current_max_parallel), "max_local_concurrency": int(args.current_max_local)},
        "recommended": {"max_parallel": int(max_parallel), "max_local_concurrency": int(max_local)},
        "metrics": {"duration_p95_s": d95, "local_slot_wait_p95_s": w95, "rows": len(rows), "overloads": overloads},
        "reasons": reasons,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

