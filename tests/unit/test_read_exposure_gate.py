"""The pilot gate must catch a copied store with no retrieval cache."""

import importlib.util
import json
import sqlite3
from pathlib import Path


def gate():
    path = Path(__file__).parents[2] / "tools" / "read_exposure_gate.py"
    spec = importlib.util.spec_from_file_location("read_exposure_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_index(root):
    folder = root / ".index"
    folder.mkdir(parents=True)
    with sqlite3.connect(folder / "index.db") as connection:
        connection.execute("create table records (name text)")
        connection.execute("insert into records values ('museum')")
        for table in ("chunks", "raw_chunks"):
            connection.execute(f"create virtual table {table} using fts5(text)")
            connection.execute(f"insert into {table}(text) values ('museum visit')")


def test_store_gate_rejects_missing_projection(tmp_path):
    checker = gate()
    question = checker.PROBE_EPISODE
    (tmp_path / "panel.json").write_text(json.dumps({"selected_ids": [question]}))
    source = tmp_path / "frozen-stores" / "W2" / question
    make_index(source)
    for arm in checker.ARMS:
        make_index(tmp_path / arm / "input-stores" / "W2" / question)
    assert checker.stores(tmp_path)["ok"]

    (tmp_path / "raw" / "input-stores" / "W2" / question / ".index" / "index.db").unlink()
    result = checker.stores(tmp_path)
    assert not result["ok"]
    assert any("raw/" + question in failure for failure in result["failures"])


def test_pilot_gate_detects_direct_file_bypass():
    checker = gate()
    events = [
        {"stderr": "/bin/bash -lc 'rg museum /tmp/input-stores/W2/q/archive/sessions' in /tmp/work"}
    ]
    assert checker.direct_store_commands(events)
    events = [{"stderr": "/bin/bash -lc 'mem recall museum --deep' in /tmp/work"}]
    assert not checker.direct_store_commands(events)
