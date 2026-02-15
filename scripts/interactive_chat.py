import json
import time
import os
from pathlib import Path

REPO_ROOT = Path("C:/Users/codym/gemini-op-clean")
HISTORY_PATH = REPO_ROOT / ".agent-jobs/latest/chat_history.jsonl"

def send_message(content):
    entry = {"role": "Commander", "content": content, "ts": time.time(), "processed": False}
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def get_latest_deputy_msg():
    if not HISTORY_PATH.exists():
        return None
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines: return None
            for line in reversed(lines):
                msg = json.loads(line)
                if msg.get("role") == "Deputy":
                    return msg.get("content")
    except:
        pass
    return None

def main():
    print("\n--- GEMINI-OP INTERACTIVE TERMINAL ---")
    print("Type 'exit' to quit. System is live.\n")
    
    while True:
        user_input = input("Commander > ")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        send_message(user_input)
        print("Waiting for Deputy...", end="\r")
        
        last_msg = get_latest_deputy_msg()
        while True:
            current_msg = get_latest_deputy_msg()
            if current_msg and current_msg != last_msg:
                print(f"Deputy > {current_msg}\n")
                break
            time.sleep(1)

if __name__ == "__main__":
    main()
