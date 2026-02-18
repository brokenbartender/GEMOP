import argparse
import json
import os
from pathlib import Path

MANA_DB = Path("data/mana_registry.json")

def update_mana(run_dir: Path):
    """
    Analyzes the learning summary and updates agent Mana (Trust Scores).
    """
    summary_path = run_dir / "learning-summary.json"
    if not summary_path.exists():
        return

    try:
        summary = json.loads(summary_path.read_text(encoding='utf-8', errors='ignore'))
        avg_score = float(summary.get("avg_score", 0))
    except Exception:
        return

    # Load existing registry
    if MANA_DB.exists():
        registry = json.loads(MANA_DB.read_text(encoding='utf-8'))
    else:
        registry = {"agents": {}}

    # Update agents found in the run
    # (Extracting roles from the run artifacts)
    for f in run_dir.glob("agent*.md"):
        agent_id = f.stem.replace("agent", "")
        # For PoC, we map agent IDs. In production, we map Role Names.
        if agent_id not in registry["agents"]:
            registry["agents"][agent_id] = {"mana": 50, "runs": 0}
        
        cur = registry["agents"][agent_id]
        cur["runs"] += 1
        
        # Merit-based adjustment
        if avg_score >= 90:
            cur["mana"] += 5
        elif avg_score < 70:
            cur["mana"] -= 10
            
        # Bounds
        cur["mana"] = max(0, min(100, cur["mana"]))
        print(f"[Mana] Agent {agent_id} now at level {cur['mana']}.")

    MANA_DB.parent.mkdir(parents=True, exist_ok=True)
    MANA_DB.write_text(json.dumps(registry, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Mana Ranker: Dynamic Agent Reputation.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    update_mana(Path(args.run_dir))

if __name__ == "__main__":
    main()
