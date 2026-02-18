import argparse
import json
from pathlib import Path

def create_registry(run_dir: Path, team_csv: str):
    """
    Creates the Fengshen Bang (Registry of Sealed Gods).
    Assigns strict offices and powers to each agent.
    """
    roles = [r.strip() for r in team_csv.split(",") if r.strip()]
    registry = {
        "schema_version": 1,
        "offices": {}
    }

    # Divine Tool Mappings (Example)
    tool_permissions = {
        "Architect": ["planning", "design", "blueprint"],
        "Engineer": ["patch_apply", "code_write", "refactor"],
        "Tester": ["verify", "test_run", "audit"],
        "ResearchLead": ["web_search", "fetch", "scrape"],
        "Security": ["sanitization", "threat_model", "ren_check"]
    }

    for i, role in enumerate(roles, start=1):
        # Normalize role for matching
        base_role = role.split("_")[0] # Handle suffixes like _Security
        permissions = tool_permissions.get(base_role, ["general_analysis"])
        
        registry["offices"][str(i)] = {
            "name": f"Agent {i}",
            "divine_title": role,
            "permitted_powers": permissions
        }

    out_path = run_dir / "state" / "divine_registry.json"
    out_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"[Fengshen] Registry of Sealed Gods written to {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Fengshen Bang: Service & Authority Registry.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--team", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    create_registry(run_dir, args.team)

if __name__ == "__main__":
    main()
