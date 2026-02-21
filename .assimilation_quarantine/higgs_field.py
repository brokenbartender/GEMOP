import argparse
import sys

def calculate_mass(token: str) -> float:
    """
    The Higgs Interaction: Determines the 'Mass' (Meaning) of a token.
    """
    # Interaction Cross-Section (Keyword Dictionary)
    heavy_bosons = {
        "architecture": 100.0, "security": 100.0, "critical": 90.0,
        "deploy": 85.0, "delete": 95.0, "auth": 90.0, "key": 80.0,
        "database": 70.0, "financial": 100.0
    }
    
    light_photons = {
        "the", "a", "is", "of", "to", "in", "and", "it", "that"
    }
    
    t = token.lower().strip(".,!?;:")
    
    if t in heavy_bosons:
        return heavy_bosons[t]
    if t in light_photons:
        return 0.0 # Massless
    return 5.0 # Standard matter

def scan_field(text: str):
    """
    Scans the text stream for High-Mass anomalies.
    """
    tokens = text.split()
    total_mass = 0.0
    max_particle = 0.0
    
    for t in tokens:
        m = calculate_mass(t)
        total_mass += m
        if m > max_particle:
            max_particle = m
            
    density = total_mass / len(tokens) if tokens else 0
    
    print(f"[Higgs] Field Scan Complete.")
    print(f" -> Total Mass: {total_mass}")
    print(f" -> Max Particle Mass: {max_particle}")
    
    if max_particle > 80.0:
        print("[Higgs] HEAVY OBJECT DETECTED. Slowing local time for deep processing.")
        print(" -> Action: Increase MaxRounds. Engage Signet Verifier.")
        return "heavy"
    else:
        print("[Higgs] Massless Radiation. Passing at light speed.")
        return "light"

def main():
    parser = argparse.ArgumentParser(description="Higgs Mechanism: Mass Generator.")
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    scan_field(args.text)

if __name__ == "__main__":
    main()
