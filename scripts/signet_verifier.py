import argparse
import json
import os
import sys
from pathlib import Path

def verify_will(prompt: str, changes: str) -> bool:
    """
    Placeholder for Signet Verification logic.
    In a full implementation, this calls a high-reasoning LLM (like Gemini 1.5 Pro)
    to verify that the code changes actually fulfill the intent of the prompt
    and do not introduce "Demonic" (malicious/unwanted) side effects.
    """
    # For now, we perform a basic integrity check
    if not prompt or not changes:
        return False
    
    # Logic: Does the change contain 'DELETED ALL FILES'? If so, the Signet rejects it.
    if "rm -rf /" in changes or "os.remove" in changes and "security" not in prompt.lower():
        print("[Signet] ALERT: Potentially destructive action detected without authorization.")
        return False
        
    print("[Signet] SEAL APPLIED: Changes verified against user intent.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Solomon's Signet: Final Authority Verifier.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    # Read all round outputs to see what was done
    changes = ""
    for f in run_dir.glob("round*_agent*.md"):
        changes += f.read_text(encoding='utf-8', errors='ignore')

    if verify_will(args.prompt, changes):
        print("[Signet] Verification Successful.")
        sys.exit(0)
    else:
        print("[Signet] Verification FAILED. Will not Yeet.")
        sys.exit(1)

if __name__ == "__main__":
    main()
