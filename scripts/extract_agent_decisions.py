from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


DECISION_FENCE_RE = re.compile(r"```json\s+DECISION_JSON\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)
GENERIC_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def try_parse_json(blob: str) -> dict[str, Any] | None:
    blob = (blob or "").strip()
    if not blob:
        return None
    try:
        obj = json.loads(blob)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def extract_decision(md: str) -> dict[str, Any] | None:
    # Prefer an explicitly labeled fence.
    m = DECISION_FENCE_RE.search(md or "")
    if m:
        return try_parse_json(m.group(1))
    # Fallback: try the first JSON fence that looks like the schema.
    for m2 in GENERIC_JSON_FENCE_RE.finditer(md or ""):
        obj = try_parse_json(m2.group(1))
        if not obj:
            continue
        if any(k in obj for k in ("files", "commands", "summary", "plan")):
            return obj
    return None


def normalize(obj: dict[str, Any], *, agent: int, round_n: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["agent"] = int(agent)
    out["round"] = int(round_n)
    out["summary"] = str(obj.get("summary") or obj.get("plan") or "").strip()
    out["files"] = [str(x) for x in (obj.get("files") or []) if str(x).strip()]
    out["commands"] = [str(x) for x in (obj.get("commands") or []) if str(x).strip()]
    out["risks"] = [str(x) for x in (obj.get("risks") or []) if str(x).strip()]
    try:
        c = float(obj.get("confidence") or 0)
        out["confidence"] = max(0.0, min(1.0, c))
    except Exception:
        out["confidence"] = 0.0
    out["raw"] = obj
    out["extracted_at"] = time.time()
    return out


def _is_suspicious_path(p: str) -> bool:
    s = (p or "").strip()
    if not s:
        return True
    # Disallow absolute paths and drive letters (grounding).
    if s.startswith(("/", "\\")):
        return True
    if re.match(r"^[a-zA-Z]:[\\/]", s):
        return True
    # Disallow parent traversal.
    if ".." in s.replace("\\", "/").split("/"):
        return True
    return False


def validate_decision(obj: dict[str, Any], *, round_n: int) -> list[str]:
    """
    "Atomic agent" reliability:
    - Strict-ish JSON contract so orchestration can be deterministic.
    - Treat invalid contract as missing (so contract_repair can fix it).
    """
    errs: list[str] = []

    if not isinstance(obj, dict):
        return ["decision_not_object"]

    summary = obj.get("summary") if "summary" in obj else obj.get("plan")
    if summary is None or (isinstance(summary, str) and not summary.strip()):
        errs.append("missing_summary")
    elif not isinstance(summary, str):
        errs.append("summary_not_string")

    for k in ("files", "commands", "risks"):
        v = obj.get(k, [])
        if v is None:
            v = []
        if not isinstance(v, list):
            errs.append(f"{k}_not_array")
            continue
        for i, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                errs.append(f"{k}[{i}]_not_string")
                continue
            if k == "files" and _is_suspicious_path(item):
                errs.append(f"files[{i}]_invalid_path")

    conf = obj.get("confidence", 0.0)
    if conf is None:
        conf = 0.0
    try:
        c = float(conf)
        if c < 0.0 or c > 1.0:
            errs.append("confidence_out_of_range")
    except Exception:
        errs.append("confidence_not_number")

    # Round-aware expectations (lightweight):
    # - later rounds should be more actionable.
    if int(round_n) >= 2:
        cmds = obj.get("commands") or []
        if not isinstance(cmds, list) or len([x for x in cmds if isinstance(x, str) and x.strip()]) == 0:
            errs.append("missing_commands_round2plus")

    return errs


def _latest_repair_output(run_dir: Path, *, round_n: int, agent: int) -> Path | None:
    repairs = run_dir / "state" / "repairs"
    if not repairs.exists():
        return None
    # Files are named round{r}_agent{i}_repair{attempt}.md
    cand = sorted(repairs.glob(f"round{int(round_n)}_agent{int(agent)}_repair*.md"))
    return cand[-1] if cand else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract structured DECISION_JSON blocks from agent outputs.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--agent-count", type=int, default=0)
    ap.add_argument("--require", action="store_true", help="Fail if any participating agent has no decision JSON.")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))
    state_dir = run_dir / "state"
    out_dir = state_dir / "decisions"
    out_dir.mkdir(parents=True, exist_ok=True)

    agent_count = int(args.agent_count or 0)
    if agent_count <= 0:
        # Infer from prompt*.txt count.
        agent_count = len(list(run_dir.glob("prompt*.txt")))
    agent_count = max(1, agent_count)

    missing: list[int] = []
    invalid: list[int] = []
    invalid_reasons: dict[str, list[str]] = {}
    extracted = 0
    for i in range(1, agent_count + 1):
        md_path = run_dir / f"round{round_n}_agent{i}.md"
        if not md_path.exists():
            md_path = run_dir / f"agent{i}.md"
        md = read_text(md_path)
        obj = extract_decision(md)
        src = md_path
        if not obj:
            rp = _latest_repair_output(run_dir, round_n=round_n, agent=i)
            if rp is not None and rp.exists():
                md2 = read_text(rp)
                obj = extract_decision(md2)
                if obj:
                    src = rp
        if not obj:
            missing.append(i)
            continue
        errs = validate_decision(obj, round_n=round_n)
        if errs:
            invalid.append(i)
            invalid_reasons[str(i)] = errs
        norm = normalize(obj, agent=i, round_n=round_n)
        norm["source_path"] = str(src)
        norm["validation_ok"] = not bool(errs)
        norm["validation_errors"] = errs
        (out_dir / f"round{round_n}_agent{i}.json").write_text(json.dumps(norm, indent=2), encoding="utf-8")
        extracted += 1

    report = {
        "ok": (not missing and not invalid) or (not args.require),
        "round": round_n,
        "agent_count": agent_count,
        "extracted": extracted,
        "missing": missing,
        "invalid": invalid,
        "invalid_reasons": invalid_reasons,
        "generated_at": time.time(),
    }
    (state_dir / f"decisions_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
