from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Tuple

from cryptography.fernet import Fernet
from mcp.server import FastMCP

try:
    import win32crypt  # type: ignore
except Exception:  # pragma: no cover
    win32crypt = None


app = FastMCP("secrets-vault")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
KEY_PATH = os.path.join(DATA_DIR, "secrets.key")  # legacy Fernet key (migration only)
STORE_PATH = os.path.join(DATA_DIR, "secrets.json")


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_store() -> Dict[str, Any]:
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            obj = json.load(handle)
            return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_store(store: Dict[str, Any]) -> None:
    _ensure_dirs()
    with open(STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2)


def _dpapi_available() -> bool:
    return win32crypt is not None and os.name == "nt"


def _dpapi_encrypt(plain: str) -> str:
    if not _dpapi_available():
        raise RuntimeError("DPAPI unavailable: install pywin32 and run on Windows.")
    raw = plain.encode("utf-8")
    # CryptProtectData binds encryption to current Windows user context.
    protected = win32crypt.CryptProtectData(raw, "Gemini-secrets", None, None, None, 0)
    return base64.b64encode(protected).decode("ascii")


def _dpapi_decrypt(cipher_b64: str) -> str:
    if not _dpapi_available():
        raise RuntimeError("DPAPI unavailable: install pywin32 and run on Windows.")
    protected = base64.b64decode(cipher_b64.encode("ascii"))
    _desc, raw = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    return raw.decode("utf-8")


def _load_legacy_key() -> bytes:
    _ensure_dirs()
    if not os.path.exists(KEY_PATH):
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as handle:
            handle.write(key)
        return key
    with open(KEY_PATH, "rb") as handle:
        return handle.read()


def _legacy_decrypt(value: str) -> str:
    f = Fernet(_load_legacy_key())
    return f.decrypt(value.encode("utf-8")).decode("utf-8")


def _migrate_legacy_if_needed(store: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Convert old Fernet-only entries into DPAPI entries.
    Old format: key -> "<fernet token string>"
    New format: key -> {"enc": "dpapi", "value": "<base64>"}
    """
    changed = False
    out: Dict[str, Any] = {}
    for k, v in store.items():
        if isinstance(v, dict) and str(v.get("enc")) == "dpapi" and isinstance(v.get("value"), str):
            out[k] = v
            continue
        if isinstance(v, str):
            # Try decrypt as legacy fernet and re-encrypt via DPAPI.
            try:
                plain = _legacy_decrypt(v)
                out[k] = {"enc": "dpapi", "value": _dpapi_encrypt(plain)}
                changed = True
            except Exception:
                # Keep unknown format as-is to avoid destructive migration.
                out[k] = v
            continue
        out[k] = v
    return out, changed


def _get_plain(store: Dict[str, Any], key: str) -> str:
    if key not in store:
        raise KeyError("not_found")
    item = store[key]
    if isinstance(item, dict) and str(item.get("enc")) == "dpapi" and isinstance(item.get("value"), str):
        return _dpapi_decrypt(item["value"])
    if isinstance(item, str):
        # Legacy fallback read path.
        return _legacy_decrypt(item)
    raise RuntimeError("invalid_secret_format")


def _set_plain(store: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
    store[key] = {"enc": "dpapi", "value": _dpapi_encrypt(value)}
    return store


@app.tool()
def vault_status() -> Dict[str, Any]:
    """Return vault backend status and migration hints."""
    store = _load_store()
    dpapi_entries = 0
    legacy_entries = 0
    for v in store.values():
        if isinstance(v, dict) and str(v.get("enc")) == "dpapi":
            dpapi_entries += 1
        elif isinstance(v, str):
            legacy_entries += 1
    return {
        "ok": True,
        "dpapi_available": _dpapi_available(),
        "store_path": STORE_PATH,
        "dpapi_entries": dpapi_entries,
        "legacy_entries": legacy_entries,
        "migration_recommended": legacy_entries > 0,
    }


@app.tool()
def migrate_legacy() -> Dict[str, Any]:
    """Migrate legacy Fernet entries in secrets.json into DPAPI format."""
    if not _dpapi_available():
        return {"ok": False, "error": "dpapi_unavailable"}
    store = _load_store()
    migrated, changed = _migrate_legacy_if_needed(store)
    if changed:
        _save_store(migrated)
    return {"ok": True, "migrated": changed}


@app.tool()
def set_secret(key: str, value: str) -> Dict[str, Any]:
    """Store a secret encrypted with Windows DPAPI."""
    if not _dpapi_available():
        return {"ok": False, "error": "dpapi_unavailable"}
    store = _load_store()
    store, changed = _migrate_legacy_if_needed(store)
    if changed:
        _save_store(store)
    store = _set_plain(store, key, value)
    _save_store(store)
    return {"ok": True, "key": key, "backend": "dpapi"}


@app.tool()
def get_secret(key: str) -> Dict[str, Any]:
    """Retrieve a secret value."""
    store = _load_store()
    store, changed = _migrate_legacy_if_needed(store)
    if changed:
        _save_store(store)
    try:
        value = _get_plain(store, key)
    except KeyError:
        return {"ok": False, "error": "not_found"}
    except Exception as e:
        return {"ok": False, "error": "decrypt_failed", "detail": str(e)}
    return {"ok": True, "key": key, "value": value}


@app.tool()
def list_secrets() -> List[str]:
    """List secret keys (values are not returned)."""
    store = _load_store()
    return sorted(store.keys())


if __name__ == "__main__":
    app.run()
