from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


def _safe_read(path: Path, max_chars: int = 5000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def _one_line_summary(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    ranked = sorted(lines, key=lambda s: len(s), reverse=True)
    summary = " | ".join(ranked[:2]).strip()
    return re.sub(r"\s+", " ", summary)[:280]


def _load_hubble(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "state" / "hubble_drift.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def build_wormholes(run_dir: Path, query: str, max_nodes: int) -> dict[str, Any]:
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    hubble = _load_hubble(run_dir)
    receding = hubble.get("receding_entries") if isinstance(hubble.get("receding_entries"), list) else []
    nodes: list[dict[str, Any]] = []
    q_terms = set(re.findall(r"[A-Za-z0-9_./\\-]+", (query or "").lower()))

    for row in receding:
        if not isinstance(row, dict):
            continue
        path = Path(str(row.get("path", "")))
        if not path.exists():
            continue
        text = _safe_read(path)
        if not text.strip():
            continue
        terms = set(re.findall(r"[A-Za-z0-9_./\\-]+", text.lower()))
        relevance = len(q_terms & terms) if q_terms else 0
        anchor_seed = f"{path}|{row.get('velocity')}|{row.get('distance')}"
        anchor_id = "wormhole_" + hashlib.sha1(anchor_seed.encode("utf-8")).hexdigest()[:12]
        node = {
            "anchor_id": anchor_id,
            "source_path": str(path),
            "distance": row.get("distance"),
            "velocity": row.get("velocity"),
            "age_hours": row.get("age_hours"),
            "query_relevance": relevance,
            "summary": _one_line_summary(text),
        }
        nodes.append(node)

    nodes.sort(key=lambda n: (float(n.get("velocity") or 0.0), int(n.get("query_relevance") or 0)), reverse=True)
    nodes = nodes[: max(1, int(max_nodes))]

    jsonl_path = state_dir / "wormholes.jsonl"
    jsonl_path.write_text("", encoding="utf-8")
    for n in nodes:
        _append_jsonl(jsonl_path, n)

    md_lines = ["# Wormhole Index", "", f"generated_at: {time.time()}", f"query: {query}", ""]
    for n in nodes:
        md_lines.append(f"## {n['anchor_id']}")
        md_lines.append(f"- source: {n['source_path']}")
        md_lines.append(f"- velocity: {n['velocity']} distance: {n['distance']} age_h: {n['age_hours']}")
        md_lines.append(f"- summary: {n['summary']}")
        md_lines.append("")
    md_path = state_dir / "wormholes.md"
    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    out = {
        "schema_version": 1,
        "generated_at": time.time(),
        "query": query,
        "nodes": nodes,
        "count": len(nodes),
        "paths": {"jsonl": str(jsonl_path), "md": str(md_path)},
    }
    (state_dir / "wormhole_index.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build wormhole summary nodes for receding memory.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-nodes", type=int, default=10)
    args = ap.parse_args()
    out = build_wormholes(Path(args.run_dir).resolve(), args.query, int(args.max_nodes))
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
