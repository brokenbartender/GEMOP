from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a compact markdown report for a council run.")
    ap.add_argument("--run-dir", required=True, help="Path to .agent-jobs/<run_...> directory")
    ap.add_argument("--out", default="", help="Output markdown path (default: <run>/state/eval_report.md)")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    state = run_dir / "state"
    if not run_dir.exists() or not state.exists():
        raise SystemExit(f"invalid run dir (missing state/): {run_dir}")

    out_path = Path(args.out).expanduser().resolve() if args.out else (state / "eval_report.md")

    rounds = sorted({int(p.stem.split("_round")[1]) for p in state.glob("supervisor_round*.json") if "_round" in p.stem})
    max_round = max(rounds) if rounds else 0

    lines: list[str] = []
    lines.append("# Council Run Report")
    lines.append("")
    lines.append(f"run_dir: `{run_dir}`")
    lines.append(f"generated_at: `{time.time()}`")
    lines.append(f"rounds: `{max_round}`")
    lines.append("")

    # Include sources list (first few URLs).
    sources_md = state / "sources.md"
    if sources_md.exists():
        src_txt = _read_text(sources_md)
        urls: list[str] = []
        for ln in src_txt.splitlines():
            ln = ln.strip()
            if ln.startswith("## [") and "] http" in ln:
                u = ln.split("] ", 1)[1].strip()
                urls.append(u)
            if len(urls) >= 10:
                break
        if urls:
            lines.append("## Sources (Top 10)")
            lines.append("")
            for u in urls:
                lines.append(f"- {u}")
            lines.append("")

    # Overall Agent Metrics (from agent_metrics.jsonl)
    agent_metrics_path = state / "agent_metrics.jsonl"
    if agent_metrics_path.exists():
        total_invalid_paths = 0
        total_injection_hits = 0
        total_refusal_hits = 0
        agent_count = 0

        for line in _read_text(agent_metrics_path).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "metrics" in data:
                    metrics = data["metrics"]
                    total_invalid_paths += metrics.get("invalid_path_count", 0)
                    total_injection_hits += metrics.get("injection_hits", 0)
                    total_refusal_hits += metrics.get("refusal_hits", 0)
                    agent_count += 1
            except json.JSONDecodeError:
                continue

        if agent_count > 0:
            lines.append("## Overall Agent Metrics")
            lines.append("")
            lines.append(f"- Total Agents Reporting: `{agent_count}`")
            lines.append(f"- Total Invalid Paths Reported: `{total_invalid_paths}`")
            lines.append(f"- Total Injection Hits: `{total_injection_hits}`")
            lines.append(f"- Total Refusal Hits: `{total_refusal_hits}`")
            lines.append("")

    # Supervisor summaries per round.
    sup_any = False
    for r in range(1, max_round + 1):
        p = state / f"supervisor_round{r}.json"
        obj = _read_json(p)
        if not isinstance(obj, dict):
            continue
        verdicts = obj.get("verdicts")
        if not isinstance(verdicts, list):
            continue
        sup_any = True
        lines.append(f"## Supervisor Round {r}")
        lines.append("")
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            agent = v.get("agent")
            score = v.get("score")
            status = v.get("status")
            mistakes = v.get("mistakes") or []
            if isinstance(mistakes, list):
                mistakes_s = ", ".join(str(x) for x in mistakes[:6])
            else:
                mistakes_s = str(mistakes)
            lines.append(f"- agent `{agent}` score `{score}` status `{status}` mistakes `{mistakes_s}`")
        lines.append("")

    if not sup_any:
        lines.append("## Supervisor")
        lines.append("")
        lines.append("(no supervisor_round*.json found)")
        lines.append("")

    # Patch apply outcomes.
    pa_any = False
    for r in range(2, max_round + 1):
        p = state / f"patch_apply_round{r}.json"
        if not p.exists():
            continue
        obj = _read_json(p)
        if not isinstance(obj, dict):
            continue
        pa_any = True
        lines.append(f"## Patch Apply Round {r}")
        lines.append("")
        lines.append(f"- ok: `{obj.get('ok')}` agent: `{obj.get('agent')}` diff_blocks: `{obj.get('diff_blocks')}`")
        blocks = obj.get("blocks") if isinstance(obj.get("blocks"), list) else []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            touched = b.get("touched_files") or []
            if isinstance(touched, list):
                touched_s = ", ".join(str(x) for x in touched)
            else:
                touched_s = str(touched)
            lines.append(f"- block `{b.get('index')}` ok `{b.get('ok')}` reason `{b.get('reason','')}` touched `{touched_s}`")
        lines.append("")

    if not pa_any:
        lines.append("## Patch Apply")
        lines.append("")
        lines.append("(no patch_apply_round*.json found)")
        lines.append("")

    # Verify pipeline (if present).
    vr = state / "verify_report.json"
    if vr.exists():
        obj = _read_json(vr)
        lines.append("## Verify Pipeline")
        lines.append("")
        if isinstance(obj, dict):
            lines.append(f"- ok: `{obj.get('ok')}`")
            checks = obj.get("checks") if isinstance(obj.get("checks"), list) else []
            for c in checks:
                if not isinstance(c, dict):
                    continue
                cmd = c.get("cmd")
                rc = c.get("rc")
                lines.append(f"- rc `{rc}` cmd `{cmd}`")
        else:
            lines.append("(verify_report.json unreadable)")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

