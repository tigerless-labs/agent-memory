"""Serve one run-scoped Manage review toolkit over stdio MCP."""

from __future__ import annotations

import pathlib
import sys
from collections.abc import Sequence
from typing import TextIO

from agent_memory.core import stdio
from agent_memory.core.manage_toolkit import ManageReviewToolkit

from . import server


def serve(directory: pathlib.Path, stream_in: TextIO, stream_out: TextIO) -> None:
    kit = ManageReviewToolkit.from_directory(directory)
    kit.save_record(directory)

    def catalogue() -> list[dict[str, object]]:
        return [
            {"name": spec.name, "description": spec.description, "inputSchema": spec.schema}
            for spec in kit.catalogue()
        ]

    def call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        reply = kit.call(name, arguments)
        kit.save_record(directory)
        return {"content": [{"type": "text", "text": reply.text}], "isError": reply.is_error}

    server.serve_lines(
        stream_in, stream_out, lambda request: server.respond(request, catalogue, call)
    )


def main(argv: Sequence[str] | None = None) -> int:
    stdio.use_utf8()
    arguments = list(sys.argv[1:] if argv is None else argv)
    serve(pathlib.Path(arguments[0]), sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
