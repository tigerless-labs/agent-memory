# -*- coding: utf-8 -*-
"""Index and manifest path keys must be forward-slash on every platform.

The indexer scanned with str(relative_to(...)), which embeds the win32
separator, and those keys became the records.path column — the root cause
behind the scoped-recall family in #55 and the reason #58 needed a
comparison-side replace. These tests pin the write-side source fix: reports
and stored rows are posix on every platform, and a store indexed before the
fix (backslash rows) self-heals on its next sync instead of erroring or
duplicating."""


def test_sync_reports_and_stores_posix_paths(store):
    store.record(type="fact", fields={"subject": "posix"}, abstract="A", body="B")
    target = store.find("posix")
    target.body = target.body + " changed"
    target.path.write_text(target.to_text(), encoding="utf-8")

    report = store.sync_index()

    assert [path.split("/")[-1] for path in report.reindexed] == ["posix.md"]
    from agent_memory.core.database import Database

    with Database(store.layout).connect() as connection:
        rows = connection.execute("SELECT path FROM records").fetchall()
    assert rows and all(chr(92) not in row["path"] for row in rows)


def test_a_pre_fix_index_self_heals_on_the_next_sync(store):
    """Simulate a store indexed before this fix: every manifest and records
    row carries the win32 separator. One sync must converge to posix rows
    without unreadable files or duplicates, and stay stable afterwards."""
    from agent_memory.core.database import Database

    store.record(type="fact", fields={"subject": "heal-a"}, abstract="A", body="B")
    store.record(type="decision", fields={"subject": "heal-b"}, abstract="C", body="D")
    separator = chr(92)
    with Database(store.layout).connect() as connection:
        for table in ("files", "records"):
            for row in connection.execute(f"SELECT path FROM {table}").fetchall():
                path = row["path"]
                if separator not in path:
                    connection.execute(
                        f"UPDATE {table} SET path = ? WHERE path = ?",
                        (path.replace("/", separator), path),
                    )
        connection.commit()

    first = store.sync_index()

    assert first.unreadable == ()
    assert all(separator not in path for path in first.reindexed)
    second = store.sync_index()
    assert second.reindexed == () and second.removed == ()
    with Database(store.layout).connect() as connection:
        total = connection.execute("SELECT count(*) FROM records").fetchone()[0]
        distinct = connection.execute(
            "SELECT count(DISTINCT name) FROM records"
        ).fetchone()[0]
        backslash = connection.execute(
            "SELECT count(*) FROM records WHERE path LIKE ?",
            ("%" + separator + "%",),
        ).fetchone()[0]
    assert total == distinct == 2
    assert backslash == 0

    from agent_memory.core.recall import Recall

    assert len(Recall(store).recall("heal", scope="fact")) == 1
