import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict
from urllib import request


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _keyring() -> Dict[str, str]:
    keys: Dict[str, str] = {}
    key_id = os.environ.get("EVIDENCE_HMAC_KEY_ID", "local-v1").strip() or "local-v1"
    key = os.environ.get("EVIDENCE_HMAC_KEY", "").strip()
    if key:
        keys[key_id] = key
    raw = os.environ.get("EVIDENCE_HMAC_KEYS_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        keys[k.strip()] = v.strip()
        except Exception:
            pass
    return keys


def _active_key_id() -> str:
    return os.environ.get("EVIDENCE_HMAC_KEY_ID", "local-v1").strip() or "local-v1"


def _require_signing() -> bool:
    return os.environ.get("EVIDENCE_SIGNING_REQUIRED", "1").strip() not in ("0", "false", "False")


def previous_hash(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    last = ""
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            last = line
    if not last:
        return ""
    try:
        obj = json.loads(last)
        return str(obj.get("entry_hash") or "")
    except Exception:
        return ""


def _canonical_base(base: Dict[str, Any]) -> str:
    return json.dumps(base, sort_keys=True, separators=(",", ":"))


def _sign(canonical_base: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), canonical_base.encode("utf-8"), hashlib.sha256).hexdigest()


def append_signed_entry(log_path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = previous_hash(log_path)
    key_id = _active_key_id()
    keys = _keyring()
    key = keys.get(key_id, "")
    required = _require_signing()
    if required and not key:
        raise RuntimeError("EVIDENCE_HMAC_KEY missing while signing is required")

    base = {
        "ts": now_iso(),
        "prev_hash": prev_hash,
        "key_id": key_id,
        "algo": "HMAC-SHA256",
        "payload": payload,
    }
    canonical_base = _canonical_base(base)
    signature = _sign(canonical_base, key) if key else ""
    entry_hash = hashlib.sha256((canonical_base + "|" + signature).encode("utf-8")).hexdigest()
    row = {**base, "signature": signature, "entry_hash": entry_hash}
    line = json.dumps(row, separators=(",", ":"))
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    sink_entry(line)
    return row


def sink_entry(line: str) -> None:
    sink_path = os.environ.get("EVIDENCE_SINK_PATH", "").strip()
    if sink_path:
        p = Path(sink_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    sink_url = os.environ.get("EVIDENCE_SINK_URL", "").strip()
    if sink_url:
        data = line.encode("utf-8")
        req = request.Request(
            sink_url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Gemini-op-evidence/1.0"},
        )
        with request.urlopen(req, timeout=10):
            pass


def verify_log(log_path: Path) -> Dict[str, Any]:
    if not log_path.exists():
        return {"ok": True, "entries": 0, "reason": "missing log file"}
    keys = _keyring()
    required = _require_signing()
    prev_hash = ""
    entries = 0

    legacy_entries = 0
    signed_entries = 0
    for lineno, raw in enumerate(log_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        entries += 1
        try:
            obj = json.loads(raw)
        except Exception:
            return {"ok": False, "entries": entries, "line": lineno, "reason": "invalid json"}

        if str(obj.get("prev_hash") or "") != prev_hash:
            return {"ok": False, "entries": entries, "line": lineno, "reason": "prev_hash mismatch"}

        key_id = str(obj.get("key_id") or "")
        signature = str(obj.get("signature") or "")
        algo = str(obj.get("algo") or "")

        # Backward compatibility for legacy hash-chain entries.
        is_legacy = not key_id and not signature and not algo
        if is_legacy:
            legacy_entries += 1
            legacy_base = {
                "ts": obj.get("ts"),
                "prev_hash": obj.get("prev_hash"),
                "payload": obj.get("payload"),
            }
            canonical_legacy = _canonical_base(legacy_base)
            expected_hash = hashlib.sha256(canonical_legacy.encode("utf-8")).hexdigest()
            if str(obj.get("entry_hash") or "") != expected_hash:
                return {"ok": False, "entries": entries, "line": lineno, "reason": "legacy entry_hash mismatch"}
            prev_hash = expected_hash
            continue

        signed_entries += 1
        base = {
            "ts": obj.get("ts"),
            "prev_hash": obj.get("prev_hash"),
            "key_id": obj.get("key_id"),
            "algo": obj.get("algo"),
            "payload": obj.get("payload"),
        }
        canonical_base = _canonical_base(base)
        key = keys.get(key_id, "")

        if required and not key:
            return {"ok": False, "entries": entries, "line": lineno, "reason": f"missing key for key_id={key_id}"}
        if key:
            expected_sig = _sign(canonical_base, key)
            if not hmac.compare_digest(signature, expected_sig):
                return {"ok": False, "entries": entries, "line": lineno, "reason": "signature mismatch"}
        elif signature:
            return {"ok": False, "entries": entries, "line": lineno, "reason": "unsigned key with non-empty signature"}

        expected_hash = hashlib.sha256((canonical_base + "|" + signature).encode("utf-8")).hexdigest()
        if str(obj.get("entry_hash") or "") != expected_hash:
            return {"ok": False, "entries": entries, "line": lineno, "reason": "entry_hash mismatch"}

        prev_hash = expected_hash

    return {
        "ok": True,
        "entries": entries,
        "legacy_entries": legacy_entries,
        "signed_entries": signed_entries,
        "head_hash": prev_hash,
    }
