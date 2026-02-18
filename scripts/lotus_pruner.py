import argparse
import os
import json
from pathlib import Path

def prune_context(run_dir: Path, max_rounds_to_keep: int = 2):
    """
    Induces 'Lotus Forgetfulness' by moving old round artifacts to a 
    '.lotus_history' folder to keep the active context window clean.
    """
    state_dir = run_dir / "state"
    lotus_dir = run_dir / ".lotus_history"
    lotus_dir.mkdir(parents=True, exist_ok=True)

    # Find all round outputs
    rounds = {}
    for f in run_dir.glob("round*_agent*.md"):
        try:
            # Extract round number from filename: round1_agent1.md
            round_num = int(f.name.split("_")[0].replace("round", ""))
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(f)
        except Exception:
            continue

    if not rounds:
        return

    # Determine which rounds to forget
    sorted_rounds = sorted(rounds.keys(), reverse=True)
    if len(sorted_rounds) <= max_rounds_to_keep:
        print(f"[Lotus] Memory is clear ({len(sorted_rounds)} active rounds). No pruning needed.")
        return

    rounds_to_forget = sorted_rounds[max_rounds_to_keep:]
    
    print(f"[Lotus] Pruning rounds {rounds_to_forget} to free up context...")
    
    for r in rounds_to_forget:
        for f in rounds[r]:
            # Move to history
            dest = lotus_dir / f.name
            os.replace(f, dest)
            print(f" -> {f.name} sent to history.")

def main():
    parser = argparse.ArgumentParser(description="Lotus Flower: Context & Memory Management.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--keep", type=int, default=2, help="Number of recent rounds to keep in active memory.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print("Run directory not found.")
        return

    prune_context(run_dir, args.keep)

if __name__ == "__main__":
    main()
