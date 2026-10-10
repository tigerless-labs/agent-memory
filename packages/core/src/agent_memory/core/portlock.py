"""Advisory file locking, portable across POSIX and Windows.

POSIX delegates to fcntl.flock; Windows uses msvcrt.locking over a one-byte
region at offset zero. Every writer locks the same region, so mutual exclusion
holds regardless of where a later write lands. Contention surfaces as
BlockingIOError on both platforms, so callers catch a single exception type.
"""

from __future__ import annotations

import contextlib
import os
import sys
from typing import Protocol


class _HasFileno(Protocol):
    def fileno(self) -> int: ...


def _fileno(handle: int | _HasFileno) -> int:
    return handle if isinstance(handle, int) else handle.fileno()


if sys.platform == "win32":
    import msvcrt

    _REGION = 1

    def lock_exclusive(handle: int | _HasFileno, *, blocking: bool) -> None:
        fileno = _fileno(handle)
        origin = os.lseek(fileno, 0, os.SEEK_CUR)
        os.lseek(fileno, 0, os.SEEK_SET)
        try:
            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            try:
                msvcrt.locking(fileno, mode, _REGION)
            except OSError as error:
                raise BlockingIOError(str(error)) from None
        finally:
            os.lseek(fileno, origin, os.SEEK_SET)

    def unlock(handle: int | _HasFileno) -> None:
        fileno = _fileno(handle)
        origin = os.lseek(fileno, 0, os.SEEK_CUR)
        os.lseek(fileno, 0, os.SEEK_SET)
        try:
            with contextlib.suppress(OSError):
                msvcrt.locking(fileno, msvcrt.LK_UNLCK, _REGION)
        finally:
            os.lseek(fileno, origin, os.SEEK_SET)

else:
    import fcntl

    def lock_exclusive(handle: int | _HasFileno, *, blocking: bool) -> None:
        flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(_fileno(handle), flags)

    def unlock(handle: int | _HasFileno) -> None:
        fcntl.flock(_fileno(handle), fcntl.LOCK_UN)
