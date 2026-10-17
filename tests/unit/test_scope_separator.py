# -*- coding: utf-8 -*-
"""Scope matching must see through the platform separator in stored paths.

The scoped SQL in SearchIndex.match compared the raw records.path column
against the always-forward-slash scope, so paths stored with the win32
separator never matched (issue #55, first family). This test manufactures a
backslash path row directly in the database so every platform, including the
POSIX CI lane, exercises the normalised comparison."""


def test_scope_matching_normalises_windows_separators(store):
    from agent_memory.core.database import Database
    from agent_memory.core.search_index import SURFACE_ACTIVE, SearchIndex

    store.record(type="fact", name="sep", abstract="separator scope probe", body="body")
    windows_path = "fact" + chr(92) + "general" + chr(92) + "sep.md"
    with Database(store.layout).connect() as connection:
        connection.execute(
            "UPDATE records SET path = ? WHERE name = 'sep'", (windows_path,)
        )
        connection.commit()
        hits = SearchIndex(connection).match(
            "separator scope", 10, SURFACE_ACTIVE, scope_path="fact"
        )
    assert [hit.name for hit in hits] == ["sep"]


def test_scope_matching_still_requires_component_boundaries(store):
    """The normalisation must not loosen the boundary rule from #33:
    scope fact still refuses fact-archive and friends, with either separator
    flavour inside the stored path."""
    from agent_memory.core.database import Database
    from agent_memory.core.search_index import SURFACE_ACTIVE, SearchIndex

    store.record(type="fact", name="real", abstract="boundary probe", body="body")
    archive = store.record(
        type="fact", name="arch", abstract="boundary probe", body="body", fields=store.find("real").fields
    )
    del archive
    with Database(store.layout).connect() as connection:
        connection.execute(
            "UPDATE records SET path = ? WHERE name = 'real'", ("fact" + chr(92) + "real.md",)
        )
        connection.execute(
            "UPDATE records SET path = ? WHERE name = 'arch'", ("fact-archive" + chr(92) + "arch.md",)
        )
        connection.commit()
        hits = SearchIndex(connection).match(
            "boundary probe", 10, SURFACE_ACTIVE, scope_path="fact"
        )
    assert [hit.name for hit in hits] == ["real"]
