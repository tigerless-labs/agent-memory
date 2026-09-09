# Memory archive and Manage audit

Baseline: `34d12a2f8678d5561aba27bd8ff73c5ae4b6a258` from freshly fetched `origin/main`.
The branch starts from main, not the Progressive Read, Raw evidence or Optional Index branches.
The original dirty worktree was left intact. Paths below are relative to this repository;
`core/` abbreviates `packages/core/src/agent_memory/core/`.

## Code facts at baseline

- `core/record.py::STATUSES`, `MemoryRecord.from_text`, `validate`, `invalidate`: only
  `active` and `invalid`. A missing status defaults to active; missing provenance defaults
  to an empty list. Invalid requires `invalid_at`. Supersession is invalid with
  `superseded_by`, not a third state. No archived/deleted enum.
- `core/store.py::record_many -> _write_one`: schema placement, validation, provenance,
  body-change restrictions, persistence and projection. In-place abstract/link updates
  retain the body; a changed nonempty body requires `supersedes`. `_predecessor` requires
  an active, distinct existing memory. Before this change it rewrote the invalid
  predecessor at its original path.
- `Store.correct`: separately permits in-place body, abstract, date, provenance and link
  replacement; it previously accepted invalid sources and invalid successors. This is
  broader than `record`, and is not a separate generic patch API.
- `Store.delete -> write`: invalidated in place; repeated delete returned immediately,
  without repairing a failed index projection. `Store.write` also receives invalidation
  from `core/manage.py::_merge_exact_duplicates`, `_merge`, `_supersede`; `_delete` delegates
  to `Store.delete`. Thus invalidation is not confined to the CLI delete command.
- `core/archive.py::Archive.append_provenance/append_session`, `core/paths.py::StoreLayout`:
  physical `archive/provenance/<name>/` Markdown and `archive/sessions/` session files.
  There was no Memory archival API. `truth_files/type_of` excluded all Archive content.
- `Store.read/trace/find` had no active filter. `core/agentic.py::_run` already filtered
  `find` results by active status. `Store.records`, `core/memory_md.py::render`, and
  `core/reconcile.py::build` filtered active memories. `core/context.py::build` opened
  Recall hits, while `core/injection.py::payload` trusted cached MEMORY.md bytes.
- `core/search_index.py::upsert` selects active/history FTS tables; `core/recall.py::_eligible`
  relied on cached invalid_at. Explicit `as_of` consults the validity interval. A failed
  projection could leave an old active row eligible. `core/indexer.py::sync/rebuild`
  rebuilds records, FTS and Raw from disk; invalid files previously stayed in the normal tree.
- `Store._store_provenance/trace_record` and `core/sessions.py::parse_pointer/resolve` bind
  multiple memories to shared session ranges. Missing sessions yield no messages.
  Invalidation never deletes Raw. Explicit deep Recall independently retrieves Raw, with
  `source=raw`; this is not progressive Memory-to-Raw reading.
- `core/migrate.py::migrate` handles legacy retired/stale layout and status conversion;
  it is an explicit migration command, not a normal invalidate entry. It is unchanged and
  was not run on user data.

## Operation matrix

CLI entries live in `packages/cli/src/agent_memory/cli/main.py`; MCP entries in
`packages/mcp/src/agent_memory/mcp/tools.py::SCHEMAS/dispatch`. All store operations act on
one configured root. Recall scope is a path-prefix search filter, not write authorization.

| Operation | Baseline entry / decision and execution | Mutation / recovery / actual risk | Recommendation and this change |
|---|---|---|---|
| Read/Recall/Context/Trace | CLI; MCP read/recall; executor `agentic._run`; core executes | Read-only truth; usage logged. Read/Trace exposed invalid bodies/evidence | Autonomous. Active checks plus explicit history access implemented |
| Create/update | CLI record, MCP memory_record; executor `reconcile.check -> Store.record_many` | Creates file or changes metadata. Body replacement restricted in record; abstract replacement loses previous wording without Git | Autonomous within existing store. Added links validated; no new scope policy |
| Patch | `reconcile.OP_ALIASES` maps patch to update | Same record path, not an independent Manage operation | No new patch API |
| Correct | CLI correct, MCP memory_correct -> Store.correct | Body/abstract/link set replacement; no guaranteed preimage without Git | Retain existing autonomy; active source/successor validation implemented. Broader content policy deferred |
| Link | record/correct links; `Manage._add_cooccurrence_links` is deterministic T0 | Slug references, not filesystem hardlinks. T0 adds both directions from repeated cooccurrence. Wrong links affect interpretation; do not delete targets | Autonomous with distinct active new endpoints in this store. Added validation; MCP now exposes existing correct links capability |
| Unlink | No standalone CLI/MCP/Manage verb; `Store.correct(links=...)` replaces full list | Removes references only; target/Raw retained. Prior set needs Git or caller knowledge for exact restoration | Complete-set replacement documented; `links=[]` via core/MCP clears. Malformed MCP arrays rejected. Delta API deferred |
| Supersede | record supersedes, correct supersede_with; Manage proposal/T0 exact duplicates | Invalidates predecessor, stores successor name; old content retained. Incorrect choice hides current knowledge | Existing automatic authority retained. Physical archive implemented; invalid successor rejected by correct |
| Merge | `Manage._review -> decide -> _merge` or CLI decide | Creates merged content, invalidates old files, unions links/provenance. LLM can omit distinctions; multi-file partial failure possible | Existing proposal menu, revalidation and per-kind sleep cap retained. Invalid files now archived; no transaction framework |
| Split | `Manage._split`, decided as above | Rewrites original with first part, creates others; provenance restricted to original pointers. Original body not independently snapshotted | Recovery policy deferred; no broader authority added |
| Invalidate/delete | CLI delete -> Store.delete; Manage delete proposal | Invalidity, not physical deletion. False judgement removes useful current knowledge, but old file/evidence survives | Autonomous within existing entry/proposal bounds; archive and retry repair implemented |
| Archive | No baseline Memory operation; Archive only wrote Raw/provenance | This change adds Archive.archive_memory via Store; no standalone Agent command | Deterministic consequence of invalidation, not another permission tier |
| Date/weight maintenance | Manage._normalise_dates/_settle_weights, deterministic | Rewrites metadata with configured floor/ceiling; Git-dependent prior values | Unchanged |
| Feedback | CLI/MCP -> Store.feedback | **Only mutates returned object at baseline; does not persist weight** | Audit finding only, fix deferred |
| Group merge/cluster | Manage._merge_near_duplicate_groups/_cluster -> Store.record | Moves schema groups, retains stable name/content/evidence. No semantic scope ACL | Existing autonomy retained; cross-scope policy deferred |
| Redistill request | Manage._request_redistill -> Pending | Schedules uncited repeatedly accessed Raw | Counts archived citations too, so invalidation alone does not requeue old evidence |
| Physical delete | CLI gc -> Store.gc; absent from Manage proposal menu and MCP | Deletes invalid files including archived memories; Raw retained. Irreversible without backup | Human confirmation recommended; existing human-run label is **not enforced authentication**. No new GC policy implemented |
| Inspect/rebuild/export | CLI -> Store/indexer/portability | Rebuildable projections or output copy; export normally includes Archive | Autonomous local maintenance; archived history included in rebuild |
| Import/migrate | CLI -> portability.import_into / migrate.migrate | Writes files, can overwrite/import history; outside Manage controls | Explicit owner authorization recommended; unchanged |

## Existing controls and their limits

`Manage._review` uses `_caps`, the open proposal menu and `decide`; `_open` regenerates
proposals before each decision. A stale/unknown proposal cannot dictate arbitrary targets.
Direct CLI `decide` is not subject to the per-sleep cap. `core/reasoning.py::parse` accepts
verdicts and text, not arbitrary executable operations. The executor's write path has
reconcile handles, but direct CLI/MCP record/correct do not use that handle boundary.

`core/locking.py::store_lock` serializes writers. This change puts correction/deletion
read-modify-write under that lock and rejects stale writes that would reactivate invalid
memories. A complete Manage sleep is not atomic. `core/ledger.py::DecisionLedger.append`
records verdicts; `Manage._write_report` records actions and `Manage._commit` attempts one
Git commit when configured. Failed operations can precede a ledger/report entry. No
pre-operation snapshot, guaranteed Git commit, restore command, actor authentication,
RBAC, approval service or host filesystem sandbox exists in this runtime.

Autonomous operations: reads, existing record/update and T0 maintenance. Deterministic
checks: relation additions, active endpoints, existing proposal bounds, validity/schema
checks and writer locking. Higher-authority recommendations: permanent GC, bulk overwrite,
cross-store modifications and direct filesystem/DB changes. Product decisions remain in
[the follow-up list](../TODO.md). An Agent with shell/file access can bypass tool menus;
this PR does not claim otherwise.

## Implemented lifecycle and recovery

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

## Verification map

Existing `tests/unit/test_storage.py`, `test_supersede_on_write.py`, `test_recall.py`,
`test_indexer.py`, `test_manage.py`, `test_manage_reasoning.py`, `test_reconcile.py` and
`tests/system/test_entry_equivalence.py` cover lifecycle, temporal retrieval, rebuild,
proposal caps/unknown verdicts, targets, Git/ledger and adapter parity.

`tests/unit/test_memory_archive.py` adds behavioral isolation, physical archive, explicit
history/rebuild, idempotence, atomic-write/move/index failures, destination conflict, missing
optional fields, missing/shared Raw, retained links, rejected endpoints, stale resurrection,
Raw redistill and temporal scope. `tests/system/test_archive_entries.py` covers CLI/MCP
history and relationship parity, malformed arrays and unavailable destructive tools.
The existing dangling-link test now uses legacy file input: controlled new writes reject
unknown link targets, while index rebuild continues reporting historical dangling links.

## Local validation results

Executed against this worktree's six package source directories via PYTHONPATH, using the
existing Python 3.12 environment (no experimental branch source imported):

```bash
export PYTHONPATH=packages/core/src:packages/cli/src:packages/mcp/src:packages/executor/src:packages/adapters/src:packages/harness/src
/home/codexlab/code/agent-memory/.venv/bin/python -m pytest -q --cov=agent_memory --cov-report=term-missing --cov-fail-under=85
/home/codexlab/code/agent-memory/.venv/bin/ruff check .
/home/codexlab/code/agent-memory/.venv/bin/mypy
git diff --check
```

Results: 411 tests passed; coverage 91.14% (required 85%); Ruff passed; Mypy passed for
66 source files; diff whitespace check passed. An additional temporary-store CLI smoke
executed 11 commands: init, record, recall/read before delete, delete, recall/read after
delete, history read, repeated delete, rebuild and Context. All expected exit codes,
physical paths and empty active results were verified. No live user Memory was touched.

CI equivalent: `uv sync --all-packages`, `uv run ruff check .`, `uv run mypy`, then
`uv run pytest -q --cov=agent_memory --cov-report=term-missing --cov-fail-under=85`.
