from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


TOOLS: List[Dict[str, Any]] = [
    {
        "id": "summon",
        "kind": "entrypoint",
        "path": "scripts/summon.ps1",
        "desc": "One-line council launcher (recommended UX).",
        "example": r"pwsh .\scripts\summon.ps1 -Task '...' -Online",
    },
    {
        "id": "orchestrator",
        "kind": "engine",
        "path": "scripts/triad_orchestrator.ps1",
        "desc": "Canonical multi-agent orchestrator (run-dir engine).",
    },
    {
        "id": "agent_runner",
        "kind": "worker",
        "path": "scripts/agent_runner_v2.py",
        "desc": "Executes one agent seat; hybrid router (cloud/local) with guardrails.",
    },
    {
        "id": "skill_bridge",
        "kind": "tooling",
        "path": "scripts/skill_bridge.py",
        "desc": "Selects/injects external skills from ~/.codex and ~/.gemini.",
    },
    {
        "id": "manifest_router",
        "kind": "planning",
        "path": "scripts/manifest_router.py",
        "desc": "Writes state/manifest.json for machine-checkable budgets/plan.",
    },
    {
        "id": "contract_repair",
        "kind": "quality",
        "path": "scripts/contract_repair.py",
        "desc": "Repairs missing DECISION_JSON by re-running only failing seats.",
    },
    {
        "id": "patch_apply",
        "kind": "execution",
        "path": "scripts/council_patch_apply.py",
        "desc": "Applies ```diff blocks from best agent output with guardrails.",
    },
    {
        "id": "verify",
        "kind": "quality",
        "path": "scripts/verify_pipeline.py",
        "desc": "Runs verification pipeline after patches (strict mode supported).",
    },
    {
        "id": "bus",
        "kind": "coordination",
        "path": "scripts/council_bus.py",
        "desc": "Async council bus (propose/claim/ack decisions + hygiene sweep).",
    },
    {
        "id": "eval_harness",
        "kind": "observability",
        "path": "scripts/eval_harness.py",
        "desc": "Scores prior runs for contract compliance + failure signals.",
    },
    {
        "id": "retrieval_pack",
        "kind": "retrieval",
        "path": "scripts/retrieval_pack.py",
        "desc": "Bounded multi-retriever pack (code/docs/memory) injected into prompts.",
    },
    {
        "id": "killswitch",
        "kind": "safety",
        "path": "scripts/killswitch.py",
        "desc": "Writes STOP flags to stop runs/agents.",
    },
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a small tool registry artifact for a run.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "generated_at": time.time(),
        "repo_root": str(repo_root),
        "run_dir": str(run_dir),
        "tools": TOOLS,
    }
    (state_dir / "tool_registry.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = ["# Tool Registry", ""]
    md.append(f"generated_at: {payload['generated_at']}")
    md.append("")
    for t in TOOLS:
        md.append(f"- `{t['id']}`: {t.get('desc','')}".strip())
        md.append(f"  path: `{t.get('path','')}`")
        ex = t.get("example")
        if ex:
            md.append(f"  example: `{ex}`")
    (state_dir / "tool_registry.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "tool_registry": str(state_dir / "tool_registry.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
