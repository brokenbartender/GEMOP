import time
import json
import os
from pathlib import Path
import sys

# Add scripts to path
sys.path.append(os.path.dirname(__file__))
from agent_runner_v2 import call_gemini_cloud_modern

def run_meta_agent():
    print("--- 🧬 RECURSIVE META-AGENT: Evolving ---")
    repo_root = Path(__file__).resolve().parents[1]
    metrics_path = repo_root / ".agent-jobs"
    policy_path = repo_root / "ramshare" / "strategy" / "adaptive_policy.json"
    
    # Ensure policy exists
    if not policy_path.exists():
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(json.dumps({"global_constraints": []}, indent=2))

    processed_lines = set()
    
    try:
        while True:
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] Meta-Agent scanning for system mutations...")
            # 1. Scan for recent failures across all runs
            failures = []
            for mfile in metrics_path.rglob("agent_metrics.jsonl"):
                try:
                    with open(mfile, "r", encoding="utf-8") as f:
                        for line in f:
                            # Simple dedup based on content hash or timestamp+agent
                            if hash(line) in processed_lines: continue
                            processed_lines.add(hash(line))
                            
                            data = json.loads(line)
                            if not data.get("ok"):
                                failures.append(data)
                except: continue

            # 2. Analyze Failures
            if failures:
                print(f"[Meta] Detected {len(failures)} new failures. Analyzing...")
                
                # Group by error type/role
                error_context = "\\n".join([
                    f"- Role: {f.get('role')} | Error: {f.get('error') or 'Unknown'} | Duration: {f.get('duration_s')}"
                    for f in failures[:5] # Analyze batch of 5
                ])

                # 3. Evolve Policy
                prompt = f"""
                [SYSTEM EVOLUTION MODE]
                You are the Meta-Agent responsible for evolving the system's operating constraints.
                
                RECENT FAILURES:
                {error_context}
                
                CURRENT POLICY:
                {(policy_path.read_text() if policy_path.exists() else "{}")}
                
                TASK:
                Generate a new, specific global constraint or hint to prevent these failures.
                Focus on prompt engineering fixes (e.g., "Agents must verify X before Y").
                
                OUTPUT JSON ONLY:
                {{
                    "new_constraint": "The concise rule to add",
                    "reason": "Why this fixes the failure"
                }}
                """
                
                try:
                    # Use Flash for fast evolution
                    resp = call_gemini_cloud_modern(prompt, model="gemini-2.0-flash")
                    if resp:
                        # Extract JSON
                        import re
                        m = re.search(r"\{.*\}", resp, re.DOTALL)
                        if m:
                            new_rule = json.loads(m.group(0))
                            
                            # Load current policy
                            policy = json.loads(policy_path.read_text())
                            policy.setdefault("global_constraints", [])
                            
                            # Add unique constraint
                            if new_rule["new_constraint"] not in policy["global_constraints"]:
                                policy["global_constraints"].append(new_rule["new_constraint"])
                                policy_path.write_text(json.dumps(policy, indent=2))
                                print(f"[Meta] 🧬 EVOLUTION: Added constraint -> {new_rule['new_constraint']}")
                except Exception as e:
                    print(f"[Meta] Evolution failed: {e}")

            time.sleep(10) # Pulse check

    except KeyboardInterrupt:
        print("\n[Meta] Dormant.")

if __name__ == "__main__":
    run_meta_agent()
