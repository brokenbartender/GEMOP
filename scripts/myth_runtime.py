from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _run_step(step: str, args: list[str]) -> dict[str, Any]:
    t0 = time.time()
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
        return {
            "step": step,
            "ok": cp.returncode == 0,
            "returncode": cp.returncode,
            "stdout": (cp.stdout or "")[-1200:],
            "stderr": (cp.stderr or "")[-1200:],
            "duration_s": round(time.time() - t0, 4),
        }
    except Exception as ex:
        return {
            "step": step,
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(ex),
            "duration_s": round(time.time() - t0, 4),
        }


def run_round(repo_root: Path, run_dir: Path, query: str, round_n: int) -> dict[str, Any]:
    py = os_fspath(Path(sys.executable))
    scripts = {
        "hubble_drift": repo_root / "scripts" / "hubble_drift.py",
        "wormhole_indexer": repo_root / "scripts" / "wormhole_indexer.py",
        "dark_matter_halo": repo_root / "scripts" / "dark_matter_halo.py",
    }
    results: list[dict[str, Any]] = []

    p = scripts["hubble_drift"]
    if p.exists():
        results.append(
            _run_step(
                "hubble_drift",
                [py, os_fspath(p), "--repo-root", os_fspath(repo_root), "--run-dir", os_fspath(run_dir), "--query", query],
            )
        )

    p = scripts["wormhole_indexer"]
    if p.exists():
        results.append(
            _run_step(
                "wormhole_indexer",
                [py, os_fspath(p), "--run-dir", os_fspath(run_dir), "--query", query, "--max-nodes", "10"],
            )
        )

    p = scripts["dark_matter_halo"]
    if p.exists():
        results.append(
            _run_step(
                "dark_matter_halo",
                [py, os_fspath(p), "--run-dir", os_fspath(run_dir), "--query", query],
            )
        )

    ok = all(bool(r.get("ok")) for r in results) if results else True
    out = {
        "schema_version": 1,
        "generated_at": time.time(),
        "round": int(round_n),
        "query": query,
        "ok": ok,
        "results": results,
    }
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"myth_runtime_round{round_n}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def os_fspath(p: Path) -> str:
    return str(p)


def main() -> None:
    ap = argparse.ArgumentParser(description="Dispatch mythology/physics plugins for a round.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--round", type=int, required=True)
    args = ap.parse_args()

    out = run_round(Path(args.repo_root).resolve(), Path(args.run_dir).resolve(), args.query, int(args.round))
    print(json.dumps(out, separators=(",", ":")))
    raise SystemExit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
