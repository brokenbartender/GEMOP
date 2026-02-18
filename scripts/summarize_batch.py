from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def rj(p: Path) -> dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def rt(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def latest_state(run_dir: Path, glob: str) -> Path | None:
    state = run_dir / "state"
    if not state.exists():
        return None
    xs = sorted(state.glob(glob))
    return xs[-1] if xs else None


@dataclass
class RunRow:
    run_dir: str
    process_score: int | None
    patch_score: int | None
    perfect_100: bool | None
    sources_count: int | None
    verify_ok: bool | None
    patch_ok: bool | None
    patch_agent: int | None
    touched_files: list[str]
    decision_summary: str
    decision_files: list[str]
    decision_commands: list[str]


def load_run(run_dir: Path) -> RunRow:
    state = run_dir / "state"
    score = rj(state / "scorecard.json") or {}
    scores = score.get("scores") if isinstance(score.get("scores"), dict) else {}
    stats = score.get("stats") if isinstance(score.get("stats"), dict) else {}

    verify = rj(state / "verify_report.json") or {}
    patch_p = latest_state(run_dir, "patch_apply_round*.json")
    patch = rj(patch_p) if patch_p else None

    decision_summary = ""
    decision_files: list[str] = []
    decision_commands: list[str] = []
    touched: list[str] = []
    patch_agent = None
    patch_ok = None

    if isinstance(patch, dict):
        try:
            patch_agent = int(patch.get("agent") or 0) or None
        except Exception:
            patch_agent = None
        patch_ok = bool(patch.get("ok") is True)

        blocks = patch.get("blocks") if isinstance(patch.get("blocks"), list) else []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            tf = b.get("touched_files")
            if isinstance(tf, list):
                for f in tf:
                    s = str(f)
                    if s and s not in touched:
                        touched.append(s)

        # Try the decision JSON that patch apply used.
        dp = patch.get("decision_path")
        if isinstance(dp, str) and dp.strip():
            d = rj(Path(dp))
            if isinstance(d, dict):
                decision_summary = str(d.get("summary") or "")
                fs = d.get("files")
                cs = d.get("commands")
                if isinstance(fs, list):
                    decision_files = [str(x) for x in fs if str(x).strip()]
                if isinstance(cs, list):
                    decision_commands = [str(x) for x in cs if str(x).strip()]

    # Fallback: best available decision from round2/round3 agent1.
    if not decision_summary:
        for guess in (
            state / "decisions" / "round3_agent1.json",
            state / "decisions" / "round2_agent1.json",
        ):
            d = rj(guess)
            if isinstance(d, dict) and str(d.get("summary") or "").strip():
                decision_summary = str(d.get("summary") or "")
                fs = d.get("files")
                cs = d.get("commands")
                if isinstance(fs, list):
                    decision_files = [str(x) for x in fs if str(x).strip()]
                if isinstance(cs, list):
                    decision_commands = [str(x) for x in cs if str(x).strip()]
                break

    process_score = scores.get("process_score")
    patch_score = scores.get("patch_score")
    perfect = score.get("perfect_100")

    try:
        process_score = int(process_score)
    except Exception:
        process_score = None
    try:
        patch_score = int(patch_score)
    except Exception:
        patch_score = None
    perfect_100 = bool(perfect) if perfect is not None else None

    src_count = stats.get("sources_count")
    try:
        src_count = int(src_count)
    except Exception:
        src_count = None

    verify_ok = bool(verify.get("ok") is True) if isinstance(verify, dict) else None

    return RunRow(
        run_dir=str(run_dir),
        process_score=process_score,
        patch_score=patch_score,
        perfect_100=perfect_100,
        sources_count=src_count,
        verify_ok=verify_ok,
        patch_ok=patch_ok,
        patch_agent=patch_agent,
        touched_files=touched,
        decision_summary=decision_summary.strip(),
        decision_files=decision_files,
        decision_commands=decision_commands,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize a batch of council runs.")
    ap.add_argument("--runs-file", required=True, help="Text file with one run_dir per line.")
    ap.add_argument("--out", default="", help="Output markdown path (default: alongside runs file).")
    args = ap.parse_args()

    runs_file = Path(args.runs_file).resolve()
    out_path = Path(args.out).resolve() if args.out else runs_file.parent / "batch_summary.md"

    run_dirs: list[Path] = []
    for ln in runs_file.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if not s:
            continue
        p = Path(s)
        if not p.is_absolute():
            p = (runs_file.parent / p).resolve()
        run_dirs.append(p)

    rows: list[RunRow] = []
    for rd in run_dirs:
        if not rd.exists():
            continue
        rows.append(load_run(rd))

    md: list[str] = []
    md.append("# Batch Summary")
    md.append("")
    md.append(f"runs_file: `{runs_file}`")
    md.append(f"run_count: `{len(rows)}`")
    md.append("")
    md.append("## Runs")
    md.append("")
    for i, r in enumerate(rows, start=1):
        md.append(f"### {i}. {Path(r.run_dir).name}")
        md.append("")
        md.append(f"- run_dir: `{r.run_dir}`")
        md.append(f"- scores: process=`{r.process_score}` patch=`{r.patch_score}` perfect_100=`{r.perfect_100}`")
        md.append(f"- sources_count: `{r.sources_count}` verify_ok: `{r.verify_ok}` patch_ok: `{r.patch_ok}` patch_agent: `{r.patch_agent}`")
        if r.decision_summary:
            md.append(f"- decision_summary: {r.decision_summary}")
        if r.decision_files:
            md.append("- decision_files:")
            for f in r.decision_files[:25]:
                md.append(f"  - `{f}`")
        if r.decision_commands:
            md.append("- decision_commands:")
            for c in r.decision_commands[:25]:
                md.append(f"  - `{c}`")
        if r.touched_files:
            md.append("- touched_files:")
            for f in r.touched_files[:25]:
                md.append(f"  - `{f}`")
        md.append("")

    out_path.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "runs": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

