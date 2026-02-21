import argparse
import math
import sys
from pathlib import Path

# Gravitational Constant (Arbitrary High Value for Thought Space)
G = 6.674e-1

def calculate_gravity(mass_obj: float, mass_thought: float, distance: float) -> float:
    """
    Newton's Law of Universal Gravitation applied to Cognition.
    F = G * (m1 * m2) / r^2
    """
    if distance == 0:
        return float('inf') # Singularity
    return G * (mass_obj * mass_thought) / (distance ** 2)

def calculate_semantic_distance(anchor_text: str, thought_text: str) -> float:
    """
    Calculates the 'Distance' in Semantic Space.
    Lower distance = Higher relevance.
    """
    # Simplified Distance: Keyword overlap inverse ratio
    # In production, this uses Vector Cosine Similarity (1 - similarity)
    anchor_words = set(w.lower() for w in anchor_text.split() if len(w) > 4)
    thought_words = set(w.lower() for w in thought_text.split() if len(w) > 4)
    
    if not anchor_words:
        return 100.0 # Far away
        
    overlap = len(anchor_words.intersection(thought_words))
    if overlap == 0:
        return 1000.0 # Light years away
    
    # Distance is inverse of overlap density
    return 10.0 / overlap

def apply_gravity(run_dir: Path):
    """
    The Gravity Well: Warps the context space around the Mission Anchor.
    """
    anchor_path = run_dir / "state" / "mission_anchor.md"
    if not anchor_path.exists():
        return

    anchor_text = anchor_path.read_text(encoding='utf-8', errors='ignore')
    mass_mission = 1000.0 # The Mission is Supermassive

    print(f"[Gravity] Mission Mass: {mass_mission}kg. Warping Space-Time...")

    files = sorted(run_dir.glob("round*_agent*.md"))
    for f in files:
        content = f.read_text(encoding='utf-8', errors='ignore')
        mass_thought = 10.0 # Standard thought mass
        
        r = calculate_semantic_distance(anchor_text, content)
        force = calculate_gravity(mass_mission, mass_thought, r)
        
        # Event Horizon Check
        if force > 0.5:
            print(f" -> {f.name}: Force={force:.4f}N. ORBIT STABLE. (Retained)")
        else:
            print(f" -> {f.name}: Force={force:.4f}N. ESCAPE VELOCITY. (Drifting into Void)")
            # In a full system, we would mark this file for 'Vacuum Decay' (Pruning)

def main():
    parser = argparse.ArgumentParser(description="Einstein Relativist: Gravity Well.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    apply_gravity(Path(args.run_dir))

if __name__ == "__main__":
    main()
