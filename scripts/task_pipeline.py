from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from phase6_schema import TASK_CONTRACT_SCHEMA_VERSION, TASK_PIPELINE_SCHEMA_VERSION, TASK_PIPELINE_STAGES


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return {}


def _stage_for_round(pattern: str, round_n: int) -> str:
    pat = (pattern or "").strip().lower()
    rn = max(1, int(round_n))
    if pat == "debate":
        if rn == 1:
            return "planner"
        if rn == 2:
            return "planner_executor"
        return "executor_verifier"
    if pat == "single":
        return "executor_verifier"
    if rn == 1:
        return "planner"
    return "executor_verifier"


def _plan_block(stage: str, contract: dict[str, Any]) -> dict[str, Any]:
    constraints = [str(x) for x in contract.get("constraints", []) if str(x).strip()][:8]
    deliverables = [str(x) for x in contract.get("deliverables", []) if str(x).strip()][:8]
    verification = [str(x) for x in contract.get("verification", []) if str(x).strip()][:8]

    planner_goal = "Map objective to minimal scoped changes and explicit acceptance criteria."
    executor_goal = "Implement only planned changes with repo-grounded diffs."
    verifier_goal = "Run strict verification and report failures with concrete remediation."

    if stage == "planner":
        planner_goal = "Prioritize requirements and settle on one minimal, testable plan."
    elif stage == "planner_executor":
        executor_goal = "Convert planned files into concrete edits while preserving contract constraints."
    elif stage == "executor_verifier":
        verifier_goal = "Fail closed on contract or verification misses before finalizing outputs."

    return {
        "planner": {
            "goal": planner_goal,
            "required": ["DECISION_JSON summary/files/commands", "explicit risks"],
            "inputs": constraints if constraints else ["objective"],
        },
        "executor": {
            "goal": executor_goal,
            "required": ["git-applyable diffs for scoped files", "verification commands"],
            "inputs": deliverables if deliverables else ["planned file list"],
        },
        "verifier": {
            "goal": verifier_goal,
            "required": ["strict command results", "failed checks and fixes"],
            "inputs": verification if verification else ["python -m pytest -q tests"],
        },
    }


def _prompt_addendum(stage: str, contract: dict[str, Any], prompt: str) -> str:
    objective = str(contract.get("objective") or "").strip() or "No objective provided."
    constraints = [str(x) for x in contract.get("constraints", []) if str(x).strip()][:5]
    verification = [str(x) for x in contract.get("verification", []) if str(x).strip()][:4]

    lines = [
        "[TASK PIPELINE DIRECTIVE]",
        f"stage: {stage}",
        f"objective: {objective}",
        "non_negotiables:",
    ]
    if constraints:
        for row in constraints:
            lines.append(f"- {row}")
    else:
        lines.append("- Keep changes minimal and repo-grounded.")
    lines.append("verification_focus:")
    if verification:
        for row in verification:
            lines.append(f"- {row}")
    else:
        lines.append("- python -m pytest -q tests")
    lines.append(f"prompt_len: {len(prompt or '')}")
    return "\n".join(lines).strip()


def build_pipeline(run_dir: Path, pattern: str, round_n: int, prompt: str) -> dict[str, Any]:
    state = run_dir / "state"
    contract = _read_json(state / "task_contract.json")
    if int(contract.get("schema_version", -1)) != TASK_CONTRACT_SCHEMA_VERSION:
        raise ValueError("missing_or_invalid_task_contract")

    stage = _stage_for_round(pattern, round_n)
    if stage not in TASK_PIPELINE_STAGES:
        raise ValueError("invalid_task_pipeline_stage")
    stage_focus = _plan_block(stage, contract)
    addendum = _prompt_addendum(stage, contract, prompt)

    return {
        "schema_version": TASK_PIPELINE_SCHEMA_VERSION,
        "generated_at": time.time(),
        "pattern": str(pattern or "").strip().lower(),
        "round": int(round_n),
        "stage": stage,
        "stage_focus": stage_focus,
        "prompt_addendum": addendum,
        "contract_objective": contract.get("objective"),
    }


def _markdown(pipeline: dict[str, Any]) -> str:
    sf = pipeline.get("stage_focus") if isinstance(pipeline.get("stage_focus"), dict) else {}
    lines = [
        "# Task Pipeline",
        "",
        f"- pattern: {pipeline.get('pattern')}",
        f"- round: {pipeline.get('round')}",
        f"- stage: {pipeline.get('stage')}",
        f"- contract_objective: {pipeline.get('contract_objective')}",
        "",
        "## Planner",
        f"- goal: {((sf.get('planner') or {}).get('goal'))}",
    ]
    for row in ((sf.get("planner") or {}).get("required") or []):
        lines.append(f"- required: {row}")

    lines.extend(["", "## Executor", f"- goal: {((sf.get('executor') or {}).get('goal'))}"])
    for row in ((sf.get("executor") or {}).get("required") or []):
        lines.append(f"- required: {row}")

    lines.extend(["", "## Verifier", f"- goal: {((sf.get('verifier') or {}).get('goal'))}"])
    for row in ((sf.get("verifier") or {}).get("required") or []):
        lines.append(f"- required: {row}")

    lines.extend(["", "## Prompt Addendum", "", str(pipeline.get("prompt_addendum") or "")])
    return "\n".join(lines).rstrip() + "\n"


def write_pipeline(run_dir: Path, pipeline: dict[str, Any], round_n: int) -> dict[str, str]:
    state = run_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    pj = state / f"task_pipeline_round{round_n}.json"
    pm = state / f"task_pipeline_round{round_n}.md"
    lj = state / "task_pipeline_latest.json"
    lm = state / "task_pipeline_latest.md"
    txt = json.dumps(pipeline, indent=2)
    md = _markdown(pipeline)
    pj.write_text(txt, encoding="utf-8")
    pm.write_text(md, encoding="utf-8")
    lj.write_text(txt, encoding="utf-8")
    lm.write_text(md, encoding="utf-8")
    return {"json": str(pj), "md": str(pm), "latest_json": str(lj), "latest_md": str(lm)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build round planner/executor/verifier pipeline artifact.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", dest="round_n", type=int, required=True)
    ap.add_argument("--pattern", default="debate")
    ap.add_argument("--prompt", default="")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    try:
        pipeline = build_pipeline(run_dir, str(args.pattern or ""), int(args.round_n), str(args.prompt or ""))
        paths = write_pipeline(run_dir, pipeline, int(args.round_n))
        print(json.dumps({"ok": True, "paths": paths, "stage": pipeline.get("stage"), "prompt_addendum": pipeline.get("prompt_addendum")}, separators=(",", ":")))
        raise SystemExit(0)
    except Exception as ex:
        print(json.dumps({"ok": False, "error": str(ex), "round": int(args.round_n)}, separators=(",", ":")))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
