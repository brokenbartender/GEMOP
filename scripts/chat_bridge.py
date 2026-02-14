import json
import os
import sys
import time
from pathlib import Path

def get_chat_history_path(run_dir=None):
    if run_dir:
        return Path(run_dir) / "state" / "chat_history.jsonl"
    repo_root = Path(os.environ.get("GEMINI_OP_REPO_ROOT", "."))
    latest_run = repo_root / ".agent-jobs/latest"
    return latest_run / "state" / "chat_history.jsonl"

def add_message(role, content, run_dir=None):
    path = get_chat_history_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "role": role, 
        "content": content, 
        "ts": time.time(),
        "processed": False if role == "Commander" else True
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def get_latest_instruction(run_dir=None):
    path = get_chat_history_path(run_dir)
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            msg = json.loads(line)
            if msg.get("role") == "Commander" and not msg.get("processed", False):
                return msg
    except:
        pass
    return None

def mark_as_processed(run_dir, ts):
    path = get_chat_history_path(run_dir)
    if not path.exists(): return
    messages = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            msg = json.loads(line)
            if msg.get("ts") == ts:
                msg["processed"] = True
            messages.append(msg)
    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "check" and len(sys.argv) == 3:
        instr = get_latest_instruction(sys.argv[2])
        if instr:
            print(json.dumps(instr))
            mark_as_processed(sys.argv[2], instr["ts"])
    elif len(sys.argv) >= 4:
        # run_dir role content...
        add_message(sys.argv[2], " ".join(sys.argv[3:]), run_dir=sys.argv[1])
