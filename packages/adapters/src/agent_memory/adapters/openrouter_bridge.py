"""Invocation-scoped OpenRouter compatibility bridge for Muse Code."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType

from .openrouter import OPENROUTER_BASE_URL, Credential

CATALOG_PATH = "/muse-code/models"
CONTEXT_LIMIT = 131_072
OUTPUT_LIMIT = 32_768
UPSTREAM_TIMEOUT_SECONDS = 300


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True


class OpenRouterBridge:
    def __init__(
        self,
        credential: Credential,
        model: str,
        *,
        upstream_url: str = OPENROUTER_BASE_URL,
    ):
        self.credential = credential
        self.model = model
        self.upstream_url = upstream_url.rstrip("/")
        self.server: _BridgeServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("OpenRouter bridge is not running")
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self) -> OpenRouterBridge:
        handler = _handler(self.credential, self.model, self.upstream_url)
        self.server = _BridgeServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _handler(
    credential: Credential, model: str, upstream_url: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0].endswith(CATALOG_PATH):
                self._send(200, _catalog(model))
                return
            self._forward()

        def do_POST(self) -> None:
            self._forward()

        def do_DELETE(self) -> None:
            self._forward()

        def do_PATCH(self) -> None:
            self._forward()

        def _forward(self) -> None:
            size = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(size) if size else None
            headers = {
                "Authorization": f"Bearer {credential.value}",
                "Accept": self.headers.get("Accept", "application/json"),
                "Accept-Encoding": "identity",
            }
            content_type = self.headers.get("Content-Type")
            if content_type:
                headers["Content-Type"] = content_type
            request = urllib.request.Request(
                f"{upstream_url}{self.path}",
                data=body,
                headers=headers,
                method=self.command,
            )
            try:
                response = urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                response = error
            except OSError as error:
                self._send(502, {"error": {"message": f"OpenRouter unavailable: {error}"}})
                return
            with response:
                payload = response.read()
                self._send_bytes(
                    int(response.status),
                    payload,
                    response.headers.get("Content-Type", "application/json"),
                )

        def _send(self, status: int, payload: dict[str, object]) -> None:
            self._send_bytes(status, json.dumps(payload).encode(), "application/json")

        def _send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def _catalog(model: str) -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "metadata": {
                    "muse-code": {
                        "release_date": None,
                        "is_hidden": False,
                        "limit": {"context": CONTEXT_LIMIT, "output": OUTPUT_LIMIT},
                    }
                },
            }
        ],
    }
