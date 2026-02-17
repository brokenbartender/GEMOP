from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunSpec:
    runner_py: Path
    prompt_path: Path
    out_md: Path


def _create_windows_job() -> int | None:
    """
    Best-effort Windows Job Object container. Returns a handle int or None.
    If job creation fails, caller should fall back to normal subprocess behavior.
    """
    if not platform.system().lower().startswith("win"):
        return None

    try:
        import ctypes
        import ctypes.wintypes as wt

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        CreateJobObjectW = kernel32.CreateJobObjectW
        CreateJobObjectW.argtypes = [wt.LPVOID, wt.LPCWSTR]
        CreateJobObjectW.restype = wt.HANDLE

        SetInformationJobObject = kernel32.SetInformationJobObject
        SetInformationJobObject.argtypes = [wt.HANDLE, wt.INT, wt.LPVOID, wt.DWORD]
        SetInformationJobObject.restype = wt.BOOL

        AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        AssignProcessToJobObject.restype = wt.BOOL

        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE via JOBOBJECT_EXTENDED_LIMIT_INFORMATION.
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", wt.ULONGLONG),
                ("WriteOperationCount", wt.ULONGLONG),
                ("OtherOperationCount", wt.ULONGLONG),
                ("ReadTransferCount", wt.ULONGLONG),
                ("WriteTransferCount", wt.ULONGLONG),
                ("OtherTransferCount", wt.ULONGLONG),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wt.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wt.LARGE_INTEGER),
                ("LimitFlags", wt.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wt.DWORD),
                ("SchedulingClass", wt.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        hjob = CreateJobObjectW(None, None)
        if not hjob:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = SetInformationJobObject(hjob, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            # If we can't set kill-on-close, close handle and fall back.
            kernel32.CloseHandle(hjob)
            return None
        return int(hjob)
    except Exception:
        return None


def _assign_to_job(hjob: int, proc_handle: int) -> None:
    try:
        import ctypes
        import ctypes.wintypes as wt

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        AssignProcessToJobObject.restype = wt.BOOL
        AssignProcessToJobObject(int(hjob), int(proc_handle))
    except Exception:
        return


def _close_job(hjob: int) -> None:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.CloseHandle(int(hjob))
    except Exception:
        return


def parse_args(argv: list[str]) -> RunSpec:
    if len(argv) != 4:
        raise SystemExit("usage: agent_host.py <runner_py> <prompt_path> <out_md>")
    runner_py = Path(argv[1]).resolve()
    prompt_path = Path(argv[2]).resolve()
    out_md = Path(argv[3]).resolve()
    return RunSpec(runner_py=runner_py, prompt_path=prompt_path, out_md=out_md)


def main(argv: list[str]) -> int:
    spec = parse_args(argv)
    cmd = [sys.executable, str(spec.runner_py), str(spec.prompt_path), str(spec.out_md)]

    # Ensure the child inherits the same repo-root context and stop flags.
    env = os.environ.copy()

    is_win = platform.system().lower().startswith("win")
    hjob = _create_windows_job() if is_win else None

    try:
        p = subprocess.Popen(cmd, env=env)
        if hjob is not None and is_win:
            try:
                import ctypes
                import ctypes.wintypes as wt

                kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                OpenProcess = kernel32.OpenProcess
                OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
                OpenProcess.restype = wt.HANDLE

                CloseHandle = kernel32.CloseHandle
                CloseHandle.argtypes = [wt.HANDLE]
                CloseHandle.restype = wt.BOOL

                PROCESS_SET_QUOTA = 0x0100
                PROCESS_TERMINATE = 0x0001
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

                hproc = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(p.pid))
                if hproc:
                    _assign_to_job(hjob, int(hproc))
                    CloseHandle(hproc)
            except Exception:
                # Not fatal; orchestrator still uses taskkill /T.
                pass
        return int(p.wait())
    finally:
        if hjob is not None:
            _close_job(hjob)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
