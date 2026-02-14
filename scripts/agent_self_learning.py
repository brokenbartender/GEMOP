from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = REPO_ROOT / ".agent-jobs"
STATE_DIR = REPO_ROOT / "ramshare" / "state" / "learning"
SCORES_PATH = STATE_DIR / "agent_quality_scores.jsonl"
RUN_SUMMARY_PATH = STATE_DIR / "run_summaries.jsonl"
MODEL_PATH = STATE_DIR / "quality_model.json"
LESSONS_PATH = REPO_ROOT / "ramshare" / "learning" / "memory" / "lessons.md"
TASKS_DIR = REPO_ROOT / "ramshare" / "notes" / "distilled" / "learning_tasks"
SCRIPT_FORMAT_ERROR_PATTERNS = [
    r"is not recognized as an internal or external command",
    r"not recognized as an internal or external command",
    r"provide a task prompt\.",
    r"unexpected token",
    r"parsererror",
    r"the term '.*' is not recognized",
    r"missing argument in parameter list",
]
RUNTIME_TIMEOUT_PATTERNS = [
    r"timed out",
    r"timeoutexpired",
    r"watchdog timeout",
    r"killed .*timeout",
]
RUNTIME_EXCEPTION_PATTERNS = [
    r"traceback \(most recent call last\)",
    r"fatal error",
    r"unhandled exception",
    r"at line:\s*\d+\s*char:\s*\d+",
]


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def list_latest_run(base: Path) -> Path:
    runs = [p for p in base.iterdir() if p.is_dir()]
    if not runs:
        raise SystemExit(f"No run folders found in {base}")
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def count_expected_agents(run_dir: Path) -> int:
    prompts = list(run_dir.glob("prompt*.txt"))
    runners = list(run_dir.glob("run-agent*.ps1"))
    return max(len(prompts), len(runners), 1)


def count_table_rows(text: str) -> int:
    rows = 0
    for ln in text.splitlines():
        if re.match(r"^\|\s*([Pp]\d+|\d+|High|Medium|Low|Critical)\s*\|", ln):
            rows += 1
        # Also accept ranked pipe rows rendered as bullets, e.g. "- 1 | Action | Why | ..."
        elif re.match(r"^\s*[-*]?\s*([Pp]\d+|\d+|High|Medium|Low|Critical)\s*\|", ln):
            rows += 1
    return rows


def score_agent_output(md_path: Path) -> Tuple[int, List[str], Dict[str, Any]]:
    mistakes: List[str] = []
    metrics: Dict[str, Any] = {"exists": md_path.exists(), "chars": 0, "table_rows": 0}
    score = 100

    if not md_path.exists():
        mistakes.append("missing_output")
        return 0, mistakes, metrics

    raw = md_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        # PowerShell redirection often emits UTF-16LE unless explicitly overridden.
        text = raw.decode("utf-16", errors="ignore")
    # Defensive normalization for mixed/invalid encodings containing null bytes.
    text = text.replace("\x00", "")
    text_l = text.lower()
    chars = len(text)
    rows = count_table_rows(text)
    metrics["chars"] = chars
    metrics["table_rows"] = rows

    if chars < 800:
        mistakes.append("too_short")
        score -= 25
    if rows == 0:
        mistakes.append("no_structured_rows")
        score -= 30
    if rows < 5:
        mistakes.append("insufficient_ranked_rows")
        score -= 10
    required_headers = ["priority", "action", "why", "exact files", "verification command"]
    if not all(h in text_l for h in required_headers):
        mistakes.append("missing_contract_headers")
        score -= 20
    if "final output" not in text_l:
        mistakes.append("missing_final_output_block")
        score -= 15
    if ("[completed]" not in text_l) and ("completion_marker" not in text_l) and ("complete" not in text_l):
        mistakes.append("missing_completion_marker")
        score -= 15
    if not re.search(r"[A-Za-z]:\\\\[^\s|]+|[A-Za-z0-9_./\\\\-]+\.(py|ps1|json|md|toml)", text):
        mistakes.append("missing_file_citations")
        score -= 20
    if (
        "Repo/File Context" not in text
        and "Primary Files" not in text
        and "Exact files" not in text
    ):
        mistakes.append("missing_repo_context")
        score -= 15
    if "TODO" in text or "TBD" in text:
        mistakes.append("contains_todo_placeholders")
        score -= 10
    if "C:\\Gemini" in text and str(REPO_ROOT) not in text:
        mistakes.append("hardcoded_path_bias")
        score -= 5

    score = max(0, min(100, score))
    return score, mistakes, metrics


def read_text_best_effort(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return raw.decode(enc, errors="ignore").replace("\x00", "")
        except Exception:
            continue
    return ""


def score_agent_logs(run_dir: Path, agent_name: str) -> Tuple[int, List[str], Dict[str, Any]]:
    mistakes: List[str] = []
    metrics: Dict[str, Any] = {"stderr_chars": 0, "log_chars": 0, "format_error_hits": 0}
    penalty = 0

    stderr_path = run_dir / f"run-{agent_name}.stderr.log"
    log_path = run_dir / f"{agent_name}.log"
    stderr_text = read_text_best_effort(stderr_path)
    log_text = read_text_best_effort(log_path)
    full = f"{stderr_text}\n{log_text}".lower()

    metrics["stderr_chars"] = len(stderr_text)
    metrics["log_chars"] = len(log_text)

    format_hits = 0
    for pat in SCRIPT_FORMAT_ERROR_PATTERNS:
        if re.search(pat, full, flags=re.IGNORECASE):
            format_hits += 1
    metrics["format_error_hits"] = format_hits

    if format_hits > 0:
        mistakes.append("script_format_error")
        penalty += min(35, 10 + (format_hits * 5))
    if any(re.search(pat, full, flags=re.IGNORECASE) for pat in RUNTIME_TIMEOUT_PATTERNS):
        mistakes.append("runtime_timeout")
        penalty += 15
    if any(re.search(pat, full, flags=re.IGNORECASE) for pat in RUNTIME_EXCEPTION_PATTERNS):
        # Ignore PowerShell NativeCommandError noise from successful Gemini stdout/stderr piping.
        if "nativecommanderror" not in full:
            mistakes.append("runtime_exception")
            penalty += 10
    if "no output" in full and "agent" in full:
        mistakes.append("runtime_no_output")
        penalty += 10

    return penalty, mistakes, metrics


def extract_council_protocol_issues(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "bus" / "messages.jsonl"
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: List[Dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue

    if not rows:
        return []

    verify = 0
    challenge = 0
    for r in rows:
        intent = str(r.get("intent", "")).lower()
        status = str(r.get("status", "")).lower()
        payload = r.get("payload") or {}
        decision = ""
        if isinstance(payload, dict):
            decision = str(payload.get("decision", "")).lower()
            message = f"{payload.get('message','')} {payload.get('content','')}".lower()
        else:
            message = str(payload).lower()
        if intent == "verify" or status == "verified" or "verified" in message or decision == "approve":
            verify += 1
        if intent == "challenge" or status == "challenged" or "challenged" in message or decision == "reject":
            challenge += 1

    if verify == 0 and challenge == 0:
        # Fallback to markdown summaries when agents didn't publish structured bus events.
        for md in sorted(run_dir.glob("agent*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore").lower()
            v_match = re.findall(r"verified_count\s*[:=]\s*(\d+)", text)
            c_match = re.findall(r"challenged_count\s*[:=]\s*(\d+)", text)
            if v_match or c_match:
                verify += sum(int(x) for x in v_match)
                challenge += sum(int(x) for x in c_match)
            else:
                verify += len(re.findall(r"\bverified\s*[:\-]", text))
                challenge += len(re.findall(r"\bchallenged\s*[:\-]", text))

    issues: List[Dict[str, Any]] = []
    if verify == 0 or challenge == 0:
        issues.append(
            {
                "agent": "council",
                "score": 69,
                "mistakes": ["council_protocol_not_followed"],
                "metrics": {
                    "verify_count": verify,
                    "challenge_count": challenge,
                    "messages": len(rows),
                },
                "path": str(path),
            }
        )
    return issues


def load_model(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "updated_at": now_iso(),
            "mistake_counts": {},
            "prompt_hints": [],
        }
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_model(path: Path, model: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2), encoding="utf-8")


def update_model_from_scores(model: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = model.get("mistake_counts") or {}
    if not isinstance(counts, dict):
        counts = {}

    for row in rows:
        for mistake in row.get("mistakes", []):
            counts[mistake] = int(counts.get(mistake, 0)) + 1

    sorted_mistakes = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    hints: List[str] = []
    top = [name for name, _ in sorted_mistakes[:5]]
    if "missing_output" in top:
        hints.append("Require explicit final output block and completion marker.")
    if "no_structured_rows" in top:
        hints.append("Force strict table output with ranked rows.")
    if "missing_contract_headers" in top:
        hints.append("Table must include: Priority|Action|Why|Exact files|Verification command.")
    if "missing_file_citations" in top:
        hints.append("Every ranked row must cite concrete file paths.")
    if "missing_completion_marker" in top:
        hints.append("End response with explicit completion marker.")
    if "missing_repo_context" in top:
        hints.append("Require file-path citations for every recommendation.")
    if "too_short" in top:
        hints.append("Enforce minimum depth and coverage per section.")
    if "contains_todo_placeholders" in top:
        hints.append("Disallow TODO/TBD placeholders in final responses.")

    model["updated_at"] = now_iso()
    model["mistake_counts"] = counts
    model["prompt_hints"] = hints
    return model


def append_lessons(lessons_path: Path, run_id: str, rows: List[Dict[str, Any]], threshold: int) -> int:
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    if not lessons_path.exists():
        lessons_path.write_text("# Lessons Learned (Tactical Memory)\n\n", encoding="utf-8")

    additions: List[str] = []
    date = dt.datetime.now().date().isoformat()
    for row in rows:
        if int(row.get("score", 0)) >= threshold:
            continue
        mistakes = ", ".join(row.get("mistakes", [])) or "quality_drop"
        additions.append(
            f"- {date} | Trigger: {run_id}/{row['agent']} score={row['score']} | "
            f"Lesson: prevent {mistakes} using stricter output contracts | "
            f"Action: apply model prompt hints and rerun section."
        )

    if additions:
        with lessons_path.open("a", encoding="utf-8") as f:
            f.write("\n")
            for line in additions:
                f.write(line + "\n")
    return len(additions)


def create_learning_tasks(tasks_dir: Path, run_id: str, rows: List[Dict[str, Any]], threshold: int) -> int:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for row in rows:
        if int(row.get("score", 0)) >= threshold:
            continue
        path = tasks_dir / f"learning_fix_{run_id}_{row['agent']}.md"
        mistakes = row.get("mistakes", [])
        content = [
            f"# Learning Fix Task: {row['agent']} ({run_id})",
            "",
            f"- Score: {row['score']}",
            f"- Mistakes: {', '.join(mistakes) if mistakes else 'n/a'}",
            "",
            "## Required Improvements",
            "- Produce strict ranked markdown table output.",
            "- Cite concrete repo file paths for each recommendation.",
            "- Eliminate placeholders and incomplete bullets.",
            "- Include explicit final output block and completion marker.",
            "",
            "## Acceptance Criteria (Machine-checkable)",
            "- Contains table headers: Priority | Action | Why | Exact files | Verification command.",
            "- Contains at least 5 ranked rows.",
            "- Contains at least one valid file citation path.",
            "- Contains completion marker.",
            "- Re-score >= threshold.",
            "",
            "## Verification Commands",
            f"- python scripts/agent_self_learning.py score-run --run-dir .agent-jobs/{run_id}",
        ]
        path.write_text("\n".join(content) + "\n", encoding="utf-8")
        count += 1
    return count


def upsert_run_summary(path: Path, summary: Dict[str, Any]) -> None:
    rows: List[Dict[str, Any]] = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    by_run: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("run_id", "")).strip()
        if rid:
            by_run[rid] = r
    by_run[str(summary.get("run_id"))] = summary
    ordered = sorted(by_run.values(), key=lambda r: str(r.get("ts", "")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in ordered[-200:]:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def run_score(run_dir: Path) -> Dict[str, Any]:
    run_id = run_dir.name
    expected = count_expected_agents(run_dir)
    rows: List[Dict[str, Any]] = []
    for idx in range(1, expected + 1):
        agent = f"agent{idx}"
        md = run_dir / f"{agent}.md"
        score, mistakes, metrics = score_agent_output(md)
        penalty, log_mistakes, log_metrics = score_agent_logs(run_dir, agent)
        score = max(0, score - penalty)
        mistakes = list(dict.fromkeys(mistakes + log_mistakes))
        metrics.update(log_metrics)
        row = {
            "ts": now_iso(),
            "run_id": run_id,
            "agent": agent,
            "score": score,
            "mistakes": mistakes,
            "metrics": metrics,
            "path": str(md),
        }
        rows.append(row)

    rows.extend(extract_council_protocol_issues(run_dir))
    for row in rows:
        append_jsonl(SCORES_PATH, row)

    avg = round(sum(r["score"] for r in rows) / max(1, len(rows)), 2)
    summary = {
        "ts": now_iso(),
        "run_id": run_id,
        "agents_expected": expected,
        "avg_score": avg,
        "min_score": min(r["score"] for r in rows),
        "max_score": max(r["score"] for r in rows),
        "failing_agents": [r["agent"] for r in rows if r["score"] < 70],
    }
    upsert_run_summary(RUN_SUMMARY_PATH, summary)
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Agent output scoring + self-learning loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_score = sub.add_parser("score-run", help="Score one run directory")
    s_score.add_argument("--run-dir", default="")

    s_learn = sub.add_parser("learn", help="Generate lessons/model updates from latest scores")
    s_learn.add_argument("--run-dir", default="")
    s_learn.add_argument("--threshold", type=int, default=70)

    s_close = sub.add_parser("close-loop", help="Score + learn + create fix tasks")
    s_close.add_argument("--run-dir", default="")
    s_close.add_argument("--threshold", type=int, default=70)

    return ap.parse_args()


def resolve_run_dir(run_dir_arg: str) -> Path:
    if run_dir_arg.strip():
        return Path(run_dir_arg).resolve()
    return list_latest_run(DEFAULT_RUN_DIR)


def main() -> None:
    args = parse_args()
    run_dir = resolve_run_dir(getattr(args, "run_dir", ""))
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")

    if args.cmd == "score-run":
        out = run_score(run_dir)
        print(json.dumps(out["summary"], indent=2))
        return

    if args.cmd in ("learn", "close-loop"):
        scored = run_score(run_dir)
        rows = scored["rows"]
        run_id = run_dir.name
        model = load_model(MODEL_PATH)
        model = update_model_from_scores(model, rows)
        save_model(MODEL_PATH, model)
        lessons_added = append_lessons(LESSONS_PATH, run_id, rows, threshold=int(args.threshold))
        tasks_added = create_learning_tasks(TASKS_DIR, run_id, rows, threshold=int(args.threshold))
        out = {
            "run_id": run_id,
            "avg_score": scored["summary"]["avg_score"],
            "lessons_added": lessons_added,
            "tasks_added": tasks_added,
            "model_path": str(MODEL_PATH),
            "lessons_path": str(LESSONS_PATH),
            "tasks_dir": str(TASKS_DIR),
            "prompt_hints": model.get("prompt_hints", []),
        }
        print(json.dumps(out, indent=2))
        return


if __name__ == "__main__":
    main()
