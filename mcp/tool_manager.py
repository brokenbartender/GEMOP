import subprocess
import sys
import json
import os
from pathlib import Path
from typing import Any, Dict, Union
from datetime import datetime
from mcp.tool_contracts import pip_install_contract, shell_contract

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
AUDIT_LOG = REPO_ROOT / "ramshare" / "state" / "audit" / "environment_changes.json"

def log_audit(action: str, details: Dict[str, Any]):
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


def _validate_tool_input(tool_name: str, input_data: Union[Dict[str, Any], str], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs basic validation of tool input against a simplified JSON schema.
    This is a lightweight validation and not a full JSON schema validator.
    """
    if not isinstance(input_data, dict):
        return {"ok": False, "error": f"Input for '{tool_name}' must be a dictionary."}

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for prop in required:
        if prop not in input_data:
            return {"ok": False, "error": f"Missing required property '{prop}' for tool '{tool_name}'."}

    for prop, value in input_data.items():
        if prop not in properties:
            if not schema.get("additionalProperties", True):
                return {"ok": False, "error": f"Unexpected property '{prop}' for tool '{tool_name}'."}
            continue

        expected_type = properties[prop].get("type")
        if expected_type == "string":
            if not isinstance(value, str):
                return {"ok": False, "error": f"Property '{prop}' for tool '{tool_name}' must be a string."}
            if not value.strip(): # Ensure string is not empty or whitespace-only
                return {"ok": False, "error": f"Property '{prop}' for tool '{tool_name}' cannot be an empty or whitespace-only string."}
    return {"ok": True}

def install(package_name):
    print(f"?? Installing: {package_name}...")
    input_dict = {"package_name": package_name}
    validation_res = _validate_tool_input("pip_install", input_dict, pip_install_contract["input_schema"])
    if not validation_res["ok"]:
        log_audit("pip_install", {"package": package_name, "status": "validation_failed", "error": validation_res["error"]})
        return validation_res
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
    input_dict = {"command": command}
    validation_res = _validate_tool_input("shell", input_dict, shell_contract["input_schema"])
    if not validation_res["ok"]:
        log_audit("shell", {"command": command, "status": "validation_failed", "error": validation_res["error"]})
        return validation_res
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
    if cmd == "install":
        input_dict_for_tool = {"package_name": " ".join(sys.argv[2:])}
        validation_res = _validate_tool_input("pip_install", input_dict_for_tool, pip_install_contract["input_schema"])
        if not validation_res["ok"]:
            print(json.dumps(validation_res, indent=2))
            sys.exit(1)
        res = install(input_dict_for_tool["package_name"])
        print(json.dumps(res, indent=2))
    elif cmd == "shell":
        input_dict_for_tool = {"command": " ".join(sys.argv[2:])}
        validation_res = _validate_tool_input("shell", input_dict_for_tool, shell_contract["input_schema"])
        if not validation_res["ok"]:
            print(json.dumps(validation_res, indent=2))
            sys.exit(1)
        res = shell(input_dict_for_tool["command"])
        print(json.dumps(res, indent=2))
