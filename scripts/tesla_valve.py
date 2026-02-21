import argparse
import sys
import re

def check_flow(premise: str, conclusion: str) -> bool:
    """
    The Tesla Valve: Ensures logic flows Forward (Premise -> Conclusion).
    Blocks Reverse Flow (Conclusion -> Premise).
    """
    if not premise or not conclusion:
        return True

    # Simplified Check: Does the premise appear IN the conclusion?
    # (Circular: A -> B, therefore A)
    # In a real system, this would use entercailment/NLI models.
    
    # "Eddy Current" detection:
    # If the conclusion repeats the premise words too closely, it's a loop.
    p_words = set(premise.lower().split())
    c_words = set(conclusion.lower().split())
    
    overlap = len(p_words.intersection(c_words))
    if len(c_words) > 0:
        ratio = overlap / len(c_words)
    else:
        ratio = 0
        
    if ratio > 0.8:
        print("[Tesla Valve] REVERSE FLOW DETECTED. Logic is circular (Eddy Current).")
        print(f" -> Premise: {premise[:50]}...")
        print(f" -> Conclusion: {conclusion[:50]}...")
        return False

    print("[Tesla Valve] Flow is Laminar. Causality preserved.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Tesla Valve: Logic Flow Diode.")
    parser.add_argument("--premise", required=True)
    parser.add_argument("--conclusion", required=True)
    args = parser.parse_args()

    if check_flow(args.premise, args.conclusion):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
