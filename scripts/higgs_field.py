import json
import argparse
from pathlib import Path

def calculate_mass(branch: dict) -> float:
    """
    Assigns 'Mass' (Validity Weight) to a parallel solution.
    """
    mass = 0.5 # Baseline mass
    content = str(branch.get("result", "")).lower()
    
    # Heuristic 1: Grounding Mass (Cites files)
    if "/" in content or "\\" in content:
        mass += 0.2
    
    # Heuristic 2: Verification Mass (Includes commands)
    if "```powershell" in content or "```bash" in content:
        mass += 0.15
    
    # Heuristic 3: Brevity Penalty (Too short = no mass)
    if len(content) < 200:
        mass -= 0.3
        
    return round(max(0.0, min(1.0, mass)), 4)

def collapse_superposition(run_dir: Path):
    print("--- 🌌 HIGGS FIELD: Collapsing Realities ---")
    
    state_path = run_dir / "state" / "quantum_superposition.json"
    if not state_path.exists():
        print(" -> No superposition found. Reality is already linear.")
        return

    wavefunction = json.loads(state_path.read_text())
    branches = wavefunction.get("branches", [])
    
    ranked_branches = []
    for b in branches:
        if not b.get("ok"): continue
        mass = calculate_mass(b)
        ranked_branches.append({**b, "mass": mass})
        print(f" -> Branch {b['role']}: Mass {mass}")

    if not ranked_branches:
        print(" -> All branches failed. Reality remains void.")
        return

    # THE COLLAPSE: Select Highest Mass
    winner = sorted(ranked_branches, key=lambda x: x['mass'], reverse=True)[0]
    print(f" -> COLLAPSE: {winner['role']} selected as Reality Prime (Mass: {winner['mass']})")
    
    # Write to Observed Reality
    out_path = run_dir / "state" / "observed_reality.md"
    md = [
        f"# 🏁 Observed Reality Prime",
        f"**Source Branch:** {winner['role']}",
        f"**Higgs Mass:** {winner['mass']}",
        "\n---\n",
        winner['result']
    ]
    out_path.write_text("\n".join(md), encoding='utf-8')
    print(f" -> Reality Prime written to {out_path.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    collapse_superposition(Path(args.run_dir))
