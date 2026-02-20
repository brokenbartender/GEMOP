import os
import time
import shutil
from pathlib import Path
import random

def trigger_chaos():
    repo_root = Path(__file__).resolve().parents[1]
    print("--- 🐒 CHAOS MONKEY: Injecting Turbulence ---")
    
    events = [
        "lock_memory",
        "starve_slots",
        "corrupt_manifest"
    ]
    
    event = random.choice(events)
    
    if event == "lock_memory":
        print("[Chaos] Locking neural_bus.db (SQLite)...")
        db_path = repo_root / "ramshare/neural_bus.db"
        if db_path.exists():
            # Open and hold lock
            f = open(db_path, "a")
            print(" -> DB LOCKED. System should switch to high-latency or fail gracefully.")
            time.sleep(30)
            f.close()
            print(" -> DB RELEASED.")

    elif event == "starve_slots":
        print("[Chaos] Filling all local slots with dummy locks...")
        slot_dir = repo_root / ".agent-jobs/run_chaos/state/local_slots"
        slot_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 10):
            (slot_dir / f"slot{i}.lock").write_text("pid=99999
agent_id=chaos")
        print(" -> SLOTS STARVED. Agents should trigger LOCAL_OVERLOAD.")
        time.sleep(30)
        # Cleanup
        for f in slot_dir.glob("*.lock"): f.unlink()
        print(" -> SLOTS CLEARED.")

    elif event == "corrupt_manifest":
        print("[Chaos] Creating a malformed manifest.json in latest run...")
        # Find latest run
        runs = sorted((repo_root / ".agent-jobs").iterdir(), key=os.path.getmtime, reverse=True)
        if runs:
            m = runs[0] / "state/manifest.json"
            if m.exists():
                old_text = m.read_text()
                m.write_text("{ 'invalid_json': True ", encoding="utf-8")
                print(f" -> MANIFEST CORRUPTED: {m.name}")
                time.sleep(20)
                m.write_text(old_text)
                print(" -> MANIFEST RESTORED.")

if __name__ == "__main__":
    trigger_chaos()
