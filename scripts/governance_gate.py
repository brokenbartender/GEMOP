from __future__ import annotations
import json
import sys
import time
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    run_dir = Path(sys.argv[1]).resolve()
    state_dir = run_dir / "state"
    plan_path = state_dir / "plan.json"
    brief_path = state_dir / "consolidated_brief.md"
    decision_path = state_dir / "decision.json"
    
    if not plan_path.exists():
        # Fallback for different job layouts
        plan_path = run_dir / "out" / "shared" / "plan.json"

    print("\n" + "!"*60)
    print("💂‍♂️ CHIEF OF STAFF: GOVERNANCE GATE ACTIVE")
    if brief_path.exists():
        print(f"Consolidated Brief: READY")
    else:
        print(f"Technical Plan: {plan_path.name}")
    print("WAITING FOR COMMANDER'S APPROVAL...")
    print("Commands: [PROCEED] [VETO] [MANUAL]")
    print("!"*60)

    # Clean up old decisions
    if decision_path.exists(): decision_path.unlink()

    while True:
        # 1. Check for UI Decision (decision.json)
        if decision_path.exists():
            try:
                data = json.loads(decision_path.read_text(encoding="utf-8"))
                action = data.get("action", "").upper()
                critique = data.get("critique", "")
                
                if action == "PROCEED":
                    print("? Approved via UI.")
                    sys.exit(0)
                elif action == "VETO":
                    print(f"? Vetoed via UI: {critique}")
                    (state_dir / "feedback.md").write_text(f"USER VETO: {critique}", encoding="utf-8")
                    sys.exit(1)
                elif action == "MANUAL":
                    print("?? Manual Mode via UI. Waiting for edit...")
                    decision_path.unlink() # Reset so it stops hitting this block
            except: pass

        # 2. Check for Terminal Input (non-blocking if possible, but simple for now)
        # Note: In some setups input() blocks the polling above. 
        # For the best UX, we rely on the UI polling mostly.
        time.sleep(1)

if __name__ == "__main__":
    main()
