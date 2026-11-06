"""Entry points exchange UTF-8 with hosts, independent of the platform's pipe code page."""

from __future__ import annotations

import io
import sys


def use_utf8() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
