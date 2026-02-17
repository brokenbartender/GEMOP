from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _read_text(p: Path, limit: int = 200_000) -> str:
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return txt[:limit]


@dataclass
class RunScore:
    run_dir: str
    created_at: float
    online: Optional[bool]
    agents: Optional[int]
    rounds: int
    decision_missing_total: int
    patch_apply_ok: Optional[bool]
    verify_ok: Optional[bool]
    local_overload_hits: int
    ollama_timeouts: int


def _parse_manifest(run_dir: Path) -> Tuple[Optional[bool], Optional[int], float]:
    m = run_dir / "state" / "manifest.json"
    if not m.exists():
        return None, None, 0.0
    obj = _read_json(m)
    if not isinstance(obj, dict):
        return None, None, 0.0
    online = obj.get("online")
    agents = obj.get("agents")
    created_at = float(obj.get("created_at") or 0.0)
    return bool(online) if online is not None else None, int(agents) if agents is not None else None, created_at


def _count_decision_missing(run_dir: Path) -> Tuple[int, int]:
    """Returns (rounds_seen, missing_total) based on state/decisions_round*.json."""
    total_missing = 0
    rounds_seen = 0
    for p in sorted((run_dir / "state").glob("decisions_round*.json")):
        obj = _read_json(p)
        if not isinstance(obj, dict):
            continue
        rounds_seen += 1
        miss = obj.get("missing") or []
        if isinstance(miss, list):
            total_missing += len(miss)
    return rounds_seen, total_missing


def _latest_patch_apply(run_dir: Path) -> Optional[bool]:
    cands = sorted((run_dir / "state").glob("patch_apply_round*.json"))
    if not cands:
        return None
    obj = _read_json(cands[-1])
    if not isinstance(obj, dict):
        return None
    ok = obj.get("ok")
    return bool(ok) if ok is not None else None


def _latest_verify_ok(run_dir: Path) -> Optional[bool]:
    # Heuristic: parse orchestrator log line "verify_pipeline round=X ok"
    logp = run_dir / "triad_orchestrator.log"
    if not logp.exists():
        return None
    txt = _read_text(logp, limit=300_000)
    ok_lines = [ln for ln in txt.splitlines() if "verify_pipeline" in ln]
    if not ok_lines:
        return None
    # if any failed, treat as failed; else ok
    for ln in reversed(ok_lines):
        if "verify_pipeline_failed" in ln:
            return False
        if re.search(r"\bverify_pipeline\b.*\bok\b", ln):
            return True
    return None


def _count_fail_signals(run_dir: Path) -> Tuple[int, int]:
    """Returns (local_overload_hits, ollama_timeouts)."""
    metrics = run_dir / "state" / "agent_metrics.jsonl"
    local_overload = 0
    ollama_timeouts = 0
    if metrics.exists():
        for ln in _read_text(metrics, limit=2_000_000).splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            # These strings are emitted in local_call() messages.
            out_md = row.get("out_md")
            if out_md and isinstance(out_md, str):
                op = Path(out_md)
                if op.exists():
                    body = _read_text(op, limit=50_000)
                    if "LOCAL_OVERLOAD:" in body:
                        local_overload += 1
    # Agent runner debug log also contains raw ollama timeout lines.
    dbg = Path("logs") / "agent_runner_debug.log"
    try:
        if dbg.exists():
            txt = _read_text(dbg, limit=3_000_000)
            # Very rough: count occurrences that mention run_dir name to avoid cross-run inflation.
            tag = run_dir.name
            for ln in txt.splitlines():
                if tag and tag not in ln:
                    continue
                if "Read timed out" in ln and "Ollama" in ln:
                    ollama_timeouts += 1
    except Exception:
        pass
    return local_overload, ollama_timeouts


def score_run(run_dir: Path) -> RunScore:
    online, agents, created_at = _parse_manifest(run_dir)
    rounds_seen, missing_total = _count_decision_missing(run_dir)
    patch_ok = _latest_patch_apply(run_dir)
    verify_ok = _latest_verify_ok(run_dir)
    local_overload, ollama_timeouts = _count_fail_signals(run_dir)
    return RunScore(
        run_dir=str(run_dir),
        created_at=created_at,
        online=online,
        agents=agents,
        rounds=rounds_seen,
        decision_missing_total=missing_total,
        patch_apply_ok=patch_ok,
        verify_ok=verify_ok,
        local_overload_hits=local_overload,
        ollama_timeouts=ollama_timeouts,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate prior runs for quality gate compliance and failure signals.")
    ap.add_argument("--jobs-dir", default=str(Path(".agent-jobs").resolve()))
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    jobs = Path(args.jobs_dir).resolve()
    if not jobs.exists():
        print(json.dumps({"ok": False, "error": "jobs_dir_not_found", "jobs_dir": str(jobs)}, indent=2))
        return 2

    runs = [p for p in jobs.iterdir() if p.is_dir()]
    scored: List[RunScore] = []
    for r in runs:
        if not (r / "triad_orchestrator.log").exists() and not (r / "state" / "manifest.json").exists():
            continue
        scored.append(score_run(r))

    scored.sort(key=lambda s: (s.created_at or 0.0), reverse=True)
    scored = scored[: max(1, int(args.limit))]

    out: Dict[str, Any] = {
        "ok": True,
        "generated_at": time.time(),
        "count": len(scored),
        "runs": [s.__dict__ for s in scored],
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        # Compact table.
        for s in scored:
            print(
                f"{Path(s.run_dir).name} rounds={s.rounds} missing_decisions={s.decision_missing_total} "
                f"patch_ok={s.patch_apply_ok} verify_ok={s.verify_ok} local_overload={s.local_overload_hits} "
                f"ollama_timeouts={s.ollama_timeouts}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

