from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / "ramshare" / "state"
WORLD_MODEL_DIR = STATE_DIR / "world_model"
WORLD_MODEL_PATH = WORLD_MODEL_DIR / "latest.json"
RUN_SUMMARIES = STATE_DIR / "learning" / "run_summaries.jsonl"
QUALITY_MODEL = STATE_DIR / "learning" / "quality_model.json"
COUNCIL_MODEL = STATE_DIR / "learning" / "council_model.json"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    return rows


def latest_capability_catalog() -> Dict[str, Any]:
    jobs = REPO_ROOT / ".agent-jobs"
    if not jobs.exists():
        return {}
    runs = sorted([p for p in jobs.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        p = run / "capability-catalog.json"
        if p.exists():
            payload = read_json(p, {})
            if isinstance(payload, dict):
                payload["run_dir"] = str(run)
                return payload
    return {}


def _parse_ts(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0
    return 0.0


def build_snapshot() -> Dict[str, Any]:
    runs = read_jsonl(RUN_SUMMARIES)
    quality = read_json(QUALITY_MODEL, {})
    council = read_json(COUNCIL_MODEL, {})
    capability = latest_capability_catalog()

    latest_run = runs[-1] if runs else {}
    avg_score = float(latest_run.get("avg_score", 0.0) or 0.0)
    fail_count = len(latest_run.get("failing_agents", []) or []) if isinstance(latest_run, dict) else 0
    latest_run_ts = _parse_ts(latest_run.get("ts")) if isinstance(latest_run, dict) else 0.0
    stale_seconds = 0.0 if latest_run_ts <= 0 else max(0.0, datetime.now().timestamp() - latest_run_ts)
    freshness_ok = latest_run_ts > 0 and stale_seconds <= 6 * 3600

    top_mistakes = []
    if isinstance(quality, dict):
        mc = quality.get("mistake_counts", {}) or {}
        if isinstance(mc, dict):
            top_mistakes = sorted(mc.items(), key=lambda kv: kv[1], reverse=True)[:5]

    status = "green" if avg_score >= 70 and fail_count == 0 else "yellow" if avg_score >= 60 else "red"
    if not freshness_ok:
        status = "red"

    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "latest_run": latest_run,
        "health": {
            "avg_score": avg_score,
            "failing_agents": fail_count,
            "status": status,
            "freshness_ok": freshness_ok,
            "stale_run_seconds": round(stale_seconds, 2),
        },
        "quality_model": {
            "updated_at": quality.get("updated_at") if isinstance(quality, dict) else None,
            "prompt_hints": quality.get("prompt_hints", []) if isinstance(quality, dict) else [],
            "top_mistakes": top_mistakes,
        },
        "council_model": {
            "latest_manifesto": council.get("current_manifesto", {}) if isinstance(council, dict) else {},
            "issue_counts": council.get("issue_counts", {}) if isinstance(council, dict) else {},
        },
        "capabilities": {
            "latest_catalog": capability,
        },
        "run_count": len(runs),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build world-model snapshot from run/learning state")
    ap.add_argument("--refresh", action="store_true", help="Write latest snapshot")
    args = ap.parse_args()

    if not args.refresh:
        print(json.dumps({"ok": False, "error": "use --refresh"}, indent=2))
        raise SystemExit(1)

    snap = build_snapshot()
    WORLD_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    WORLD_MODEL_PATH.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(WORLD_MODEL_PATH), "health": snap.get("health", {})}, indent=2))


if __name__ == "__main__":
    main()
