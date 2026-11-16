import io
import json

import pytest
from agent_memory.cli.main import _emit


@pytest.mark.parametrize(
    ("ok", "required", "status"),
    [(True, True, "PASS"), (True, False, "PASS"), (False, True, "FAIL"), (False, False, "WARN")],
)
def test_emit_check_preserves_code_state_and_detail(ok: bool, required: bool, status: str) -> None:
    check = {"code": "HOST_CHECK", "ok": ok, "required": required, "detail": "Host detail"}
    stream = io.StringIO()

    _emit({"checks": [check]}, False, stream=stream)

    rendered = stream.getvalue()
    assert f"{check['code']}: {status}" in rendered
    assert check["detail"] in rendered
    assert "score=" not in rendered


def test_emit_check_without_required_defaults_to_failure() -> None:
    stream = io.StringIO()

    _emit(
        {"checks": [{"code": "FAILED_CHECK", "ok": False, "detail": "Missing"}]},
        False,
        stream=stream,
    )

    assert "FAILED_CHECK: FAIL" in stream.getvalue()


@pytest.mark.parametrize("multiple", [False, True])
def test_emit_diagnostic_json_preserves_payload(multiple: bool) -> None:
    report = {
        "status": "READY",
        "checks": [
            {"code": "OPTIONAL_CHECK", "ok": False, "required": False, "detail": "Optional"}
        ],
    }
    payload = {"status": "READY", "hosts": {"codex": report}} if multiple else report
    stream = io.StringIO()

    _emit(payload, True, stream=stream)

    assert json.loads(stream.getvalue()) == payload


def test_emit_recall_hit_preserves_text_format() -> None:
    hit = {
        "name": "release",
        "abstract": "Signed tags",
        "path": "fact/release.md",
        "anchor": "policy",
        "score": 0.5,
    }
    stream = io.StringIO()

    _emit({"hits": [hit]}, False, stream=stream)

    assert "release — Signed tags · fact/release.md#policy · score=0.5" in stream.getvalue()
