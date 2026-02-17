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
        norm = normalize(obj, agent=i, round_n=round_n)
        norm["source_path"] = str(src)
        (out_dir / f"round{round_n}_agent{i}.json").write_text(json.dumps(norm, indent=2), encoding="utf-8")
        extracted += 1

    report = {
        "ok": (not missing) or (not args.require),
        "round": round_n,
        "agent_count": agent_count,
        "extracted": extracted,
        "missing": missing,
        "generated_at": time.time(),
    }
    (state_dir / f"decisions_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
