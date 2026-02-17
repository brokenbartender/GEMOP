from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a concise run status summary for a council RunDir.")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state = run_dir / "state"
    out: dict[str, Any] = {
        "run_dir": str(run_dir),
        "has_stop": (state / "STOP").exists(),
    }

    for name in ("learning-summary.json",):
        p = run_dir / name
        if p.exists():
            out[name] = str(p)

    for name in ("quota.json", "concurrency.json", "verify_report.json"):
        p = state / name
        if p.exists():
            out[name] = read_json(p)

    # Patch apply report for round2 (most common).
    for p in sorted(state.glob("patch_apply_round*.json")):
        out.setdefault("patch_apply_reports", []).append(read_json(p))

    # Decisions summary.
    decs = []
    for p in sorted(state.glob("decisions_round*.json")):
        decs.append(read_json(p))
    if decs:
        out["decisions"] = decs

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

