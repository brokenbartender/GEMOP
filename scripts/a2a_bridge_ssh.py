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
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _pwsh_literal(s: str) -> str:
    # Single-quoted PowerShell literal. Double-up single quotes.
    return "'" + (s or "").replace("'", "''") + "'"


def remote_command(remote_repo: str, remote_python: str, payload: Dict[str, Any], *, platform: str) -> str:
    repo = str(remote_repo)
    py = str(remote_python or "").strip() or ("python3" if platform != "windows" else "python")
    if platform == "windows":
        repo_win = repo.replace("/", "\\")
        script = str(Path(repo_win) / "scripts" / "gemini_a2a_send_structured.py")
    else:
        if repo.startswith("~/"):
            repo = "$HOME/" + repo[2:]
        # NOTE: Use lowercase script names for Linux compatibility.
        script = f"{repo}/scripts/gemini_a2a_send_structured.py"
    message = str(payload.get("message", ""))
    sender = str(payload.get("sender", "Gemini"))
    receiver = str(payload.get("receiver", "remote"))
    priority = str(payload.get("priority", "normal"))
    mode = str(payload.get("mode", "plan"))
    task_id = str(payload.get("task_id", ""))
    if platform == "windows":
        # Use PowerShell explicitly to get reliable quoting on Windows sshd.
        # stdin is not used for this path (chat-only); arguments are passed directly.
        ps = (
            f"powershell -NoProfile -Command "
            f"\"Set-Location -LiteralPath {_pwsh_literal(repo_win)}; "
            f"& {_pwsh_literal(py)} {_pwsh_literal(script)} {_pwsh_literal(message)} "
            f"--sender {_pwsh_literal(sender)} "
            f"--receiver {_pwsh_literal(receiver)} "
            f"--priority {_pwsh_literal(priority)} "
            f"--mode {_pwsh_literal(mode)} "
            f"{('--task-id ' + _pwsh_literal(task_id)) if task_id else ''}"
            f"\""
        )
        return ps

    cmd = (
        f"cd {repo} && "
        f"{shlex.quote(py)} {shlex.quote(script)} "
        f"{shlex.quote(message)} "
        f"--sender {shlex.quote(sender)} "
        f"--receiver {shlex.quote(receiver)} "
        f"--priority {shlex.quote(priority)} "
        f"--mode {shlex.quote(mode)} "
        f"{('--task-id ' + shlex.quote(task_id)) if task_id else ''} "
    )
    return cmd


def remote_receive_command(remote_repo: str, remote_python: str, *, platform: str) -> str:
    repo = str(remote_repo)
    py = str(remote_python or "").strip() or ("python3" if platform != "windows" else "python")
    if platform == "windows":
        repo_win = repo.replace("/", "\\")
        script = str(Path(repo_win) / "scripts" / "a2a_receive.py")
        # Payload will be provided on stdin.
        return (
            f"powershell -NoProfile -Command "
            f"\"Set-Location -LiteralPath {_pwsh_literal(repo_win)}; "
            f"& {_pwsh_literal(py)} {_pwsh_literal(script)} --stdin\""
        )

    if repo.startswith("~/"):
        repo = "$HOME/" + repo[2:]
    script = f"{repo}/scripts/a2a_receive.py"
    # Payload will be provided on stdin to avoid brittle shell quoting.
    return f"cd {repo} && {shlex.quote(py)} {shlex.quote(script)} --stdin"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Send A2A payload to remote host over SSH.")
    ap.add_argument("--host", required=True, help="SSH host alias or user@host")
    ap.add_argument("--payload-file", required=True, help="Local JSON payload file")
    ap.add_argument("--remote-repo", default=REMOTE_DEFAULT_REPO, help="Remote Gemini-op repo path")
    ap.add_argument("--remote-python", default=REMOTE_DEFAULT_PY, help="Remote python executable")
    ap.add_argument("--platform", default="linux", choices=["linux", "windows"], help="Remote platform")
    ap.add_argument("--hostkey-policy", default="accept-new", help="StrictHostKeyChecking policy (accept-new|yes|no)")
    ap.add_argument("--ssh-timeout", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload_path = Path(args.payload_file).expanduser().resolve()
    if not payload_path.exists():
        raise SystemExit(f"payload file not found: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    intent = str(payload.get("intent") or "chat").strip() or "chat"
    has_action = payload.get("action_payload") is not None
    use_receive = has_action or intent != "chat" or str(payload.get("schema_version") or "").strip() == "a2a.v2"
    platform = str(args.platform or "linux").strip().lower()
    if use_receive:
        ssh_cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"StrictHostKeyChecking={args.hostkey_policy}",
            args.host,
            remote_receive_command(
                remote_repo=str(args.remote_repo),
                remote_python=str(args.remote_python),
                platform=platform,
            ),
        ]
    else:
        ssh_cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"StrictHostKeyChecking={args.hostkey_policy}",
            args.host,
            remote_command(
                remote_repo=str(args.remote_repo),
                remote_python=str(args.remote_python),
                payload=payload,
                platform=platform,
            ),
        ]

    if args.dry_run:
        out = {"ssh": ssh_cmd, "transport": "receive" if use_receive else "agentic_console"}
        if use_receive:
            out["stdin_payload"] = payload
        print(json.dumps(out, indent=2))
        return

    if use_receive:
        # Pass full payload over stdin so we preserve action_payload and avoid quoting issues.
        ssh_res = subprocess.run(
            ssh_cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.ssh_timeout,
        )
    else:
        ssh_res = run(ssh_cmd, timeout=args.ssh_timeout)
    if ssh_res.returncode != 0:
        raise SystemExit(f"ssh failed: {ssh_res.stderr.strip() or ssh_res.stdout.strip()}")

    print(json.dumps({"ok": True, "host": args.host, "stdout": ssh_res.stdout.strip()}, indent=2))


if __name__ == "__main__":
    main()
