import argparse
import json
from pathlib import Path

TASK_PATH = Path(r"C:\Users\codym\.Gemini\current_task.json")


def load():
    if TASK_PATH.exists():
        try:
            return json.loads(TASK_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"task": "", "steps": []}
    return {"task": "", "steps": []}


def save(data):
    TASK_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Gemini task plan")
    ap.add_argument("--init", help="Initialize task name")
    ap.add_argument("--add-step", help="Add a step")
    ap.add_argument("--set", nargs=2, metavar=("ID", "STATUS"))
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    data = load()

    if args.init:
        data["task"] = args.init
        data.setdefault("steps", [])
        save(data)

    if args.add_step:
        steps = data.setdefault("steps", [])
        next_id = 1 + max([s.get("id", 0) for s in steps] or [0])
        steps.append({"id": next_id, "text": args.add_step, "status": "pending"})
        save(data)

    if args.set:
        step_id = int(args.set[0])
        status = args.set[1]
        for s in data.get("steps", []):
            if s.get("id") == step_id:
                s["status"] = status
        save(data)

    if args.show or (not args.init and not args.add_step and not args.set):
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
