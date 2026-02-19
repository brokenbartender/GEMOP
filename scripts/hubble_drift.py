from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


def _tok(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_./\\-]+", (text or "").lower()))


def _safe_read(path: Path, max_chars: int = 6000) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return txt[:max_chars]


def _recent_runs(repo_root: Path, limit: int) -> list[Path]:
    jobs = repo_root / ".agent-jobs"
    if not jobs.exists():
        return []
    runs = [d for d in jobs.iterdir() if d.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[: max(1, limit)]


def _candidate_files(repo_root: Path, run_dir: Path, recent_runs: int) -> list[Path]:
    out: list[Path] = []
    out.extend(
        [
            run_dir / "state" / "world_state.md",
            run_dir / "state" / "fact_sheet.md",
            run_dir / "state" / "mission_anchor.md",
            repo_root / "ramshare" / "learning" / "memory" / "lessons.md",
        ]
    )
    for r in _recent_runs(repo_root, recent_runs):
        out.extend(
            [
                r / "triad_orchestrator.log",
                r / "state" / "manifest.json",
                r / "state" / "world_state.md",
                r / "state" / "decisions_round1.json",
            ]
        )
    seen = set()
    dedup: list[Path] = []
    for p in out:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp in seen:
            continue
        seen.add(rp)
        dedup.append(p)
    return dedup


def compute_drift(repo_root: Path, run_dir: Path, query: str, h0: float, recent_runs: int) -> dict[str, Any]:
    now = time.time()
    qtok = _tok(query)
    receding = []
    distances = []
    velocities = []
    max_age_h = 0.0

    for p in _candidate_files(repo_root, run_dir, recent_runs):
        if not p.exists():
            continue
        text = _safe_read(p)
        if not text.strip():
            continue
        ptok = _tok(text)
        if qtok and ptok:
            inter = len(qtok & ptok)
            uni = max(1, len(qtok | ptok))
            similarity = inter / uni
            distance = 1.0 - similarity
        else:
            distance = 1.0
        try:
            age_h = max(0.0, (now - p.stat().st_mtime) / 3600.0)
        except Exception:
            age_h = 0.0
        age_factor = 1.0 + (age_h / 24.0)
        velocity = float(h0) * float(distance) * age_factor
        max_age_h = max(max_age_h, age_h)
        distances.append(distance)
        velocities.append(velocity)
        receding.append(
            {
                "path": str(p),
                "distance": round(distance, 6),
                "velocity": round(velocity, 6),
                "age_hours": round(age_h, 3),
            }
        )

    receding.sort(key=lambda x: x.get("velocity", 0.0), reverse=True)
    avg_distance = (sum(distances) / len(distances)) if distances else 0.0
    avg_velocity = (sum(velocities) / len(velocities)) if velocities else 0.0
    drift_alert = avg_velocity >= 0.85 or (max_age_h >= 72 and avg_distance >= 0.75)

    return {
        "schema_version": 1,
        "generated_at": now,
        "query": query,
        "equation": "v = H0 * D",
        "H0": h0,
        "avg_distance": round(avg_distance, 6),
        "avg_velocity": round(avg_velocity, 6),
        "max_age_hours": round(max_age_h, 3),
        "drift_alert": bool(drift_alert),
        "receding_entries": receding[:30],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute semantic drift using Hubble-style expansion model.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--h0", type=float, default=1.0)
    ap.add_argument("--recent-runs", type=int, default=10)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    run_state = run_dir / "state"
    run_state.mkdir(parents=True, exist_ok=True)
    payload = compute_drift(repo_root, run_dir, args.query, float(args.h0), int(args.recent_runs))
    out = run_state / "hubble_drift.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
