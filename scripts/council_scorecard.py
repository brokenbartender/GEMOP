from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _latest_state_file(run_dir: Path, glob: str) -> Path | None:
    state = run_dir / "state"
    if not state.exists():
        return None
    files = sorted(state.glob(glob))
    return files[-1] if files else None


@dataclass
class Gate:
    name: str
    ok: bool
    detail: str = ""


def score_run(*, run_dir: Path) -> dict[str, Any]:
    state = run_dir / "state"
    now = time.time()

    # Inputs
    sup_latest_path = _latest_state_file(run_dir, "supervisor_round*.json")
    patch_latest_path = _latest_state_file(run_dir, "patch_apply_round*.json")
    verify_path = state / "verify_report.json"
    sources_path = state / "sources.md"

    sup = _read_json(sup_latest_path) if sup_latest_path else None
    patch = _read_json(patch_latest_path) if patch_latest_path else None
    verify = _read_json(verify_path) if verify_path.exists() else None
    sources_txt = _read_text(sources_path) if sources_path.exists() else ""

    # Gates (must all pass for 100)
    gates: list[Gate] = []

    # 1) Verification gate.
    ver_ok = bool(verify and verify.get("ok") is True)
    gates.append(Gate("verify_ok", ver_ok, "" if ver_ok else "verify_report.json missing or ok=false"))

    # 2) Patch apply gate: if a patch report exists and contains diff_blocks>0, require ok=true.
    patch_gate_ok = True
    patch_detail = "no_patch_apply_report"
    patch_score = 100
    block_stats: dict[str, Any] = {"diff_blocks": 0, "ok_blocks": 0, "failed_blocks": 0, "fail_reasons": {}}
    if isinstance(patch, dict):
        diff_blocks = int(patch.get("diff_blocks") or 0)
        block_stats["diff_blocks"] = diff_blocks
        blocks = patch.get("blocks") if isinstance(patch.get("blocks"), list) else []
        ok_blocks = sum(1 for b in blocks if isinstance(b, dict) and b.get("ok") is True)
        failed = [b for b in blocks if isinstance(b, dict) and b.get("ok") is False]
        block_stats["ok_blocks"] = int(ok_blocks)
        block_stats["failed_blocks"] = int(len(failed))
        for b in failed:
            r = str(b.get("reason") or "unknown")
            block_stats["fail_reasons"][r] = int(block_stats["fail_reasons"].get(r, 0)) + 1

        patch_ok = bool(patch.get("ok") is True)
        patch_detail = f"diff_blocks={diff_blocks} ok_blocks={ok_blocks} failed_blocks={len(failed)}"

        # If no diffs, don't punish; otherwise require patch_ok.
        if diff_blocks > 0 and not patch_ok:
            patch_gate_ok = False

        # Patch score
        # - Start at 100
        # - If diff_blocks>0 and patch_ok false: -40
        # - Per failed block: -10
        patch_score = 100
        if diff_blocks > 0 and not patch_ok:
            patch_score -= 40
        patch_score -= 10 * int(len(failed))
        patch_score = max(0, min(100, patch_score))
    gates.append(Gate("patch_apply_ok", bool(patch_gate_ok), patch_detail))

    # 3) Supervisor hygiene gate: no invalid_file_refs in the latest supervisor report.
    # Supervisor hygiene: judge the "primary" agent (the one whose patch was applied),
    # not every participant. Supporting agents may brainstorm and mention hypothetical
    # files; that should not block a perfect run.
    sup_ok = True
    sup_detail = "no_supervisor_report"
    supervisor_avg = None
    invalid_refs_total = 0
    primary_agent = None
    if isinstance(patch, dict):
        try:
            primary_agent = int(patch.get("agent") or 0) or None
        except Exception:
            primary_agent = None
    if isinstance(sup, dict) and isinstance(sup.get("verdicts"), list):
        verdicts = [v for v in sup["verdicts"] if isinstance(v, dict)]
        scores = []
        for v in verdicts:
            try:
                scores.append(int(v.get("score") or 0))
            except Exception:
                pass
        supervisor_avg = (sum(scores) / len(scores)) if scores else None

        # Choose primary agent if patch didn't run.
        if primary_agent is None and verdicts:
            best = sorted(verdicts, key=lambda v: int(v.get("score") or 0), reverse=True)[0]
            try:
                primary_agent = int(best.get("agent") or 0) or None
            except Exception:
                primary_agent = None

        focus = None
        if primary_agent is not None:
            for v in verdicts:
                try:
                    if int(v.get("agent") or 0) == int(primary_agent):
                        focus = v
                        break
                except Exception:
                    continue
        if focus is None and verdicts:
            focus = verdicts[0]

        mistakes = focus.get("mistakes") if isinstance(focus.get("mistakes"), list) else []
        sup_ok = "invalid_file_refs" not in mistakes
        try:
            invalid_refs_total = int((focus.get("metrics") or {}).get("invalid_path_count") or 0)
        except Exception:
            invalid_refs_total = 0
        sup_detail = f"primary_agent={primary_agent} avg={supervisor_avg} invalid_paths={invalid_refs_total}"
    gates.append(Gate("supervisor_clean", bool(sup_ok), sup_detail))

    # 4) Sources gate: require at least a few sources when sources.md exists.
    # (If the user runs offline, this may be empty; we keep it weakly enforced.)
    src_count = 0
    for ln in sources_txt.splitlines():
        s = ln.strip()
        if s.startswith("## [") and "http" in s:
            src_count += 1
    src_ok = src_count >= 3 if sources_txt else True
    gates.append(Gate("sources_present", bool(src_ok), f"count={src_count}"))

    # Process score
    # Start at 100, subtract penalties for gate failures.
    score = 100
    for g in gates:
        if g.ok:
            continue
        if g.name == "verify_ok":
            score -= 60
        elif g.name == "patch_apply_ok":
            score -= 30
        elif g.name == "supervisor_clean":
            score -= 10
        elif g.name == "sources_present":
            score -= 5
        else:
            score -= 5
    score = max(0, min(100, score))

    out = {
        "ok": True,
        "generated_at": now,
        "run_dir": str(run_dir),
        "paths": {
            "supervisor_latest": str(sup_latest_path) if sup_latest_path else "",
            "patch_latest": str(patch_latest_path) if patch_latest_path else "",
            "verify_report": str(verify_path) if verify_path.exists() else "",
            "sources": str(sources_path) if sources_path.exists() else "",
        },
        "gates": [{"name": g.name, "ok": g.ok, "detail": g.detail} for g in gates],
        "scores": {
            "process_score": int(score),
            "patch_score": int(patch_score),
        },
        "stats": {
            "supervisor_avg": supervisor_avg,
            "invalid_refs_total": int(invalid_refs_total),
            "sources_count": int(src_count),
            "patch": block_stats,
        },
    }
    out["perfect_100"] = bool(out["scores"]["process_score"] == 100 and out["scores"]["patch_score"] == 100)
    return out


def write_outputs(run_dir: Path, obj: dict[str, Any]) -> tuple[Path, Path]:
    state = run_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    json_path = state / "scorecard.json"
    md_path = state / "scorecard.md"
    json_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

    md = []
    md.append("# Scorecard")
    md.append("")
    md.append(f"run_dir: `{obj.get('run_dir','')}`")
    md.append(f"generated_at: `{obj.get('generated_at','')}`")
    md.append("")
    md.append("## Scores")
    md.append("")
    md.append(f"- process_score: `{obj.get('scores',{}).get('process_score','')}`")
    md.append(f"- patch_score: `{obj.get('scores',{}).get('patch_score','')}`")
    md.append(f"- perfect_100: `{obj.get('perfect_100','')}`")
    md.append("")
    md.append("## Gates")
    md.append("")
    for g in obj.get("gates") or []:
        name = g.get("name")
        ok = g.get("ok")
        detail = g.get("detail") or ""
        md.append(f"- {name}: `{ok}` {detail}".rstrip())
    md.append("")
    md.append("## Stats")
    md.append("")
    st = obj.get("stats") or {}
    md.append(f"- supervisor_avg: `{st.get('supervisor_avg')}`")
    md.append(f"- invalid_refs_total: `{st.get('invalid_refs_total')}`")
    md.append(f"- sources_count: `{st.get('sources_count')}`")
    patch = st.get("patch") or {}
    md.append(f"- patch.diff_blocks: `{patch.get('diff_blocks')}`")
    md.append(f"- patch.ok_blocks: `{patch.get('ok_blocks')}`")
    md.append(f"- patch.failed_blocks: `{patch.get('failed_blocks')}`")
    md_path.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")

    # Patch scorecard (separate file for quick scanning).
    patch_md_path = state / "patch_scorecard.md"
    p = obj.get("stats", {}).get("patch", {}) if isinstance(obj.get("stats"), dict) else {}
    lines = []
    lines.append("# Patch Scorecard")
    lines.append("")
    lines.append(f"run_dir: `{obj.get('run_dir','')}`")
    lines.append("")
    lines.append(f"- patch_score: `{obj.get('scores',{}).get('patch_score','')}`")
    lines.append(f"- diff_blocks: `{p.get('diff_blocks')}`")
    lines.append(f"- ok_blocks: `{p.get('ok_blocks')}`")
    lines.append(f"- failed_blocks: `{p.get('failed_blocks')}`")
    fr = p.get("fail_reasons") if isinstance(p.get("fail_reasons"), dict) else {}
    if fr:
        lines.append("")
        lines.append("## Fail Reasons")
        lines.append("")
        for k in sorted(fr.keys()):
            lines.append(f"- {k}: `{fr.get(k)}`")
    patch_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a run scorecard (process + patch).")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    obj = score_run(run_dir=run_dir)
    json_path, md_path = write_outputs(run_dir, obj)
    print(json.dumps({"ok": True, "scorecard": str(json_path), "scorecard_md": str(md_path), "scores": obj.get("scores")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
