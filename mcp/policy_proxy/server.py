from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mcp.server import FastMCP


app = FastMCP("policy-proxy")

REPO_ROOT = Path(r"C:\Gemini")
POLICY_PATH = Path(__file__).with_name("policy.json")
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "policy_proxy.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_policy() -> Dict[str, Any]:
    if not POLICY_PATH.exists():
        raise RuntimeError(f"Missing policy file: {POLICY_PATH}")
    return json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))


def _audit(action: str, ok: bool, details: Dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now_iso(),
        "action": action,
        "ok": ok,
        "details": details,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _norm_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _path_allowed(path: Path, policy: Dict[str, Any]) -> bool:
    if bool(policy.get("filesystem", {}).get("allow_all_roots", False)):
        return True
    roots = policy.get("filesystem", {}).get("allowed_roots", [])
    for r in roots:
        rp = _norm_path(str(r))
        if _is_within(path, rp):
            return True
    return False


def _domain_allowed(hostname: str, policy: Dict[str, Any]) -> bool:
    if bool(policy.get("network", {}).get("allow_all_domains", False)):
        return True
    allowed = [str(d).lower().strip() for d in policy.get("network", {}).get("allowed_domains", [])]
    hn = hostname.lower().strip()
    for dom in allowed:
        if dom == "*":
            return True
        if hn == dom or hn.endswith("." + dom):
            return True
    return False


def _stop_files(policy: Dict[str, Any]) -> List[Path]:
    configured = policy.get("control_plane", {}).get("stop_files", [])
    if configured:
        return [_norm_path(str(p)) for p in configured]
    return [REPO_ROOT / "STOP_ALL_AGENTS.flag", REPO_ROOT / "ramshare" / "state" / "STOP"]


def _is_stopped(policy: Dict[str, Any]) -> bool:
    return any(p.exists() for p in _stop_files(policy))


def _command_allowed(command: str, policy: Dict[str, Any]) -> bool:
    shell_policy = policy.get("shell", {})
    if bool(shell_policy.get("allow_all_commands", False)):
        return True
    blocked = [str(x).lower() for x in shell_policy.get("blocked_substrings", [])]
    low = command.lower()
    for b in blocked:
        if b and b in low:
            return False

    allowed_prefixes: List[List[str]] = shell_policy.get("allowed_prefixes", [])
    if not allowed_prefixes:
        return False
    try:
        tokens = shlex.split(command, posix=False)
    except Exception:
        return False
    if not tokens:
        return False

    normalized = [t.lower() for t in tokens]
    for pref in allowed_prefixes:
        pref_norm = [str(t).lower() for t in pref]
        if len(normalized) >= len(pref_norm) and normalized[: len(pref_norm)] == pref_norm:
            return True
    return False


@app.tool()
def policy_status() -> Dict[str, Any]:
    """Return the currently loaded policy and audit location."""
    policy = _load_policy()
    out = {
        "policy_path": str(POLICY_PATH),
        "audit_path": str(AUDIT_PATH),
        "policy": policy,
    }
    _audit("policy_status", True, {"policy_path": str(POLICY_PATH)})
    return out


@app.tool()
def guarded_read_file(path: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
    """Read a file only if path is allowed by policy."""
    policy = _load_policy()
    p = _norm_path(path)
    if not _path_allowed(p, policy):
        _audit("guarded_read_file", False, {"path": str(p), "reason": "path_denied"})
        return {"ok": False, "error": "path_denied", "path": str(p)}
    if not p.exists() or not p.is_file():
        _audit("guarded_read_file", False, {"path": str(p), "reason": "not_found"})
        return {"ok": False, "error": "not_found", "path": str(p)}

    hard_max = int(policy.get("filesystem", {}).get("max_read_bytes", 1048576))
    read_max = min(max_bytes if max_bytes is not None else hard_max, hard_max)
    content = p.read_bytes()[:read_max]
    _audit("guarded_read_file", True, {"path": str(p), "bytes": len(content)})
    return {"ok": True, "path": str(p), "bytes": len(content), "content": content.decode("utf-8", errors="replace")}


@app.tool()
def guarded_write_file(path: str, content: str, append: bool = False) -> Dict[str, Any]:
    """Write or append file content only if path is allowed by policy."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("guarded_write_file", False, {"path": path, "reason": "stopped"})
        return {"ok": False, "error": "stopped"}
    p = _norm_path(path)
    if not _path_allowed(p, policy):
        _audit("guarded_write_file", False, {"path": str(p), "reason": "path_denied"})
        return {"ok": False, "error": "path_denied", "path": str(p)}

    max_write = int(policy.get("filesystem", {}).get("max_write_bytes", 524288))
    raw = content.encode("utf-8")
    if len(raw) > max_write:
        _audit("guarded_write_file", False, {"path": str(p), "reason": "write_too_large", "bytes": len(raw)})
        return {"ok": False, "error": "write_too_large", "max_write_bytes": max_write}

    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as f:
        f.write(content)
    _audit("guarded_write_file", True, {"path": str(p), "append": append, "bytes": len(raw)})
    return {"ok": True, "path": str(p), "append": append, "bytes": len(raw)}


@app.tool()
def guarded_list_dir(path: str, recursive: bool = False) -> Dict[str, Any]:
    """List files in an allowed directory."""
    policy = _load_policy()
    p = _norm_path(path)
    if not _path_allowed(p, policy):
        _audit("guarded_list_dir", False, {"path": str(p), "reason": "path_denied"})
        return {"ok": False, "error": "path_denied", "path": str(p)}
    if not p.exists() or not p.is_dir():
        _audit("guarded_list_dir", False, {"path": str(p), "reason": "not_dir"})
        return {"ok": False, "error": "not_dir", "path": str(p)}

    if recursive:
        items = [str(x) for x in p.rglob("*")]
    else:
        items = [str(x) for x in p.glob("*")]
    _audit("guarded_list_dir", True, {"path": str(p), "count": len(items), "recursive": recursive})
    return {"ok": True, "path": str(p), "count": len(items), "items": items}


@app.tool()
def guarded_run_command(command: str, timeout_sec: int = 30, workdir: Optional[str] = None) -> Dict[str, Any]:
    """Run a shell command if it matches allowed prefixes and timeout limits."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("guarded_run_command", False, {"command": command, "reason": "stopped"})
        return {"ok": False, "error": "stopped"}
    if not _command_allowed(command, policy):
        _audit("guarded_run_command", False, {"command": command, "reason": "command_denied"})
        return {"ok": False, "error": "command_denied"}

    max_t = int(policy.get("shell", {}).get("timeout_sec_max", 60))
    timeout = min(max(timeout_sec, 1), max_t)

    wd = _norm_path(workdir) if workdir else None
    if wd is not None and not _path_allowed(wd, policy):
        _audit("guarded_run_command", False, {"command": command, "reason": "workdir_denied", "workdir": str(wd)})
        return {"ok": False, "error": "workdir_denied"}

    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(wd) if wd else None,
    )
    _audit("guarded_run_command", proc.returncode == 0, {"command": command, "rc": proc.returncode, "timeout": timeout})
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@app.tool()
def guarded_fetch_url(url: str, method: str = "GET", body: str = "", headers_json: str = "{}") -> Dict[str, Any]:
    """Fetch a URL only if the domain and scheme are allowed by policy."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("guarded_fetch_url", False, {"url": url, "reason": "stopped"})
        return {"ok": False, "error": "stopped"}
    pr = urlparse(url)
    if pr.scheme not in ("http", "https"):
        _audit("guarded_fetch_url", False, {"url": url, "reason": "invalid_scheme"})
        return {"ok": False, "error": "invalid_scheme"}
    if pr.scheme == "http" and not bool(policy.get("network", {}).get("allow_http", False)):
        _audit("guarded_fetch_url", False, {"url": url, "reason": "http_disallowed"})
        return {"ok": False, "error": "http_disallowed"}
    if not pr.hostname or not _domain_allowed(pr.hostname, policy):
        _audit("guarded_fetch_url", False, {"url": url, "reason": "domain_denied"})
        return {"ok": False, "error": "domain_denied"}

    try:
        headers = json.loads(headers_json) if headers_json.strip() else {}
    except Exception:
        headers = {}

    req = Request(url, method=method.upper(), headers={str(k): str(v) for k, v in headers.items()})
    data_bytes = body.encode("utf-8") if body else None
    max_resp = int(policy.get("network", {}).get("max_response_bytes", 1048576))

    with urlopen(req, data=data_bytes, timeout=20) as resp:
        raw = resp.read(max_resp + 1)
        limited = raw[:max_resp]
        truncated = len(raw) > max_resp
        text = limited.decode("utf-8", errors="replace")
        result = {
            "ok": True,
            "status": getattr(resp, "status", 200),
            "url": url,
            "truncated": truncated,
            "bytes": len(limited),
            "text": text,
        }
        _audit("guarded_fetch_url", True, {"url": url, "status": result["status"], "bytes": len(limited), "truncated": truncated})
        return result


if __name__ == "__main__":
    app.run()
