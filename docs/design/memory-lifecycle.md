# Memory lifecycle

Memory has two states: active and invalid. Supersession invalidates a predecessor with a
successor reference; deletion invalidates without one. Archive is a physical location,
not a third state. Invalid memories retain content, identity, validity dates, links and
provenance inside the existing Archive, separate from append-only raw evidence.

Store persists invalidity before moving a file. Failed moves leave invalid truth available
for retry; failed projections leave file truth authoritative. Retrying deletion completes
archival and projection without changing the original invalidation time or successor.
Normal reads and recall check current truth; explicit history reads and temporal recall
retain history. Rebuild includes archived history. Existing invalid files remain readable
as history without an automatic bulk migration. Raw evidence remains independently available.

## Recovery and history access

`Store.delete`, `Store.correct(supersede_with=...)`, `_write_one` predecessor invalidation,
and Manage's existing `Store.write` calls converge on `_persist`. It atomically replaces
file content with invalid metadata, then calls `Archive.archive_memory`, moving to
`archive/memories/<original relative path>`. `_project` refreshes MEMORY.md before SQLite.
`Indexer` includes archived memories in the existing history projection and rebuild.

- Failed status persistence leaves the old file unchanged; temporary files are removed.
- Failed directory creation/move leaves an invalid file at its source. Retry `delete` on
  that name; original invalid_at and successor remain. Destination collisions raise
  FileExistsError and preserve both copies; resolve that collision with backed-up,
  owner-reviewed recovery before retrying. No automatic overwrite or deletion.
- Successful move plus failed index projection leaves invalid truth in Archive. Default
  Recall checks current file validity; Read/Trace scan when an indexed old path disappears.
  Injection renders current active truth. Retry delete or rebuild repairs projections.
- Cached static MEMORY.md may remain stale after a move failure before projection, or an
  external consumer may already hold injected context. Controlled injection renders fresh
  truth; this cannot retract prior context or stop arbitrary direct filesystem reading.
- Read/Trace default to active; `include_invalid=True`, CLI `--history` and MCP read's
  explicit include_invalid access history. CLI/MCP read report status and successor.
  Temporal Context opens historical bodies; Recall scope still addresses original paths.
- Raw files are never moved or deleted by invalidation, including missing/shared evidence.
  Deep Raw search remains explicit and unchanged; redistill counts historical citations.
- Existing valid old-format files work with omitted optional fields; old-location invalid
  files are filtered without migration and archive when deletion is retried. Malformed
  legacy state missing required invalid_at still requires repair; no speculative data fix.
- Multi-file supersede/merge remains nontransactional: a successor may be persisted before
  predecessor archival fails. Inspect both names, then retry predecessor deletion to finish
  archival; do not blindly replay a whole merge. Evidence remains in the old files.

No bulk migration was executed. If owners later want old-location invalid files moved,
first enumerate those files with `Store.records(include_invalid=True)` and their paths,
back up the entire store including Archive and schemas, stop writers, then review the
list before applying existing delete per name. Verify history/Raw and rebuild. Rollback
restores that backup and rebuilds projections; this is a proposed runbook, not a migration
implemented or run by this PR.

## Remaining history policy

Explicit deep Raw search remains independent. Whether it should suppress evidence cited
exclusively by invalid memories is deferred; shared evidence and history must remain available.
