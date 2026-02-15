import os
import sys
import json
import argparse
import google.genai as genai
import pathlib
import datetime as dt

# --- CONFIGURATION ---
REPO_ROOT = pathlib.Path(r"C:\Users\codym\gemini-op-clean")
LOG_FILE = REPO_ROOT / "foundry.log"
GCLOUD_KEY_FILE = REPO_ROOT / "gcloud_service_key.json"
# --- END CONFIGURATION ---

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now().isoformat()}] {msg}\n")

def configure_gemini():
    if GCLOUD_KEY_FILE.exists():
        try:
            with open(GCLOUD_KEY_FILE, 'r') as f:
                credentials_info = json.load(f)
            credentials = genai.Credentials.from_service_account_info(credentials_info)
            genai.configure(credentials=credentials)
            log("FOUNDRY: SUCCESS: Gemini configured with Service Account.")
            return True
        except Exception as e:
            log(f"FOUNDRY: Service Account config failed: {e}")
    return False

def get_team_recommendation(prompt):
    log("FOUNDRY: Routing to Gemini Cloud for team formulation.")
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    system_prompt = """
    You are the Agent Foundry. Your job is to analyze a mission prompt and select the optimal team of specialist agents.
    Available agents: architect, engineer, tester, researcher, security_officer, data_analyst, ChiefOfStaff, CouncilFacilitator, DocSpecialist.
    Respond with a single line: MISSION_TEAM: <agent1>, <agent2>, ...
    Example: MISSION_TEAM: architect, engineer, tester
    """
    
    full_prompt = f"{system_prompt}\n\nMISSION BRIEF:\n{prompt}"
    
    response = model.generate_content(full_prompt)
    
    for line in response.text.splitlines():
        if "MISSION_TEAM:" in line:
            return line.strip()
    return "MISSION_TEAM: architect, engineer, tester" # Fallback

# --- MAIN EXECUTION ---
GEMINI_CONFIGURED = configure_gemini()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    team_line = "MISSION_TEAM: architect, engineer, tester" # Default
    if GEMINI_CONFIGURED:
        try:
            team_line = get_team_recommendation(args.mission)
            print(team_line)
        except Exception as e:
            log(f"FOUNDRY: CRITICAL FAILURE: {e}")
    else:
        log("FOUNDRY: ERROR: No valid Gemini credentials. Using default team.")
    
    # Write manifest for the orchestrator
    team = [t.strip() for t in team_line.split(":")[1].split(",")]
    manifest_path = pathlib.Path(args.run_dir) / "team_manifest.json"
    manifest_path.write_text(json.dumps({"team": team}), encoding="utf-8")
