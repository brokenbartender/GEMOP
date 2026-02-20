import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[2]))
STATE_DIR = REPO_ROOT / "ramshare" / "state"
MEMORY_DIR = REPO_ROOT / "ramshare" / "evidence" / "memory"
HISTORY_PATH = STATE_DIR / "product_history.json"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def normalize(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return " ".join(cleaned.split())


def load_history(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"entries": []}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"entries": []}


def save_history(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_and_record_trend(trend: str, window_days: int = 30) -> Tuple[bool, Dict[str, Any]]:
    trend_norm = normalize(trend)
    history = load_history(HISTORY_PATH)
    entries: List[Dict[str, Any]] = history.get("entries") or []
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=max(window_days, 1))

    duplicate = False
    recent_match: Dict[str, Any] = {}
    for e in entries:
        if normalize(str(e.get("trend") or "")) != trend_norm:
            continue
        try:
            ts = dt.datetime.fromisoformat(str(e.get("ts")))
        except Exception:
            continue
        if ts >= cutoff:
            duplicate = True
            recent_match = e
            break

    decision = {
        "ts": now_iso(),
        "trend": trend,
        "trend_norm": trend_norm,
        "window_days": window_days,
        "duplicate": duplicate,
        "recent_match": recent_match,
    }

    if not duplicate:
        entries.append({"ts": decision["ts"], "trend": trend, "trend_norm": trend_norm})
        history["entries"] = entries[-2000:]
        save_history(HISTORY_PATH, history)

    return duplicate, decision


def pick_trend(job: Dict[str, Any]) -> str:
    if isinstance(job.get("input_data"), str) and job["input_data"].strip():
        return job["input_data"].strip()
    inputs = job.get("inputs") or {}
    for key in ("trend", "keyword", "concept"):
        v = inputs.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def pick_window(job: Dict[str, Any]) -> int:
    policy = job.get("policy") or {}
    try:
        return int(policy.get("memory_window_days") or 30)
    except Exception:
        return 30


def main() -> None:
    ap = argparse.ArgumentParser(description="Librarian skill: dedupe trend concepts using local memory")
    ap.add_argument("job_file", help="Path to librarian job json")
    args = ap.parse_args()

    job_path = Path(args.job_file)
    job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    trend = pick_trend(job)
    if not trend:
        raise SystemExit("Missing trend in job (input_data or inputs.trend)")

    duplicate, decision = check_and_record_trend(trend, pick_window(job))
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    out = MEMORY_DIR / f"librarian_{now_stamp()}.json"
    out.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    if duplicate:
        print(f"Librarian duplicate: {trend}")
        return
    print(f"Librarian allowed: {trend}")


if __name__ == "__main__":
    main()
