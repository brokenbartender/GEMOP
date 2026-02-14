from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict


def repo_root() -> Path:
    import os

    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
REMOTE_DEFAULT_REPO = "~/Gemini-op"
REMOTE_DEFAULT_PY = "python3"


def run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def remote_command(remote_repo: str, remote_python: str, payload: Dict[str, Any]) -> str:
    repo = str(remote_repo)
    if repo.startswith("~/"):
        repo = "$HOME/" + repo[2:]
    script = f"{remote_repo}/scripts/GEMINI_a2a_send_structured.py"
    message = str(payload.get("message", ""))
    sender = str(payload.get("sender", "Gemini"))
    receiver = str(payload.get("receiver", "remote"))
    priority = str(payload.get("priority", "normal"))
    mode = str(payload.get("mode", "plan"))
    task_id = str(payload.get("task_id", ""))
    script = f"{repo}/scripts/GEMINI_a2a_send_structured.py"
    cmd = (
        f"cd {repo} && "
        f"{shlex.quote(remote_python)} {shlex.quote(script)} "
        f"{shlex.quote(message)} "
        f"--sender {shlex.quote(sender)} "
        f"--receiver {shlex.quote(receiver)} "
        f"--priority {shlex.quote(priority)} "
        f"--mode {shlex.quote(mode)} "
        f"{('--task-id ' + shlex.quote(task_id)) if task_id else ''} "
    )
    return cmd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Send A2A payload to remote host over SSH.")
    ap.add_argument("--host", required=True, help="SSH host alias or user@host")
    ap.add_argument("--payload-file", required=True, help="Local JSON payload file")
    ap.add_argument("--remote-repo", default=REMOTE_DEFAULT_REPO, help="Remote Gemini-op repo path")
    ap.add_argument("--remote-python", default=REMOTE_DEFAULT_PY, help="Remote python executable")
    ap.add_argument("--ssh-timeout", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload_path = Path(args.payload_file).expanduser().resolve()
    if not payload_path.exists():
        raise SystemExit(f"payload file not found: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ssh_cmd = [
        "ssh",
        args.host,
        remote_command(
            remote_repo=str(args.remote_repo),
            remote_python=str(args.remote_python),
            payload=payload,
        ),
    ]

    if args.dry_run:
        print(json.dumps({"ssh": ssh_cmd}, indent=2))
        return

    ssh_res = run(ssh_cmd, timeout=args.ssh_timeout)
    if ssh_res.returncode != 0:
        raise SystemExit(f"ssh failed: {ssh_res.stderr.strip() or ssh_res.stdout.strip()}")

    print(json.dumps({"ok": True, "host": args.host, "stdout": ssh_res.stdout.strip()}, indent=2))


if __name__ == "__main__":
    main()
