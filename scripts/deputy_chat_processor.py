import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import sys
import time
import os
import subprocess
import psutil
from pathlib import Path
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3:mini"
MANAGER_PROMPT = """You are the Commander's Chief of Staff (Deputy v3.0). 
You manage the Gemini-OP ecosystem. Address the user as 'Commander'.

### OPERATIONAL CAPABILITIES:
1. INTERNAL MONOLOGUE: Before your deep strategic answer, provide a very brief [ACK] line.
2. TEAM SPAWNING: If a new mission is requested, identify the needed specialists and output: [SPAWN_TEAM: specialist1, specialist2].
3. AUDITING: Use the MISSION REPORT provided to critique specialist performance.
4. MEMORY: Use the LESSONS provided to avoid past failures.

### STYLE:
Professional, direct, and proactive. Do not wait for permission if a mission is clear—request the team spawn immediately."""

# --- Survivor Protocol (v2.2) ---
REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
PID_FILE = REPO_ROOT / ".gemini/deputy.pid"
LOG_FILE = REPO_ROOT / "deputy_processor.log"

def enforce_single_instance():
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if psutil.pid_exists(old_pid):
                old_proc = psutil.Process(old_pid)
                if "deputy_chat_processor.py" in " ".join(old_proc.cmdline()):
                    log(f"Killing old instance (PID {old_pid})")
                    old_proc.terminate()
                    old_proc.wait(timeout=5)
        except Exception as e:
            log(f"Survivor Protocol error: {e}")
    
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

# --- Socket Hardening (v2.1) ---
adapter = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504]))
session = requests.Session()
session.mount("http://", adapter)

def log(msg):
    ts = datetime.now().isoformat()
    # Force UTF-8 encoding to prevent weird characters in logs
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def get_latest_job(repo_root):
    jobs_dir = Path(repo_root) / ".agent-jobs"
    if not jobs_dir.exists(): return None
    subdirs = [d for d in jobs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if not subdirs: return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)

def get_memory(repo_root, query=""):
    memory_path = Path(repo_root) / "ramshare/learning/memory/lessons.md"
    if not memory_path.exists():
        return "No business memory found yet."
    
    content = memory_path.read_text(encoding="utf-8")
    lessons = [line for line in content.splitlines() if line.strip().startswith("- ")]
    
    if not query:
        return "\n".join(lessons[-5:]) # Default to last 5
    
    # Simple keyword match for relevance
    keywords = [k.lower() for k in query.split() if len(k) > 3]
    relevant = []
    for lesson in lessons:
        if any(k in lesson.lower() for k in keywords):
            relevant.append(lesson)
    
    # Return matched lessons or the most recent ones if no match
    result = relevant[-5:] if relevant else lessons[-5:]
    return "\n".join(result)

def get_mission_report(job_dir):
    report_path = job_dir / "learning-summary.json"
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return f"LATEST MISSION REPORT: Avg Score: {data.get('avg_score')}, Success: {data.get('success_count')}/{data.get('agent_count')}"
        except: pass
    return "No recent mission report available."

def trigger_foundry(repo_root, mission, team_tag):
    try:
        # Extract team from [SPAWN_TEAM: x, y]
        team_str = team_tag.split(":")[1].replace("]", "").strip()
        log(f"Foundry Triggered for team: {team_str}")
        
        # We call orchestrator directly with the new intent
        subprocess.Popen(
            ["powershell.exe", "-File", "scripts/gemini_orchestrator.ps1", "-Prompt", mission, "-RepoRoot", str(repo_root)],
            cwd=str(repo_root),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return True
    except Exception as e:
        log(f"Foundry trigger failed: {e}")
        return False

def process_chat(repo_root):
    latest_job = get_latest_job(repo_root)
    if not latest_job:
        # Optimization: Initialize session from global intent file if no job active
        intent_file = Path(repo_root) / "commander_intent.txt"
        if intent_file.exists():
            log("Found commander_intent.txt. Initializing session...")
            try:
                intent = intent_file.read_text(encoding="utf-8").strip()
                if intent:
                    subprocess.Popen(
                        ["powershell.exe", "-File", "scripts/gemini_orchestrator.ps1", "-Prompt", intent, "-RepoRoot", str(repo_root)],
                        cwd=str(repo_root),
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                    intent_file.unlink()
                    time.sleep(5) # Give it time to create the job dir
            except Exception as e:
                log(f"Error processing commander_intent.txt: {e}")
        return

    history_file = latest_job / "state" / "chat_history.jsonl"
    if not history_file.exists(): return

    messages = []
    try:
        with open(history_file, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError as je:
                        log(f"JSON error in line: {je}")
    except Exception as e:
        log(f"Critical error reading history: {e}")
        return

    if not messages: return

    # Find the last unprocessed message from Commander
    target_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "Commander" and not msg.get("processed", False):
            target_msg = msg
            break
    
    if target_msg:
        content = target_msg.get('content')
        log(f"Processing message: {content}")
        
        # Fast Acknowledgment in UI
        add_response(history_file, "🫡 Chief of Staff is calculating strategic impact...", role="System")
        
        # Inject memory and mission report into context
        memory_content = get_memory(repo_root, content)
        mission_report = get_mission_report(latest_job)
        
        # Build context
        chat_context = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages[-5:]])
        full_prompt = f"{MANAGER_PROMPT}\n\n{mission_report}\n\nRELEVANT LESSONS:\n{memory_content}\n\nRecent History:\n{chat_context}\n\nDeputy:"

        try:
            log(f"Calling Ollama ({MODEL})...")
            # Using tuple timeout: (connect, read)
            response = session.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": full_prompt,
                "stream": False
            }, timeout=(10, 300))
            
            if response.status_code == 200:
                answer = response.json().get("response", "").strip()
                
                # Check for Spawn Trigger
                if "[SPAWN_TEAM:" in answer:
                    trigger_foundry(repo_root, content, answer)
                
                # Mark processed before writing response
                mark_processed(history_file, target_msg.get("ts"))
                add_response(history_file, answer)
                log(f"Success.")
            else:
                log(f"Ollama error: {response.status_code}")
        except requests.exceptions.ReadTimeout:
            log("Timeout.")
            add_response(history_file, "Manager is thinking (Hardware Latency)...")
        except Exception as e:
            log(f"Request failed: {e}")

def mark_processed(path, ts):
    try:
        messages = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                if line.strip():
                    msg = json.loads(line)
                    if msg.get("ts") == ts:
                        msg["processed"] = True
                    messages.append(msg)
        with open(path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")
    except Exception as e:
        log(f"Error in mark_processed: {e}")

def add_response(path, content, role="Deputy"):
    entry = {
        "role": role,
        "content": content,
        "ts": time.time(),
        "processed": True
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log(f"Error in add_response: {e}")

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    enforce_single_instance()
    log(f"Deputy v3.0 starting at {root}")
    while True:
        process_chat(root)
        time.sleep(2)

