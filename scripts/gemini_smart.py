import argparse
import os
import subprocess
import sys
from pathlib import Path

GEMINI_DIR = Path(r"C:\Users\codym\.Gemini")
PRESETS_SCRIPT = GEMINI_DIR / "scripts" / "GEMINI_presets.py"
PREFLIGHT_SCRIPT = GEMINI_DIR / "scripts" / "GEMINI_preflight.py"
SELECTOR_SCRIPT = GEMINI_DIR / "scripts" / "GEMINI_tool_selector.py"
MEMORY_PATH = GEMINI_DIR / "memory.md"
TASK_PATH = GEMINI_DIR / "current_task.json"
LEGAL_CONTEXT = GEMINI_DIR / "context" / "legal_stack.md"


def run(cmd, env=None):
    return subprocess.call(cmd, shell=False, env=env)


def apply_context_rules(prompt: str) -> str:
    prompt_lower = prompt.lower()
    legal_keywords = ["contract", "legal", "compliance", "law", "attorney", "lease", "eviction"]
    if any(k in prompt_lower for k in legal_keywords) and LEGAL_CONTEXT.exists():
        context_text = LEGAL_CONTEXT.read_text(encoding="utf-8", errors="ignore").strip()
        if context_text:
            print(f"[SmartLoader] Detected legal task. Injecting context: {LEGAL_CONTEXT}")
            return f"{context_text}\n\nUser task:\n{prompt}"
    return prompt


def main():
    ap = argparse.ArgumentParser(description="Smart Gemini launcher with preset selection")
    ap.add_argument("task", nargs="*", help="Task prompt")
    ap.add_argument("--auto-disable", action="store_true", help="Disable MCPs after Gemini exits")
    ap.add_argument("--confirm", action="store_true", help="Prompt before applying preset")
    ap.add_argument("--no-preflight", action="store_true", help="Skip preflight checks")
    args = ap.parse_args()

    prompt = " ".join(args.task).strip()
    if not prompt:
        print("Provide a task prompt.")
        sys.exit(1)

    prompt = apply_context_rules(prompt)

    # Show journal and current task
    if MEMORY_PATH.exists():
        print("\n=== Gemini Memory ===")
        print(MEMORY_PATH.read_text(encoding="utf-8", errors="ignore"))
    if TASK_PATH.exists():
        print("\n=== Current Task ===")
        print(TASK_PATH.read_text(encoding="utf-8", errors="ignore"))

    env = dict(**os.environ)
    env["GEMINI_HOME"] = r"C:\Users\codym\.Gemini"
    env["GEMINI_CONFIG"] = r"C:\Users\codym\.Gemini\config.toml"

    # Optional preflight checks
    if not args.no_preflight and PREFLIGHT_SCRIPT.exists():
        print("\n=== Preflight ===")
        run([sys.executable, str(PREFLIGHT_SCRIPT), "--prompt", prompt], env=env)

    # Show recommendations before applying preset
    if SELECTOR_SCRIPT.exists():
        print("\n=== Tool Recommendations ===")
        run([sys.executable, str(SELECTOR_SCRIPT), "--task", prompt], env=env)

    # Apply preset based on task
    preset_cmd = [
        sys.executable,
        str(PRESETS_SCRIPT),
        "--task",
        prompt,
        "--project",
        str(Path.cwd()),
        "--apply",
    ]
    if args.confirm:
        preset_cmd.append("--confirm")
    run(preset_cmd, env=env)

    # Launch Gemini CLI with the prompt
    exit_code = subprocess.call([r"C:\nvm4w\nodejs\Gemini.cmd", prompt], shell=False, env=env)

    # Optionally disable MCPs after exit
    if args.auto_disable:
        subprocess.call([sys.executable, str(PRESETS_SCRIPT), "--disable"], shell=False, env=env)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
