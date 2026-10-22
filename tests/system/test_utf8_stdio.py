"""Entry points speak UTF-8 on stdio whatever the platform's pipe encoding is."""

import json
import os
import pathlib
import subprocess
import sys

from agent_memory.core.store import Store

ABSTRACT = "共享记忆用 agent-memory 存储"
BODY = "跨代理的中文正文"


def _entry(name):
    return str(pathlib.Path(sys.executable).parent / name)


def _run(command, store_root, stdin=b""):
    environment = {**os.environ, "PYTHONIOENCODING": "ascii", "AGENT_MEMORY_STORE": str(store_root)}
    environment.pop("PYTHONUTF8", None)
    return subprocess.run(command, input=stdin, capture_output=True, env=environment, timeout=60)


def test_text_recall_prints_non_ascii_memories(store):
    store.record(type="decision", name="zh-probe", abstract=ABSTRACT, body=BODY)

    completed = _run([_entry("mem"), "recall", "agent-memory"], store.root)

    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert ABSTRACT in completed.stdout.decode("utf-8")


def test_mcp_records_raw_utf8_input_without_corrupting_it(store):
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "memory_record",
            "arguments": {"type": "decision", "name": "zh-mcp", "abstract": ABSTRACT, "body": BODY},
        },
    }
    payload = (json.dumps(call, ensure_ascii=False) + "\n").encode("utf-8")

    completed = _run([_entry("mem-mcp")], store.root, payload)

    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    recorded = Store(store.root).find("zh-mcp")
    assert recorded.abstract == ABSTRACT
    assert recorded.body.strip() == BODY
