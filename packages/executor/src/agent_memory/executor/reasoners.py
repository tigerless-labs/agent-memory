"""Two ways to supply the reading a sleep needs, both outside the core (Invariant 5).

They fail differently, which is why both exist. A host reasoner spends the agent the user is
already running: no key, no second bill, and the reasoning shows up in that agent's own
transcript where it can be read. An endpoint reasoner answers on a cron at three in the
morning when no agent session exists, at the cost of a credential and a network hop.

Neither carries algorithm. Text goes out, text comes back, and everything about which text is
worth sending — and which of the reply to believe — stays in the core.
"""

from __future__ import annotations

import dataclasses
import json
import os
import urllib.error
import urllib.request

from .credentials import API_KEY_ENV, BASE_URL_ENV, VertexCredentials
from .hosts import BINARIES, Host, HostSpec

CHAT_COMPLETIONS = "/chat/completions"
DEFAULT_ENDPOINT_MODEL = "google/gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 120.0
ROLE_USER = "user"
EMPTY = ""


@dataclasses.dataclass
class HostReasoner:
    """The consuming agent's own CLI, run headless for one turn."""

    host: Host
    max_turns: int = 1

    def __call__(self, prompt: str) -> str:
        result = self.host.run(prompt, tools_enabled=False, max_turns=self.max_turns)
        return result.text if result.ok else EMPTY

    @classmethod
    def for_host(cls, name: str, model: str = EMPTY) -> HostReasoner:
        """A host is named by its dialect, not by its binary — `claude-code` runs `claude`."""
        binary, default_model = BINARIES.get(name, (name, EMPTY))
        return cls(host=Host(HostSpec(name=name, binary=binary, model=model or default_model)))


@dataclasses.dataclass
class EndpointReasoner:
    """An OpenAI-shaped chat endpoint, credentialed the way the hosts already are."""

    model: str = DEFAULT_ENDPOINT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    credentials: VertexCredentials = dataclasses.field(default_factory=VertexCredentials)

    def __call__(self, prompt: str) -> str:
        environment = {**os.environ, **self.credentials.environment()}
        base = environment.get(BASE_URL_ENV, EMPTY)
        key = environment.get(API_KEY_ENV, EMPTY)
        if not base or not key:
            return EMPTY
        request = urllib.request.Request(
            base.rstrip("/") + CHAT_COMPLETIONS,
            data=json.dumps(
                {"model": self.model, "messages": [{"role": ROLE_USER, "content": prompt}]}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return EMPTY
        return _first_message(payload)


def _first_message(payload: object) -> str:
    if not isinstance(payload, dict):
        return EMPTY
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return EMPTY
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else EMPTY
