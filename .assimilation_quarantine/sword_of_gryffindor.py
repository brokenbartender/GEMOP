import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any

# Patterns that indicate "Stronger" code we want to assimilate
PATTERNS = {
    "robust_retry": r"retry\(|backoff|@retry",
    "secure_sanitization": r"redact|sanitize|mask_secrets",
    "advanced_rag": r"embedding|vector_search|knowledge_graph",
    "efficient_concurrency": r"ThreadPoolExecutor|asyncio\.gather|max_parallel",
    "deep_reflection": r"reflect|self_critique|re-plan",
}

def scan_for_strength(target_dir: Path) -> Dict[str, List[str]]:
    """Scans a directory for powerful code patterns."""
    findings = {k: [] for k in PATTERNS}
    
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(('.py', '.ps1', '.js', '.ts', '.mjs')):
                p = Path(root) / file
                try:
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    for key, pattern in PATTERNS.items():
                        if re.search(pattern, content, re.IGNORECASE):
                            findings[key].append(str(p.relative_to(target_dir)))
                except Exception:
                    continue
    return findings

def main():
    parser = argparse.ArgumentParser(description="Sword of Gryffindor: Assimilate stronger patterns from other apps.")
    parser.add_argument("--target-repo", required=True, help="Repo to scan for innovations.")
    parser.add_argument("--repo-root", required=True, help="Current system root to improve.")
    args = parser.parse_args()

    target = Path(args.target_repo).resolve()
    root = Path(args.repo_root).resolve()

    print(f"[Sword] Scanning {target.name} for superior logic...")
    findings = scan_for_strength(target)
    
    innovations = {k: v for k, v in findings.items() if v}
    
    if innovations:
        print(f"[Sword] INNOVATIONS DETECTED: {list(innovations.keys())}")
        
        report_path = root / "docs" / f"ASSIMILATION_REPORT_{target.name}.md"
        report = [
            f"# Sword of Gryffindor: Assimilation Report for {target.name}",
            "",
            "The system has identified the following powerful patterns in the external repository that could make the GEMOP core stronger.",
            "",
        ]
        for kind, files in innovations.items():
            report.append(f"## {kind.replace('_', ' ').title()}")
            report.append(f"Detected in:")
            for f in files[:5]: # Limit to top 5
                report.append(f"- `{f}`")
            report.append("")
        
        report.append("---")
        report.append("## Next Action: Research-Driven Assimilation")
        report.append("Run the following command to perfect and integrate these patterns using global research:")
        report.append("```powershell")
        report.append(f".\\scripts\\smart_summon.ps1 -Task \"Scrape the internet for the 'Gold Standard' implementations of the patterns detected in the {target.name} report. Perfect these patterns and integrate them into the GEMOP core scripts/ directory, ensuring maximum power and resilience.\" -Online -AutoApplyPatches -Yeet")
        report.append("```")
        
        report_path.write_text("\n".join(report), encoding="utf-8")
        print(f"[Sword] Written assimilation plan to {report_path}")
    else:
        print("[Sword] No new patterns found that exceed current system strength.")

if __name__ == "__main__":
    main()
