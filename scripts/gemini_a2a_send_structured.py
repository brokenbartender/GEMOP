import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

A2A_SCHEMA_VERSION = "a2a.v1"
ACK_SCHEMA_VERSION = "a2a.ack.v1"

ENV_PATH = Path(r"C:\Users\codym\agentic-console\.env")
REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
PREFLIGHT_SCRIPT = REPO_ROOT / "scripts" / "GEMINI_preflight.py"
TASK_PATH = Path(r"C:\Users\codym\.Gemini\current_task.json")


def risk_score(text: str) -> tuple[int, list[str]]:
    lowered = (text or "").lower()
    score = 100
    reasons = []

    rules = [
        (r"\b(delete|del|remove-item|rm|rmdir|rd)\b", 35, "delete/remove"),
        (r"\b(format|diskpart|clean all|wipe)\b", 45, "disk destructive"),
        (r"\b(shutdown|reboot|restart|poweroff)\b", 25, "system power"),
        (r"\b(regedit|registry|reg add|reg delete)\b", 20, "registry change"),
        (r"\b(taskkill|kill -9|stop-process)\b", 15, "process kill"),
        (r"\b(system32|boot|bcdedit)\b", 25, "system critical"),
        (r"\b(chkdsk|sfc|dism)\b", 10, "system repair"),
        (r"\b(password|credential|token|secret)\b", 10, "sensitive data"),
        (r"\b(ssh|scp|rsync)\b", 5, "remote ops"),
    ]

    for pattern, penalty, label in rules:
        if re.search(pattern, lowered):
            score -= penalty
            reasons.append(label)

    if score < 0:
        score = 0
    return score, reasons


def read_env():
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def _task_load():
    if TASK_PATH.exists():
        try:
            return json.loads(TASK_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"task": "", "steps": []}
    return {"task": "", "steps": []}


def _task_save(data):
    TASK_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _task_add_step(task_name: str, step_text: str) -> int:
    data = _task_load()
    if task_name:
        data["task"] = task_name
    steps = data.setdefault("steps", [])
    next_id = 1 + max([s.get("id", 0) for s in steps] or [0])
    steps.append({"id": next_id, "text": step_text, "status": "pending"})
    _task_save(data)
    return next_id


def _task_set(step_id: int, status: str):
    data = _task_load()
    for s in data.get("steps", []):
        if s.get("id") == step_id:
            s["status"] = status
    _task_save(data)


def main():
    ap = argparse.ArgumentParser(description="Send structured A2A payload")
    ap.add_argument("message", help="Message to send")
    ap.add_argument("--sender", default="Gemini")
    ap.add_argument("--receiver", default="remote")
    ap.add_argument("--priority", default="normal")
    ap.add_argument("--mode", default="plan")
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--schema-version", default=A2A_SCHEMA_VERSION)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="Send dry-run flag to console")
    ap.add_argument("--reflect", action="store_true", help="Emit reflection prompt on failure")
    ap.add_argument("--timeout", type=int, default=5, help="HTTP timeout (seconds)")
    ap.add_argument("--risk-threshold", type=int, default=80, help="Minimum risk score to proceed")
    ap.add_argument("--force", action="store_true", help="Bypass risk threshold")
    ap.add_argument("--verify-path", help="Verify file path exists after send")
    ap.add_argument("--verify-url", help="Verify URL responds after send")
    ap.add_argument("--watch", type=int, default=0, help="Watch job queue for N seconds")
    ap.add_argument("--preflight", action="store_true", help="Run preflight checks before sending")
    ap.add_argument("--no-preflight", action="store_true", help="Skip preflight checks")
    ap.add_argument("--task", help="Initialize current_task.json task name")
    ap.add_argument("--step", help="Add a pending step before send")
    ap.add_argument("--complete-on-success", action="store_true", help="Mark step done after successful send")
    args = ap.parse_args()

    if args.preflight or (not args.no_preflight and PREFLIGHT_SCRIPT.exists()):
        subprocess.check_call([sys.executable, str(PREFLIGHT_SCRIPT), "--prompt", args.message])

    env = read_env()
    host = env.get("AGENTIC_A2A_HOST", "127.0.0.1")
    port = env.get("AGENTIC_A2A_PORT", "9451")
    secret = env.get("AGENTIC_A2A_SHARED_SECRET", "")

    score, reasons = risk_score(args.message)
    if score < args.risk_threshold and not args.force:
        reason_txt = ", ".join(reasons) if reasons else "unknown risk"
        raise SystemExit(
            f"Risk score {score} below threshold {args.risk_threshold}. Reasons: {reason_txt}. "
            "Re-run with --force to bypass."
        )

    step_id = None
    if args.step:
        step_id = _task_add_step(args.task or "", args.step)

    payload = {
        "sender": args.sender,
        "receiver": args.receiver,
        "message": args.message,
        "task_id": args.task_id or str(uuid.uuid4()),
        "schema_version": args.schema_version,
        "priority": args.priority,
        "mode": args.mode,
        "timestamp": time.time(),
        "risk_score": score,
        "risk_reasons": reasons,
    }
    if args.dry_run:
        payload["dry_run"] = True
    if secret:
        payload["shared_secret"] = secret

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}/a2a",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_err = None
    ack_result = {
        "ack_contract_version": ACK_SCHEMA_VERSION,
        "ack_status": "none",
        "ack_observed": False,
    }
    for attempt in range(args.retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(resp.status)
                body_raw = resp.read().decode("utf-8", errors="ignore").strip()
                if body_raw:
                    try:
                        parsed = json.loads(body_raw)
                        if isinstance(parsed, dict):
                            if isinstance(parsed.get("ack"), dict):
                                ack = parsed["ack"]
                                ack_result["ack_status"] = str(ack.get("ack_status", "received"))
                                ack_result["ack_observed"] = bool(ack.get("ack_observed", True))
                                ack_result["ack_contract_version"] = str(
                                    ack.get("ack_contract_version", ACK_SCHEMA_VERSION)
                                )
                            elif "ack_status" in parsed:
                                ack_result["ack_status"] = str(parsed.get("ack_status", "received"))
                                ack_result["ack_observed"] = ack_result["ack_status"] in {"accepted", "received", "queued"}
                            else:
                                ack_result["ack_status"] = "transport_only"
                    except Exception:
                        ack_result["ack_status"] = "transport_only"
                else:
                    ack_result["ack_status"] = "transport_only"
                break
        except Exception as exc:
            last_err = exc
            time.sleep(0.5 * (attempt + 1))

    if last_err is not None:
        if args.reflect:
            print(f"REFLECT: A2A send failed with error: {last_err}. Analyze cause and propose a fix.")
        raise SystemExit(f"A2A send failed: {last_err}")
    if ack_result["ack_status"] in {"received", "accepted", "queued"}:
        ack_result["ack_observed"] = True

    # Optional verification
    verify_ok = True
    if args.verify_path:
        exists = os.path.exists(args.verify_path)
        print(json.dumps({"verify_path": args.verify_path, "exists": bool(exists)}))
        verify_ok = verify_ok and bool(exists)
    if args.verify_url:
        status = None
        try:
            with urllib.request.urlopen(args.verify_url, timeout=5) as resp:
                status = resp.status
        except Exception as exc:
            status = f"ERROR: {exc}"
        print(json.dumps({"verify_url": args.verify_url, "status": status}))
        verify_ok = verify_ok and (status == 200)

    # Optional watch: poll job queue for up to N seconds
    if args.watch and args.watch > 0:
        web_host = env.get("AGENTIC_WEB_HOST", "127.0.0.1")
        web_port = env.get("AGENTIC_WEB_PORT", "8333")
        deadline = time.time() + args.watch
        warned = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://{web_host}:{web_port}/api/jobs", timeout=3) as resp:
                    if resp.status == 200:
                        jobs = json.loads(resp.read().decode("utf-8", errors="ignore"))
                        if jobs and not warned and time.time() + 1 < deadline:
                            warned = True
                            print("WATCH: jobs still running; consider waiting or cancelling.")
            except Exception:
                pass
            time.sleep(2)

    if args.force:
        print(json.dumps({"force_used": True, "risk_score": score, "risk_reasons": reasons}))

    if args.complete_on_success and step_id is not None and verify_ok:
        _task_set(step_id, "done")

    print(
        json.dumps(
            {
                "ok": True,
                "task_id": payload["task_id"],
                "schema_version": payload["schema_version"],
                "ack": ack_result,
            }
        )
    )


if __name__ == "__main__":
    main()
