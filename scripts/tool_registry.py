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
        "id": "team_compiler",
        "kind": "planning",
        "path": "scripts/team_compiler.py",
        "desc": "Compiles a 3..7 role team for the prompt (reduces swarm chaos).",
    },
    {
        "id": "agent_cards",
        "kind": "coordination",
        "path": "scripts/agent_cards.py",
        "desc": "Writes state/agent_cards.json (A2A-style 'Agent Cards' for dynamic routing/team introspection).",
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
        "id": "approve_action",
        "kind": "safety",
        "path": "scripts/approve_action.py",
        "desc": "Appends an approval record (HITL) to state/approvals.jsonl for a specific action_id.",
    },
    {
        "id": "killswitch",
        "kind": "safety",
        "path": "scripts/killswitch.py",
        "desc": "Writes STOP flags to stop runs/agents.",
    },
    {
        "id": "a2a_receive",
        "kind": "a2a",
        "path": "scripts/a2a_receive.py",
        "desc": "Receives A2A payloads (stdin/file) and enqueues into ramshare/state/a2a/inbox with idempotency + ACK.",
    },
    {
        "id": "a2a_executor",
        "kind": "a2a",
        "path": "scripts/a2a_remote_executor.py",
        "desc": "Processes ramshare/state/a2a/inbox and executes a2a.v2 action_payload (default-off; enable with GEMINI_OP_REMOTE_EXEC_ENABLE=1).",
    },
    {
        "id": "a2a_bridge_wsl",
        "kind": "a2a",
        "path": "scripts/a2a_bridge_wsl.py",
        "desc": "Routes A2A payloads into a local WSL distro via stdin (no SSH).",
    },
    {
        "id": "health_reporter",
        "kind": "observability",
        "path": "scripts/health_reporter.py",
        "desc": "Runs health checks, parses results, and generates a structured Markdown report.",
        "example": r"python scripts/health_reporter.py --repo-root . --run-dir ."
    },
    {
        "id": "finance_council_run",
        "kind": "finance",
        "path": "scripts/finance_council_run.py",
        "desc": "Queues or runs the finance_council multi-agent skillset (technical/fundamental/sentiment/risk/execution).",
        "example": r"python scripts/finance_council_run.py --account-id Z39213144 --run-now",
    },
    {
        "id": "market_theme_run",
        "kind": "finance",
        "path": "scripts/market_theme_run.py",
        "desc": "Queues or runs theme-driven stock research for any finance theme and returns ranked non-portfolio candidates.",
        "example": r"python scripts/market_theme_run.py --theme \"best ai micro investments for this week\" --run-now",
    },
    {
        "id": "rb_style_train",
        "kind": "commerce",
        "path": "scripts/rb_style_train.py",
        "desc": "Builds a reusable style profile from local artwork ZIP/folder for Redbubble product generation consistency.",
        "example": r"python scripts/rb_style_train.py --zip \"C:\path\to\artwork.zip\"",
    },
    {
        "id": "rb_style_cycle",
        "kind": "commerce",
        "path": "scripts/rb_style_cycle.py",
        "desc": "Runs multi-cycle style calibration + variety testing to tune generator overrides toward reference linework metrics.",
        "example": r"python scripts/rb_style_cycle.py --cycles 8 --zip \"C:\path\to\artwork.zip\" --apply",
    },
    {
        "id": "rb_catalog_scan",
        "kind": "commerce",
        "path": "scripts/rb_catalog_scan.py",
        "desc": "Scans local + live Redbubble sources to build duplicate-prevention catalog cache.",
        "example": r"python scripts/rb_catalog_scan.py --shop-url \"https://www.redbubble.com/people/<handle>/shop?asc=u\"",
    },
    {
        "id": "art_syndicate_run",
        "kind": "commerce",
        "path": "scripts/art_syndicate_run.py",
        "desc": "Runs the Art Syndicate council loop (trend hunter -> generator -> compliance/quality/SEO council -> packet).",
        "example": r"python scripts/art_syndicate_run.py --query \"trendy spots in michigan 2026\"",
    },
    {
        "id": "rb_photo_to_style",
        "kind": "commerce",
        "path": "scripts/rb_photo_to_style.py",
        "desc": "Converts a real landmark/building photo into your Redbubble-ready line-art style with iterative scoring + preview output.",
        "example": r"python scripts/rb_photo_to_style.py --image \"C:\Users\codym\Downloads\Fox Theater.jpg\" --cycles 14",
    },
    {
        "id": "ai_ops_report",
        "kind": "observability",
        "path": "scripts/ai_ops_report.py",
        "desc": "Generates an AI Ops report including token usage, cache hits, and estimated human ROI.",
    },
    {
        "id": "system_qa_check",
        "kind": "quality",
        "path": "scripts/system_qa_check.py",
        "desc": "Runs a comprehensive system-wide health check (Memory, Security, Performance).",
    },
    {
        "id": "formal_verifier",
        "kind": "safety",
        "path": "scripts/formal_verifier.py",
        "desc": "Deterministic neuro-symbolic safety gate; mathematically verifies code patches for dangerous calls or leaks.",
    },
    {
        "id": "meta_agent",
        "kind": "evolution",
        "path": "scripts/recursive_meta_agent.py",
        "desc": "Self-evolving logic daemon; monitors failures and autonomously updates global operating constraints.",
    },
    {
        "id": "mem1_consolidator",
        "kind": "memory",
        "path": "scripts/mem1_consolidator.py",
        "desc": "Synthesizes multi-agent round outputs into a compact, cohesive internal state block (ICLR 2026 pattern).",
    },
    {
        "id": "data_factory",
        "kind": "data",
        "path": "scripts/ai_data_factory.py",
        "desc": "Autonomous knowledge indexer; watches the filesystem and vectorizes new documentation in real-time.",
    },
    {
        "id": "omnimodal_mediator",
        "kind": "ecosystem",
        "path": "scripts/omnimodal_mediator.py",
        "desc": "Personal AI mediator; aggregates run artifacts into a single unified mission report.",
    },
    {
        "id": "observer_daemon",
        "kind": "context",
        "path": "scripts/observer_daemon.py",
        "desc": "Anticipatory computing daemon; builds real-time user context graphs to align agent intent.",
    },
    {
        "id": "rlhf_logger",
        "kind": "learning",
        "path": "scripts/rlhf_logger.py",
        "desc": "Implicit learning loop; records human approvals/rejections as reward signals for style tuning.",
    },
    {
        "id": "scan_secrets",
        "kind": "security",
        "path": "scripts/scan_secrets.py",
        "desc": "Scans the repository for accidental leaks of API keys, tokens, or credentials.",
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
