import argparse
import os
import shutil
import ast
import subprocess
from pathlib import Path

def verify_tool_code(code: str) -> tuple[bool, str]:
    """Scans Python code for destructive patterns using AST."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if hasattr(node.func.value, 'id') and node.func.value.id in ['os', 'subprocess', 'shutil']:
                    if node.func.attr in ['system', 'popen', 'rmtree', 'remove']:
                        return False, f"Dangerous syscall detected: {node.func.value.id}.{node.func.attr}"
        return True, "Code passed static analysis."
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

def simulate_patch(repo_root: Path, patch_path: Path):
    """
    The Shield of Achilles: Simulates a world state change in a sandbox.
    """
    shield_dir = repo_root / ".shield_achilles"
    if shield_dir.exists():
        shutil.rmtree(shield_dir)
    
    # Create the 'Depiction of the Cosmos' (Workspace Clone)
    shield_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Achilles] Forging the Shield in {shield_dir}...")
    
    # Only copy necessary folders to keep it fast
    for folder in ["scripts", "docs", "mcp", "configs"]:
        src = repo_root / folder
        if src.exists():
            shutil.copytree(src, shield_dir / folder)

    # 2. Apply the 'Action' (The Patch)
    print(f"[Achilles] Simulating action outcomes...")
    try:
        # Check if patch applies cleanly in the shield
        cmd = ["git", "apply", "--check", str(patch_path.resolve())]
        result = subprocess.run(cmd, cwd=shield_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[Achilles] SIMULATION SUCCESS: The cosmos remains stable.")
            return True
        else:
            print(f"[Achilles] SIMULATION FAILED: War detected in the shield.\n{result.stderr}")
            return False
    except Exception as e:
        print(f"[Achilles] Error during simulation: {e}")
        return False
    finally:
        # 3. Destroy the Shield (Impermanence)
        shutil.rmtree(shield_dir)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()
    
    if simulate_patch(Path(args.repo_root), Path(args.patch)):
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    main()
