import mmap
import os
import json
import time
import sys
from pathlib import Path

# The Standing Wave Frequency (File Size)
WAVE_SIZE = 1024 * 1024 # 1MB

def broadcast_state(run_dir: Path, state_key: str, value: dict):
    """
    Injects a signal into the Telluric current.
    """
    wave_path = run_dir / "state" / "telluric_wave.bin"
    
    # Ensure the wave medium exists
    if not wave_path.exists():
        with open(wave_path, "wb") as f:
            f.write(b"\0" * WAVE_SIZE)

    try:
        with open(wave_path, "r+b") as f:
            with mmap.mmap(f.fileno(), WAVE_SIZE) as mm:
                # Read existing state map
                try:
                    # Find the null terminator of the current JSON
                    current_data = mm.read(WAVE_SIZE).rstrip(b"\0")
                    if current_data:
                        state = json.loads(current_data)
                    else:
                        state = {}
                except:
                    state = {}

                # Update the specific frequency (key)
                state[state_key] = {
                    "value": value,
                    "ts": time.time()
                }
                
                # Resonate (Write back)
                new_data = json.dumps(state).encode("utf-8")
                if len(new_data) > WAVE_SIZE:
                    print("[Wardenclyffe] ALERT: Signal clipping. State too large for wave.")
                    return

                mm.seek(0)
                mm.write(new_data)
                mm.write(b"\0" * (WAVE_SIZE - len(new_data))) # Zero out rest
                print(f"[Wardenclyffe] Signal '{state_key}' broadcasted to the Earth.")
    except Exception as e:
        print(f"[Wardenclyffe] Interference detected: {e}")

def tune_in(run_dir: Path, state_key: str):
    """
    Taps into the earth current to read a specific frequency.
    """
    wave_path = run_dir / "state" / "telluric_wave.bin"
    if not wave_path.exists():
        return None

    try:
        with open(wave_path, "r+b") as f:
            with mmap.mmap(f.fileno(), WAVE_SIZE, access=mmap.ACCESS_READ) as mm:
                current_data = mm.read(WAVE_SIZE).rstrip(b"\0")
                if not current_data:
                    return None
                
                state = json.loads(current_data)
                if state_key in state:
                    return state[state_key]["value"]
    except:
        return None
    return None

if __name__ == "__main__":
    # CLI for testing
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--key")
    parser.add_argument("--val")
    parser.add_argument("--read", action="store_true")
    args = parser.parse_args()

    rd = Path(args.run_dir)
    if args.read and args.key:
        print(json.dumps(tune_in(rd, args.key), indent=2))
    elif args.key and args.val:
        broadcast_state(rd, args.key, json.loads(args.val))
