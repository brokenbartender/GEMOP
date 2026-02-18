import argparse
import json
import sys
from pathlib import Path

def check_alignment(anchor_text: str, current_output: str) -> bool:
    """
    Placeholder for Zhinan Alignment logic.
    In a full implementation, this uses a specialized 'Compass' LLM
    to calculate the semantic distance between the current state 
    and the original mission objective.
    """
    if not anchor_text or not current_output:
        return True # Default to OK if missing context
    
    # Simple check: Is the agent talking about the core task keywords?
    # (In production, this would be a high-fidelity semantic vector comparison)
    keywords = [k.lower() for k in anchor_text.split() if len(k) > 4]
    matches = sum(1 for k in keywords if k in current_output.lower())
    
    if len(keywords) > 0 and (matches / len(keywords)) < 0.1:
        print("[Zhinan] ALERT: Significant Goal Drift detected. Logic no longer points South.")
        return False
        
    print("[Zhinan] ALIGNMENT OK: The figure points South.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Zhinan Chariot: Goal Alignment Monitor.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--round", type=int, required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    anchor_path = run_dir / "state" / "mission_anchor.md"
    
    if not anchor_path.exists():
        print("[Zhinan] No mission anchor found. Cannot align.")
        sys.exit(0)

    anchor = anchor_path.read_text(encoding='utf-8', errors='ignore')
    
    drift_detected = False
    for f in run_dir.glob(f"round{args.round}_agent*.md"):
        content = f.read_text(encoding='utf-8', errors='ignore')
        if not check_alignment(anchor, content):
            drift_detected = True
            print(f" -> Drift detected in {f.name}")

    if drift_detected:
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
