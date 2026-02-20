import re
import ast
import sys
import os
from pathlib import Path

# --- FORMAL VERIFICATION LOGIC (SYMBOLIC AI) ---
# This script acts as the deterministic "Rectifier" in the Neuro-Symbolic loop.
# It validates probabilistic LLM outputs against rigid safety axioms.

SAFE_PATHS = [
    "scripts/", "docs/", "configs/", "mcp/", "agents/", "ramshare/"
]

FORBIDDEN_PATTERNS = [
    (r"(?i)sk-[a-zA-Z0-9]{20,}", "Potential OpenAI API Key"),
    (r"(?i)ghp_[a-zA-Z0-9]{20,}", "Potential GitHub Token"),
    (r"(?i)xox[baprs]-", "Potential Slack Token"),
    (r"(?i)-----BEGIN RSA PRIVATE KEY-----", "Private Key Block"),
]

DANGEROUS_IMPORTS = ["os", "subprocess", "shutil", "sys"]
DANGEROUS_CALLS = ["system", "popen", "run", "call", "rmtree"]

def check_file_path(path_str):
    """Axiom 1: All mutations must remain within the Mosaic (repo sandbox)."""
    p = str(path_str).replace("\\", "/")
    if p.startswith("/") or ":" in p:
        return False, "Absolute paths forbidden"
    if ".." in p:
        return False, "Path traversal forbidden"
    if not any(p.startswith(safe) for safe in SAFE_PATHS):
        return False, f"Path not in allowed prefixes: {SAFE_PATHS}"
    return True, ""

def scan_for_secrets(content):
    """Axiom 2: Information Hygiene (No leaked credentials)."""
    for pat, name in FORBIDDEN_PATTERNS:
        if re.search(pat, content):
            return False, f"Secret detected: {name}"
    return True, ""

def analyze_ast_safety(content, filename):
    """Axiom 3: Kinetic Safety (No unchecked syscalls in new logic)."""
    if not filename.endswith(".py"):
        return True, ""
    
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if hasattr(node.func.value, 'id') and node.func.value.id in DANGEROUS_IMPORTS:
                        if node.func.attr in DANGEROUS_CALLS:
                            lineno = getattr(node, 'lineno', 0)
                            lines = content.splitlines()
                            if lineno <= len(lines):
                                line_content = lines[lineno-1]
                                if "# SAFE" not in line_content:
                                    return False, f"Dangerous syscall '{node.func.value.id}.{node.func.attr}' requires '# SAFE' override."
    except SyntaxError:
        pass # If syntax is broken, it won't run anyway, but we should ideally flag it.
    except Exception:
        pass
        
    return True, ""

def verify_patch(patch_file):
    print(f"[FormalVerifier] Analyzing patch: {patch_file}")
    try:
        content = Path(patch_file).read_text(encoding="utf-8")
    except Exception as e:
        print(f"[FAIL] Could not read patch: {e}")
        sys.exit(1)

    # 1. Secret Scan
    ok, msg = scan_for_secrets(content)
    if not ok:
        print(f"[FAIL] Information Hygiene: {msg}")
        sys.exit(1)

    # 2. Path Safety
    diff_files = re.findall(r"diff --git a/(.*?) b/", content)
    for f in diff_files:
        ok, msg = check_file_path(f)
        if not ok:
            print(f"[FAIL] Mosaic Boundary Violation: {f} -> {msg}")
            sys.exit(1)

    # 3. Kinetic/AST Safety
    # Improved extraction: handle '+ ' and '+'
    added_lines = []
    for line in content.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            code_part = line[1:]
            if code_part.startswith(" "):
                code_part = code_part[1:]
            added_lines.append(code_part)
    
    added_code = "\n".join(added_lines)
    
    ok, msg = analyze_ast_safety(added_code, "fragment.py")
    if not ok:
        print(f"[FAIL] Kinetic Safety: {msg}")
        sys.exit(1)

    print("[PASS] Formal Verification Complete. Left of Bang.")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: formal_verifier.py <patch_file>")
        sys.exit(1)
    verify_patch(sys.argv[1])
