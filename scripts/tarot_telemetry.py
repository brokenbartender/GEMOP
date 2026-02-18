import json
import os
import psutil
import time
from pathlib import Path

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

def draw_spread():
    root = get_repo_root()
    registry_path = root / "data/tarot_registry.json"
    if not registry_path.exists():
        return

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    
    # 1. Gather Physical Telemetry
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    spread = {
        "ts": time.time(),
        "active_cards": []
    }

    # 2. Map Metrics to Minor Arcana (Stacks)
    if cpu > 80:
        spread["active_cards"].append({"id": "10_of_Wands", "name": "CPU Overload", "suit": "Fire"})
    elif cpu < 10:
        spread["active_cards"].append({"id": "4_of_Swords", "name": "Sleep Mode", "suit": "Air"})
    else:
        spread["active_cards"].append({"id": "Ace_of_Wands", "name": "Process Spark", "suit": "Fire"})

    if ram > 80:
        spread["active_cards"].append({"id": "7_of_Cups", "name": "Feature Bloat", "suit": "Water"})
    else:
        spread["active_cards"].append({"id": "Ace_of_Cups", "name": "Data Flow", "suit": "Water"})

    # 3. Check Logs for Major Arcana (Kernel Events)
    # (Simplified: Just check for recent run directories)
    jobs_dir = root / ".agent-jobs"
    if jobs_dir.exists():
        latest_runs = list(jobs_dir.glob("run_*"))
        if latest_runs:
            spread["active_cards"].append({"id": "X_Wheel_of_Fortune", "name": "Active Scheduler", "role": "Kernel"})

    # 4. Persistence
    state_file = root / "state/tarot_spread.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(spread, indent=2), encoding="utf-8")
    print(f"[Tarot] Spread updated at {state_file}")

if __name__ == "__main__":
    draw_spread()
