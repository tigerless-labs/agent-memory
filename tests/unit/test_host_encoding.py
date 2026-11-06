"""Prompts reach host CLIs as UTF-8 and answers come back intact, whatever the code page."""

import sys

import pytest
from agent_memory.executor import hosts

PROMPT = "记住：跨代理代号是 BLUE-HERON-42 — 不要遗忘"
ANSWER = "已记录 — BLUE-HERON-42"

FAKE_HOST = """#!{python}
import json, os, sys

argv = sys.argv[1:]
received = sys.stdin.buffer.read()
with open(os.environ["FAKE_STDIN_LOG"], "wb") as log:
    log.write(received)
answer = {answer!r}
if "--output-last-message" in argv:
    with open(argv[argv.index("--output-last-message") + 1], "w", encoding="utf-8") as handle:
        handle.write(answer)
if "--json" in argv:
    sys.stdout.buffer.write((json.dumps({{"type": "turn.completed"}}) + "\\n").encode("utf-8"))
else:
    sys.stdout.buffer.write(answer.encode("utf-8"))
"""


@pytest.mark.parametrize("name", [hosts.HOST_CLAUDE_CODE, hosts.HOST_CODEX])
def test_non_ascii_prompts_and_answers_cross_the_host_boundary(name, tmp_path, python_executable):
    binary = python_executable(
        tmp_path / "bin" / name, FAKE_HOST.format(python=sys.executable, answer=ANSWER)
    )
    log = tmp_path / "stdin.bin"
    host = hosts.Host(
        hosts.HostSpec(name=name, binary=str(binary), model="m", attempts=1, timeout_seconds=15)
    )

    result = host.run(PROMPT, workdir=tmp_path, environment={"FAKE_STDIN_LOG": str(log)})

    assert result.ok, result.error
    assert PROMPT in log.read_bytes().decode("utf-8")
    assert result.text == ANSWER
