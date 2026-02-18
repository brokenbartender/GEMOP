from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


ACK_SCHEMA_VERSION = "a2a.ack.v1"


def repo_root() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT", "") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
DEFAULT_INBOX = REPO_ROOT / "ramshare" / "state" / "a2a" / "inbox"
DEFAULT_DONE = REPO_ROOT / "ramshare" / "state" / "a2a" / "inbox_done"
DEFAULT_DLQ = REPO_ROOT / "ramshare" / "state" / "a2a" / "inbox_dlq"
DEFAULT_ACKS = REPO_ROOT / "ramshare" / "state" / "a2a" / "acks"
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "a2a_executor.jsonl"
IDEMPOTENCY_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "exec_idempotency.json"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _load_idempotency() -> Dict[str, float]:
    if not IDEMPOTENCY_PATH.exists():
        return {}
    try:
        data = json.loads(IDEMPOTENCY_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _save_idempotency(data: Dict[str, float]) -> None:
    _atomic_write_text(IDEMPOTENCY_PATH, json.dumps(data, indent=2))


def _mark_or_reject_task(task_id: str, ttl_sec: int = 30 * 24 * 3600) -> bool:
    now = time.time()
    data = _load_idempotency()
    data = {k: v for k, v in data.items() if (now - float(v)) < ttl_sec}
    if task_id in data:
        _save_idempotency(data)
        return False
    data[task_id] = now
    _save_idempotency(data)
    return True


def _enabled() -> bool:
    return (os.environ.get("GEMINI_OP_REMOTE_EXEC_ENABLE", "") or "").strip().lower() in ("1", "true", "yes")


def _safe_tail(s: str, n: int = 4000) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    return s[-n:]


def _resolve_under_repo(rel: str) -> Path:
    p = (rel or "").strip()
    if not p:
        raise ValueError("empty path")
    cand = (REPO_ROOT / p).resolve()
    repo = REPO_ROOT.resolve()
    try:
        cand.relative_to(repo)
    except Exception as exc:
        raise ValueError(f"path escapes repo: {p}") from exc
    return cand


def _run_script(params: Dict[str, Any]) -> Tuple[int, str, str]:
    rel = str(params.get("path") or "").strip()
    args = params.get("args") if isinstance(params.get("args"), list) else []
    cwd_rel = str(params.get("cwd") or "").strip()
    timeout_sec = int(params.get("timeout_sec") or 600)

    script_path = _resolve_under_repo(rel)
    if not script_path.exists():
        raise FileNotFoundError(f"script not found: {rel}")
    cwd = _resolve_under_repo(cwd_rel) if cwd_rel else REPO_ROOT

    ext = script_path.suffix.lower()
    if ext == ".py":
        argv = [sys.executable, str(script_path)] + [str(a) for a in args]
    elif ext == ".ps1":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh:
            raise RuntimeError("pwsh/powershell not found for .ps1")
        argv = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)] + [str(a) for a in args]
    elif ext in (".sh", ".bash"):
        bash = shutil.which("bash")
        if not bash:
            raise RuntimeError("bash not found for .sh")
        argv = [bash, str(script_path)] + [str(a) for a in args]
    else:
        argv = [str(script_path)] + [str(a) for a in args]

    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _shell_execute(params: Dict[str, Any]) -> Tuple[int, str, str]:
    # Safe-by-default: only argv-style execution, never a raw shell string.
    argv = params.get("argv")
    if not isinstance(argv, list) or not argv:
        raise ValueError("shell_execute requires params.argv as a non-empty list")
    argv_s = [str(x) for x in argv]
    cwd_rel = str(params.get("cwd") or "").strip()
    timeout_sec = int(params.get("timeout_sec") or 600)
    cwd = _resolve_under_repo(cwd_rel) if cwd_rel else REPO_ROOT
    proc = subprocess.run(
        argv_s,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _write_file(params: Dict[str, Any]) -> Tuple[int, str, str]:
    rel = str(params.get("path") or "").strip()
    content = params.get("content")
    if not isinstance(content, str):
        raise ValueError("write_file requires params.content as string")
    dst = _resolve_under_repo(rel)
    _atomic_write_text(dst, content)
    return 0, f"wrote:{rel}", ""


def _execute_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    intent = str(payload.get("intent") or "chat").strip() or "chat"
    ap = payload.get("action_payload")
    if intent == "chat" and ap is None:
        return {"skipped": True, "reason": "chat_only"}
    if not isinstance(ap, dict):
        raise ValueError("missing or invalid action_payload")
    tool = str(ap.get("tool") or "").strip()
    params = ap.get("params") if isinstance(ap.get("params"), dict) else {}

    if tool == "run_script":
        rc, out, err = _run_script(params)
    elif tool == "shell_execute":
        rc, out, err = _shell_execute(params)
    elif tool == "write_file":
        rc, out, err = _write_file(params)
    else:
        raise ValueError(f"unsupported tool: {tool}")

    return {
        "tool": tool,
        "returncode": int(rc),
        "stdout_tail": _safe_tail(out),
        "stderr_tail": _safe_tail(err),
    }


def _ack(task_id: str, status: str, *, detail: str = "", result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ack: Dict[str, Any] = {
        "ack_contract_version": ACK_SCHEMA_VERSION,
        "ack_status": status,
        "ack_observed": status in ("executed", "rejected", "duplicate_ignored", "skipped"),
        "detail": detail,
        "task_id": task_id,
        "ts": time.time(),
    }
    if result is not None:
        ack["result"] = result
    return ack


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Process A2A inbox and execute action_payload (default-off).")
    ap.add_argument("--inbox-dir", default=str(DEFAULT_INBOX))
    ap.add_argument("--done-dir", default=str(DEFAULT_DONE))
    ap.add_argument("--dlq-dir", default=str(DEFAULT_DLQ))
    ap.add_argument("--acks-dir", default=str(DEFAULT_ACKS))
    ap.add_argument("--poll-sec", type=float, default=1.0)
    ap.add_argument("--max-per-pass", type=int, default=20)
    ap.add_argument("--once", action="store_true", help="Process one pass then exit")
    return ap.parse_args()


def _move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    try:
        src.replace(dst)
    except Exception:
        # Cross-device: fallback copy+unlink
        shutil.copy2(src, dst)
        src.unlink(missing_ok=True)
    return dst


def _process_one_file(p: Path, *, acks_dir: Path, done_dir: Path, dlq_dir: Path, enabled: bool) -> None:
    started = time.time()
    raw = p.read_text(encoding="utf-8-sig")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        task_id = f"missing-{int(time.time()*1000)}"

    if not _mark_or_reject_task(task_id):
        ack = _ack(task_id, "duplicate_ignored", detail="executor idempotency: already processed")
        _atomic_write_text(acks_dir / f"{task_id}.json", json.dumps(ack, indent=2))
        _append_jsonl(AUDIT_PATH, {"ts": time.time(), "task_id": task_id, "status": "duplicate_ignored"})
        _move(p, done_dir)
        return

    if not enabled:
        ack = _ack(task_id, "rejected", detail="remote execution disabled (set GEMINI_OP_REMOTE_EXEC_ENABLE=1)")
        _atomic_write_text(acks_dir / f"{task_id}.json", json.dumps(ack, indent=2))
        _append_jsonl(AUDIT_PATH, {"ts": time.time(), "task_id": task_id, "status": "rejected_disabled"})
        _move(p, done_dir)
        return

    try:
        result = _execute_action(payload)
        if result.get("skipped"):
            ack = _ack(task_id, "skipped", detail=str(result.get("reason") or "skipped"), result=result)
        else:
            status = "executed" if int(result.get("returncode", 1)) == 0 else "executed"
            ack = _ack(task_id, status, result=result)
        _atomic_write_text(acks_dir / f"{task_id}.json", json.dumps(ack, indent=2))
        _append_jsonl(
            AUDIT_PATH,
            {
                "ts": time.time(),
                "task_id": task_id,
                "status": ack["ack_status"],
                "latency_ms": round((time.time() - started) * 1000.0, 2),
                "tool": result.get("tool"),
                "returncode": result.get("returncode"),
            },
        )
        _move(p, done_dir)
    except Exception as exc:
        ack = _ack(task_id, "rejected", detail=f"execution_error:{exc}")
        _atomic_write_text(acks_dir / f"{task_id}.json", json.dumps(ack, indent=2))
        _append_jsonl(AUDIT_PATH, {"ts": time.time(), "task_id": task_id, "status": "error", "error": str(exc)})
        _move(p, dlq_dir)


def main() -> int:
    args = parse_args()
    inbox_dir = Path(args.inbox_dir).expanduser().resolve()
    done_dir = Path(args.done_dir).expanduser().resolve()
    dlq_dir = Path(args.dlq_dir).expanduser().resolve()
    acks_dir = Path(args.acks_dir).expanduser().resolve()
    inbox_dir.mkdir(parents=True, exist_ok=True)
    acks_dir.mkdir(parents=True, exist_ok=True)

    enabled = _enabled()
    while True:
        files = sorted([p for p in inbox_dir.glob("*.json") if p.is_file()], key=lambda x: x.name)
        for p in files[: max(1, int(args.max_per_pass))]:
            _process_one_file(p, acks_dir=acks_dir, done_dir=done_dir, dlq_dir=dlq_dir, enabled=enabled)
        if args.once:
            return 0
        time.sleep(max(0.1, float(args.poll_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
