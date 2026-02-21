import argparse
import json
import asyncio
import os
import sys
from pathlib import Path
try:
    from scripts.system_metrics import get_ground_state
except ImportError:
    from system_metrics import get_ground_state

# Add current dir to path for imports
sys.path.append(os.path.dirname(__file__))
from agent_runner_v2 import call_gemini_cloud_modern

async def spawn_branch(role: str, task: str, model: str):
    """Spawns a single parallel reality (agent thread)."""
    prompt = f"[QUANTUM BRANCH: {role}]\n{task}"
    try:
        # Each branch runs independently in memory
        result = await asyncio.to_thread(call_gemini_cloud_modern, prompt, model=model)
        return {"role": role, "result": result, "ok": True}
    except Exception as e:
        return {"role": role, "error": str(e), "ok": False}

async def simulate_superposition(run_dir: Path, task: str):
    print("--- ⚛️ QUANTUM STATE: Branching Realities ---")
    
    # 1. Thermal Failsafe (Telluric Check)
    ground_state = get_ground_state(run_dir)
    cpu_load = ground_state.get("cpu_percent", 0)
    
    if cpu_load > 85.0:
        print(f" -> [DECOHERENCE] CPU load {cpu_load}% too high. Falling back to Linear Reality.")
        return None

    # 2. Spawn Parallel Realities
    branches = [
        spawn_branch("Proposer", task, "gemini-2.0-flash"),
        spawn_branch("Critic", f"Critique this task: {task}", "gemini-2.0-flash"),
        spawn_branch("SecurityEngineer", f"Audit security for: {task}", "gemini-2.0-flash")
    ]
    
    print(f" -> Spawning {len(branches)} concurrent agent threads...")
    results = await asyncio.gather(*branches)
    
    # 3. Store the Superposition (Before Collapse)
    wavefunction = {
        "task": task,
        "branches": results,
        "ts": asyncio.get_event_loop().time()
    }
    
    state_path = run_dir / "state" / "quantum_superposition.json"
    state_path.write_text(json.dumps(wavefunction, indent=2))
    print(f" -> Superposition stabilized in {state_path.name}")
    return wavefunction

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args()
    
    asyncio.run(simulate_superposition(Path(args.run_dir), args.task))
