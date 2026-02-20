import os
import time
import json
from pathlib import Path
from scripts.memory_manager import MemoryManager

def run_data_factory():
    print("--- 🏭 AI DATA FACTORY: Engaged ---")
    repo_root = Path(__file__).resolve().parents[1]
    resources_dir = repo_root / "ramshare" / "resources"
    state_file = repo_root / "ramshare" / "state" / "data_factory_state.json"
    
    # Load processed files state
    processed = {}
    if state_file.exists():
        try:
            processed = json.loads(state_file.read_text())
        except: pass

    mem = MemoryManager()
    
    try:
        while True:
            updated = False
            # Scan for new files
            for file_path in resources_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix in ['.md', '.txt', '.json']:
                    mtime = file_path.stat().st_mtime
                    f_key = str(file_path.relative_to(repo_root))
                    
                    if f_key not in processed or processed[f_key] < mtime:
                        print(f"Index Update: {f_key}")
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            # Chunking for long docs
                            if len(content) > 2000:
                                chunks = [content[i:i+2000] for i in range(0, len(content), 1500)]
                            else:
                                chunks = [content]
                                
                            for i, chunk in enumerate(chunks):
                                mem.store_memory(
                                    agent_id="data_factory",
                                    content=f"FILE: {f_key} (Part {i})
{chunk}",
                                    collection_name="project_data",
                                    metadata={"source": f_key, "part": i}
                                )
                            
                            processed[f_key] = mtime
                            updated = True
                        except Exception as e:
                            print(f"Error indexing {f_key}: {e}")
            
            if updated:
                state_file.write_text(json.dumps(processed, indent=2))
                print("Data Factory: Knowledge Base Synchronized.")
            
            # Sleep until next check
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("
Data Factory: Offline.")
    finally:
        mem.close()

if __name__ == "__main__":
    run_data_factory()
