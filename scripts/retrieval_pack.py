from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _which(cmd: str) -> bool:
    try:
        cp = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=2)
        return cp.returncode == 0
    except Exception:
        return False


def _rg(query: str, roots: List[Path], *, max_count: int) -> List[str]:
    if not query.strip():
        return []
    if not roots:
        return []
    roots2 = [str(r) for r in roots if r.exists()]
    if not roots2:
        return []
    if not _which("rg"):
        return []
    try:
        cp = subprocess.run(
            ["rg", "-n", "--no-heading", "--color", "never", "-S", "--max-count", str(max_count), query, *roots2],
            capture_output=True,
            text=True,
            timeout=12,
        )
        out = (cp.stdout or "").splitlines()
        return [ln.strip() for ln in out if ln.strip()][:max_count]
    except Exception:
        return []


def _keyword_query(q: str) -> str:
    # rg already does decent matching; keep simple.
    return re.sub(r"\s+", " ", (q or "").strip())


def _recent_runs(repo_root: Path, limit: int = 8) -> List[Path]:
    jobs = repo_root / ".agent-jobs"
    if not jobs.exists():
        return []
    runs = [d for d in jobs.iterdir() if d.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[:limit]


def _write(run_dir: Path, round_n: int, payload: Dict[str, Any]) -> Tuple[Path, Path]:
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    jp = state_dir / f"retrieval_pack_round{round_n}.json"
    mp = state_dir / f"retrieval_pack_round{round_n}.md"
    jp.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md: List[str] = []
    md.append("# Retrieval Pack")
    md.append("")
    md.append(f"generated_at: {payload.get('generated_at')}")
    md.append(f"round: {payload.get('round')}")
    md.append(f"query: {payload.get('query')}")
    md.append("")
    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        md.append(f"## {section.get('title')}")
        md.append("")
        hits = section.get("hits") or []
        if not hits:
            md.append("(none)")
            md.append("")
            continue
        for h in hits:
            md.append(f"- {h}")
        md.append("")
    mp.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a bounded retrieval pack (specialized retrievers).")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-per-section", type=int, default=20)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))
    query = _keyword_query(args.query)
    max_n = max(5, min(50, int(args.max_per_section)))

    # Specialized retrievers (Multi-Agent RAG pattern, but local + deterministic):
    code_roots = [
        repo_root / "scripts",
        repo_root / "agents",
        repo_root / "mcp",
        repo_root / "configs",
    ]
    docs_roots = [
        repo_root / "docs",
        repo_root / "README.md",
        repo_root / "GEMINI.md",
    ]
    memory_roots: List[Path] = [
        repo_root / "ramshare" / "learning" / "memory" / "lessons.md",
        run_dir / "triad_orchestrator.log",
        run_dir / "state" / "manifest.json",
        run_dir / "state" / "invocation_context.json",
    ]
    for r in _recent_runs(repo_root):
        memory_roots.append(r / "triad_orchestrator.log")
        memory_roots.append(r / "state" / "manifest.json")
        memory_roots.append(r / "state" / "decisions_round1.json")

    payload: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at": time.time(),
        "repo_root": str(repo_root),
        "run_dir": str(run_dir),
        "round": round_n,
        "query": query,
        "sections": [],
    }

    payload["sections"].append(
        {"id": "code", "title": "Code Retriever (scripts/ agents/ mcp/ configs/)", "hits": _rg(query, code_roots, max_count=max_n)}
    )
    payload["sections"].append(
        {"id": "docs", "title": "Docs Retriever (docs/ README GEMINI)", "hits": _rg(query, docs_roots, max_count=max_n)}
    )
    payload["sections"].append(
        {"id": "memory", "title": "Memory Retriever (lessons + recent runs)", "hits": _rg(query, memory_roots, max_count=max_n)}
    )

    _write(run_dir, round_n, payload)
    print(json.dumps({"ok": True, "round": round_n}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

