import json
import re
import time
from pathlib import Path
from collections import defaultdict

def index_wormholes(repo_root: Path):
    """
    Creates zero-latency shortcuts between conceptually linked files.
    """
    print("--- 🌀 WORMHOLE INDEXER: Folding Space ---")
    
    # 1. Define 'Singularities' (Unique Identifiers)
    # Regex for distinct entities: Project IDs, specific variable names, error codes
    patterns = {
        "project_id": r"PROJECT-[A-Z0-9]+",
        "error_code": r"ERR-[0-9]{4}",
        "class_def": r"class ([A-Z][a-zA-Z0-9]+)",
        "func_def": r"def ([a-z_][a-z0-9_]+)\("
    }
    
    index = defaultdict(list)
    
    # 2. Scan the Universe (Ramshare + Scripts)
    scan_paths = [
        repo_root / "scripts",
        repo_root / "ramshare" / "notes",
        repo_root / "ramshare" / "evidence"
    ]
    
    for base in scan_paths:
        if not base.exists(): continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in ['.py', '.md', '.json', '.ps1']:
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(f.relative_to(repo_root))
                    
                    for p_name, p_regex in patterns.items():
                        matches = set(re.findall(p_regex, content))
                        for m in matches:
                            if len(m) > 4: # Ignore short noise
                                index[m].append(rel_path)
                except: pass

    # 3. Collapse the Map
    # Only keep entities that appear in 2+ files (a link)
    wormhole_map = {k: v for k, v in index.items() if len(v) > 1}
    
    out_path = repo_root / "ramshare" / "state" / "wormhole_map.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(wormhole_map, indent=2))
    
    print(f" -> Stabilized {len(wormhole_map)} wormholes.")
    # Preview top links
    top_links = sorted(wormhole_map.items(), key=lambda x: len(x[1]), reverse=True)[:3]
    for k, v in top_links:
        print(f"    * {k} connects {len(v)} locations")

if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    index_wormholes(repo)
