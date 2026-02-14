import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
AUDIT_LOG = REPO_ROOT / "ramshare" / "state" / "audit" / "environment_changes.json"

def log_audit(action, details):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details
    }
    log = []
    if AUDIT_LOG.exists():
        try:
            log = json.loads(AUDIT_LOG.read_text(encoding="utf-8"))
        except: pass
    log.append(entry)
    AUDIT_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")

def install(package_name):
    print(f"?? Installing: {package_name}...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", package_name], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            log_audit("pip_install", {"package": package_name, "status": "success"})
            return {"ok": True, "output": result.stdout}
        else:
            log_audit("pip_install", {"package": package_name, "status": "failed", "error": result.stderr})
            return {"ok": False, "error": result.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def shell(command):
    print(f"?? Executing: {command}...")
    try:
        # Use shell=True for Windows command compatibility
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"exit_code": 1, "error": str(e)}

if __name__ == "__main__":
    # CLI interface for agents
    import sys
    if len(sys.argv) < 3:
        print("Usage: tool_manager.py <install|shell> <target>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    target = " ".join(sys.argv[2:])
    
    if cmd == "install":
        res = install(target)
        print(json.dumps(res, indent=2))
    elif cmd == "shell":
        res = shell(target)
        print(json.dumps(res, indent=2))
