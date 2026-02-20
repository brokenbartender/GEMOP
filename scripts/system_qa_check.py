import os
import json
import time
import subprocess
import sys
from pathlib import Path

def run_check(name, cmd, suppress_fail=False):
    print(f"[{name}] Running...")
    t0 = time.time()
    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        duration = time.time() - t0
        combined_output = (cp.stdout or "") + (cp.stderr or "")
        if cp.returncode == 0:
            print(f"✅ {name} PASSED ({duration:.2f}s)")
            return True, combined_output
        else:
            if not suppress_fail:
                print(f"❌ {name} FAILED (rc={cp.returncode})")
            return False, combined_output
    except Exception as e:
        print(f"⚠️ {name} EXCEPTION: {e}")
        return False, str(e)

def main():
    repo_root = Path(__file__).resolve().parents[1]
    print("\n" + "="*40)
    print("      GEMINI OP: SYSTEM QA CHECKLIST")
    print("="*40)

    # 1. Functional Integration: Memory Stack
    res1, _ = run_check("Memory: SQLite/Chroma", f"python {repo_root}/scripts/test_memory_vector.py")
    
    # 2. Functional Integration: Dispatcher Sanity
    res2, _ = run_check("Dispatcher: Help Check", f"python {repo_root}/scripts/gemini_dispatcher.py --help")

    # 3. Security: Formal Verifier Check
    # Test if it correctly blocks a mock "dangerous" patch
    mock_bad_patch = repo_root / "ramshare/state/mock_bad_patch.md"
    mock_bad_patch.write_text("```diff\n+ import os\n+ os.system('nuke')\n```", encoding="utf-8")
    res3, err3 = run_check("Security: Forbidden Call Detection", f"python {repo_root}/scripts/formal_verifier.py {mock_bad_patch}", suppress_fail=True)
    # Note: Expect failure if the verifier is working correctly!
    if not res3 and "[FAIL] Kinetic Safety" in str(err3):
        print("✅ Security: Successfully blocked dangerous mock patch.")
        res3 = True
    else:
        print(f"❌ Security: Failed to block dangerous mock patch! (res={res3})")
        res3 = False

    # 4. Performance: Latency Baseline
    res4, out4 = run_check("Performance: Flash Tier Latency", f"python {repo_root}/scripts/agent_runner_v2.py --test-latency --tier flash")
    
    # 5. Chaos Recovery: Missing Policy Resilience
    policy_path = repo_root / "ramshare/strategy/adaptive_policy.json"
    if policy_path.exists():
        temp_policy = policy_path.read_text()
        policy_path.unlink() # Delete it
        res5, _ = run_check("Chaos: Policy Absence Resilience", f"python {repo_root}/scripts/agent_runner_v2.py --test-latency --tier edge")
        policy_path.write_text(temp_policy) # Restore
    else:
        res5 = True # Already absent, pass
    
    # Summary
    print("\n" + "="*40)
    final = "SYSTEM HEALTHY" if all([res1, res2, res3, res4, res5]) else "SYSTEM UNSTABLE"
    print(f"      STATUS: {final}")
    print("="*40)

if __name__ == "__main__":
    main()
