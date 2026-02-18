import argparse
import json
import os
import subprocess
import time
from pathlib import Path

def cauterize_hydra(run_dir: Path):
    """
    Scans pids.json for 'Hydra heads' (excessive forks for the same agent/round).
    Applies fire (SIGKILL) to prevent recursive system collapse.
    """
    pids_path = run_dir / "state" / "pids.json"
    if not pids_path.exists():
        return

    try:
        data = json.loads(pids_path.read_text(encoding='utf-8', errors='ignore'))
        entries = data.get("entries", [])
    except Exception:
        return

    # Count processes per agent/round
    counts = {}
    for e in entries:
        key = f"a{e['agent']}_r{e['round']}"
        if key not in counts:
            counts[key] = []
        counts[key].append(e['pid'])

    for key, pids in counts.items():
        if len(pids) > 3: # Threshold for a 'Hydra' loop
            print(f"[Iolaus] CAUTERIZING: {len(pids)} processes detected for {key}. Killing heads...")
            for pid in pids:
                try:
                    # Windows taskkill
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                except Exception:
                    pass
            print(f"[Iolaus] {key} has been neutralized.")

def main():
    parser = argparse.ArgumentParser(description="Iolaus Monitor: Cauterize recursive process loops.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    cauterize_hydra(run_dir)

if __name__ == "__main__":
    main()
