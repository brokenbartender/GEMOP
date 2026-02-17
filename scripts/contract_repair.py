from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List


def _now() -> float:
    return time.time()


def _stop_requested(repo_root: Path, run_dir: Path) -> bool:
    for p in (
        repo_root / "STOP_ALL_AGENTS.flag",
        repo_root / "ramshare" / "state" / "STOP",
        run_dir / "state" / "STOP",
    ):
        try:
            if p.exists():
                return True
        except Exception:
            continue
    return False


def _tail_text(path: Path, max_chars: int) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if max_chars <= 0:
        return txt
    if len(txt) <= max_chars:
        return txt
    return txt[-max_chars:]


def _agent_output_path(run_dir: Path, round_n: int, agent_id: int) -> Path:
    p = run_dir / f"round{int(round_n)}_agent{int(agent_id)}.md"
    if p.exists():
        return p
    p2 = run_dir / f"agent{int(agent_id)}.md"
    return p2


def _build_repair_prompt(
    *,
    repo_root: Path,
    run_dir: Path,
    round_n: int,
    agent_id: int,
    task: str,
    mode: str,
    prior_tail: str,
) -> str:
    mode_n = (mode or "").strip().lower()
    if mode_n != "decision_json":
        mode_n = "decision_json"

    # Keep this prompt extremely deterministic; the goal is contract compliance, not creativity.
    return (
        "[SYSTEM]\n"
        "REPAIR_MODE=decision_json\n"
        "You are repairing a contract violation. Output must be machine-parseable.\n\n"
        f"REPO_ROOT: {repo_root}\n"
        f"RUN_DIR: {run_dir}\n"
        f"ROUND: {int(round_n)}\n"
        f"AGENT_ID: {int(agent_id)}\n\n"
        f"TASK:\n{task.strip()}\n\n"
        "[INSTRUCTIONS]\n"
        "- Return EXACTLY ONE fenced JSON block labeled DECISION_JSON.\n"
        "- No prose outside the JSON fence.\n"
        "- The JSON must include keys: summary (string), files (array), commands (array), risks (array), confidence (0..1).\n"
        "- files must be repo-relative paths only (no absolute paths, no drive letters, no .. traversal).\n"
        "- commands must be runnable commands to verify your suggested work.\n\n"
        "[PRIOR_OUTPUT_TAIL]\n"
        + (prior_tail.strip() or "(empty)") +
        "\n"
    )


def _parse_agents_csv(s: str) -> List[int]:
    out: List[int] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    # preserve order, de-dupe
    seen = set()
    dedup: List[int] = []
    for a in out:
        if a in seen:
            continue
        seen.add(a)
        dedup.append(a)
    return dedup


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair missing contract artifacts (DECISION_JSON) by re-running only failing seats.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--agents", required=True, help="Comma-separated agent ids to repair (1-based).")
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--mode", default="decision_json", choices=["decision_json"])
    ap.add_argument("--task", default="")
    ap.add_argument("--prior-tail-chars", type=int, default=6000)
    ap.add_argument("--timeout-s", type=int, default=900)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))
    attempt = max(1, int(args.attempt))
    agents = _parse_agents_csv(args.agents)

    state_dir = run_dir / "state"
    repairs_dir = state_dir / "repairs"
    repairs_dir.mkdir(parents=True, exist_ok=True)

    # Prefer mission anchor task if not provided.
    task = str(args.task or "").strip()
    if not task:
        try:
            task = (state_dir / "mission_anchor.md").read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            task = ""

    report: Dict[str, Any] = {
        "ok": True,
        "mode": args.mode,
        "round": round_n,
        "attempt": attempt,
        "agents": agents,
        "started_at": _now(),
        "results": [],
    }

    if _stop_requested(repo_root, run_dir):
        report["ok"] = False
        report["reason"] = "stop_requested"
        (repairs_dir / f"repair_round{round_n}_attempt{attempt}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 2

    runner = repo_root / "scripts" / "agent_runner_v2.py"
    if not runner.exists():
        report["ok"] = False
        report["reason"] = "missing_agent_runner"
        (repairs_dir / f"repair_round{round_n}_attempt{attempt}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 2

    for agent_id in agents:
        if _stop_requested(repo_root, run_dir):
            report["ok"] = False
            report["reason"] = "stop_requested_mid_repair"
            break

        prior_path = _agent_output_path(run_dir, round_n, agent_id)
        prior_tail = _tail_text(prior_path, int(args.prior_tail_chars))

        prompt_path = repairs_dir / f"prompt_round{round_n}_agent{agent_id}_repair{attempt}.txt"
        out_md = repairs_dir / f"round{round_n}_agent{agent_id}_repair{attempt}.md"
        prompt_txt = _build_repair_prompt(
            repo_root=repo_root,
            run_dir=run_dir,
            round_n=round_n,
            agent_id=agent_id,
            task=task,
            mode=args.mode,
            prior_tail=prior_tail,
        )
        prompt_path.write_text(prompt_txt, encoding="utf-8")

        t0 = _now()
        cp = subprocess.run(
            ["python", str(runner), str(prompt_path), str(out_md)],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            timeout=int(args.timeout_s),
        )
        report["results"].append(
            {
                "agent": agent_id,
                "prompt_path": str(prompt_path),
                "out_md": str(out_md),
                "rc": cp.returncode,
                "duration_s": round(_now() - t0, 3),
                "stderr_tail": (cp.stderr or "")[-1200:],
            }
        )
        if cp.returncode != 0:
            report["ok"] = False

    report["finished_at"] = _now()
    (repairs_dir / f"repair_round{round_n}_attempt{attempt}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
