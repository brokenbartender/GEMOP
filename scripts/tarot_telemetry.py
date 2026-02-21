import json
import time
import sys
from pathlib import Path
import mmap

# The Standing Wave Frequency
WAVE_SIZE = 1024 * 1024

def read_resonance(run_dir: Path):
    wave_path = run_dir / "state" / "telluric_wave.bin"
    if not wave_path.exists(): return {}
    try:
        with open(wave_path, "r+b") as f:
            with mmap.mmap(f.fileno(), WAVE_SIZE, access=mmap.ACCESS_READ) as mm:
                data = mm.read(WAVE_SIZE).rstrip(b"\0")
                return json.loads(data) if data else {}
    except: return {}

def read_radio(run_dir: Path):
    radio_path = run_dir / "state" / "spirit_radio_broadcast.json"
    if not radio_path.exists(): return {}
    try:
        return json.loads(radio_path.read_text(encoding="utf-8"))
    except: return {}

def draw_cards(run_dir: Path):
    """
    Heuristic Warning Engine.
    Interprets raw signals into 'Fates' (System Events).
    """
    print("--- TAROT TELEMETRY: Drawing the Fates ---")
    
    # 1. State Tracking
    history = []
    
    try:
        while True:
            resonance = read_resonance(run_dir)
            radio = read_radio(run_dir)
            
            fate = "The Fool (Stable)"
            action_needed = None
            
            # --- THE CARDS ---
            
            # The Tower: Rapid Memory Growth
            ram_pct = resonance.get("ram_percent", 0)
            if ram_pct > 90:
                fate = "The Tower (Memory Exhaustion)"
                action_needed = "PRUNE_MEMORY"
            
            # The Hanged Man: High Latency / Stalls
            ollama_lat = radio.get("signals", {}).get("local_ollama", 0)
            if ollama_lat > 2000 or ollama_lat < 0:
                fate = "The Hanged Man (Service Stall)"
                action_needed = "RESTART_DAEMONS"
            
            # Death: Critical Overload
            cpu_load = resonance.get("cpu_percent", 0)
            if cpu_load > 95 and ram_pct > 95:
                fate = "Death (System Collapse Imminent)"
                action_needed = "HARD_ABORT"

            # 2. Log the Fate
            if action_needed:
                print(f"\n[FATE] {fate} detected! Triggering {action_needed}...")
                # Signal the bus
                bus_cmd = f"python scripts/council_bus.py signal --run-dir {run_dir} --agent tarot --type emergency --note '{fate}'"
                import subprocess
                subprocess.run(bus_cmd, shell=True)
            
            sys.stdout.write(f"\r[Tarot] Current Fate: {fate}   ")
            sys.stdout.flush()
            
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[Tarot] The future is obscured.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    draw_cards(Path(args.run_dir))
