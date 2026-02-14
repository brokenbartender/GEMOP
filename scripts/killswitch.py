from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
import sys
from pathlib import Path
from typing import List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
STOP_FILES = [
    REPO_ROOT / "STOP_ALL_AGENTS.flag",
    REPO_ROOT / "ramshare" / "state" / "STOP",
]

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_K = 0x4B
HOTKEY_ID = 0xC0DE
WM_HOTKEY = 0x0312


def _write_stop_files() -> List[str]:
    written: List[str] = []
    for path in STOP_FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("STOP\n", encoding="utf-8")
        written.append(str(path))
    return written


def _clear_stop_files() -> List[str]:
    cleared: List[str] = []
    for path in STOP_FILES:
        if path.exists():
            path.unlink()
            cleared.append(str(path))
    return cleared


def run_listener() -> int:
    user32 = ctypes.windll.user32
    mods = MOD_CONTROL | MOD_ALT | MOD_SHIFT

    if not user32.RegisterHotKey(None, HOTKEY_ID, mods, VK_K):
        print("Failed to register hotkey Ctrl+Alt+Shift+K", file=sys.stderr)
        return 1

    print("Kill switch armed: press Ctrl+Alt+Shift+K to stop all agents.")
    print("Watching for hotkey...")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                written = _write_stop_files()
                print("Emergency stop activated.")
                for item in written:
                    print(f" - {item}")
                return 0
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Global Gemini kill switch helper.")
    parser.add_argument("--trigger", action="store_true", help="Immediately create stop files and exit.")
    parser.add_argument("--clear", action="store_true", help="Clear stop files and exit.")
    args = parser.parse_args()

    if args.clear:
        cleared = _clear_stop_files()
        if cleared:
            print("Cleared stop files:")
            for item in cleared:
                print(f" - {item}")
        else:
            print("No stop files found.")
        return 0

    if args.trigger:
        written = _write_stop_files()
        print("Emergency stop activated.")
        for item in written:
            print(f" - {item}")
        return 0

    return run_listener()


if __name__ == "__main__":
    raise SystemExit(main())
