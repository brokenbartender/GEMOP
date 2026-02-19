from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phase6_schema import is_num, validate_task_contract_obj, validate_task_pipeline_obj

def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _validate_dark_matter(path: Path, errors: list[str]) -> None:
    obj = _load_json(path)
    if obj is None:
        errors.append(f"missing_or_invalid_json:{path}")
        return
    if int(obj.get("schema_version", -1)) != 1:
        errors.append("dark_matter.schema_version")
    if not is_num(obj.get("generated_at")):
        errors.append("dark_matter.generated_at")
    if not isinstance(obj.get("query"), str):
        errors.append("dark_matter.query")

    w = obj.get("weights")
    if not isinstance(w, dict):
        errors.append("dark_matter.weights")
        return
    keys = ("safety", "efficiency", "goal_coherence", "verification")
    total = 0.0
    for k in keys:
        if k not in w or not is_num(w.get(k)):
            errors.append(f"dark_matter.weights.{k}")
            continue
        vv = float(w[k])
        if vv < 0.0 or vv > 1.0:
            errors.append(f"dark_matter.weights.{k}.range")
        total += vv
    if total < 0.95 or total > 1.05:
        errors.append("dark_matter.weights.sum")

    d = obj.get("directives")
    if not isinstance(d, list) or not d or not all(isinstance(x, str) and x.strip() for x in d):
        errors.append("dark_matter.directives")


def _validate_myth_runtime(path: Path, round_n: int, errors: list[str]) -> None:
    obj = _load_json(path)
    if obj is None:
        errors.append(f"missing_or_invalid_json:{path}")
        return
    if int(obj.get("schema_version", -1)) != 1:
        errors.append("myth_runtime.schema_version")
    if not is_num(obj.get("generated_at")):
        errors.append("myth_runtime.generated_at")
    if int(obj.get("round", -1)) != int(round_n):
        errors.append("myth_runtime.round")
    if not isinstance(obj.get("query"), str):
        errors.append("myth_runtime.query")
    if not isinstance(obj.get("ok"), bool):
        errors.append("myth_runtime.ok")

    rows = obj.get("results")
    if not isinstance(rows, list) or not rows:
        errors.append("myth_runtime.results")
        return
    required_steps = {"hubble_drift", "wormhole_indexer", "dark_matter_halo"}
    seen_steps: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"myth_runtime.results[{i}]")
            continue
        step = row.get("step")
        if not isinstance(step, str) or not step:
            errors.append(f"myth_runtime.results[{i}].step")
        else:
            seen_steps.add(step)
        if not isinstance(row.get("ok"), bool):
            errors.append(f"myth_runtime.results[{i}].ok")
        rc = row.get("returncode")
        if not isinstance(rc, int):
            errors.append(f"myth_runtime.results[{i}].returncode")
        if not is_num(row.get("duration_s")):
            errors.append(f"myth_runtime.results[{i}].duration_s")
    if not required_steps.issubset(seen_steps):
        errors.append("myth_runtime.results.required_steps")


def _validate_task_contract(path: Path, round_n: int, errors: list[str]) -> None:
    obj = _load_json(path)
    if obj is None:
        errors.append(f"missing_or_invalid_json:{path}")
        return
    errors.extend(validate_task_contract_obj(obj, int(round_n)))


def _validate_task_pipeline(path: Path, round_n: int, errors: list[str]) -> None:
    obj = _load_json(path)
    if obj is None:
        errors.append(f"missing_or_invalid_json:{path}")
        return
    errors.extend(validate_task_pipeline_obj(obj, int(round_n)))


def validate(run_dir: Path, round_n: int) -> dict[str, Any]:
    state = run_dir / "state"
    errors: list[str] = []
    _validate_dark_matter(state / "dark_matter_profile.json", errors)
    _validate_myth_runtime(state / f"myth_runtime_round{round_n}.json", round_n, errors)
    _validate_task_contract(state / f"task_contract_round{round_n}.json", round_n, errors)
    _validate_task_pipeline(state / f"task_pipeline_round{round_n}.json", round_n, errors)
    return {"ok": len(errors) == 0, "errors": errors, "run_dir": str(run_dir), "round": int(round_n)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Strict validator for Phase VI contract artifacts.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", dest="round_n", type=int, required=True)
    args = ap.parse_args()

    out = validate(Path(args.run_dir).resolve(), int(args.round_n))
    print(json.dumps(out, separators=(",", ":")))
    raise SystemExit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
