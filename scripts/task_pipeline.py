from __future__ import annotations

import argparse
import json
import re
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


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


def _load_supervisor_scores(run_dir: Path, round_n: int) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    sup = _read_json(run_dir / "state" / f"supervisor_round{round_n}.json")
    rows = sup.get("verdicts") if isinstance(sup.get("verdicts"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            aid = int(row.get("agent") or 0)
        except Exception:
            aid = 0
        if aid <= 0:
            continue
        out[aid] = {
            "score": int(row.get("score") or 0),
            "status": str(row.get("status") or ""),
        }
    return out


def _round_output_text(run_dir: Path, round_n: int, agent_id: int) -> str:
    p = run_dir / f"round{round_n}_agent{agent_id}.md"
    if p.exists():
        return _read_text(p)
    return _read_text(run_dir / f"agent{agent_id}.md")


DIFF_RE = re.compile(r"```diff\s*.*?```", flags=re.IGNORECASE | re.DOTALL)
DECISION_RE = re.compile(r"```json\s*DECISION_JSON\s*(\{.*?\})\s*```", flags=re.IGNORECASE | re.DOTALL)


def _signals(text: str) -> dict[str, bool]:
    t = text or ""
    return {
        "has_diff": bool(DIFF_RE.search(t)),
        "has_decision_json": bool(DECISION_RE.search(t)),
        "completed": bool(re.search(r"(?m)^COMPLETED\s*$", t)),
    }


def build_rankings(run_dir: Path, round_n: int, agent_count: int) -> dict[str, Any]:
    sup = _load_supervisor_scores(run_dir, round_n)
    rankings: list[dict[str, Any]] = []

    for aid in range(1, max(1, int(agent_count)) + 1):
        txt = _round_output_text(run_dir, round_n, aid)
        sig = _signals(txt)
        sv = sup.get(aid, {})
        s_score = int(sv.get("score") or 0)
        s_status = str(sv.get("status") or "")

        # Deterministic weighted score in [0, 100]
        score = 0.0
        score += 0.70 * max(0, min(100, s_score))
        if s_status == "OK":
            score += 10.0
        elif s_status == "WARN":
            score += 2.0
        if sig["has_decision_json"]:
            score += 8.0
        if sig["has_diff"]:
            score += 8.0
        if sig["completed"]:
            score += 4.0
        if not txt.strip():
            score = 0.0
        score = max(0.0, min(100.0, score))

        rankings.append(
            {
                "agent": aid,
                "score": int(round(score)),
                "supervisor_score": int(s_score),
                "status": s_status,
                "has_decision_json": bool(sig["has_decision_json"]),
                "has_diff": bool(sig["has_diff"]),
                "completed": bool(sig["completed"]),
            }
        )

    rankings.sort(key=lambda r: (-int(r.get("score") or 0), int(r.get("agent") or 0)))
    top_agent = int(rankings[0]["agent"]) if rankings else 0

    return {
        "schema_version": 1,
        "generated_at": time.time(),
        "method": "deterministic_v1",
        "round": int(round_n),
        "agent_count": int(agent_count),
        "top_agent": top_agent,
        "rankings": rankings,
    }


def write_rankings(run_dir: Path, ranking: dict[str, Any], round_n: int) -> dict[str, str]:
    state = run_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    rj = state / f"task_rank_round{round_n}.json"
    lj = state / "task_rank_latest.json"
    rm = state / f"task_rank_round{round_n}.md"
    lines = [
        "# Task Rank",
        "",
        f"- round: {ranking.get('round')}",
        f"- top_agent: {ranking.get('top_agent')}",
        f"- method: {ranking.get('method')}",
        "",
    ]
    for row in ranking.get("rankings", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "- agent {0}: score={1} supervisor={2} status={3} decision={4} diff={5} completed={6}".format(
                row.get("agent"),
                row.get("score"),
                row.get("supervisor_score"),
                row.get("status"),
                row.get("has_decision_json"),
                row.get("has_diff"),
                row.get("completed"),
            )
        )
    txt = json.dumps(ranking, indent=2)
    rj.write_text(txt, encoding="utf-8")
    lj.write_text(txt, encoding="utf-8")
    rm.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"json": str(rj), "latest_json": str(lj), "md": str(rm)}


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
    ap.add_argument("--rank", action="store_true", help="Build deterministic round rankings for owner/auto-apply selection.")
    ap.add_argument("--agent-count", type=int, default=0)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    try:
        if args.rank:
            ac = int(args.agent_count or 0)
            if ac <= 0:
                raise ValueError("missing_agent_count_for_rank")
            ranking = build_rankings(run_dir, int(args.round_n), ac)
            paths = write_rankings(run_dir, ranking, int(args.round_n))
            print(
                json.dumps(
                    {"ok": True, "mode": "rank", "paths": paths, "top_agent": ranking.get("top_agent")},
                    separators=(",", ":"),
                )
            )
            raise SystemExit(0)
        pipeline = build_pipeline(run_dir, str(args.pattern or ""), int(args.round_n), str(args.prompt or ""))
        paths = write_pipeline(run_dir, pipeline, int(args.round_n))
        print(json.dumps({"ok": True, "paths": paths, "stage": pipeline.get("stage"), "prompt_addendum": pipeline.get("prompt_addendum")}, separators=(",", ":")))
        raise SystemExit(0)
    except Exception as ex:
        print(json.dumps({"ok": False, "error": str(ex), "round": int(args.round_n)}, separators=(",", ":")))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
