import re

def find_unbalanced_braces(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    depth = 0
    for i, line in enumerate(lines):
        # Remove comments and strings to avoid false positives
        line = re.sub(r'#.*$', '', line)
        line = re.sub(r'".*?"', '', line)
        line = re.sub(r"'.*?'", '', line)
        
        opens = line.count('{')
        closes = line.count('}')
        
        old_depth = depth
        depth += opens - closes
        
        if depth < 0:
            print(f"ERROR: Negative depth at line {i+1}: {line.strip()} (Depth: {depth})")
            return
            
    print(f"Final depth: {depth}")
    if depth > 0:
        print("ERROR: Missing closing braces.")

if __name__ == "__main__":
    find_unbalanced_braces('scripts/triad_orchestrator.ps1')
