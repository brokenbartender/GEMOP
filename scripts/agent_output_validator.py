from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate an agent markdown output contains a valid DECISION_JSON contract.")
    ap.add_argument("path", help="Path to agent output markdown (ex: .agent-jobs/<run>/round2_agent1.md)")
    ap.add_argument("--round", type=int, default=2, help="Round number (affects validation expectations).")
    args = ap.parse_args()

    md_path = Path(args.path).expanduser().resolve()
    if not md_path.exists():
        print(json.dumps({"ok": False, "reason": "file_not_found", "path": str(md_path)}, indent=2))
        return 2

    # Reuse the repo's canonical DECISION_JSON extractor/validator to keep behavior consistent.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
        from extract_agent_decisions import extract_decision, read_text, validate_decision  # type: ignore
    except Exception as e:
        print(json.dumps({"ok": False, "reason": "import_failed", "error": str(e)}, indent=2))
        return 3

    md = read_text(md_path)
    obj = extract_decision(md)
    if not obj:
        print(json.dumps({"ok": False, "reason": "missing_decision_json", "path": str(md_path)}, indent=2))
        return 4

    errs = validate_decision(obj, round_n=max(1, int(args.round)))
    payload = {"ok": not bool(errs), "errors": errs, "path": str(md_path)}
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 5


if __name__ == "__main__":
    raise SystemExit(main())

