from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict


def run(cmd: list[str], timeout: int = 60, *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def remote_receive_command(remote_repo: str, remote_python: str) -> str:
    repo = str(remote_repo).strip()
    py = str(remote_python).strip() or "python3"
    script = f"{repo.rstrip('/')}/scripts/a2a_receive.py"
    # Run under bash -lc so `cd` and quoting behave consistently.
    return f"cd {shlex.quote(repo)} && {shlex.quote(py)} {shlex.quote(script)} --stdin"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Send A2A payload into a WSL distro via stdin (no SSH).")
    ap.add_argument("--distro", default="Ubuntu", help="WSL distro name (see: wsl -l -v)")
    ap.add_argument("--payload-file", required=True, help="Local JSON payload file")
    ap.add_argument("--remote-repo", required=True, help="Repo path inside WSL (e.g., /home/user/gemini-op-clean)")
    ap.add_argument("--remote-python", default="python3", help="Python executable inside WSL")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    payload_path = Path(args.payload_file).expanduser().resolve()
    if not payload_path.exists():
        raise SystemExit(f"payload file not found: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("payload must be a JSON object")

    cmd_str = remote_receive_command(remote_repo=str(args.remote_repo), remote_python=str(args.remote_python))
    wsl_cmd = ["wsl.exe", "-d", str(args.distro), "--", "bash", "-lc", cmd_str]

    if args.dry_run:
        print(json.dumps({"wsl": wsl_cmd, "stdin_payload": payload}, indent=2))
        return 0

    res = run(wsl_cmd, timeout=int(args.timeout), stdin=json.dumps(payload))
    if res.returncode != 0:
        raise SystemExit(f"wsl failed: {res.stderr.strip() or res.stdout.strip()}")
    print(json.dumps({"ok": True, "distro": args.distro, "stdout": res.stdout.strip()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
