import argparse
import json
from pathlib import Path

GEMINI_DIR = Path(r"C:\Users\codym\.Gemini")
MEMORY_PATH = GEMINI_DIR / "memory.md"
TASK_PATH = GEMINI_DIR / "current_task.json"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Rough estimate: 4 chars per token
    return max(1, int(len(text) / 4))


def main():
    ap = argparse.ArgumentParser(description="Estimate context budget usage")
    ap.add_argument("--context", type=int, default=128000, help="Context window tokens")
    ap.add_argument("--warn-threshold", type=float, default=0.8, help="Warn when usage exceeds ratio")
    ap.add_argument("--prompt", default="", help="Prompt text to include in estimate")
    args = ap.parse_args()

    mem_text = MEMORY_PATH.read_text(encoding="utf-8", errors="ignore") if MEMORY_PATH.exists() else ""
    task_text = TASK_PATH.read_text(encoding="utf-8", errors="ignore") if TASK_PATH.exists() else ""
    prompt_text = args.prompt or ""

    mem_tokens = estimate_tokens(mem_text)
    task_tokens = estimate_tokens(task_text)
    prompt_tokens = estimate_tokens(prompt_text)
    total = mem_tokens + task_tokens + prompt_tokens
    ratio = total / args.context if args.context else 0.0

    payload = {
        "context_tokens": args.context,
        "memory_tokens": mem_tokens,
        "task_tokens": task_tokens,
        "prompt_tokens": prompt_tokens,
        "total_tokens": total,
        "usage_ratio": round(ratio, 4),
    }
    print(json.dumps(payload, indent=2))

    if ratio >= args.warn_threshold:
        print("WARNING: context usage is high; consider compacting memory.md or trimming the prompt.")


if __name__ == "__main__":
    main()
