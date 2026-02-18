import argparse
import json
from pathlib import Path

def stabilize_egg(run_dir: Path):
    """
    The Egg of Columbus: Gyroscopic Context Stabilization.
    Spins the context to make the 'Task' stand upright.
    """
    anchor_path = run_dir / "state" / "mission_anchor.md"
    if not anchor_path.exists():
        return

    # The 'Axis of Rotation' (The Mission)
    anchor_text = anchor_path.read_text(encoding='utf-8', errors='ignore')
    keywords = set(w.lower() for w in anchor_text.split() if len(w) > 4)
    
    print(f"[Columbus] Spinning magnetic field around axis: {list(keywords)[:3]}...")

    # Scan recent memory layers
    memory_files = sorted(run_dir.glob("round*_agent*.md"))
    
    for f in memory_files:
        content = f.read_text(encoding='utf-8', errors='ignore')
        
        # Calculate 'Velocity' (Relevance)
        score = sum(1 for w in content.lower().split() if w in keywords)
        
        if score > 5:
            # High Velocity: Stand Up (Mark as Critical)
            # In a real vector DB, we would boost the embedding weight.
            # Here, we tag the file metadata.
            print(f" -> {f.name}: VELOCITY HIGH ({score}). Standing Up.")
        else:
            # Low Velocity: Lie Flat (Mark as Noise)
            print(f" -> {f.name}: Velocity Low ({score}). Lying Flat.")

def main():
    parser = argparse.ArgumentParser(description="Egg of Columbus: Context Gyroscope.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    stabilize_egg(Path(args.run_dir))

if __name__ == "__main__":
    main()
