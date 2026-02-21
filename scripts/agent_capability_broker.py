import os
import re
import json
import pathlib

def log_message(run_dir, message):
    log_path = run_dir / "broker.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] {message}\n")

def find_capability_requests(text):
    """Parses agent output for capability request blocks."""
    pattern = r"### Capability Requests\n```\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return []
    
    requests = []
    content = match.group(1).strip()
    for line in content.splitlines():
        if "tool:" in line:
            try:
                # Expecting format: tool: <name> | code: ```<code>```
                parts = line.split("|")
                tool_name = parts[0].split("tool:")[1].strip()
                code_block = parts[1].split("code:")[1].strip().replace("`", "")
                requests.append({"type": "tool", "name": tool_name, "code": code_block})
            except Exception as e:
                log_message(f"Could not parse tool request: {line} | Error: {e}")
    return requests

def forge_tool(run_dir, request):
    """Creates a new tool script in the tools directory."""
    tools_dir = pathlib.Path(run_dir).parent.parent / "tools"
    tools_dir.mkdir(exist_ok=True)
    
    tool_name = request['name']
    tool_code = request['code']
    file_extension = ".py" if "python" in tool_code.lower() or "import" in tool_code.lower() else ".ps1"
    tool_path = tools_dir / f"{tool_name}{file_extension}"
    
    log_message(run_dir, f"FORGING NEW TOOL: {tool_path}")
    tool_path.write_text(tool_code, encoding="utf-8")
    
    # Update the manifest
    manifest_path = tools_dir / "tool_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        
    manifest[tool_name] = {"path": str(tool_path), "description": "Dynamically forged tool."}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log_message(run_dir, f"SUCCESS: Tool '{tool_name}' forged and registered.")

def run_broker(run_dir):
    """Main broker function to scan for and fulfill capability requests."""
    run_path = pathlib.Path(run_dir)
    log_message(run_path, f"Capability Broker activated for {run_path.name}")

    for report_file in run_path.glob("agent*.md"):
        content = report_file.read_text(encoding="utf-8")
        requests = find_capability_requests(content)
        
        if not requests:
            continue
            
        log_message(run_path, f"Found {len(requests)} capability requests in {report_file.name}")
        
        for req in requests:
            if req['type'] == 'tool':
                forge_tool(run_path, req)
            elif req['type'] == 'capability':
                cap = req.get('name')
                if cap == 'governance':
                    subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "dark_matter_halo.py"), "--run-dir", str(run_dir), "--query", "implicit_governance_check"])
                elif cap == 'mythology':
                    subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "myth_runtime.py"), "--run-dir", str(run_dir), "--round", "1"])
                elif cap == 'entropy':
                    subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "maxwells_demon.py"), "--run-dir", str(run_dir)])

if __name__ == "__main__":
    import sys
    import subprocess
    if len(sys.argv) > 1:
        run_broker(sys.argv[1])
    else:
        print("Usage: python agent_capability_broker.py <run_dir>")
