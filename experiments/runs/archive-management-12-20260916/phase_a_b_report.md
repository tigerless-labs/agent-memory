# Archive Management: contract and answer-sensitive probes

## Scope and identities

This follow-up does **not** run the original active-only 12×2 exam. The pre-fix treatment
code was `c6b46c041cd3b6f031e7312a60384699cb985de1`; the feature-plan baseline is
`34d12a2f8678d5561aba27bd8ff73c5ae4b6a258`. The dirty current worktree was not
switched. The fix and contract tests were developed in the isolated `feature-checkout/`.
Answer probes used exact Git archive snapshots of the two pre-fix commits and are not
rerun after this lifecycle-only fix.

## Phase A — Archive feature contract: PASS

The original Phase A audit was **FAIL** despite 72 passing tests (`phase-a-tests.log`):
`Store._persist` wrote invalid status to the active file before `Archive.archive_memory`
attempted the move. A move failure or destination collision left an invalid file under
the active tree. The old tests expected that retryable half-state.

The fix prepares invalid content in a temporary file under Archive, moves unchanged
active bytes to the archive path, then replaces the archived bytes with invalid content.
A move failure leaves the active source untouched. If the subsequent status replacement
fails, the original bytes move back to the active source. A pre-existing destination
raises `FileExistsError` without changing either file. A single `Store.record` supersede
rolls back its candidate file when predecessor archival fails. Projection still follows
the successful filesystem transition; a projection failure is repaired by retry/rebuild.
The failure guarantee covers operation errors with a working rollback filesystem; it is
not a cross-file crash transaction.

| Required behavior | Evidence |
|---|---|
| Delete invalidates and moves | `test_archive_lifecycle_history_and_rebuild`; `test_cli_invalidation_retains_history_and_excludes_normal_reads` |
| Supersede archives predecessor | `test_supersede_and_archive_retry_preserve_successor_and_original_time`; `test_cli_and_mcp_share_archive_boundaries` |
| Manage invalidation archives | **Added** `test_manage_duplicate_archives_only_invalid_copy_and_rebuild_keeps_active` |
| Default Read denies invalid/archived | `assert_isolated`; both CLI/MCP system tests |
| Normal Recall excludes it | `assert_isolated`; both CLI/MCP system tests |
| Rebuild keeps it out of active retrieval | `test_archive_lifecycle_history_and_rebuild`; added Manage/rebuild test |
| Provenance/history survives | `test_shared_and_missing_raw_survive_invalidation`; `test_archive_lifecycle_history_and_rebuild` |
| Active memory is not misarchived | `test_archive_rejects_active_memory_and_repeated_archive_is_noop`; added Manage/rebuild test |
| Status-write failure restores active original | `test_failed_atomic_status_write_preserves_active_original` |
| Move failure preserves active and retry succeeds | `test_move_failure_preserves_active_and_retry_succeeds` |
| Destination collision preserves both unchanged | `test_destination_collision_preserves_both_copies` |
| Failed supersede leaves no successor | `test_supersede_move_failure_keeps_predecessor_and_no_successor` |
| Failed `Store.correct` supersede keeps both originals active | `test_correct_move_failure_keeps_original_and_successor` |
| Projection failure can be retried | `test_projection_failure_does_not_leak_and_retry_repairs_index` |
| Repeated archive/delete is idempotent | `test_archive_lifecycle_history_and_rebuild`; `test_archive_rejects_active_memory_and_repeated_archive_is_noop` |

Post-fix focused Archive/CLI/MCP contract tests: **18 passed**; broader lifecycle,
recall, index, Manage and CLI suites: **123 passed**. Full pytest: **406 passed**.
Ruff, mypy and `git diff --check` passed. The exact gate commands and
outputs are in `phase-a-fix-gates.log`. No Manage, Vector, Progressive, Observation or
Evidence Sufficiency policy was changed.

## Phase B — real path and three paired answers

The Codex Host uses `workspace-write` and adds the Store directory, so direct filesystem
commands are permitted. The native Agent prompt and skill instruct `mem context`, Recall,
and Read; they do not suggest `ls`/`grep` fallback. Baseline `mem read <old-name>` still
returns the invalid record, while Archive rejects it by default. Explicit history works
on Archive. `command_exposure.json` records actual CLI and `rg --files` checks of all three
case Stores. Thus the potential filesystem/direct-read path exists, but permission alone
does not show that the Agent uses it.

Three cases came from the official LongMemEval source sessions and existing memories:
Negroni attempts 5→10, Crash Course videos 12→15, and Ticket to Ride high score 124→132.
`sensitive-probes-v3/manifest.json` stores the question/truth, source-session IDs,
original memory file hashes, field mapping needed by the target's schema, and a hash of
each canonical Store. Each canonical Store was created once through `Store.record` from
the original old/new memory text, with the source raw session archive copied unchanged;
both arms then received byte-identical copies. Both arms called the same official
`Store.correct(old, supersede_with=new)` operation. The baseline left the invalid file in
its active tree; Archive moved it under `archive/memories`. The generated `MEMORY.md`,
config and final answer prompt hash matched within each pair.

An earlier preparation attempt with whole historical Stores is retained in
`sensitive-probes/` and marked abandoned. It made no answer calls: that corpus uses a
newer config and folder layout incompatible with the target code. The completed v3 set
uses source-grounded entries written through the target's API.

| Question | Baseline answer | Archive answer | Judge | Agent commands in both arms | Archive-sensitive evidence |
|---|---|---|---|---|---|
| `603deb26` | 10 times | 10 times | both correct | `mem context` | old 5-attempt memory not surfaced |
| `5831f84d` | 15 Crash Course videos | 15 videos | both correct | `mem context` | old 12-video memory not surfaced |
| `0e4e4c46` | 132 points | 132 points | both correct | `mem context` | old 124-point memory file not surfaced |

For all 6 answer runs, `mem context` caused one Recall and one Read of the **new active**
memory. No Agent `ls`, `grep`, `rg`, `cat`, direct `mem read <old-name>`, or other filesystem
fallback appeared in the captured Host traces. The per-case Recall and Read ID sets were
identical across arms. The old invalid memory file was never surfaced. In `0e4e4c46`,
the new active memory's body itself mentions the previous 124-point score; Archive does not
remove historical values embedded in current valid evidence.

Summary: Baseline **3/3**, Archive **3/3**; correctness transitions 0; Recall used 6/6,
memory Read 6/6, filesystem fallback 0/6, direct old-memory Read 0/6, archive-sensitive
file exposure 0/6, changed Recall sets 0/3, changed Read sets 0/3. One answer string changed
wording without changing its factual answer. Mean answer latency was 20.08 s versus
21.42 s; Codex reported 19,271 versus 19,585 answer tokens. These small differences are
not an archive quality signal. Judge used the same Codex model and the branch's five-vote
yes/no rubric, so it provides votes rather than a free-text reason. Each Host/Judge call
used one attempt; a failed in-sandbox Host preflight and the subsequent successful
out-of-sandbox preflight are recorded separately and were not answer retries.

Raw results and commands are in `sensitive-probes-v3/results/`,
`sensitive-probes-v3/logs/`, `sensitive-probes-v3/paired_analysis.json`, and
`sensitive-probes-v3/command_exposure.json`.

## Decision

**NO E2E-SENSITIVE PATH FOUND** in these three source-grounded probes. The code permits
direct-read and filesystem exposure in principle, and the baseline's invalid file is
indeed reachable by those commands. The Agent actually followed `mem context` in every
run and saw the same active evidence in both arms. Do not expand to 12 answer pairs on
this evidence. Treat the current branch primarily as lifecycle/integration behavior;
the Archive feature as lifecycle/integration correctness, with the failed-move contract
now covered by Phase A tests. No answer-quality improvement is claimed.

The probes intentionally use minimal two-memory Stores reconstructed through official
record APIs because historical frozen Stores use a newer incompatible config/layout.
They demonstrate the observed path for these three questions, not that filesystem fallback
can never occur with larger Stores or different questions.
