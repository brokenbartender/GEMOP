import json
import os
import re
from pathlib import Path
import sys

# Add scripts to path for agent_runner
sys.path.append(os.path.dirname(__file__))
from agent_runner_v2 import call_gemini_cloud_modern

def consolidate_state(run_dir_path, round_n):
    run_dir = Path(run_dir_path)
    mem1_path = run_dir / "state" / "mem1_consolidated_state.md"
    
    current_state = ""
    if mem1_path.exists():
        current_state = mem1_path.read_text(encoding="utf-8")
    else:
        current_state = "Mission Initialized."

    # Collect all updates from this round
    updates = []
    for out_file in run_dir.glob(f"round{round_n}_agent*.md"):
        try:
            text = out_file.read_text(encoding="utf-8")
            # Extract [MEM1_UPDATE] content
            match = re.search(r"\[MEM1_UPDATE\](.*?)($|COMPLETED)", text, re.DOTALL | re.IGNORECASE)
            if match:
                updates.append(match.group(1).strip())
        except: continue

    if not updates:
        print(f"[MEM1] No updates found in round {round_n}.")
        return

    # Synthesize using a fast model (Flash)
    prompt = f"""
    You are the MEM1 State Consolidator. 
    CURRENT INTERNAL STATE:
    {current_state}

    NEW UPDATES FROM ROUND {round_n}:
    {chr(10).join(['- ' + u for u in updates])}

    TASK:
    Synthesize the current state and new updates into a single, compact, cohesive paragraph (max 150 words).
    Preserve all critical technical decisions and file paths.
    Output ONLY the synthesized paragraph.
    """
    
    try:
        # Using Gemini Flash for cheap synthesis
        new_state = call_gemini_cloud_modern(prompt, model="gemini-2.0-flash")
        if new_state:
            mem1_path.write_text(new_state.strip(), encoding="utf-8")
            print(f"[MEM1] Consolidated state updated for round {round_n}.")
    except Exception as e:
        print(f"[MEM1] Synthesis failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        consolidate_state(sys.argv[1], sys.argv[2])
