import argparse
from pathlib import Path

MEM_PATH = Path(r"C:\Users\codym\.Gemini\memory.md")


def main():
    ap = argparse.ArgumentParser(description="Gemini memory journal")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--append", help="Append a lesson")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--compact", type=int, default=0, help="Keep last N non-empty lines")
    args = ap.parse_args()

    if args.init and not MEM_PATH.exists():
        MEM_PATH.write_text("# Gemini Memory\n\n", encoding="utf-8")

    if args.append:
        if not MEM_PATH.exists():
            MEM_PATH.write_text("# Gemini Memory\n\n", encoding="utf-8")
        with MEM_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"- {args.append.strip()}\n")

    if args.compact and MEM_PATH.exists():
        lines = [ln for ln in MEM_PATH.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        header = ["# Gemini Memory"]
        tail = lines[-args.compact:] if args.compact > 0 else lines
        text = "\n".join(header + [""] + tail) + "\n"
        MEM_PATH.write_text(text, encoding="utf-8")

    if args.show or (not args.append and not args.init):
        if MEM_PATH.exists():
            print(MEM_PATH.read_text(encoding="utf-8", errors="ignore"))
        else:
            print("(memory.md not found)")


if __name__ == "__main__":
    main()
