from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "ramshare" / "state" / "learning" / "efficiency_model.json"


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def score_run(run_dir: Path) -> Dict[str, Any]:
    md_files = sorted(run_dir.glob("agent*.md"))
    log_files = sorted(run_dir.glob("agent*.log"))
    total = len(md_files)
    timeout_count = 0
    for f in md_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "TIMEOUT" in text:
            timeout_count += 1

    # Learn script-format reliability from log signatures.
    # These patterns indicate command quoting/wrapper format mistakes, not model quality.
    format_error_patterns = [
        r"is not recognized as an internal or external command",
        r"not recognized as an internal or external command",
        r"Provide a task prompt\.",
        r"Unexpected token",
        r"ParserError",
        r"The term '.*' is not recognized",
        r"Missing argument in parameter list",
    ]
    fmt_errors = 0
    fmt_hits: Dict[str, int] = {}
    for lf in log_files:
        text = lf.read_text(encoding="utf-8", errors="ignore")
        for pat in format_error_patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                fmt_errors += 1
                fmt_hits[pat] = fmt_hits.get(pat, 0) + 1

    success = max(0, total - timeout_count)
    timeout_rate = (timeout_count / total) if total else 1.0
    format_error_rate = (fmt_errors / max(1, len(log_files))) if log_files else 0.0
    return {
        "run_id": run_dir.name,
        "agents_total": total,
        "agents_success": success,
        "agents_timeout": timeout_count,
        "timeout_rate": round(timeout_rate, 4),
        "format_errors": fmt_errors,
        "format_error_rate": round(format_error_rate, 4),
        "format_error_signatures": fmt_hits,
    }


def update_model(model: Dict[str, Any], run_stats: Dict[str, Any]) -> Dict[str, Any]:
    history: List[Dict[str, Any]] = model.setdefault("history", [])
    # Keep one latest row per run_id to avoid drift from repeated rescoring of the same run.
    run_id = run_stats.get("run_id")
    replaced = False
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("run_id") == run_id:
            history[i] = run_stats
            replaced = True
            break
    if not replaced:
        history.append(run_stats)
    # Collapse duplicate run_ids (keep latest occurrence).
    latest_by_run: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in history:
        rid = str(row.get("run_id", ""))
        if rid not in latest_by_run:
            order.append(rid)
        latest_by_run[rid] = row
    history = [latest_by_run[rid] for rid in order if rid]
    history = history[-30:]
    model["history"] = history

    # Tune recommendation from recent timeout pressure.
    # Ignore empty runs (no agent outputs) so interrupted runs don't poison the model.
    recent = [x for x in history[-5:] if int(x.get("agents_total", 0)) > 0]
    avg_timeout = (
        sum(x.get("timeout_rate", 1.0) for x in recent) / max(1, len(recent))
        if recent
        else float(model.get("avg_timeout_rate_recent", 0.0))
    )
    avg_fmt_err = (
        sum(x.get("format_error_rate", 0.0) for x in recent) / max(1, len(recent))
        if recent
        else float(model.get("avg_format_error_rate_recent", 0.0))
    )
    current = int(model.get("recommended_agents_per_console", 2))

    if avg_timeout > 0.30:
        current = max(1, current - 1)
    elif avg_timeout < 0.05:
        current = min(4, current + 1)

    # Learn preferred runner format.
    # If format errors appear, bias to explicit raw Gemini path with direct stdin piping.
    preferred = str(model.get("preferred_launch_format", "raw_GEMINI_cmd_exec"))
    if avg_fmt_err > 0.15:
        preferred = "raw_GEMINI_cmd_exec_strict_quote"
    elif avg_fmt_err <= 0.02:
        preferred = "raw_GEMINI_cmd_exec"

    model["recommended_agents_per_console"] = current
    model["avg_timeout_rate_recent"] = round(avg_timeout, 4)
    model["avg_format_error_rate_recent"] = round(avg_fmt_err, 4)
    model["preferred_launch_format"] = preferred

    # Aggregate top error signatures so future runs can avoid them.
    sig_counts: Dict[str, int] = model.get("format_error_signature_counts", {}) or {}
    for row in recent:
        for k, v in (row.get("format_error_signatures") or {}).items():
            sig_counts[k] = int(sig_counts.get(k, 0)) + int(v)
    model["format_error_signature_counts"] = sig_counts
    return model


def main() -> None:
    ap = argparse.ArgumentParser(description="Self-tune agent concurrency from run outcomes")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    stats = score_run(run_dir)

    model = load_json(
        STATE_PATH,
        {
            "recommended_agents_per_console": 2,
            "avg_timeout_rate_recent": 0.0,
            "avg_format_error_rate_recent": 0.0,
            "preferred_launch_format": "raw_GEMINI_cmd_exec",
            "format_error_signature_counts": {},
            "history": [],
        },
    )
    model = update_model(model, stats)
    save_json(STATE_PATH, model)

    print(json.dumps({"ok": True, "run": stats, "model": model}, indent=2))


if __name__ == "__main__":
    main()
