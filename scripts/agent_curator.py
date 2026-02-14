import os
import sys
import argparse
import difflib
from pathlib import Path

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
ROLES_DIR = REPO_ROOT / "agents/roles"

def calculate_similarity(text1, text2):
    return difflib.SequenceMatcher(None, text1, text2).ratio()

def main():
    parser = argparse.ArgumentParser(description="Gemini Agent Curator - Deduplication Engine")
    parser.add_argument("--new-role-content", help="Content of the proposed new role")
    parser.add_argument("--new-role-id", help="ID of the proposed new role")
    args = parser.parse_args()

    if not args.new_role_content:
        print("Error: --new-role-content is required", file=sys.stderr)
        sys.exit(1)

    existing_roles = list(ROLES_DIR.glob("*.md"))
    found_match = None
    max_sim = 0.0

    for role_file in existing_roles:
        content = role_file.read_text(encoding="utf-8")
        sim = calculate_similarity(args.new_role_content, content)
        if sim > max_sim:
            max_sim = sim
            found_match = role_file.stem

    if max_sim > 0.80:
        print(f"MATCH_FOUND: {found_match} (Similarity: {max_sim:.2%})")
        print(f"ACTION: Use existing role '{found_match}' or merge instructions.")
    else:
        print(f"NO_MATCH: Highest similarity was {max_sim:.2%}")
        print("ACTION: Proceed with new role creation.")

if __name__ == "__main__":
    main()
