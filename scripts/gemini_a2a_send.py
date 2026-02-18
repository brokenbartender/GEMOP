import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

A2A_SCHEMA_VERSION = "a2a.v1"
ACK_SCHEMA_VERSION = "a2a.ack.v1"

ENV_PATH = Path(r"C:\Users\codym\agentic-console\.env")
REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
PREFLIGHT_SCRIPT = REPO_ROOT / "scripts" / "gemini_preflight.py"


def read_env():
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def main():
    ap = argparse.ArgumentParser(description="Send a2a message to local agentic-console")
    ap.add_argument("message", help="Message to send")
    ap.add_argument("--sender", default="Gemini", help="Sender label")
    ap.add_argument("--receiver", default="remote", help="Receiver label")
    ap.add_argument("--schema-version", default=A2A_SCHEMA_VERSION, help="A2A schema contract version")
    ap.add_argument("--preflight", action="store_true", help="Run preflight checks before sending")
    ap.add_argument("--no-preflight", action="store_true", help="Skip preflight checks")
    args = ap.parse_args()

    if args.preflight or (not args.no_preflight and PREFLIGHT_SCRIPT.exists()):
        subprocess.check_call([sys.executable, str(PREFLIGHT_SCRIPT), "--prompt", args.message])

    env = read_env()
    host = env.get("AGENTIC_A2A_HOST", "127.0.0.1")
    port = env.get("AGENTIC_A2A_PORT", "9451")
    secret = env.get("AGENTIC_A2A_SHARED_SECRET", "")

    payload = {
        "sender": args.sender,
        "receiver": args.receiver,
        "message": args.message,
        "schema_version": args.schema_version,
    }
    if secret:
        payload["shared_secret"] = secret

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}/a2a",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise SystemExit(f"A2A send failed: {resp.status}")
        body_raw = resp.read().decode("utf-8", errors="ignore").strip()
        ack = {
            "ack_contract_version": ACK_SCHEMA_VERSION,
            "ack_status": "transport_only",
            "ack_observed": False,
        }
        if body_raw:
            try:
                parsed = json.loads(body_raw)
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("ack"), dict):
                        ack_payload = parsed["ack"]
                        ack["ack_status"] = str(ack_payload.get("ack_status", "received"))
                        ack["ack_observed"] = bool(ack_payload.get("ack_observed", True))
                        ack["ack_contract_version"] = str(ack_payload.get("ack_contract_version", ACK_SCHEMA_VERSION))
                    elif "ack_status" in parsed:
                        ack["ack_status"] = str(parsed.get("ack_status", "received"))
                        ack["ack_observed"] = ack["ack_status"] in {"accepted", "received", "queued"}
            except Exception:
                pass
        print(json.dumps({"ok": True, "schema_version": args.schema_version, "ack": ack}))


if __name__ == "__main__":
    main()
