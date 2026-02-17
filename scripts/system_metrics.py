from __future__ import annotations

import ctypes
import os
import platform
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemInfo:
    total_mb: int
    avail_mb: int
    used_mb: int
    ts: float


def _clamp_i(x: int) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def memory_info() -> MemInfo:
    """
    Cross-platform-ish memory info. On Windows, uses GlobalMemoryStatusEx (no deps).
    On other platforms, returns 0s (best-effort).
    """
    ts = time.time()
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))  # type: ignore[attr-defined]
        if ok:
            total_mb = _clamp_i(st.ullTotalPhys // (1024 * 1024))
            avail_mb = _clamp_i(st.ullAvailPhys // (1024 * 1024))
            used_mb = max(0, total_mb - avail_mb)
            return MemInfo(total_mb=total_mb, avail_mb=avail_mb, used_mb=used_mb, ts=ts)

    # Linux/macOS: could parse /proc/meminfo, but keep dependency-free for now.
    return MemInfo(total_mb=0, avail_mb=0, used_mb=0, ts=ts)


def env_min_free_mem_mb(default: int = 1200) -> int:
    try:
        v = str(os.environ.get("GEMINI_OP_MIN_FREE_MEM_MB", "")).strip()
        return int(v) if v else int(default)
    except Exception:
        return int(default)


def low_memory() -> tuple[bool, dict[str, Any]]:
    mi = memory_info()
    min_free = env_min_free_mem_mb()
    if mi.avail_mb <= 0:
        return False, {"reason": "unknown", "min_free_mb": min_free, **mi.__dict__}
    ok = mi.avail_mb >= min_free
    return (not ok), {"reason": "low_memory" if not ok else "ok", "min_free_mb": min_free, **mi.__dict__}

