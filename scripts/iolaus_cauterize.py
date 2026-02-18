import argparse
import json
import os
import subprocess
import time
from pathlib import Path

def cauterize_hydra(run_dir: Path, agent_id: int = 0, round_num: int = 0, lyapunov_kill: bool = False):
    """
    Scans pids.json for 'Hydra heads' or kills specific Lyapunov-diverged threads.
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

    if lyapunov_kill and agent_id > 0 and round_num > 0:
        print(f"[Iolaus] LYAPUNOV KILL: Divergence detected for Agent {agent_id} in Round {round_num}. Neutralizing...")
        for e in entries:
            if e['agent'] == agent_id and e['round'] == round_num:
                pid = e['pid']
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                    print(f" -> PID {pid} cauterized.")
                except Exception:
                    pass
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
    parser.add_argument("--agent", type=int, default=0)
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--lyapunov", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    cauterize_hydra(run_dir, args.agent, args.round, args.lyapunov)

if __name__ == "__main__":
    main()
