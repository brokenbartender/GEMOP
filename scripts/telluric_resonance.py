import mmap
import os
import json
import time
import sys
from pathlib import Path
import platform

try:
    import psutil
except ImportError:
    psutil = None

# The Standing Wave Frequency (File Size)
WAVE_SIZE = 1024 * 1024 # 1MB

def get_cpu_temp():
    """Attempt to get CPU temperature (Platform dependent)."""
    if not psutil: return 0.0
    try:
        if platform.system() == "Linux":
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                return temps['coretemp'][0].current
        # Windows/macOS support for temp is limited in psutil without extra drivers
    except: pass
    return 0.0

def run_sensor(run_dir: Path):
    """
    Continuous background hardware sensor.
    Broadcasting 'resonance' to memory-mapped file.
    """
    print("--- ⚡ TELLURIC RESONANCE: Sensing Ground State ---")
    wave_path = run_dir / "state" / "telluric_wave.bin"
    wave_path.parent.mkdir(parents=True, exist_ok=True)

    if not wave_path.exists():
        with open(wave_path, "wb") as f:
            f.write(b"\0" * WAVE_SIZE)

    try:
        with open(wave_path, "r+b") as f:
            with mmap.mmap(f.fileno(), WAVE_SIZE) as mm:
                while True:
                    if not psutil:
                        print("[Telluric] psutil not installed. Cannot sense.")
                        break
                    
                    # Sense the Ground State
                    data = {
                        "cpu_percent": psutil.cpu_percent(interval=1),
                        "cpu_count": psutil.cpu_count(),
                        "ram_avail_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                        "ram_percent": psutil.virtual_memory().percent,
                        "cpu_temp": get_cpu_temp(),
                        "ts": time.time()
                    }

                    # Broadcast
                    payload = json.dumps(data).encode("utf-8")
                    mm.seek(0)
                    mm.write(payload)
                    mm.write(b"\0" * (WAVE_SIZE - len(payload)))
                    
                    # Log to console quietly
                    sys.stdout.write(f"\r[Telluric] Resonance: CPU {data['cpu_percent']}% | RAM {data['ram_percent']}%   ")
                    sys.stdout.flush()
                    
                    time.sleep(2) # Pulse every 2 seconds
    except KeyboardInterrupt:
        print("\n[Telluric] Sensor powered down.")
    except Exception as e:
        print(f"\n[Telluric] Interference: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_sensor(Path(args.run_dir))
