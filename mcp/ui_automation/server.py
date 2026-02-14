from __future__ import annotations

import ctypes
import json
import re
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import winsound

import win32con
import win32gui
import win32process

from mcp.server import FastMCP


app = FastMCP("ui-automation")

REPO_ROOT = Path(r"C:\Gemini")
POLICY_PATH = REPO_ROOT / "mcp" / "policy_proxy" / "policy.json"
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "ui_automation.jsonl"
SECURITY_ALERT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "security_alerts.jsonl"
NOTIFY_LOG_PATH = REPO_ROOT / "mcp" / "data" / "notifications.log"
STOP_FILES_DEFAULT = [
    REPO_ROOT / "STOP_ALL_AGENTS.flag",
    REPO_ROOT / "ramshare" / "state" / "STOP",
]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32 = ctypes.windll.user32


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_policy() -> Dict[str, Any]:
    if not POLICY_PATH.exists():
        return {}
    return json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))


def _audit(action: str, ok: bool, details: Dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now_iso(), "action": action, "ok": ok, "details": details}
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _emit_notify_event(message: str, level: str = "error") -> None:
    event = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
    }
    NOTIFY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTIFY_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")


def _emit_security_alert(details: Dict[str, Any]) -> None:
    SECURITY_ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now_iso(), "type": "sidecar_escape_attempt", "details": details}
    with SECURITY_ALERT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _signal_local_alert() -> None:
    try:
        winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        pass


def _stop_files(policy: Dict[str, Any]) -> List[Path]:
    configured = policy.get("control_plane", {}).get("stop_files", [])
    if configured:
        return [Path(str(p)) for p in configured]
    return STOP_FILES_DEFAULT


def _is_stopped(policy: Dict[str, Any]) -> bool:
    for p in _stop_files(policy):
        if p.exists():
            return True
    return False


def _window_process_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return ""
    try:
        import psutil

        return psutil.Process(pid).name()
    except Exception:
        return ""


def _title_blocked(title: str, blocked_keywords: List[str]) -> bool:
    low = title.lower()
    return any(item.lower() in low for item in blocked_keywords)


def _process_allowed(proc_name: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    low = proc_name.lower()
    return any(low == item.lower() for item in allowed)


def _window_allowed(hwnd: int, policy: Dict[str, Any]) -> Dict[str, Any]:
    conf = policy.get("ui_automation", {})
    allowed_processes = [str(x) for x in conf.get("allowed_processes", [])]
    blocked_titles = [str(x) for x in conf.get("blocked_title_keywords", [])]
    title = win32gui.GetWindowText(hwnd) or ""
    proc_name = _window_process_name(hwnd)
    if not _process_allowed(proc_name, allowed_processes):
        return {"ok": False, "error": "process_denied", "title": title, "process": proc_name}
    if _title_blocked(title, blocked_titles):
        return {"ok": False, "error": "title_blocked", "title": title, "process": proc_name}
    return {"ok": True, "title": title, "process": proc_name}


def _seconds_since_last_input() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    tick_now = user32.GetTickCount()
    elapsed_ms = max(0, int(tick_now - info.dwTime))
    return elapsed_ms / 1000.0


def _enforce_yield(policy: Dict[str, Any]) -> Optional[str]:
    sec = float(policy.get("ui_automation", {}).get("yield_on_user_activity_sec", 2))
    if sec <= 0:
        return None
    elapsed = _seconds_since_last_input()
    if elapsed < sec:
        return f"user_active_recently:{elapsed:.2f}s"
    return None


def _list_visible_windows() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _cb(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return True
        rect = win32gui.GetWindowRect(hwnd)
        out.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "process": _window_process_name(hwnd),
                "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
            }
        )
        return True

    win32gui.EnumWindows(_cb, None)
    return out


def _find_windows_by_title(pattern: str) -> List[int]:
    rx = re.compile(pattern, re.IGNORECASE)
    out: List[int] = []
    for row in _list_visible_windows():
        if rx.search(row["title"]):
            out.append(int(row["hwnd"]))
    return out


def _matches_sidecar_title(title: str, patterns: List[str]) -> bool:
    if not patterns:
        return True
    for pattern in patterns:
        try:
            if re.search(pattern, title, re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in title.lower():
                return True
    return False


def _sidecar_window_required(policy: Dict[str, Any]) -> bool:
    return bool(policy.get("ui_automation", {}).get("require_sidecar_window", False))


def _validate_sidecar_window(hwnd: int, policy: Dict[str, Any]) -> Optional[str]:
    if not _sidecar_window_required(policy):
        return None
    title = win32gui.GetWindowText(hwnd) or ""
    patterns = [str(x) for x in policy.get("ui_automation", {}).get("sidecar_title_patterns", [])]
    if _matches_sidecar_title(title, patterns):
        return None
    return "sidecar_window_required"


def _audit_sidecar_escape(action: str, hwnd: int) -> None:
    details = {
        "action": action,
        "hwnd": int(hwnd),
        "title": win32gui.GetWindowText(int(hwnd)) or "",
        "process": _window_process_name(int(hwnd)),
        "reason": "sidecar_window_required",
    }
    _audit(
        "sidecar_escape_attempt",
        False,
        details,
    )
    _emit_security_alert(details)
    _emit_notify_event(
        f"SIDECAR containment blocked action={details['action']} target={details['process']} title={details['title']}",
        level="critical",
    )
    _signal_local_alert()


def _enum_child_controls(hwnd: int, max_items: int = 300) -> List[Dict[str, Any]]:
    controls: List[Dict[str, Any]] = []

    def _child_cb(chwnd: int, _: Any) -> bool:
        if len(controls) >= max_items:
            return False
        try:
            class_name = win32gui.GetClassName(chwnd)
            text = win32gui.GetWindowText(chwnd) or ""
            rect = win32gui.GetWindowRect(chwnd)
            controls.append(
                {
                    "hwnd": int(chwnd),
                    "class_name": class_name,
                    "text": text,
                    "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                }
            )
        except Exception:
            pass
        return True

    win32gui.EnumChildWindows(hwnd, _child_cb, None)
    return controls


def _send_click(hwnd: int) -> None:
    win32gui.PostMessage(hwnd, win32con.BM_CLICK, 0, 0)


def _send_set_text(hwnd: int, text: str) -> None:
    win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, text)


@app.tool()
def list_windows(limit: int = 30) -> Dict[str, Any]:
    """List visible top-level windows available to the automation layer."""
    windows = _list_visible_windows()
    windows = windows[: max(1, int(limit))]
    _audit("list_windows", True, {"count": len(windows)})
    return {"ok": True, "count": len(windows), "windows": windows}


@app.tool()
def list_sidecar_windows(limit: int = 30) -> Dict[str, Any]:
    """List windows matching sidecar title patterns."""
    policy = _load_policy()
    patterns = [str(x) for x in policy.get("ui_automation", {}).get("sidecar_title_patterns", [])]
    windows = _list_visible_windows()
    filtered = [w for w in windows if _matches_sidecar_title(str(w.get("title", "")), patterns)]
    filtered = filtered[: max(1, int(limit))]
    _audit("list_sidecar_windows", True, {"count": len(filtered), "patterns": patterns})
    return {"ok": True, "count": len(filtered), "patterns": patterns, "windows": filtered}


@app.tool()
def list_controls(window_hwnd: int, max_items: int = 200) -> Dict[str, Any]:
    """List child controls for a top-level window handle."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("list_controls", False, {"window_hwnd": int(window_hwnd), "error": "stopped"})
        return {"ok": False, "error": "stopped"}

    hwnd = int(window_hwnd)
    if not win32gui.IsWindow(hwnd):
        _audit("list_controls", False, {"window_hwnd": hwnd, "error": "window_not_found"})
        return {"ok": False, "error": "window_not_found"}

    allow = _window_allowed(hwnd, policy)
    if not bool(allow.get("ok")):
        _audit("list_controls", False, {"window_hwnd": hwnd, "error": allow.get("error")})
        return {"ok": False, "error": str(allow.get("error"))}
    sidecar_error = _validate_sidecar_window(hwnd, policy)
    if sidecar_error:
        _audit_sidecar_escape("list_controls", hwnd)
        _audit("list_controls", False, {"window_hwnd": hwnd, "error": sidecar_error})
        return {"ok": False, "error": sidecar_error}

    controls = _enum_child_controls(hwnd, max_items=max(1, int(max_items)))
    _audit("list_controls", True, {"window_hwnd": hwnd, "count": len(controls)})
    return {"ok": True, "window_hwnd": hwnd, "count": len(controls), "controls": controls}


@app.tool()
def focus_window(title_pattern: str) -> Dict[str, Any]:
    """Focus a window by title regex only when policy allows focus stealing."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("focus_window", False, {"pattern": title_pattern, "error": "stopped"})
        return {"ok": False, "error": "stopped"}

    allow_focus = bool(policy.get("ui_automation", {}).get("allow_focus_steal", False))
    if not allow_focus:
        _audit("focus_window", False, {"pattern": title_pattern, "error": "focus_steal_denied"})
        return {"ok": False, "error": "focus_steal_denied"}

    matches = _find_windows_by_title(title_pattern)
    if not matches:
        _audit("focus_window", False, {"pattern": title_pattern, "error": "window_not_found"})
        return {"ok": False, "error": "window_not_found"}
    hwnd = int(matches[0])
    allow = _window_allowed(hwnd, policy)
    if not bool(allow.get("ok")):
        _audit("focus_window", False, {"pattern": title_pattern, "error": allow.get("error"), "hwnd": hwnd})
        return {"ok": False, "error": str(allow.get("error"))}
    sidecar_error = _validate_sidecar_window(hwnd, policy)
    if sidecar_error:
        _audit_sidecar_escape("focus_window", hwnd)
        _audit("focus_window", False, {"pattern": title_pattern, "error": sidecar_error, "hwnd": hwnd})
        return {"ok": False, "error": sidecar_error}

    user_busy = _enforce_yield(policy)
    if user_busy:
        _audit("focus_window", False, {"pattern": title_pattern, "error": user_busy})
        return {"ok": False, "error": user_busy}

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    _audit("focus_window", True, {"pattern": title_pattern, "hwnd": hwnd})
    return {"ok": True, "hwnd": hwnd, "title": allow.get("title"), "process": allow.get("process")}


@app.tool()
def click_control(control_hwnd: int) -> Dict[str, Any]:
    """Invoke a click on a control handle without moving the mouse cursor."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("click_control", False, {"control_hwnd": int(control_hwnd), "error": "stopped"})
        return {"ok": False, "error": "stopped"}

    hwnd = int(control_hwnd)
    if not win32gui.IsWindow(hwnd):
        _audit("click_control", False, {"control_hwnd": hwnd, "error": "control_not_found"})
        return {"ok": False, "error": "control_not_found"}

    root = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
    allow = _window_allowed(int(root), policy)
    if not bool(allow.get("ok")):
        _audit("click_control", False, {"control_hwnd": hwnd, "error": allow.get("error"), "root": int(root)})
        return {"ok": False, "error": str(allow.get("error"))}
    sidecar_error = _validate_sidecar_window(int(root), policy)
    if sidecar_error:
        _audit_sidecar_escape("click_control", int(root))
        _audit("click_control", False, {"control_hwnd": hwnd, "error": sidecar_error, "root": int(root)})
        return {"ok": False, "error": sidecar_error}

    user_busy = _enforce_yield(policy)
    if user_busy:
        _audit("click_control", False, {"control_hwnd": hwnd, "error": user_busy})
        return {"ok": False, "error": user_busy}

    _send_click(hwnd)
    _audit("click_control", True, {"control_hwnd": hwnd, "root": int(root)})
    return {"ok": True, "control_hwnd": hwnd}


@app.tool()
def set_control_text(control_hwnd: int, text: str) -> Dict[str, Any]:
    """Set control text via WM_SETTEXT without cursor injection."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("set_control_text", False, {"control_hwnd": int(control_hwnd), "error": "stopped"})
        return {"ok": False, "error": "stopped"}

    hwnd = int(control_hwnd)
    if not win32gui.IsWindow(hwnd):
        _audit("set_control_text", False, {"control_hwnd": hwnd, "error": "control_not_found"})
        return {"ok": False, "error": "control_not_found"}

    root = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
    allow = _window_allowed(int(root), policy)
    if not bool(allow.get("ok")):
        _audit("set_control_text", False, {"control_hwnd": hwnd, "error": allow.get("error"), "root": int(root)})
        return {"ok": False, "error": str(allow.get("error"))}
    sidecar_error = _validate_sidecar_window(int(root), policy)
    if sidecar_error:
        _audit_sidecar_escape("set_control_text", int(root))
        _audit("set_control_text", False, {"control_hwnd": hwnd, "error": sidecar_error, "root": int(root)})
        return {"ok": False, "error": sidecar_error}

    user_busy = _enforce_yield(policy)
    if user_busy:
        _audit("set_control_text", False, {"control_hwnd": hwnd, "error": user_busy})
        return {"ok": False, "error": user_busy}

    _send_set_text(hwnd, text)
    _audit("set_control_text", True, {"control_hwnd": hwnd, "chars": len(text), "root": int(root)})
    return {"ok": True, "control_hwnd": hwnd, "chars": len(text)}


@app.tool()
def send_keys_to_window(window_title_pattern: str, text: str) -> Dict[str, Any]:
    """Send text keystrokes to a matched window (focus required; disabled by default)."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": "stopped"})
        return {"ok": False, "error": "stopped"}

    allow_focus = bool(policy.get("ui_automation", {}).get("allow_focus_steal", False))
    if not allow_focus:
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": "focus_steal_denied"})
        return {"ok": False, "error": "focus_steal_denied"}

    matches = _find_windows_by_title(window_title_pattern)
    if not matches:
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": "window_not_found"})
        return {"ok": False, "error": "window_not_found"}
    hwnd = int(matches[0])
    allow = _window_allowed(hwnd, policy)
    if not bool(allow.get("ok")):
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": allow.get("error"), "hwnd": hwnd})
        return {"ok": False, "error": str(allow.get("error"))}
    sidecar_error = _validate_sidecar_window(hwnd, policy)
    if sidecar_error:
        _audit_sidecar_escape("send_keys_to_window", hwnd)
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": sidecar_error, "hwnd": hwnd})
        return {"ok": False, "error": sidecar_error}

    user_busy = _enforce_yield(policy)
    if user_busy:
        _audit("send_keys_to_window", False, {"pattern": window_title_pattern, "error": user_busy})
        return {"ok": False, "error": user_busy}

    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    for ch in text:
        win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(ch), 0)
    _audit("send_keys_to_window", True, {"hwnd": hwnd, "chars": len(text), "pattern": window_title_pattern})
    return {"ok": True, "hwnd": hwnd, "chars": len(text)}


if __name__ == "__main__":
    app.run()
