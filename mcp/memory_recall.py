import json
import os
import re
from pathlib import Path

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()

def recall(query):
    print(f"?? RECALL: Searching memory for '{query}'...")
    memory_hits = []
    
    # 1. Search lessons (ramshare memory)
    lessons_path = REPO_ROOT / "ramshare" / "learning" / "memory" / "lessons.md"
    if lessons_path.exists():
        text = lessons_path.read_text(encoding="utf-8")
        # Simple keyword matching for local context
        if any(word.lower() in text.lower() for word in query.split()):
            memory_hits.append(f"--- FROM LESSONS.MD ---\n{text[:1000]}")

    # 2. Search recent run manifests / decisions (cheap, deterministic)
    jobs_dir = REPO_ROOT / ".agent-jobs"
    if jobs_dir.exists():
        recent_jobs = sorted([d for d in jobs_dir.iterdir() if d.is_dir()], key=os.path.getmtime, reverse=True)[:10]
        for job in recent_jobs:
            for p in [
                job / "state" / "manifest.json",
                job / "state" / "decisions_round1.json",
                job / "state" / "world_state.md",
            ]:
                if not p.exists():
                    continue
                try:
                    blob = p.read_text(encoding="utf-8", errors="ignore")
                    if any(word.lower() in blob.lower() for word in query.split()):
                        memory_hits.append(f"--- HIT ({job.name}) {p.name} ---\n{blob[:800]}")
                except Exception:
                    pass

    if not memory_hits:
        return "No specific previous patterns found. Procedural logic from scratch required."
    
    return "\n\n".join(memory_hits[:3]) # Return top 3 hits

if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if q:
        print(recall(q))
