from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import win32gui
import win32process
from PIL import Image, ImageGrab

from mcp.server import FastMCP


app = FastMCP("screen-perception")

REPO_ROOT = Path(r"C:\Gemini")
POLICY_PATH = REPO_ROOT / "mcp" / "policy_proxy" / "policy.json"
AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "screen_perception.jsonl"
STOP_FILES_DEFAULT = [
    REPO_ROOT / "STOP_ALL_AGENTS.flag",
    REPO_ROOT / "ramshare" / "state" / "STOP",
]


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


def _get_stop_files(policy: Dict[str, Any]) -> List[Path]:
    configured = policy.get("control_plane", {}).get("stop_files", [])
    if configured:
        return [Path(str(p)) for p in configured]
    return STOP_FILES_DEFAULT


def _is_stopped(policy: Dict[str, Any]) -> bool:
    for stop_file in _get_stop_files(policy):
        if stop_file.exists():
            return True
    return False


def _window_process_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return ""
    try:
        import psutil

        proc = psutil.Process(pid)
        return proc.name()
    except Exception:
        return ""


def _title_blocked(title: str, blocked_keywords: List[str]) -> bool:
    low = title.lower()
    for item in blocked_keywords:
        if item.lower() in low:
            return True
    return False


def _process_allowed(proc_name: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    low = proc_name.lower()
    return any(low == a.lower() for a in allowed)


def _window_allowed(hwnd: int, policy: Dict[str, Any]) -> Dict[str, Any]:
    conf = policy.get("screen_perception", {})
    allowed_processes = [str(x) for x in conf.get("allowed_processes", [])]
    blocked_titles = [str(x) for x in conf.get("blocked_title_keywords", [])]

    title = win32gui.GetWindowText(hwnd) or ""
    proc_name = _window_process_name(hwnd)

    if not _process_allowed(proc_name, allowed_processes):
        return {"ok": False, "error": "process_denied", "title": title, "process": proc_name}
    if _title_blocked(title, blocked_titles):
        return {"ok": False, "error": "title_blocked", "title": title, "process": proc_name}
    return {"ok": True, "title": title, "process": proc_name}


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
                "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                "process": _window_process_name(hwnd),
            }
        )
        return True

    win32gui.EnumWindows(_cb, None)
    return out


def _find_window_by_title(pattern: str) -> Optional[int]:
    rx = re.compile(pattern, re.IGNORECASE)
    for row in _list_visible_windows():
        if rx.search(row["title"]):
            return int(row["hwnd"])
    return None


def _find_windows_by_patterns(patterns: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not patterns:
        return out
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    for row in _list_visible_windows():
        title = row.get("title", "")
        if any(rx.search(title) for rx in compiled):
            out.append(row)
            if len(out) >= max(1, int(limit)):
                break
    return out


def _image_to_output(image: Image.Image, max_width: int) -> Dict[str, Any]:
    original_size = image.size
    if max_width > 0 and image.width > max_width:
        ratio = max_width / float(image.width)
        new_size = (max_width, max(1, int(image.height * ratio)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    out_dir = REPO_ROOT / "ramshare" / "state" / "captures"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = out_dir / f"capture_{ts}.png"
    image.save(out_path, format="PNG")
    return {
        "path": str(out_path),
        "size": {"width": image.width, "height": image.height},
        "original_size": {"width": original_size[0], "height": original_size[1]},
    }


@app.tool()
def get_active_window_info() -> Dict[str, Any]:
    """Return active window title, rectangle, and owning process."""
    policy = _load_policy()
    hwnd = int(win32gui.GetForegroundWindow())
    if hwnd <= 0:
        _audit("get_active_window_info", False, {"error": "no_active_window"})
        return {"ok": False, "error": "no_active_window"}
    title = win32gui.GetWindowText(hwnd) or ""
    rect = win32gui.GetWindowRect(hwnd)
    proc_name = _window_process_name(hwnd)
    allowed = _window_allowed(hwnd, policy)
    ok = bool(allowed.get("ok"))
    result = {
        "ok": ok,
        "hwnd": hwnd,
        "title": title,
        "process": proc_name,
        "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
    }
    if not ok:
        result["error"] = str(allowed.get("error"))
    _audit("get_active_window_info", ok, {"hwnd": hwnd, "title": title, "process": proc_name})
    return result


@app.tool()
def list_windows(limit: int = 30) -> Dict[str, Any]:
    """List visible top-level windows."""
    windows = _list_visible_windows()
    limited = windows[: max(1, int(limit))]
    _audit("list_windows", True, {"count": len(limited)})
    return {"ok": True, "count": len(limited), "windows": limited}


@app.tool()
def capture_active_window(max_width: Optional[int] = None) -> Dict[str, Any]:
    """Capture the active window as a PNG under ramshare/state/captures."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("capture_active_window", False, {"error": "stopped"})
        return {"ok": False, "error": "stopped"}

    hwnd = int(win32gui.GetForegroundWindow())
    if hwnd <= 0:
        _audit("capture_active_window", False, {"error": "no_active_window"})
        return {"ok": False, "error": "no_active_window"}

    allowed = _window_allowed(hwnd, policy)
    if not bool(allowed.get("ok")):
        _audit("capture_active_window", False, {"error": allowed.get("error"), "hwnd": hwnd})
        return {"ok": False, "error": str(allowed.get("error"))}

    rect = win32gui.GetWindowRect(hwnd)
    image = ImageGrab.grab(bbox=rect, all_screens=True)
    policy_max = int(policy.get("screen_perception", {}).get("max_image_width", 1600))
    use_max = int(max_width) if max_width else policy_max
    out = _image_to_output(image, max_width=min(use_max, policy_max))
    result = {"ok": True, "hwnd": hwnd, "title": allowed.get("title"), "process": allowed.get("process"), **out}
    _audit("capture_active_window", True, {"hwnd": hwnd, "path": out["path"]})
    return result


@app.tool()
def capture_window_by_title(title_pattern: str, max_width: Optional[int] = None) -> Dict[str, Any]:
    """Capture a window matching regex title_pattern."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("capture_window_by_title", False, {"error": "stopped", "pattern": title_pattern})
        return {"ok": False, "error": "stopped"}

    hwnd = _find_window_by_title(title_pattern)
    if not hwnd:
        _audit("capture_window_by_title", False, {"error": "window_not_found", "pattern": title_pattern})
        return {"ok": False, "error": "window_not_found", "pattern": title_pattern}

    allowed = _window_allowed(hwnd, policy)
    if not bool(allowed.get("ok")):
        _audit("capture_window_by_title", False, {"error": allowed.get("error"), "hwnd": hwnd})
        return {"ok": False, "error": str(allowed.get("error"))}

    rect = win32gui.GetWindowRect(hwnd)
    image = ImageGrab.grab(bbox=rect, all_screens=True)
    policy_max = int(policy.get("screen_perception", {}).get("max_image_width", 1600))
    use_max = int(max_width) if max_width else policy_max
    out = _image_to_output(image, max_width=min(use_max, policy_max))
    result = {"ok": True, "hwnd": hwnd, "title": allowed.get("title"), "process": allowed.get("process"), **out}
    _audit("capture_window_by_title", True, {"hwnd": hwnd, "path": out["path"], "pattern": title_pattern})
    return result


@app.tool()
def ocr_image(path: str, lang: str = "eng") -> Dict[str, Any]:
    """Run OCR on a local image path."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("ocr_image", False, {"error": "stopped", "path": path})
        return {"ok": False, "error": "stopped"}

    img_path = Path(path).expanduser().resolve()
    if not img_path.exists() or not img_path.is_file():
        _audit("ocr_image", False, {"error": "not_found", "path": str(img_path)})
        return {"ok": False, "error": "not_found", "path": str(img_path)}

    try:
        import pytesseract
    except Exception as exc:
        _audit("ocr_image", False, {"error": "pytesseract_missing", "path": str(img_path)})
        return {"ok": False, "error": f"pytesseract_missing: {exc}"}

    text = pytesseract.image_to_string(Image.open(img_path), lang=lang)
    _audit("ocr_image", True, {"path": str(img_path), "chars": len(text)})
    return {"ok": True, "path": str(img_path), "chars": len(text), "text": text}


@app.tool()
def list_sidecar_windows(limit: int = 10) -> Dict[str, Any]:
    """List windows matching sidecar title patterns from policy."""
    policy = _load_policy()
    patterns = [str(x) for x in policy.get("screen_perception", {}).get("sidecar_title_patterns", [])]
    rows = _find_windows_by_patterns(patterns, limit=max(1, int(limit)))
    _audit("list_sidecar_windows", True, {"count": len(rows), "patterns": patterns})
    return {"ok": True, "count": len(rows), "patterns": patterns, "windows": rows}


@app.tool()
def capture_sidecar_window(max_width: Optional[int] = None) -> Dict[str, Any]:
    """Capture the first window matching sidecar title patterns."""
    policy = _load_policy()
    if _is_stopped(policy):
        _audit("capture_sidecar_window", False, {"error": "stopped"})
        return {"ok": False, "error": "stopped"}

    patterns = [str(x) for x in policy.get("screen_perception", {}).get("sidecar_title_patterns", [])]
    rows = _find_windows_by_patterns(patterns, limit=1)
    if not rows:
        _audit("capture_sidecar_window", False, {"error": "sidecar_window_not_found", "patterns": patterns})
        return {"ok": False, "error": "sidecar_window_not_found", "patterns": patterns}

    hwnd = int(rows[0]["hwnd"])
    allowed = _window_allowed(hwnd, policy)
    if not bool(allowed.get("ok")):
        _audit("capture_sidecar_window", False, {"error": allowed.get("error"), "hwnd": hwnd})
        return {"ok": False, "error": str(allowed.get("error"))}

    rect = win32gui.GetWindowRect(hwnd)
    image = ImageGrab.grab(bbox=rect, all_screens=True)
    policy_max = int(policy.get("screen_perception", {}).get("max_image_width", 1600))
    use_max = int(max_width) if max_width else policy_max
    out = _image_to_output(image, max_width=min(use_max, policy_max))
    result = {"ok": True, "hwnd": hwnd, "title": allowed.get("title"), "process": allowed.get("process"), **out}
    _audit("capture_sidecar_window", True, {"hwnd": hwnd, "path": out["path"], "patterns": patterns})
    return result


if __name__ == "__main__":
    app.run()
