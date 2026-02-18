from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict

#
# A2A schema:
# - a2a.v1: chat-style payloads (sender/receiver/message)
# - a2a.v2: adds `intent` + `action_payload` for RPC-style execution
#
A2A_SCHEMA_V1 = "a2a.v1"
A2A_SCHEMA_V2 = "a2a.v2"
ACK_SCHEMA_VERSION = "a2a.ack.v1"


def repo_root() -> Path:
    import os

    env = os.environ.get("GEMINI_OP_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
PEERS_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "peers.json"
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "a2a_router.jsonl"
OUTBOX_DIR = REPO_ROOT / "ramshare" / "state" / "a2a" / "outbox"
DLQ_DIR = REPO_ROOT / "ramshare" / "state" / "a2a" / "dlq"
IDEMPOTENCY_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "idempotency.json"
LATENCY_HISTOGRAM_PATH = REPO_ROOT / "ramshare" / "state" / "a2a" / "latency_histogram.json"
SEND_LOCAL = REPO_ROOT / "scripts" / "gemini_a2a_send_structured.py"
RECEIVE_LOCAL = REPO_ROOT / "scripts" / "a2a_receive.py"
SEND_SSH = REPO_ROOT / "scripts" / "a2a_bridge_ssh.py"
SEND_WSL = REPO_ROOT / "scripts" / "a2a_bridge_wsl.py"


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def load_peers(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def load_idempotency() -> Dict[str, float]:
    if not IDEMPOTENCY_PATH.exists():
        return {}
    try:
        data = json.loads(IDEMPOTENCY_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_idempotency(data: Dict[str, float]) -> None:
    IDEMPOTENCY_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEMPOTENCY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def mark_or_reject_task(task_id: str, ttl_sec: int = 7 * 24 * 3600) -> bool:
    t = time.time()
    data = load_idempotency()
    data = {k: v for k, v in data.items() if (t - float(v)) < ttl_sec}
    if task_id in data:
        save_idempotency(data)
        return False
    data[task_id] = t
    save_idempotency(data)
    return True


def create_outbox(payload: Dict[str, Any]) -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTBOX_DIR / f"{int(time.time() * 1000)}_{payload.get('task_id','unknown')}.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def move_to_dlq(outbox_file: Path, error: str) -> Path:
    DLQ_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(outbox_file.read_text(encoding="utf-8-sig"))
    payload["_dlq_error"] = error
    payload["_dlq_at"] = time.time()
    dst = DLQ_DIR / outbox_file.name
    dst.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    outbox_file.unlink(missing_ok=True)
    return dst


def update_latency_histogram(route: str, latency_ms: float) -> None:
    buckets = [100, 250, 500, 1000, 2500, 5000]
    label = ">5000"
    for b in buckets:
        if latency_ms <= b:
            label = f"<={b}"
            break
    data: Dict[str, Any] = {}
    if LATENCY_HISTOGRAM_PATH.exists():
        try:
            loaded = json.loads(LATENCY_HISTOGRAM_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    route_hist = data.get(route) if isinstance(data.get(route), dict) else {}
    route_hist[label] = int(route_hist.get(label, 0)) + 1
    route_hist["count"] = int(route_hist.get("count", 0)) + 1
    route_hist["last_latency_ms"] = round(latency_ms, 2)
    data[route] = route_hist
    LATENCY_HISTOGRAM_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATENCY_HISTOGRAM_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.payload_file:
        p = Path(args.payload_file).expanduser().resolve()
        if not p.exists():
            raise SystemExit(f"payload file not found: {p}")
        payload = json.loads(p.read_text(encoding="utf-8"))
        if "task_id" not in payload:
            payload["task_id"] = str(uuid.uuid4())
        payload.setdefault("timestamp", time.time())
        payload.setdefault("schema_version", A2A_SCHEMA_V1)
        payload.setdefault("intent", "chat")
        return payload
    if not args.message:
        raise SystemExit("message required when --payload-file is not used")
    payload: Dict[str, Any] = {
        "sender": args.sender,
        "receiver": args.receiver,
        "message": args.message,
        "task_id": str(uuid.uuid4()),
        "priority": args.priority,
        "mode": args.mode,
        "timestamp": time.time(),
        "schema_version": A2A_SCHEMA_V1,
        "intent": str(getattr(args, "intent", "chat") or "chat"),
    }
    action_tool = str(getattr(args, "action_tool", "") or "").strip()
    action_params_json = str(getattr(args, "action_params_json", "") or "").strip()
    if payload.get("intent") != "chat" or action_tool or action_params_json:
        payload["schema_version"] = A2A_SCHEMA_V2
    if action_tool:
        params: Dict[str, Any] = {}
        if action_params_json:
            try:
                parsed = json.loads(action_params_json)
                if isinstance(parsed, dict):
                    params = parsed
            except Exception:
                raise SystemExit("--action-params-json must be valid JSON object")
        payload["action_payload"] = {"tool": action_tool, "params": params}
    return payload


def validate_payload_contract(payload: Dict[str, Any]) -> None:
    version = str(payload.get("schema_version", "")).strip()
    if not version:
        payload["schema_version"] = A2A_SCHEMA_V1
        version = A2A_SCHEMA_V1
    if not version.startswith("a2a."):
        raise SystemExit(f"invalid schema_version: {version}")
    payload["schema_version"] = version
    payload.setdefault("intent", "chat")
    intent = str(payload.get("intent") or "chat").strip() or "chat"
    payload["intent"] = intent
    if ("action_payload" in payload) or (intent != "chat"):
        if version == A2A_SCHEMA_V1:
            payload["schema_version"] = A2A_SCHEMA_V2
            version = A2A_SCHEMA_V2
    if version == A2A_SCHEMA_V2:
        ap = payload.get("action_payload")
        if ap is not None:
            if not isinstance(ap, dict):
                raise SystemExit("action_payload must be an object in a2a.v2")
            tool = ap.get("tool")
            params = ap.get("params")
            if not isinstance(tool, str) or not tool.strip():
                raise SystemExit("action_payload.tool must be a non-empty string")
            if params is None:
                ap["params"] = {}
            elif not isinstance(params, dict):
                raise SystemExit("action_payload.params must be an object")


def shared_secret_env() -> str:
    import os

    s = (os.environ.get("GEMINI_OP_A2A_SHARED_SECRET", "") or "").strip()
    if s:
        return s
    return (os.environ.get("AGENTIC_A2A_SHARED_SECRET", "") or "").strip()


def parse_ack(stdout_text: str, ok: bool) -> Dict[str, Any]:
    ack: Dict[str, Any] = {
        "ack_contract_version": ACK_SCHEMA_VERSION,
        "ack_status": "none",
        "ack_observed": False,
    }
    text = (stdout_text or "").strip()
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                if isinstance(parsed.get("ack"), dict):
                    candidate = parsed.get("ack", {})
                    ack["ack_status"] = str(candidate.get("ack_status", "none"))
                    ack["ack_observed"] = bool(candidate.get("ack_observed", False))
                    ack["ack_contract_version"] = str(candidate.get("ack_contract_version", ACK_SCHEMA_VERSION))
                elif "ack_status" in parsed:
                    ack["ack_status"] = str(parsed.get("ack_status", "none"))
                    ack["ack_observed"] = ack["ack_status"] in {"accepted", "received", "queued"}
        except Exception:
            # Keep fallback behavior below.
            pass
    if not ack["ack_observed"] and ok:
        ack["ack_status"] = "transport_only"
        ack["ack_observed"] = False
    return ack


def backoff_sleep_ms(base_ms: int, attempt: int) -> None:
    jitter = random.randint(0, 250)
    delay_ms = min(5000, (base_ms * (2**attempt)) + jitter)
    time.sleep(delay_ms / 1000.0)


def route_local(payload: Dict[str, Any], retries: int, backoff_ms: int, dry_run: bool) -> Dict[str, Any]:
    # v2 action payloads should go through the local inbox/exec path (not agentic-console).
    intent = str(payload.get("intent") or "chat").strip() or "chat"
    if (payload.get("action_payload") is not None) or (intent != "chat"):
        if not RECEIVE_LOCAL.exists():
            return {"ok": False, "route": "local", "error": f"missing_receiver:{RECEIVE_LOCAL}"}
        temp = REPO_ROOT / "ramshare" / "state" / "a2a" / f"payload_local_{int(time.time()*1000)}.json"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        cmd = ["python", str(RECEIVE_LOCAL), "--payload-file", str(temp)]
        if dry_run:
            return {"ok": True, "route": "local", "dry_run": True, "cmd": cmd}
        try:
            last = None
            for attempt in range(retries + 1):
                res = run(cmd, timeout=30)
                if res.returncode == 0:
                    return {"ok": True, "route": "local", "stdout": res.stdout.strip()}
                last = res.stderr.strip() or res.stdout.strip() or f"exit {res.returncode}"
                backoff_sleep_ms(backoff_ms, attempt)
            return {"ok": False, "route": "local", "error": last}
        finally:
            temp.unlink(missing_ok=True)

    cmd = [
        "python",
        str(SEND_LOCAL),
        str(payload.get("message", "")),
        "--sender",
        str(payload.get("sender", "Gemini")),
        "--receiver",
        str(payload.get("receiver", "remote")),
        "--priority",
        str(payload.get("priority", "normal")),
        "--mode",
        str(payload.get("mode", "plan")),
        "--task-id",
        str(payload.get("task_id", str(uuid.uuid4()))),
        "--schema-version",
        str(payload.get("schema_version", A2A_SCHEMA_V1)),
    ]
    if dry_run:
        return {"ok": True, "route": "local", "dry_run": True, "cmd": cmd}
    last = None
    for attempt in range(retries + 1):
        res = run(cmd, timeout=45)
        if res.returncode == 0:
            return {"ok": True, "route": "local", "stdout": res.stdout.strip()}
        last = res.stderr.strip() or res.stdout.strip() or f"exit {res.returncode}"
        backoff_sleep_ms(backoff_ms, attempt)
    return {"ok": False, "route": "local", "error": last}


def route_remote(payload: Dict[str, Any], peer: Dict[str, Any], retries: int, backoff_ms: int, dry_run: bool) -> Dict[str, Any]:
    transport = str(peer.get("transport", "ssh") or "ssh").strip().lower()
    temp = REPO_ROOT / "ramshare" / "state" / "a2a" / f"payload_{int(time.time()*1000)}.json"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if transport == "wsl":
        cmd = [
            "python",
            str(SEND_WSL),
            "--distro",
            str(peer.get("distro", "Ubuntu")),
            "--payload-file",
            str(temp),
            "--remote-repo",
            str(peer.get("remote_repo", "/home/codym/gemini-op-clean")),
            "--remote-python",
            str(peer.get("remote_python", "python3")),
        ]
    else:
        cmd = [
            "python",
            str(SEND_SSH),
            "--host",
            str(peer.get("host", "")),
            "--payload-file",
            str(temp),
            "--remote-repo",
            str(peer.get("remote_repo", "~/Gemini-op")),
            "--remote-python",
            str(peer.get("remote_python", "python3")),
            "--platform",
            str(peer.get("platform", "linux")),
        ]
    if dry_run:
        cmd.append("--dry-run")
        out = run(cmd, timeout=30)
        temp.unlink(missing_ok=True)
        return {
            "ok": out.returncode == 0,
            "route": "remote",
            "dry_run": True,
            "stdout": out.stdout.strip(),
            "stderr": out.stderr.strip(),
        }

    last = None
    try:
        for attempt in range(retries + 1):
            res = run(cmd, timeout=90)
            if res.returncode == 0:
                return {"ok": True, "route": "remote", "stdout": res.stdout.strip()}
            last = res.stderr.strip() or res.stdout.strip() or f"exit {res.returncode}"
            backoff_sleep_ms(backoff_ms, attempt)
        return {"ok": False, "route": "remote", "error": last}
    finally:
        temp.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Route A2A payload to local or remote peer with retries.")
    ap.add_argument("--route", choices=["local", "remote", "auto"], default="auto")
    ap.add_argument("--peer", default="laptop", help="peer key in peers.json when route is remote/auto")
    ap.add_argument("--message")
    ap.add_argument("--payload-file")
    ap.add_argument("--sender", default="Gemini")
    ap.add_argument("--receiver", default="remote")
    ap.add_argument("--priority", default="normal")
    ap.add_argument("--mode", default="plan")
    ap.add_argument("--intent", default="chat", help="a2a.v2: chat|execute_tool|write_file")
    ap.add_argument("--action-tool", dest="action_tool", default="", help="a2a.v2: tool name (e.g., run_script, shell_execute)")
    ap.add_argument("--action-params-json", dest="action_params_json", default="", help="a2a.v2: JSON object for tool params")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--backoff-ms", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    peers = load_peers(PEERS_PATH)
    payload = build_payload(args)
    validate_payload_contract(payload)
    task_id = str(payload.get("task_id") or str(uuid.uuid4()))
    payload["task_id"] = task_id

    if not mark_or_reject_task(task_id):
        result = {"ok": False, "route": "blocked", "error": f"duplicate_task_id:{task_id}"}
        print(json.dumps(result, indent=2))
        raise SystemExit(1)

    outbox_file = create_outbox(payload)
    chosen_route = args.route
    if args.route == "auto":
        chosen_route = "remote" if args.peer in peers else "local"
    # Optional shared secret injection for v2 receive path (and agentic-console if desired).
    # - If peer has shared_secret, prefer it.
    # - Else, fall back to environment variable.
    if "shared_secret" not in payload:
        if chosen_route == "remote":
            peer_cfg = peers.get(args.peer) if isinstance(peers, dict) else None
            peer_secret = ""
            if isinstance(peer_cfg, dict):
                peer_secret = str(peer_cfg.get("shared_secret", "") or "").strip()
            payload_secret = peer_secret or shared_secret_env()
        else:
            payload_secret = shared_secret_env()
        if payload_secret:
            payload["shared_secret"] = payload_secret

    routed_at = time.time()
    if chosen_route == "local":
        result = route_local(payload, retries=args.retries, backoff_ms=args.backoff_ms, dry_run=args.dry_run)
    else:
        peer = peers.get(args.peer)
        if not peer:
            raise SystemExit(f"peer not found: {args.peer}. define it in {PEERS_PATH}")
        result = route_remote(payload, peer=peer, retries=args.retries, backoff_ms=args.backoff_ms, dry_run=args.dry_run)
        # Auto failover (chat-only): if remote fails in --route auto mode, attempt local delivery.
        intent = str(payload.get("intent") or "chat").strip() or "chat"
        if (
            args.route == "auto"
            and not bool(result.get("ok", False))
            and intent == "chat"
            and payload.get("action_payload") is None
            and not args.dry_run
        ):
            fallback = route_local(payload, retries=0, backoff_ms=args.backoff_ms, dry_run=False)
            if bool(fallback.get("ok", False)):
                fallback["fallback_from"] = "remote"
                fallback["remote_error"] = str(result.get("error", ""))
                result = fallback
    latency_ms = max(0.0, (time.time() - routed_at) * 1000.0)
    result["latency_ms"] = round(latency_ms, 2)
    stdout_text = str(result.get("stdout", "") or "")
    result["a2a_schema_version"] = str(payload.get("schema_version", A2A_SCHEMA_V1))
    result["ack"] = parse_ack(stdout_text, bool(result.get("ok", False)))
    result["ack_observed"] = bool(result["ack"].get("ack_observed", False))
    update_latency_histogram(chosen_route, latency_ms)

    if result.get("ok"):
        outbox_file.unlink(missing_ok=True)
    else:
        dlq_file = move_to_dlq(outbox_file, str(result.get("error", "unknown_error")))
        result["dlq_file"] = str(dlq_file)

    append_jsonl(
        AUDIT_PATH,
        {
            "ts": time.time(),
            "route": chosen_route,
            "ok": bool(result.get("ok")),
            "peer": args.peer,
            "task_id": task_id,
            "sender": payload.get("sender"),
            "receiver": payload.get("receiver"),
            "message": str(payload.get("message", ""))[:300],
            "result": result,
        },
    )
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

