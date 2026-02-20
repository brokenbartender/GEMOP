#!/usr/bin/env python3
"""
Sovereign: The Unified Cortex for Gemini OP.
Cohesively integrates Swarm, Finance, Commerce, and Governance subsystems.
"""

import argparse
import os
import sys
import subprocess
import shutil
import json
import time
from pathlib import Path

# --- Context Bootstrap ---
def repo_root() -> Path:
    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # Fallback: assume this script is in scripts/
    return Path(__file__).resolve().parents[1]

REPO_ROOT = repo_root()
SCRIPTS_DIR = REPO_ROOT / "scripts"
CONFIGS_DIR = REPO_ROOT / "configs"
GOVERNANCE_SCRIPT = SCRIPTS_DIR / "gemini_governance.py"
RECOVERY_SCRIPT = SCRIPTS_DIR / "slavic_recovery.ps1"
CONFIG_ASSEMBLE_SCRIPT = SCRIPTS_DIR / "config_assemble.py"
EVENT_HORIZON_SCRIPT = SCRIPTS_DIR / "event_horizon.py"

# --- Subsystem Paths ---
SUMMON_SCRIPT = SCRIPTS_DIR / "summon.ps1"
FINANCE_SCRIPT = SCRIPTS_DIR / "finance_council_run.py"
COMMERCE_SCRIPT = SCRIPTS_DIR / "redbubble_pipeline_run.py"
DISPATCHER_SCRIPT = SCRIPTS_DIR / "gemini_dispatcher.py"
DASHBOARD_SCRIPT = SCRIPTS_DIR / "dashboard.py"

# --- Helpers ---

def print_banner():
    print(f"\n\033[1;36m== GEMINI OP: SOVEREIGN CORTEX ==\033[0m")
    print(f"\033[0;90mRepo: {REPO_ROOT}\033[0m\n")

def run_subprocess(cmd: list[str], env: dict = None, check: bool = False) -> int:
    try:
        # Merge current env with overrides
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        
        # Handle PowerShell scripts on Windows
        if cmd[0].endswith(".ps1"):
            cmd = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + cmd
            
        print(f"\033[0;90m[Exec] {' '.join(cmd)}\033[0m")
        cp = subprocess.run(cmd, env=run_env)
        if check and cp.returncode != 0:
            print(f"\033[1;31m[Error] Command failed with exit code {cp.returncode}\033[0m")
            sys.exit(cp.returncode)
        return cp.returncode
    except KeyboardInterrupt:
        print("\n\033[1;33m[Interrupt] User cancelled operation.\033[0m")
        return 130
    except Exception as e:
        print(f"\033[1;31m[Critical] Execution failed: {e}\033[0m")
        return 1

def ensure_config(profile: str = "full"):
    """Enforces configuration layering (Base > Profile > Local > Alatyr)."""
    print(f"\033[1;34m[Init] Assembling configuration (profile={profile})...\033[0m")
    run_subprocess(
        [sys.executable, str(CONFIG_ASSEMBLE_SCRIPT), "--repo-root", str(REPO_ROOT), "--config-profile", profile],
        check=True
    )

def check_governance(action: str, cost: float = 0.0) -> bool:
    """Invokes the Governor to gate high-risk or costly actions."""
    if not GOVERNANCE_SCRIPT.exists():
        print("\033[1;33m[Warn] Governance script missing. Proceeding with caution.\033[0m")
        return True
        
    print(f"\033[1;34m[Gov] Enforcing policy for '{action}' (Est. Cost: ${cost})...\033[0m")
    
    cmd = [sys.executable, str(GOVERNANCE_SCRIPT)]
    budget_env = os.environ.get("GEMINI_OP_BUDGET_PATH", "").strip()
    if budget_env:
        cmd += ["--budget-path", budget_env]
    else:
        # Fallback to standard workspace location if env not set
        local_budget = REPO_ROOT / "configs" / "budget.json"
        if local_budget.exists():
            cmd += ["--budget-path", str(local_budget)]
        
    cmd += ["enforce", "--action", action, "--estimated-spend-usd", str(cost)]
    
    rc = run_subprocess(cmd)
    return rc == 0

def check_physics(prompt: str) -> bool:
    """Runs Event Horizon checks on prompts."""
    if not prompt or not EVENT_HORIZON_SCRIPT.exists():
        return True
        
    print(f"\033[1;34m[Physics] Analyzing Event Horizon (Prompt Mass)...\033[0m")
    # We capture output to check JSON, but here we just rely on exit code/output for now
    # Ideally we'd parse the JSON to warn the user about sharding.
    rc = run_subprocess([sys.executable, str(EVENT_HORIZON_SCRIPT), "--run-dir", str(REPO_ROOT / ".agent-jobs" / "_govtest_tmp"), "--prompt", prompt])
    return rc == 0

# --- Commands ---

def cmd_summon(args):
    """Orchestrates a Swarm Council run."""
    ensure_config(args.profile)
    if not check_governance("summon_council", cost=0.50): # Estimate
        return
    if not check_physics(args.task):
        print("\033[1;31m[Physics] Prompt too heavy. Refine or allow sharding.\033[0m")
        # Proceeding anyway as the orchestrator handles sharding, but user warned.

    cmd = [str(SUMMON_SCRIPT), "-Task", args.task]
    if args.online: cmd.append("-Online")
    if args.agents: cmd += ["-Agents", str(args.agents)]
    
    run_subprocess(cmd)

def cmd_finance(args):
    """Runs the Finance Council pipeline."""
    ensure_config("fidelity")
    if not check_governance("finance_council", cost=0.20):
        return

    cmd = [sys.executable, str(FINANCE_SCRIPT)]
    if args.run_now: cmd.append("--run-now")
    if args.account_id: cmd += ["--account-id", args.account_id]
    
    run_subprocess(cmd)

def cmd_commerce(args):
    """Runs the Redbubble Commerce pipeline."""
    ensure_config("research") # Commerce uses research profile
    if not check_governance("commerce_pipeline", cost=0.10):
        return

    cmd = [sys.executable, str(COMMERCE_SCRIPT)]
    if args.run_now: cmd.append("--run-now")
    if args.theme: cmd += ["--theme", args.theme]
    
    run_subprocess(cmd)

def cmd_recover(args):
    """Initiates Slavic Recovery Protocol."""
    print(f"\033[1;35m[Recovery] invoking Slavic Recovery Protocol (Dead/Living Water)...\033[0m")
    cmd = [str(RECOVERY_SCRIPT)]
    run_subprocess(cmd)

def cmd_dashboard(args):
    """Launches Olympus UI and Dispatcher."""
    ensure_config("full")
    print(f"\033[1;32m[System] Launching Sovereign Dashboard & Dispatcher...\033[0m")
    
    # 1. Start Dispatcher (Background)
    # 2. Start Streamlit (Foreground)
    
    procs = []
    try:
        print(" -> Starting Dispatcher...")
        p1 = subprocess.Popen([sys.executable, str(DISPATCHER_SCRIPT)], cwd=str(REPO_ROOT))
        procs.append(p1)
        
        print(" -> Starting Olympus UI (Streamlit)...")
        run_subprocess(["streamlit", "run", str(DASHBOARD_SCRIPT), "--server.port", str(args.port)])
        
    finally:
        print("\n[Shutdown] Terminating background services...")
        for p in procs:
            p.terminate()

def main():
    print_banner()
    
    parser = argparse.ArgumentParser(description="Gemini OP Sovereign Interface")
    sub = parser.add_subparsers(dest="command", help="Subsystem commands")
    
    # Summon (Swarm)
    p_sum = sub.add_parser("summon", help="Summon a Swarm Council")
    p_sum.add_argument("task", help="The objective for the council")
    p_sum.add_argument("--online", action="store_true", help="Enable internet access")
    p_sum.add_argument("--agents", type=int, help="Number of agents")
    p_sum.add_argument("--profile", default="full", help="Config profile to use")
    p_sum.set_defaults(func=cmd_summon)
    
    # Finance
    p_fin = sub.add_parser("finance", help="Finance Council Operations")
    p_fin.add_argument("--run-now", action="store_true", help="Execute immediately")
    p_fin.add_argument("--account-id", help="Fidelity Account ID")
    p_fin.set_defaults(func=cmd_finance)
    
    # Commerce
    p_com = sub.add_parser("commerce", help="Redbubble Commerce Pipeline")
    p_com.add_argument("--run-now", action="store_true", help="Execute immediately")
    p_com.add_argument("--theme", help="Niche/Theme for generation")
    p_com.set_defaults(func=cmd_commerce)
    
    # Recover
    p_rec = sub.add_parser("recover", help="Self-Healing (Slavic Protocol)")
    p_rec.set_defaults(func=cmd_recover)
    
    # Dashboard
    p_dash = sub.add_parser("dashboard", help="Launch Olympus UI & Dispatcher")
    p_dash.add_argument("--port", type=int, default=8501)
    p_dash.set_defaults(func=cmd_dashboard)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    args.func(args)

if __name__ == "__main__":
    main()
