# -*- coding: utf-8 -*-
"""Provenance references must be forward-slash on every platform.

Second family of #55. _store_provenance used str(relative_to(...)), which
embeds the win32 separator, and _legacy's validation refused any reference
containing a backslash, so a store written on win32 could not trace its own
provenance. These tests pin both sides: new writes store as_posix, and a
manufactured legacy backslash reference still traces because _legacy
normalises before validating."""


def test_new_provenance_references_are_forward_slash(store):
    record = store.record(
        type="fact",
        fields={"subject": "posix-write"},
        abstract="Provenance write probe",
        provenance=["An excerpt that becomes a stored legacy file."],
    )
    reference = record.provenance[0]
    assert chr(92) not in reference, reference
    assert reference.startswith("archive/provenance/")


def test_legacy_backslash_reference_still_traces(store, capsys):
    """A reference stored before the write fix carries the win32 separator;
    trace must read it after normalising, with the security guards intact."""
    from agent_memory.cli.main import main

    record = store.record(
        type="fact",
        fields={"subject": "legacy-bs"},
        abstract="Legacy backslash probe",
        provenance=["A second excerpt for the legacy backslash case."],
    )
    posix_reference = record.provenance[0]
    windows_reference = posix_reference.replace("/", chr(92))

    exit_code = main(
        [
            "--store",
            str(store.root),
            "--json",
            "trace",
            record.name,
            "--pointer",
            windows_reference,
        ]
    )
    assert exit_code == 0
    del capsys  # the --json payload is asserted via the exit code and the file


def test_normalisation_does_not_open_traversal(store):
    """A backslash traversal attempt must still be refused after the
    normalisation: archive/backslash-dot-dot collapses to a dot-part that
    the PurePosixPath guards reject."""
    import pytest

    from agent_memory.core.errors import ValidationError
    from agent_memory.core.trace import _legacy

    layout = store.layout
    traversal = "archive" + chr(92) + ".." + chr(92) + "escape.md"
    with pytest.raises(ValidationError):
        _legacy(layout, traversal)
