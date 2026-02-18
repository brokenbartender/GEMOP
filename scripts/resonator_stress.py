import argparse
import random
import time
import sys
from pathlib import Path

def find_resonant_frequency(run_dir: Path):
    """
    The Earthquake Machine: Pulses the system with variable input frequencies
    to find the 'Shudder Point' (Hallucination/Failure).
    """
    print("[Resonator] Attaching oscillator to system foundation...")
    
    frequencies = [10, 50, 100, 500, 1000, 5000] # Input lengths in chars
    
    for freq in frequencies:
        print(f"[Resonator] Pulsing at {freq}Hz (chars)...")
        noise = "".join(random.choices("abcdefghijklmnopqrstuvwxyz ", k=freq))
        
        # Simulate processing load (In a real system, we'd hit the API)
        # Here we check if the system can 'absorb' the noise without crashing.
        try:
            # We "tap" the telluric wave to see if it holds
            start = time.time()
            # ... simulated stress ...
            time.sleep(freq / 10000.0) # Artificial latency
            duration = time.time() - start
            
            if duration > 1.0:
                print(f"[Resonator] RESONANCE DETECTED at {freq}Hz! System shuddered (High Latency).")
                return freq
        except Exception:
            print(f"[Resonator] STRUCTURAL FAILURE at {freq}Hz.")
            return freq

    print("[Resonator] Structure is stable. No resonant frequency found.")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Telegeodynamics: System Stress Tester.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    find_resonant_frequency(Path(args.run_dir))

if __name__ == "__main__":
    main()
