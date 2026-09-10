# Agent memory management operation audit

Baseline: `34d12a2f8678d5561aba27bd8ff73c5ae4b6a258` (main).
This change isolates management boundaries from the separate memory archival lifecycle.
Paths beginning with `core/` refer to `packages/core/src/agent_memory/core/`.

## Operation matrix

| Operation | Existing entry / authority | This change and remaining risks |
|---|---|---|
| Read/Recall/Context/Trace | Existing CLI, MCP and executor reads | Unchanged |
| Create/update | CLI record, MCP memory_record, executor reconcile -> Store.record_many | New links validated; body replacement still requires supersedes; metadata preimages need Git |
| Patch | reconcile.OP_ALIASES maps patch to update | No separate patch API |
| Correct | CLI correct, MCP memory_correct -> Store.correct | Active source/successor and link validation under writer lock; replacement lacks guaranteed preimages |
| Link | record/correct; Manage._add_cooccurrence_links is existing deterministic T0 | MCP correct now exposes links; new targets must be distinct active memories in this store |
| Unlink | No standalone CLI/MCP/Manage verb | correct replaces full list; core/MCP links=[] clears; CLI repeats --link for retained targets. Target and Raw retained; previous set needs Git/caller knowledge |
| Supersede | record/correct, Manage proposals/exact duplicates | Invalid correct successor rejected; existing predecessor checks retained |
| Merge | Manage._review -> decide -> _merge, CLI decide | Existing proposal revalidation and per-kind sleep caps retained; multi-file partial failure and loss of distinctions remain possible |
| Split | Manage._split through existing proposals | Unchanged; rewrites original with first part without unconditional snapshot |
| Invalidate/delete | CLI delete, existing Manage proposals | Unchanged in this PR |
| Date/weight maintenance | Deterministic Manage routines | Unchanged |
| Feedback | CLI/MCP Store.feedback | Audit finding only: returned weight changes but is not persisted; fix deferred |
| Group merge/cluster | Manage -> Store.record | Existing authority; no scope ACL added |
| Redistill request | Manage -> Pending | Unchanged in this PR |
| Physical delete | CLI gc; absent from Manage/MCP | Unchanged; human-run label is not authentication |
| Inspect/rebuild/export | Existing CLI | Unchanged; legacy dangling links still reported by rebuild |
| Import/migrate | Existing CLI | Unchanged; owner authorization for overwrite is a recommendation |

## Implemented checks

`Store._validate_links` compares against persisted links and validates only newly added
relations. Missing, self and invalid targets fail before mutation. Existing historical
links can remain during unrelated updates. Names resolve within one configured store;
Recall scope is only a search filter, not authorization. Store.write checks that the
source path belongs to this store. MCP rejects malformed arrays instead of clearing links.
Missing correction sources/successors retain explicit NotFoundError behavior.

Store.correct and Store.write validate/persist under the existing writer lock. Correction
reads after locking and validates before appending provenance. This reduces stale updates
and evidence side effects; a whole Manage sleep remains nontransactional. Automatic
cooccurrence linking remains enabled. No link/unlink delta command is added.

Manage._review uses existing caps, proposal menu and decide; _open regenerates proposals
before decisions. Unknown/stale proposals cannot dictate arbitrary targets. Direct CLI
decide lacks the per-sleep cap. reasoning.parse accepts verdicts/text, not executable
operations. Executor reconcile handles do not apply to direct CLI/MCP record/correct.
DecisionLedger/reports record outcomes; failure may precede an entry, and Git recovery
requires a successful commit.

## Recommendations, not implemented permissions

Deployment owners should control permanent GC, bulk overwrite/import, cross-store changes
and direct filesystem/database access. No RBAC, actor authentication, approval service,
policy engine, restore command, guaranteed snapshots or host sandbox is implemented.
Shell access can bypass tool menus. Correct/split can still lose old wording without Git.
See [follow-ups](../TODO.md).

## Verification

Management boundary tests cover link replacement/clearing, all write paths rejecting
invalid endpoints, active correction/successor checks, historical links and retained
target/evidence. Adapter tests cover CLI/MCP parity, malformed arrays and unavailable
destructive tools. Existing storage/indexer/Manage/reasoning/reconcile tests cover normal
writes/reads and proposal controls. Validation commands/results are recorded in the PR.
