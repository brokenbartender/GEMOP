import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from scripts.memory_manager import MemoryManager
except ImportError:
    from memory_manager import MemoryManager
import re
import json

def ingest_historical_data():
    print("--- Ingesting Historical Knowledge into Vector Memory ---")
    mem = MemoryManager()
    repo_root = Path(__file__).resolve().parents[1]
    
    # 1. Ingest Lessons
    lessons_path = repo_root / "ramshare" / "learning" / "memory" / "lessons.md"
    if lessons_path.exists():
        print(f"Ingesting lessons from {lessons_path}...")
        content = lessons_path.read_text(encoding="utf-8")
        # Split by level 2 or 3 headers OR bullets to create discrete memory chunks
        chunks = re.split(r'\n(?:#{2,3}|-)\s+', content)
        for chunk in chunks:
            text = chunk.strip()
            if len(text) > 30:
                mem.store_memory(agent_id="system_ingest", content=text)
    
    # 2. Ingest Recent Run Summaries
    summaries_path = repo_root / "ramshare" / "state" / "learning" / "run_summaries.jsonl"
    if summaries_path.exists():
        print(f"Ingesting run summaries from {summaries_path}...")
        with open(summaries_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    summary = data.get("summary") or data.get("task")
                    if summary:
                        mem.store_memory(agent_id="system_ingest", content=summary)
                except: continue

    mem.close()
    print("Ingestion Complete.")

if __name__ == "__main__":
    ingest_historical_data()
