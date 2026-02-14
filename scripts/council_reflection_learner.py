from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / "ramshare" / "state" / "learning"
COUNCIL_MODEL_PATH = STATE_DIR / "council_model.json"
LESSONS_PATH = REPO_ROOT / "ramshare" / "learning" / "memory" / "lessons.md"


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


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
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


def classify_issue(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["parsererror", "unexpected token", "not recognized as an internal or external command"]):
        return "script_format_error"
    if any(k in t for k in ["timeout", "hung", "stalled"]):
        return "timeout_or_stall"
    if any(k in t for k in ["no output", "missing output", "empty"]):
        return "missing_output"
    if any(k in t for k in ["path", "hardcoded", "wrong repo", "file not found"]):
        return "path_context_error"
    if any(k in t for k in ["conflict", "merge", "race", "lock"]):
        return "coordination_conflict"
    return "general_quality_issue"


def build_manifesto(top_issues: List[str]) -> Dict[str, str]:
    stop: List[str] = []
    start: List[str] = []
    prompt_snippets: List[str] = []

    for i in top_issues:
        if i == "script_format_error":
            stop.append("Launching ad-hoc command formats without parse checks.")
            start.append("Normalize launch scripts + pre-parse validate before execution.")
            prompt_snippets.append("Use strict PowerShell-safe quoting and explicit raw Gemini path.")
        elif i == "timeout_or_stall":
            stop.append("Running long loops without progress checkpoints.")
            start.append("Emit progress heartbeat every step and abort on stale loops.")
            prompt_snippets.append("Every plan step must include a timeout and success signal.")
        elif i == "missing_output":
            stop.append("Marking work done without verifiable outputs.")
            start.append("Require explicit output artifacts and completion markers.")
            prompt_snippets.append("Respond with strict output schema and file paths.")
        elif i == "path_context_error":
            stop.append("Using ambiguous or hardcoded paths across nodes.")
            start.append("Resolve and cite absolute repo paths in every result.")
            prompt_snippets.append("All recommendations must reference real repo file paths.")
        elif i == "coordination_conflict":
            stop.append("Parallel workers writing conflicting changes without arbitration.")
            start.append("Use council bus arbitration before write/commit phases.")
            prompt_snippets.append("Before final write, request council verify/challenge round.")
        elif i == "council_protocol_not_followed":
            stop.append("Skipping verify/challenge protocol in council rounds.")
            start.append("Require at least one verify and one challenge before final output.")
            prompt_snippets.append("Use round-robin with explicit VERIFIED or CHALLENGED response per agent.")
        else:
            stop.append("Low-signal generic updates.")
            start.append("Provide concise, testable, evidence-based updates.")
            prompt_snippets.append("State assumptions, evidence, and acceptance criteria.")

    return {
        "stop_doing": " ".join(dict.fromkeys(stop))[:500],
        "start_doing": " ".join(dict.fromkeys(start))[:500],
        "updated_prompt_snippet": " ".join(dict.fromkeys(prompt_snippets))[:700],
    }


def append_lessons(run_id: str, issue_counts: Dict[str, int]) -> int:
    LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LESSONS_PATH.exists():
        LESSONS_PATH.write_text("# Lessons Learned (Tactical Memory)\n\n", encoding="utf-8")

    lines = []
    for issue, cnt in sorted(issue_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        lines.append(
            f"- Council {run_id}: {issue} observed {cnt}x | Action: enforce manifesto delta and verify via council ack."
        )
    if not lines:
        return 0

    with LESSONS_PATH.open("a", encoding="utf-8") as f:
        f.write("\n")
        for ln in lines:
            f.write(ln + "\n")
    return len(lines)


def reflect(run_dir: Path) -> Dict[str, Any]:
    msg_path = run_dir / "bus" / "messages.jsonl"
    rows = load_jsonl(msg_path)
    if not rows:
        return {"ok": False, "reason": "no_bus_messages", "run_id": run_dir.name}

    challenge_count = 0
    verify_count = 0
    issues = Counter()

    for r in rows:
        intent = str(r.get("intent", "")).lower()
        status = str(r.get("status", "")).lower()
        if intent == "lifecycle":
            continue
        payload = r.get("payload") or {}
        issue_code = ""
        decision = ""
        msg = ""
        if isinstance(payload, dict):
            issue_code = str(payload.get("issue_code", "")).strip().lower()
            decision = str(payload.get("decision", "")).strip().lower()
            msg = str(payload.get("message", "")) + " " + str(payload.get("content", ""))
        else:
            msg = str(payload)
        raw = f"{intent} {status} {msg}".strip()
        raw_l = raw.lower()
        if intent == "challenge" or ("challenged" in raw_l) or (status == "challenged") or decision == "reject":
            challenge_count += 1
        if intent == "verify" or ("verified" in raw_l) or (status == "verified") or decision == "approve":
            verify_count += 1
        if issue_code:
            issues[issue_code] += 1
        else:
            issues[classify_issue(raw)] += 1

    # Fallback: if bus doesn't include explicit verify/challenge events,
    # infer protocol participation from agent markdown outputs.
    if verify_count == 0 and challenge_count == 0:
        for md in sorted(run_dir.glob("agent*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore").lower()
            v_match = re.findall(r"verified_count\s*[:=]\s*(\d+)", text)
            c_match = re.findall(r"challenged_count\s*[:=]\s*(\d+)", text)
            if v_match or c_match:
                verify_count += sum(int(x) for x in v_match)
                challenge_count += sum(int(x) for x in c_match)
                continue
            # Fallback for unstructured transcripts: explicit protocol tokens only.
            verify_count += len(re.findall(r"\bverified\s*[:\-]", text))
            challenge_count += len(re.findall(r"\bchallenged\s*[:\-]", text))

    # Enforce council protocol quality: at least one verify + one challenge.
    if verify_count == 0 or challenge_count == 0:
        issues["council_protocol_not_followed"] += 1

    top_issues = [k for k, _ in issues.most_common(3)]
    manifesto = build_manifesto(top_issues)

    model = load_json(
        COUNCIL_MODEL_PATH,
        {
            "runs": [],
            "issue_counts": {},
            "current_manifesto": {},
            "council_protocol": {
                "round_robin": True,
                "require_verify_or_challenge": True,
                "max_rounds": 3,
            },
        },
    )

    global_counts = model.get("issue_counts", {}) or {}
    for k, v in issues.items():
        global_counts[k] = int(global_counts.get(k, 0)) + int(v)
    model["issue_counts"] = global_counts
    model["current_manifesto"] = manifesto
    model.setdefault("runs", []).append(
        {
            "run_id": run_dir.name,
            "messages": len(rows),
            "verified": verify_count,
            "challenged": challenge_count,
            "top_issues": top_issues,
        }
    )
    model["runs"] = model["runs"][-30:]
    save_json(COUNCIL_MODEL_PATH, model)

    manifest_path = run_dir / "council-manifesto.json"
    save_json(manifest_path, manifesto)

    lessons_added = append_lessons(run_dir.name, dict(issues))

    return {
        "ok": True,
        "run_id": run_dir.name,
        "messages": len(rows),
        "verified": verify_count,
        "challenged": challenge_count,
        "top_issues": top_issues,
        "manifesto_path": str(manifest_path),
        "council_model_path": str(COUNCIL_MODEL_PATH),
        "lessons_added": lessons_added,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Learn from council bus discussions and update manifesto")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    out = reflect(Path(args.run_dir).resolve())
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
