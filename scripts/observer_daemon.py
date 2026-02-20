import time
import json
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys

# Add scripts to path for agent_runner
sys.path.append(os.path.dirname(__file__))
from agent_runner_v2 import call_gemini_cloud_modern

class ContextHandler(FileSystemEventHandler):
    def __init__(self, context_path):
        self.context_path = context_path
        self.last_update = 0
        self.buffer = []

    def on_modified(self, event):
        if event.is_directory: return
        if event.src_path.endswith(".json") or event.src_path.endswith(".md"):
            self.buffer.append(event.src_path)
            self.process_buffer()

    def process_buffer(self):
        # Debounce updates (5s)
        if time.time() - self.last_update < 5: return
        self.last_update = time.time()
        
        print(f"[Observer] Context shift detected in: {len(self.buffer)} files.")
        
        # Build prompt for Evaluator
        changed_files = list(set(self.buffer))
        self.buffer = [] # Clear
        
        prompt = f"""
        [ANTICIPATORY COMPUTING MODE]
        You are the Observer Agent. The user is actively working on these files:
        {json.dumps(changed_files, indent=2)}
        
        TASK:
        Infer the user's current focus and intent.
        Output a valid JSON object with the current context state.
        
        OUTPUT JSON:
        {{
            "current_focus": "One sentence summary",
            "inferred_intent": "What they are trying to achieve",
            "proactive_suggestion": "A high-value task we could offer to do (or null if none)"
        }}
        """
        
        try:
            # Use Flash for low-latency context updates
            resp = call_gemini_cloud_modern(prompt, model="gemini-2.0-flash-lite-preview-02-05")
            if resp:
                import re
                m = re.search(r"\{.*\}", resp, re.DOTALL)
                if m:
                    ctx = json.loads(m.group(0))
                    self.context_path.write_text(json.dumps(ctx, indent=2))
                    print(f"[Observer] Context Updated: {ctx.get('current_focus')}")
                    if ctx.get("proactive_suggestion"):
                        print(f"💡 PROACTIVE: {ctx['proactive_suggestion']}")
        except Exception as e:
            print(f"[Observer] Update failed: {e}")

def run_observer():
    print("--- 👁️ OBSERVER DAEMON: Anticipating ---")
    repo_root = Path(__file__).resolve().parents[1]
    
    # Watch high-signal directories
    watch_dirs = [
        repo_root / "ramshare" / "notes",
        repo_root / "ramshare" / "evidence" / "inbox"
    ]
    
    context_file = repo_root / "ramshare" / "state" / "real_time_context.json"
    handler = ContextHandler(context_file)
    
    observer = Observer()
    for d in watch_dirs:
        d.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(d), recursive=True)
        print(f"[Observer] Watching: {d.relative_to(repo_root)}")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    run_observer()
