"""Explicit Monid text transport for executor reasoning."""

import dataclasses
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from agent_memory.core.errors import ReasonerUnavailableError


@dataclasses.dataclass
class MonidReasoner:
    model: str
    timeout_seconds: float

    def __call__(self, prompt: str) -> str:
        key = os.environ.get("MONID_API_KEY", "")
        if not key:
            raise ReasonerUnavailableError("monid reasoner requires MONID_API_KEY")
        if not 1 <= len(prompt) <= 4000:
            raise ReasonerUnavailableError("monid prompt must contain 1 to 4000 characters")
        headers = {"Authorization": f"Bearer {key}"}
        request = urllib.request.Request(
            "https://api.monid.ai/v1/run",
            data=json.dumps({
                "provider": "dataforseo",
                "endpoint": "/ai/claude-response",
                "input": {"body": {"user_prompt": prompt, "model_name": self.model}},
            }, ensure_ascii=False).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
        )
        deadline = time.monotonic() + self.timeout_seconds
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                run = json.loads(response.read().decode("utf-8"))
                asynchronous = response.status == 202
            if asynchronous:
                run_id = urllib.parse.quote(run["runId"], safe="")
                while run.get("status") not in (
                    "COMPLETED", "FAILED", "TIMED_OUT", "STOPPED", "BLOCKED"
                ):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    time.sleep(min(2, remaining))
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    poll = urllib.request.Request(
                        f"https://api.monid.ai/v1/runs/{run_id}", headers=headers
                    )
                    with urllib.request.urlopen(poll, timeout=remaining) as response:
                        run = json.loads(response.read().decode("utf-8"))
            if run.get("status") not in (None, "COMPLETED"):
                raise ReasonerUnavailableError("endpoint request failed")
            if (run.get("providerResponse") or {}).get("httpStatus", 200) >= 400:
                raise ReasonerUnavailableError("endpoint request failed")
            text = self._text(run["output"])
            if not text.strip():
                raise ReasonerUnavailableError("endpoint returned no valid message")
            return text
        except json.JSONDecodeError as error:
            raise ReasonerUnavailableError("endpoint returned invalid JSON") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ReasonerUnavailableError("endpoint request failed") from error
        except (KeyError, TypeError, AttributeError) as error:
            raise ReasonerUnavailableError("endpoint returned no valid message") from error

    def _text(self, output: dict) -> str:
        parts = []
        for task in output.get("tasks", []):
            if task.get("status_code", 20000) != 20000:
                raise ReasonerUnavailableError("endpoint request failed")
            for result in task.get("result") or []:
                for item in result.get("items") or []:
                    for section in item.get("sections") or []:
                        text = section.get("text")
                        if isinstance(text, str):
                            parts.append(text)
        return "\n".join(parts)
