import json
import time
import sys
import socket
from pathlib import Path
import urllib.request

def measure_latency(url):
    try:
        t0 = time.time()
        urllib.request.urlopen(url, timeout=5)
        return round((time.time() - t0) * 1000, 2)
    except:
        return -1.0 # Static / Offline

def run_radio(run_dir: Path):
    """
    Continuous background latency sensor.
    Listens to the 'Static' in the network.
    """
    print("--- SPIRIT RADIO: Tuning to the Ether ---")
    broadcast_path = run_dir / "state" / "spirit_radio_broadcast.json"
    broadcast_path.parent.mkdir(parents=True, exist_ok=True)

    endpoints = {
        "gemini_api": "https://google.com", # Proxy for API reachability
        "github": "https://github.com",
        "local_ollama": "http://127.0.0.1:11434"
    }

    try:
        while True:
            signals = {}
            for name, url in endpoints.items():
                latency = measure_latency(url)
                signals[name] = latency
            
            # Record the broadcast
            data = {
                "signals": signals,
                "overall_static": sum(1 for l in signals.values() if l > 1000 or l < 0),
                "ts": time.time()
            }
            
            broadcast_path.write_text(json.dumps(data), encoding="utf-8")
            
            # Quiet log
            latency_str = " | ".join([f"{k}: {v}ms" for k, v in signals.items()])
            sys.stdout.write(f"\r[Radio] {latency_str}   ")
            sys.stdout.flush()
            
            time.sleep(5) # Sample every 5 seconds
    except KeyboardInterrupt:
        print("\n[Radio] Station offline.")
    except Exception as e:
        print(f"\n[Radio] Frequency lost: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_radio(Path(args.run_dir))
