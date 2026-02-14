import os
import json
import argparse
import subprocess
import sys
from pathlib import Path

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
ROLES_DIR = REPO_ROOT / "agents/roles"
TRIAD_PACK_PATH = REPO_ROOT / "agents/packs/triad_autonomous.json"

def scan_roles():
    roles = {}
    for role_file in ROLES_DIR.glob("*.md"):
        role_id = role_file.stem
        roles[role_id] = role_file.read_text(encoding="utf-8")
    return roles

def call_gemini_foundry(mission, existing_roles):
    role_list = ", ".join(existing_roles.keys())
    prompt = f"""You are the Agent Foundry. 
Current Strike Team Roles: {role_list}

Mission Brief: {mission}

TASK:
1. Analyze if the current roles are sufficient for this mission.
2. If a specialized role is missing, design a new one.
3. If a new role is designed, output it in JSON format:
{{
  "new_role_needed": true,
  "role_id": "specialist_name",
  "markdown_content": "# Role: ...
## Persona...
## Mandates..."
}}
4. If no new role is needed, output:
{{
  "new_role_needed": false,
  "selected_roles": ["architect", "engineer", "tester", "etc"]
}}

STRICT RULES:
- Never create a redundant role.
- Use 'architect', 'engineer', 'tester' as the foundation.
- Output ONLY the JSON block.
"""
    
    # We use 'gemini' CLI to get the response. 
    # Note: This assumes 'gemini' is in path and authenticated.
    try:
        # Using --yolo to avoid confirmation prompts in this sub-call if possible, 
        # but standard 'gemini' might be better.
        # We'll use a temp file for the prompt to avoid shell escaping issues.
        temp_prompt = REPO_ROOT / ".gemini/tmp/foundry_prompt.txt"
        temp_prompt.parent.mkdir(parents=True, exist_ok=True)
        temp_prompt.write_text(prompt, encoding="utf-8")
        
        result = subprocess.run(
            ["gemini", "--model", "gemini-2.0-flash-exp", "-p", prompt],
            capture_output=True, text=True, encoding="utf-8"
        )
        
        if result.returncode != 0:
            print(f"Gemini call failed: {result.stderr}", file=sys.stderr)
            return None
            
        # Parse JSON from output
        output = result.stdout.strip()
        # Find JSON block
        start = output.find("{")
        end = output.rfind("}") + 1
        if start != -1 and end != 0:
            return json.loads(output[start:end])
        return None
    except Exception as e:
        print(f"Error calling Gemini: {e}", file=sys.stderr)
        return None

def update_triad_pack(role_id):
    if not TRIAD_PACK_PATH.exists():
        return
    
    with open(TRIAD_PACK_PATH, "r", encoding="utf-8") as f:
        pack = json.load(f)
    
    # Check if role already exists in pack
    existing_role_ids = [r["role_id"] for r in pack.get("roles", [])]
    if role_id not in existing_role_ids:
        pack["roles"].append({
            "role_id": role_id,
            "template": f"agents/roles/{role_id}.md"
        })
        with open(TRIAD_PACK_PATH, "w", encoding="utf-8") as f:
            json.dump(pack, f, indent=2)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Gemini Agent Foundry")
    parser.add_argument("--mission", required=True, help="The mission prompt/brief")
    parser.add_argument("--run-dir", help="The current run directory for IPC")
    args = parser.parse_args()

    existing_roles = scan_roles()
    print(f"Foundry: Scanning {len(existing_roles)} existing roles...")
    
    decision = call_gemini_foundry(args.mission, existing_roles)
    
    team_msg = ""
    if decision and decision.get("new_role_needed"):
        role_id = decision["role_id"]
        content = decision["markdown_content"]
        
        role_path = ROLES_DIR / f"{role_id}.md"
        role_path.write_text(content, encoding="utf-8")
        print(f"Foundry: Formulated new specialist: {role_id}")
        
        if update_triad_pack(role_id):
            print(f"Foundry: Registered {role_id} to triad pack.")
        else:
            print(f"Foundry: {role_id} already registered.")
            
        team_msg = f"Commander, for this mission, I am deploying architect and engineer, and I have formulated a new specialist: {role_id}."
        print(f"MISSION_TEAM: architect, engineer, {role_id}")
    elif decision:
        selected = decision.get("selected_roles", ["architect", "engineer", "tester"])
        team_msg = f"Commander, for this mission, I am deploying: {', '.join(selected)}."
        print(f"Foundry: Current team is sufficient: {', '.join(selected)}")
        print(f"MISSION_TEAM: {', '.join(selected)}")
    else:
        team_msg = "Commander, I am deploying the standard triad team for this mission."
        print("Foundry: Fallback to default triad.")
        print("MISSION_TEAM: architect, engineer, tester")

    if args.run_dir and team_msg:
        history_file = Path(args.run_dir) / "state" / "chat_history.jsonl"
        if history_file.exists():
            entry = {
                "role": "Deputy",
                "content": team_msg,
                "ts": __import__("time").time(),
                "processed": True
            }
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    main()
