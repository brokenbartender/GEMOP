import json
import requests
import sys
import time
import os
import subprocess
from pathlib import Path
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3:mini"
MANAGER_PROMPT = """You are the Commander's Operations Manager. You are in a direct chat. 
Acknowledge greetings, answer questions about the business, and help the Commander brainstorm new missions. 
Stay in character. Use professional, proactive, and brief language. Address the user as 'Commander'.

IMPORTANT: You have access to the business memory (LESSONS). Always reference past successes or failures 
to provide proactive insights. If you see a risk based on memory, warn the Commander immediately."""

LOG_FILE = Path("deputy_processor.log")

def log(msg):
    ts = datetime.now().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def get_latest_job(repo_root):
    jobs_dir = Path(repo_root) / ".agent-jobs"
    if not jobs_dir.exists(): return None
    subdirs = [d for d in jobs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if not subdirs: return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)

def get_memory(repo_root):
    memory_path = Path(repo_root) / "ramshare/learning/memory/lessons.md"
    if memory_path.exists():
        return memory_path.read_text(encoding="utf-8")
    return "No business memory found yet."

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
        log(f"Processing message: {target_msg.get('content')}")
        
        # Inject memory into context
        memory_content = get_memory(repo_root)
        
        # Build context
        chat_context = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages[-5:]])
        full_prompt = f"{MANAGER_PROMPT}\n\nBUSINESS MEMORY:\n{memory_content}\n\nRecent History:\n{chat_context}\n\nDeputy:"

        try:
            log(f"Calling Ollama ({MODEL})...")
            response = requests.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": full_prompt,
                "stream": False
            }, timeout=300)
            
            if response.status_code == 200:
                answer = response.json().get("response", "").strip()
                # Mark processed before writing response
                mark_processed(history_file, target_msg.get("ts"))
                add_response(history_file, answer)
                log(f"Success.")
            else:
                log(f"Ollama error: {response.status_code}")
        except requests.exceptions.ReadTimeout:
            log("Timeout.")
            add_response(history_file, "🫡 Commander, inference is heavy. Still working...")
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

def add_response(path, content):
    entry = {
        "role": "Deputy",
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
    log(f"Deputy v2.0 starting at {root}")
    while True:
        process_chat(root)
        time.sleep(2)
