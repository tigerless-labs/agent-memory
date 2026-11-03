"""Reader/writer advisory lock on an open file, with one semantics on POSIX and Windows."""

from __future__ import annotations

import sys
from typing import IO, Any

WINDOWS_FAIL_IMMEDIATELY = 0x1
WINDOWS_EXCLUSIVE = 0x2
WINDOWS_LOCK_VIOLATION = 33
WINDOWS_REGION_BEYOND_CONTENT_OFFSET_HIGH = 0x7FFFFFFF
WINDOWS_REGION_LENGTH = 1

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("internal", ctypes.c_void_p),
            ("internal_high", ctypes.c_void_p),
            ("offset", wintypes.DWORD),
            ("offset_high", wintypes.DWORD),
            ("event", wintypes.HANDLE),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.LockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    _kernel32.LockFileEx.restype = wintypes.BOOL
    _kernel32.UnlockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    _kernel32.UnlockFileEx.restype = wintypes.BOOL

    def _region() -> _Overlapped:
        return _Overlapped(offset=0, offset_high=WINDOWS_REGION_BEYOND_CONTENT_OFFSET_HIGH)

    def acquire(handle: IO[Any], *, shared: bool, blocking: bool) -> bool:
        flags = (0 if shared else WINDOWS_EXCLUSIVE) | (0 if blocking else WINDOWS_FAIL_IMMEDIATELY)
        os_handle = msvcrt.get_osfhandle(handle.fileno())
        region = ctypes.byref(_region())
        if _kernel32.LockFileEx(os_handle, flags, 0, WINDOWS_REGION_LENGTH, 0, region):
            return True
        error = ctypes.get_last_error()
        if error == WINDOWS_LOCK_VIOLATION and not blocking:
            return False
        raise ctypes.WinError(error)

    def release(handle: IO[Any]) -> None:
        os_handle = msvcrt.get_osfhandle(handle.fileno())
        region = ctypes.byref(_region())
        if not _kernel32.UnlockFileEx(os_handle, 0, WINDOWS_REGION_LENGTH, 0, region):
            raise ctypes.WinError(ctypes.get_last_error())

else:
    import fcntl

    def acquire(handle: IO[Any], *, shared: bool, blocking: bool) -> bool:
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        operation = mode if blocking else mode | fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), operation)
        except BlockingIOError:
            return False
        return True

    def release(handle: IO[Any]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
