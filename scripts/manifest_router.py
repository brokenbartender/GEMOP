from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


def _now() -> float:
    return time.time()


def _round_plan(pattern: str, max_rounds: int) -> List[Dict[str, Any]]:
    pat = (pattern or "").strip().lower()
    mr = max(1, int(max_rounds or 1))
    if pat == "debate":
        base = [
            {
                "round": 1,
                "goal": "Diverge: propose best options with acceptance + key risks.",
                "required_artifacts": ["round*_agent*.md", "DECISION_JSON(per seat)"],
            },
            {
                "round": 2,
                "goal": "Cross-exam + converge: pick top plan and verification commands.",
                "required_artifacts": ["round*_agent*.md", "DECISION_JSON(per seat)"],
            },
            {
                "round": 3,
                "goal": "Implement: produce clean unified diffs and verify commands.",
                "required_artifacts": ["```diff blocks", "DECISION_JSON(files,commands)"],
            },
            {
                "round": 4,
                "goal": "Verify + repair: run verify pipeline; fix failures with patches.",
                "required_artifacts": ["verify_pipeline ok", "patch_apply report"],
            },
        ]
        return base[:mr]
    if pat == "single":
        return [
            {
                "round": 1,
                "goal": "Single-pass completion with verification commands.",
                "required_artifacts": ["agent*.md", "DECISION_JSON"],
            }
        ]
    # voting / unknown
    base = [
        {
            "round": 1,
            "goal": "Propose options + score; include acceptance + verification.",
            "required_artifacts": ["round*_agent*.md", "DECISION_JSON(per seat)"],
        },
        {
            "round": 2,
            "goal": "Vote + finalize: produce a single plan + commands.",
            "required_artifacts": ["round*_agent*.md", "decision summary"],
        },
    ]
    return base[:mr]

def _default_service_router(*, online: bool) -> Dict[str, Any]:
    """
    "Service Router" concept: decouple workflow (roles) from intelligence (models/providers).
    This is a lightweight, repo-native config that agent_runner_v2 can consult.
    """
    # Provider names align with scripts/agent_runner_v2.py provider router.
    return {
        "schema_version": 1,
        "online": bool(online),
        "roles": {
            # High-leverage reasoning seats.
            "Architect": {"tier": "cloud", "providers": ["cloud_codex_cli", "cloud_gemini", "cloud_gemini_cli"]},
            "ResearchLead": {"tier": "cloud", "providers": ["cloud_gemini", "cloud_codex_cli", "cloud_gemini_cli"]},
            "Engineer": {"tier": "cloud", "providers": ["cloud_gemini", "cloud_codex_cli", "cloud_gemini_cli"]},
            "Security": {"tier": "cloud", "providers": ["cloud_codex_cli", "cloud_gemini", "cloud_gemini_cli"]},
            "CodexReviewer": {"tier": "cloud", "providers": ["cloud_codex_cli", "cloud_gemini_cli", "cloud_gemini"]},
            "Operator": {"tier": "cloud", "providers": ["cloud_gemini", "cloud_codex_cli", "cloud_gemini_cli"]},
            "Auditor": {"tier": "flash", "providers": ["local_ollama", "cloud_gemini_cli"]},
            "MultimediaDirector": {"tier": "cloud", "providers": ["cloud_gemini", "cloud_codex_cli", "cloud_gemini_cli"]},
            "RedTeam": {"tier": "ultra", "providers": ["cloud_gemini", "cloud_codex_cli"]},
            # Precision / cost-controlled seats.
            "Tester": {"tier": "local", "providers": ["local_ollama"]},
            "Critic": {"tier": "local", "providers": ["local_ollama"]},
            "Ops": {"tier": "local", "providers": ["local_ollama"]},
            "Docs": {"tier": "local", "providers": ["local_ollama"]},
            "Release": {"tier": "local", "providers": ["local_ollama"]},
        },
        "fallback": {"tier": "cloud" if online else "local"},
    }


def _manifest_mermaid(manifest: Dict[str, Any]) -> str:
    rounds = manifest.get("rounds") if isinstance(manifest.get("rounds"), list) else []
    lines = ["flowchart TD"]
    lines.append("  start([Start])")
    prev = "start"
    for r in rounds:
        rn = int(r.get("round") or 0) if isinstance(r, dict) else 0
        if rn <= 0:
            continue
        node = f"r{rn}"
        label = (r.get("goal") or "").replace('"', "'") if isinstance(r, dict) else ""
        lines.append(f'  {node}["Round {rn}: {label}"]')
        lines.append(f"  {prev} --> {node}")
        prev = node
    lines.append("  end([End])")
    lines.append(f"  {prev} --> end")
    # Quality gates (conceptual)
    lines.append('  gate1{{"DECISION_JSON required"}}')
    lines.append('  gate2{{"diff blocks required on autopatch"}}')
    lines.append('  gate3{{"verify pipeline strict"}}')
    lines.append("  r1 -.-> gate1")
    lines.append("  r2 -.-> gate1")
    lines.append("  r2 -.-> gate2")
    lines.append("  r2 -.-> gate3")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a run manifest (machine-checkable plan + budgets).")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--pattern", default="debate")
    ap.add_argument("--agents", type=int, default=3)
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--cloud-seats", type=int, default=3)
    ap.add_argument("--codex-seats", type=int, default=0)
    ap.add_argument("--max-local-concurrency", type=int, default=2)
    ap.add_argument("--quota-cloud-calls", type=int, default=0)
    ap.add_argument("--quota-cloud-calls-per-agent", type=int, default=0)
    ap.add_argument("--require-decision-json", action="store_true")
    ap.add_argument("--auto-apply-patches", action="store_true")
    ap.add_argument("--verify-after-patches", action="store_true")
    ap.add_argument("--require-approval", action="store_true", help="Require HITL approval before sensitive actions (ex: patch apply).")
    ap.add_argument("--require-grounding", action="store_true", help="Require grounding citations before applying patches.")
    ap.add_argument("--contract-repair-attempts", type=int, default=1)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "schema_version": 1,
        "created_at": _now(),
        "repo_root": str(repo_root),
        "run_dir": str(run_dir),
        "task": str(args.task or "").strip(),
        "pattern": str(args.pattern or "").strip().lower(),
        "agents": int(args.agents),
        "max_rounds": int(args.max_rounds),
        "online": bool(args.online),
        "routing": {
            "cloud_seats": int(args.cloud_seats),
            "codex_seats": int(args.codex_seats),
            "max_local_concurrency": int(args.max_local_concurrency),
            "cloud_spillover": bool(args.online),  # controlled by orchestrator env when -Online
        },
        "budgets": {
            "quota_cloud_calls": int(args.quota_cloud_calls),
            "quota_cloud_calls_per_agent": int(args.quota_cloud_calls_per_agent),
            "contract_repair_attempts": int(args.contract_repair_attempts),
        },
        "quality_gates": {
            "require_decision_json": bool(args.require_decision_json),
            "require_diff_blocks_on_autopatch": bool(args.auto_apply_patches),
            "verify_after_patches": bool(args.verify_after_patches),
            "require_approval": bool(args.require_approval),
            "require_grounding": bool(args.require_grounding),
        },
        "rounds": _round_plan(str(args.pattern), int(args.max_rounds)),
        "service_router": _default_service_router(online=bool(args.online)),
    }

    out_path = state_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (state_dir / "manifest.mmd").write_text(_manifest_mermaid(manifest), encoding="utf-8")
    print(json.dumps({"ok": True, "manifest_path": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
