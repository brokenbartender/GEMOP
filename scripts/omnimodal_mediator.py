import json
import os
from pathlib import Path
import datetime as dt

def aggregate_run(run_dir_path):
    run_dir = Path(run_dir_path)
    state_dir = run_dir / "state"
    report_path = run_dir / "OMNIMODAL_REPORT.md"
    
    print(f"--- 🌐 OMNIMODAL MEDIATOR: Aggregating {run_dir.name} ---")
    
    report = []
    report.append(f"# 🚀 Omnimodal Mission Report")
    report.append(f"**Run ID:** {run_dir.name}")
    report.append(f"**Timestamp:** {dt.datetime.now().isoformat()}")
    report.append("\n---\n")

    # 1. Mission Objective
    anchor = state_dir / "mission_anchor.md"
    if anchor.exists():
        content = anchor.read_text(encoding="utf-8")
        if "## Objective" in content:
            obj = content.split("## Objective")[1].split("##")[0].strip()
            report.append(f"## 🎯 Objective\n{obj}\n")

    # 2. Executive Decisions
    report.append("## 🧠 Swarm Decisions")
    for decision_file in sorted(state_dir.glob("decisions/round*_agent*.json")):
        try:
            data = json.loads(decision_file.read_text(encoding="utf-8"))
            agent_id = decision_file.stem.split("_agent")[1]
            report.append(f"### Agent {agent_id} Summary")
            report.append(f"> {data.get('summary', 'No summary provided.')}")
            if data.get('files'):
                report.append(f"**Files Touched:** `{', '.join(data['files'])}`")
        except: continue
    report.append("")

    # 3. Multimedia & Assets (Mock/Scaffold for real assets)
    report.append("## 🎨 Generated Assets")
    assets_found = False
    # Check for PNGs or other assets generated in the run
    for asset in run_dir.glob("**/*.png"):
        assets_found = True
        rel_path = asset.relative_to(run_dir)
        report.append(f"- ![Asset]({rel_path})\n  *Path: {rel_path}*")
    
    if not assets_found:
        report.append("*(No visual assets generated in this run)*")
    report.append("")

    # 4. Governance Audit
    report.append("## 🛡️ Governance & Ops")
    metrics_file = state_dir / "agent_metrics.jsonl"
    if metrics_file.exists():
        turns = 0
        cache_hits = 0
        with open(metrics_file, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                turns += 1
                if d.get("cached"): cache_hits += 1
        report.append(f"- **Total Turns:** {turns}")
        report.append(f"- **Tokens Saved (Cache Hits):** {cache_hits}")

    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"✅ Omnimodal Report Generated: {report_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        aggregate_run(sys.argv[1])
    else:
        # Auto-detect latest run
        repo_root = Path(__file__).resolve().parents[1]
        jobs = sorted((repo_root / ".agent-jobs").iterdir(), key=os.path.getmtime, reverse=True)
        if jobs:
            aggregate_run(jobs[0])
