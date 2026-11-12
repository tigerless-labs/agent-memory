import dataclasses
import io
import json
import urllib.error

import pytest
from agent_memory.core.config import Config
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor import distiller, selection


def configured():
    return dataclasses.replace(
        Config.default().executor, reasoner="monid", model="claude-sonnet-4-0"
    )


def output():
    return {"tasks": [{"result": [{"items": [{"sections": [{"text": "answer"}]}]}]}]}


def fake_http(monkeypatch, replies):
    sent = []

    def open_request(request, timeout=None):
        sent.append(request)
        reply, status = replies.pop(0)
        response = io.BytesIO(json.dumps(reply).encode())
        response.status = status
        return response

    monkeypatch.setenv("MONID_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", open_request)
    monkeypatch.setattr("time.sleep", lambda _: None)
    return sent


def test_monid_request_and_text_mapping_with_only_monid_key(monkeypatch):
    sent = fake_http(monkeypatch, [({"output": output()}, 200)])
    reasoner = distiller.distiller(selection.resolve(configured(), selection.WRITE))
    assert reasoner("问题") == "answer"
    request = sent[0]
    assert request.full_url == "https://api.monid.ai/v1/run"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer fake-key"
    assert request.get_header("Content-type") == "application/json; charset=utf-8"
    assert "问题".encode() in request.data
    assert json.loads(request.data) == {
        "provider": "dataforseo",
        "endpoint": "/ai/claude-response",
        "input": {"body": {"user_prompt": "问题", "model_name": "claude-sonnet-4-0"}},
    }


def test_default_stays_host_without_monid_key(monkeypatch):
    monkeypatch.delenv("MONID_API_KEY", raising=False)
    chosen = selection.resolve(Config.default().executor, selection.WRITE)
    assert chosen.reasoner == "host"
    assert distiller.distiller(chosen).host.spec.name == "claude-code"


def test_monid_requires_its_key(monkeypatch):
    monkeypatch.delenv("MONID_API_KEY", raising=False)
    with pytest.raises(ReasonerUnavailableError, match="MONID_API_KEY"):
        distiller.distiller(configured())("prompt")


def test_monid_polls_until_completed(monkeypatch):
    sent = fake_http(monkeypatch, [
        ({"runId": "run-1"}, 202),
        ({"status": "RUNNING"}, 200),
        ({"status": "COMPLETED", "output": output()}, 200),
    ])
    assert distiller.distiller(configured())("prompt") == "answer"
    assert [request.full_url for request in sent[1:]] == [
        "https://api.monid.ai/v1/runs/run-1",
        "https://api.monid.ai/v1/runs/run-1",
    ]


@pytest.mark.parametrize("status", ["FAILED", "TIMED_OUT", "STOPPED", "BLOCKED"])
def test_monid_terminal_failure(monkeypatch, status):
    fake_http(monkeypatch, [({"status": status}, 200)])
    with pytest.raises(ReasonerUnavailableError, match="endpoint request failed"):
        distiller.distiller(configured())("prompt")


def test_provider_error_uses_existing_endpoint_failure(monkeypatch):
    fake_http(monkeypatch, [({"providerResponse": {"httpStatus": 429, "error": {}}}, 200)])
    with pytest.raises(ReasonerUnavailableError, match="endpoint request failed"):
        distiller.distiller(configured())("prompt")


def test_monid_http_error(monkeypatch):
    fake_http(monkeypatch, [])

    def fail(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(ReasonerUnavailableError, match="endpoint request failed"):
        distiller.distiller(configured())("prompt")


@pytest.mark.parametrize("payload", [{"output": {}}, {}, {"output": {"tasks": None}}])
def test_monid_rejects_missing_text(monkeypatch, payload):
    fake_http(monkeypatch, [(payload, 200)])
    with pytest.raises(ReasonerUnavailableError, match="endpoint returned no valid message"):
        distiller.distiller(configured())("prompt")


def test_monid_polling_has_a_deadline(monkeypatch):
    sent = fake_http(monkeypatch, [({"runId": "run-1"}, 202)])
    times = iter([0, 61])
    monkeypatch.setattr("time.monotonic", lambda: next(times))
    config = dataclasses.replace(configured(), timeout_seconds=60)
    with pytest.raises(ReasonerUnavailableError, match="endpoint request failed"):
        distiller.distiller(config)("prompt")
    assert len(sent) == 1


def test_key_alone_does_not_select_monid(monkeypatch):
    monkeypatch.setenv("MONID_API_KEY", "fake-key")
    chosen = selection.resolve(Config.default().executor, selection.WRITE)
    assert chosen.reasoner == "host"
