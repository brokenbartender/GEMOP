import argparse
import json
import subprocess
import sys
from pathlib import Path


def _emit_hawking(run_dir: Path, *, pid: int | None, agent_id: int, round_num: int, reason: str, error: str = "") -> None:
    try:
        from hawking_emitter import emit_radiation

        emit_radiation(
            run_dir,
            source="iolaus_cauterize",
            reason=reason,
            agent=agent_id,
            round_num=round_num,
            pid=pid,
            error=error,
        )
        return
    except Exception:
        pass

    emitter = Path(__file__).with_name("hawking_emitter.py")
    if not emitter.exists():
        return
    args = [
        sys.executable,
        str(emitter),
        "--run-dir",
        str(run_dir),
        "--source",
        "iolaus_cauterize",
        "--reason",
        reason,
        "--agent",
        str(agent_id),
        "--round",
        str(round_num),
        "--no-bus",
    ]
    if pid is not None:
        args += ["--pid", str(pid)]
    if error:
        args += ["--error", error]
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=8, check=False)
    except Exception:
        pass


def cauterize_hydra(run_dir: Path, agent_id: int = 0, round_num: int = 0, lyapunov_kill: bool = False):
    """
    Scans pids.json for 'Hydra heads' or kills specific Lyapunov-diverged threads.
    Applies fire (SIGKILL) to prevent recursive system collapse.
    """
    pids_path = run_dir / "state" / "pids.json"
    if not pids_path.exists():
        return

    try:
        data = json.loads(pids_path.read_text(encoding='utf-8', errors='ignore'))
        entries = data.get("entries", [])
    except Exception:
        return

    if lyapunov_kill and round_num > 0:
        if agent_id > 0:
            print(f"[Iolaus] LYAPUNOV KILL: Divergence detected for Agent {agent_id} in Round {round_num}. Neutralizing...")
        else:
            print(f"[Iolaus] LYAPUNOV KILL: Divergence detected in Round {round_num}. Neutralizing all matching processes...")
        for e in entries:
            try:
                e_agent = int(e.get("agent", 0))
                e_round = int(e.get("round", 0))
                pid = int(e.get("pid", 0))
            except Exception:
                continue
            if e_round != round_num:
                continue
            if agent_id > 0 and e_agent != agent_id:
                continue
            _emit_hawking(
                run_dir,
                pid=pid,
                agent_id=e_agent,
                round_num=e_round,
                reason="lyapunov_divergence",
            )
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                print(f" -> PID {pid} cauterized.")
            except Exception as ex:
                _emit_hawking(
                    run_dir,
                    pid=pid,
                    agent_id=e_agent,
                    round_num=e_round,
                    reason="lyapunov_kill_failed",
                    error=str(ex),
                )
        return

    # Count processes per agent/round
    counts = {}
    for e in entries:
        try:
            agent = int(e.get("agent", 0))
            rnum = int(e.get("round", 0))
            pid = int(e.get("pid", 0))
        except Exception:
            continue
        key = f"a{agent}_r{rnum}"
        if key not in counts:
            counts[key] = []
        counts[key].append({"pid": pid, "agent": agent, "round": rnum})

    for key, pids in counts.items():
        if len(pids) > 3: # Threshold for a 'Hydra' loop
            print(f"[Iolaus] CAUTERIZING: {len(pids)} processes detected for {key}. Killing heads...")
            for row in pids:
                pid = int(row.get("pid", 0))
                agent = int(row.get("agent", 0))
                rnum = int(row.get("round", 0))
                _emit_hawking(
                    run_dir,
                    pid=pid,
                    agent_id=agent,
                    round_num=rnum,
                    reason="hydra_loop_detected",
                )
                try:
                    # Windows taskkill
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                except Exception as ex:
                    _emit_hawking(
                        run_dir,
                        pid=pid,
                        agent_id=agent,
                        round_num=rnum,
                        reason="hydra_kill_failed",
                        error=str(ex),
                    )
            print(f"[Iolaus] {key} has been neutralized.")

def main():
    parser = argparse.ArgumentParser(description="Iolaus Monitor: Cauterize recursive process loops.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--agent", type=int, default=0)
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--lyapunov", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    cauterize_hydra(run_dir, args.agent, args.round, args.lyapunov)

if __name__ == "__main__":
    main()
