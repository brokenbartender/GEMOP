from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


CONSTRAINT_RE = re.compile(
    r"(?i)\b(must|must not|should|should not|required|requirement|constraint|never|always|exactly|at least|without)\b"
)
FILE_RE = re.compile(r"(?i)\b[\w\-./\\]+\.(py|ps1|md|json|toml|yaml|yml|txt)\b")
COMMAND_HINT_RE = re.compile(r"(?i)\b(pytest|python|pwsh|powershell|npm|npx|node|ruff|mypy|git)\b")


def _safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _dedupe_keep_order(rows: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        norm = " ".join((row or "").split()).strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
        if len(out) >= limit:
            break
    return out


def _extract_constraints(prompt: str, limit: int = 24) -> list[str]:
    rows: list[str] = []
    for ln in prompt.splitlines():
        s = ln.strip()
        if not s:
            continue
        if CONSTRAINT_RE.search(s):
            rows.append(s.lstrip("-*0123456789. ").strip())
    if len(rows) < limit:
        for sent in re.split(r"(?<=[.!?])\s+", prompt):
            s = sent.strip()
            if s and CONSTRAINT_RE.search(s):
                rows.append(s)
    return _dedupe_keep_order(rows, limit)


def _extract_deliverables(prompt: str, limit: int = 20) -> list[str]:
    rows: list[str] = []
    for m in re.finditer(FILE_RE, prompt):
        rows.append(f"Touch or create `{m.group(0)}` as needed.")
    for ln in prompt.splitlines():
        s = ln.strip()
        if not s:
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", ln) and re.search(r"(?i)\b(add|create|build|implement|fix|update|write|test)\b", s):
            rows.append(s.lstrip("-*0123456789. ").strip())
    out = _dedupe_keep_order(rows, limit)
    if out:
        return out
    return ["Deliver repo-grounded output that satisfies the request."]


def _extract_verification(prompt: str, limit: int = 12) -> list[str]:
    rows: list[str] = []
    for ln in prompt.splitlines():
        s = ln.strip().strip("`")
        if not s:
            continue
        if COMMAND_HINT_RE.search(s):
            rows.append(s)
    out = _dedupe_keep_order(rows, limit)
    if out:
        return out
    return ["python -m pytest -q tests"]


def _objective(prompt: str) -> str:
    txt = " ".join(prompt.split()).strip()
    if not txt:
        return "No prompt provided."
    parts = re.split(r"(?<=[.!?])\s+", txt)
    first = (parts[0] or txt).strip()
    return first[:280]


def _read_event_horizon(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "state" / "event_horizon.json"
    try:
        if p.exists():
            obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return {}


def build_contract(prompt: str, run_dir: Path, *, pattern: str, round_n: int, max_rounds: int) -> dict[str, Any]:
    constraints = _extract_constraints(prompt)
    deliverables = _extract_deliverables(prompt)
    verification = _extract_verification(prompt)
    eh = _read_event_horizon(run_dir)
    mass = None
    split_required = False
    try:
        if eh:
            mass = float(eh.get("mass")) if eh.get("mass") is not None else None
            split_required = bool(eh.get("split_required"))
    except Exception:
        mass = None
        split_required = False

    return {
        "schema_version": 1,
        "generated_at": time.time(),
        "pattern": str(pattern or "").strip().lower(),
        "round": int(round_n),
        "max_rounds": int(max_rounds),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8", errors="ignore")).hexdigest() if prompt else "",
        "objective": _objective(prompt),
        "constraints": constraints,
        "deliverables": deliverables,
        "verification": verification,
        "event_horizon": {
            "mass": mass,
            "split_required": split_required,
        },
    }


def _contract_markdown(contract: dict[str, Any]) -> str:
    lines = [
        "# Task Contract",
        "",
        f"- pattern: {contract.get('pattern')}",
        f"- round: {contract.get('round')}",
        f"- max_rounds: {contract.get('max_rounds')}",
        f"- objective: {contract.get('objective')}",
        "",
        "## Constraints",
    ]
    for row in contract.get("constraints", []):
        lines.append(f"- {row}")
    if not contract.get("constraints"):
        lines.append("- none detected")

    lines.extend(["", "## Deliverables"])
    for row in contract.get("deliverables", []):
        lines.append(f"- {row}")
    if not contract.get("deliverables"):
        lines.append("- none detected")

    lines.extend(["", "## Verification"])
    for row in contract.get("verification", []):
        lines.append(f"- {row}")
    if not contract.get("verification"):
        lines.append("- none detected")

    eh = contract.get("event_horizon") if isinstance(contract.get("event_horizon"), dict) else {}
    lines.extend(
        [
            "",
            "## Event Horizon",
            f"- mass: {eh.get('mass')}",
            f"- split_required: {eh.get('split_required')}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_outputs(run_dir: Path, contract: dict[str, Any], round_n: int) -> dict[str, str]:
    state = run_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    out_json = state / "task_contract.json"
    out_md = state / "task_contract.md"
    out_json.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    out_md.write_text(_contract_markdown(contract), encoding="utf-8")
    paths = {"json": str(out_json), "md": str(out_md)}

    if round_n > 0:
        rj = state / f"task_contract_round{round_n}.json"
        rm = state / f"task_contract_round{round_n}.md"
        rj.write_text(json.dumps(contract, indent=2), encoding="utf-8")
        rm.write_text(_contract_markdown(contract), encoding="utf-8")
        paths["round_json"] = str(rj)
        paths["round_md"] = str(rm)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a canonical task contract for the run.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--prompt-file", default="")
    ap.add_argument("--pattern", default="debate")
    ap.add_argument("--round", dest="round_n", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=1)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    prompt = str(args.prompt or "")
    if args.prompt_file and not prompt:
        prompt = _safe_text(Path(args.prompt_file))

    contract = build_contract(
        prompt,
        run_dir,
        pattern=str(args.pattern or ""),
        round_n=int(args.round_n),
        max_rounds=int(args.max_rounds),
    )
    paths = _write_outputs(run_dir, contract, int(args.round_n))
    out = {
        "ok": True,
        "paths": paths,
        "constraints": len(contract.get("constraints", [])),
        "deliverables": len(contract.get("deliverables", [])),
        "verification": len(contract.get("verification", [])),
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
