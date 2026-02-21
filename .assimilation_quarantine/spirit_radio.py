import argparse
import re
from pathlib import Path

def listen_to_vlf(run_dir: Path):
    """
    The Spirit Radio: Listens to the Noise Floor for Phantom Patterns.
    """
    print("[Spirit Radio] Tuning crystal receiver to VLF...")
    
    # We scan logs for 'ignored' or 'subtle' signals
    log_path = run_dir / "triad_orchestrator.log"
    if not log_path.exists():
        return

    content = log_path.read_text(encoding='utf-8', errors='ignore')
    
    # VLF Signatures (Subtle errors or hints)
    phantoms = {
        "user_preference": r"user (?:likes|hates|prefers|wants) (\w+)",
        "hidden_error": r"(?:warn|trace|debug):.*?(slow|leak|retry)",
        "ghost_agent": r"agent (\d+) (?:stalled|silent|waiting)"
    }
    
    alerts = []
    for kind, pattern in phantoms.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # We found a signal in the static
            msg = f"PHANTOM DETECTED ({kind}): {matches}"
            alerts.append(msg)
            print(f"[Spirit Radio] {msg}")
            
    if alerts:
        # Amplify the signal
        alert_path = run_dir / "state" / "spirit_radio_broadcast.txt"
        alert_path.parent.mkdir(parents=True, exist_ok=True)
        alert_path.write_text("\n".join(alerts), encoding="utf-8")
        print("[Spirit Radio] Signal Amplified to Main Bus.")
    else:
        print("[Spirit Radio] Static only. The ether is quiet.")

def main():
    parser = argparse.ArgumentParser(description="Spirit Radio: VLF Listener.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    listen_to_vlf(Path(args.run_dir))

if __name__ == "__main__":
    main()
