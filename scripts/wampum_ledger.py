import argparse
import hashlib
import json
import time
from pathlib import Path

def sign_treaty(run_dir: Path, agent_id: int, round_num: int, decision: dict):
    """
    Records a decision as an immutable Wampum Treaty.
    """
    wampum_path = run_dir / "state" / "wampum.jsonl"
    
    # Create a unique hash for this decision
    decision_str = json.dumps(decision, sort_keys=True)
    decision_hash = hashlib.sha256(decision_str.encode()).hexdigest()
    
    treaty = {
        "ts": time.time(),
        "agent": agent_id,
        "round": round_num,
        "hash": decision_hash,
        "decision": decision,
        "sig": f"WAMPUM-{agent_id}-{round_num}"
    }
    
    # Simple spin-lock for thread safety
    lock_path = wampum_path.with_suffix(".lock")
    timeout = 5.0
    start = time.time()
    while lock_path.exists():
        if time.time() - start > timeout:
            print("[Wampum] Lock timeout. Forcing write.")
            break
        time.sleep(0.1)
    
    try:
        lock_path.touch()
        with open(wampum_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(treaty) + "\n")
    finally:
        if lock_path.exists():
            lock_path.unlink()
    
    print(f"[Wampum] Treaty Signed for Agent {agent_id} Round {round_num}: {decision_hash[:8]}")

def main():
    parser = argparse.ArgumentParser(description="Wampum Belt: Immutable Treaty Ledger.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--agent", type=int, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--decision-file", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    decision_path = Path(args.decision_file)
    
    if not decision_path.exists():
        print("Decision file not found.")
        return

    try:
        decision = json.loads(decision_path.read_text(encoding='utf-8', errors='ignore'))
        sign_treaty(run_dir, args.agent, args.round, decision)
    except Exception as e:
        print(f"Failed to sign treaty: {e}")

if __name__ == "__main__":
    main()
