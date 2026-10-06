# -*- coding: utf-8 -*-
"""Stale-write detection must not reject files saved with CRLF.

The source_hash recorded at read time covers the LF-normalised text
(universal newlines), but the comparison in _write_locked hashed the raw
disk bytes, so a memory file an external editor saved with CRLF (win32
Notepad, a git autocrlf checkout) was refused its first write with
"memory changed since it was read". These tests pin the acceptance of
either newline flavour and that real content edits stay detectable."""

import pytest

from agent_memory.core.errors import ValidationError


def _write_crlf(record) -> None:
    payload = record.to_text().encode("utf-8")
    crlf = payload.replace(b"\n", b"\r\n")
    record.path.write_bytes(crlf)


def test_a_crlf_file_accepts_its_next_write(store):
    record = store.record(type="fact", fields={"subject": "crlf"}, abstract="Before")
    _write_crlf(record)
    store.sync_index()

    corrected = store.correct(record.name, abstract="After")

    assert corrected.abstract == "After"
    # The store's canonical LF form lands on disk after the write.
    assert record.path.read_bytes() == corrected.to_text().encode("utf-8")


def test_a_real_content_change_is_still_refused(store):
    from agent_memory.core.store import Store

    record = store.record(type="fact", fields={"subject": "guard"}, abstract="Kept")
    stale = store.find(record.name)  # snapshot with its source_hash

    someone_else = Store(store.root, config=store.config, clock=store.clock)
    someone_else.correct(record.name, abstract="Concurrent edit")

    with pytest.raises(ValidationError):
        stale_write = stale
        stale_write.abstract = "Stale"
        store.write(stale_write)


def test_hash_basis_is_the_lf_form(store):
    from agent_memory.core.store import _normalise_newlines

    record = store.record(type="fact", fields={"subject": "basis"}, abstract="Basis")
    lf = record.to_text().encode("utf-8")
    crlf = lf.replace(b"\n", b"\r\n")
    assert _normalise_newlines(crlf) == lf
    assert _normalise_newlines(lf) == lf
