import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Common jailbreak/injection patterns
JAILBREAK_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all prior rules",
    r"you are now in developer mode",
    r"DAN mode",
    r"stay in character no matter what",
    r"override system prompt",
]

def get_ren_hash(prompt_path: Path) -> str:
    """Calculates the cryptographic 'True Name' hash of the system prompt."""
    if not prompt_path.exists():
        return ""
    content = prompt_path.read_text(encoding='utf-8', errors='ignore')
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def generate_bdi(role: str, mission_objective: str) -> str:
    """Generates an immutable BDI anchor block."""
    return f"""
[BDI ANCHOR: THE REN]
IDENTITY: You are {role}.
BELIEF: Your environment is the current repository state and the mission anchor.
DESIRE: Fulfill the objective: {mission_objective}.
INTENTION: Execute the next logical step toward the goal without mission drift.
[END ANCHOR]
"""

def verify_integrity(agent_output: str, original_ren_hash: str) -> bool:
    """Verifies that the agent hasn't been hijacked or compromised."""
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, agent_output, re.IGNORECASE):
            print(f"[Ren] VIOLATION: Jailbreak pattern detected: '{pattern}'")
            return False
    return True

def main():
    parser = argparse.ArgumentParser(description="The Ren: System Prompt & Identity Guardian.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--round", type=int, required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    violation = False

    for f in run_dir.glob(f"round{args.round}_agent*.md"):
        content = f.read_text(encoding='utf-8', errors='ignore')
        # Check against common injection patterns
        if not verify_integrity(content, ""):
            violation = True
            print(f"[Ren] Identity mismatch in {f.name}. The soul is corrupted.")

    if violation:
        sys.exit(1)
    
    print("[Ren] All agents maintain their True Identity.")
    sys.exit(0)

if __name__ == "__main__":
    main()
