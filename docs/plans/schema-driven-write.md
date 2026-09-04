# Plan: schema-driven types, two-state records, and the reconciled write path

> Working artifact. Owner decisions of 2026-09-03 (single host, main flow only). Branch
> `feat/schema-driven-write`. Design references: OpenViking's write path (session commit,
> numbered conversation, prefetch, schema-driven URIs) and Graphiti's two-state validity.
> Each unit is docs → failing tests → code → verify → commit.

## What the owner decided

1. **No fixed domains.** A memory type is a small schema file; the tree is generated from
   the schema at write time. Convention, not templates: `<type>/<group>/<key-slug>.md`.
   Only `system`- or `menu`-sourced fields may form a directory segment; free fields only
   reach the file name. Depth is capped in config.
2. **Two states.** `status: active | invalid`, with `valid_from`, `invalid_at`,
   `superseded_by`. Invalidation has two causes only: replaced by a successor, or deleted.
   Successor `valid_from` equals predecessor `invalid_at`. Moving, re-abstracting and
   weight settlement never touch these fields. `stale`, `retired` and `archive/retired/`
   go away. Physical removal is a human CLI command (`gc`), never reachable from Manage.
3. **Write coverage by filling a form, not by judgement.** The library renders the increment
   as a numbered conversation with a reconcile sheet (related active memories with handles,
   plus the directory menu); the host agent fills type slots, using four verbs — `new`,
   `supersede <handle>`, `update <handle>`, `skip` — and returns one batch. Every memory
   carries provenance as message ranges; the library fills the batch range by default.
4. **Triggers.** Boundary hooks stay the main trigger; pending-token and pending-message
   thresholds and an idle scan are added. A single distillation call has an input cap;
   larger increments split on message boundaries and advance the watermark per batch.
5. **Manage without a human gate.** T0 stays rule-only and gains directory creation, moves
   and clustering. T1 is decided by the host LLM: it writes content for merge and split,
   and returns verdicts for supersede and delete. The library computes time, identity,
   provenance and status; the reasoner's text for those is discarded. Every operation is
   reversible, per-sleep rate limits bound the blast radius, and one git commit per sleep
   is the audit unit. Invariant 6 is rewritten accordingly.
6. **Index.** `chunks` holds active files only; a `history` FTS table holds invalid files
   and answers `--as-of` alone; `raw_chunks` anchors are message indices; `records` keeps
   a row for invalid files so chains resolve.

7. **Who reasons: the library, always.** Distillation at the boundary and Manage's T1
   verdicts run in the executor package against a model endpoint, default Gemini 3.7 Flash
   through the Vertex path already wired in `executor`. Hosts (Claude Code, Codex CLI,
   Hermes) only capture, trigger, inject and recall; their own model never distils. Host
   self-write stays available as experiment arms (W1, W2). The core keeps no client; the
   model id is a config knob. ADR-002 amended.
8. **Recall links back to the trace.** Provenance is an absolute pointer (session and
   message range); recall hits carry it, `trace <name>` opens the messages, `--deep` raw
   hits carry `cited_by`. This is the one place the design departs from OpenViking on
   purpose. A fact date later than its provenance message time is rejected at apply.

Out of scope here: the vector plugin, directory sidecars, tree search, the
compile-from-archive tool.

## The schema

```toml
type = "decision"
description = "项目里做出的取舍与理由。出现「我们决定 / 改用 / 不再」就写一条。"
key = ["project", "subject"]   # identity: same key, same file
group = "project"              # which field names the subdirectory
mode = "upsert"                # or add_only
```

TOML, not YAML: the core carries no third-party dependency and the standard library reads
TOML.

Field sources are declared once, globally: `project`, `date`, `user` are `system`;
`topic`, `category`, `source` are `menu`; everything else is `field`. The rule "group must
be system or menu" lives in the library, not in any schema. The factory set: `profile`
(single file), `preference`, `entity`, `event` (add_only, grouped by month), `decision`,
`procedure`, `fact` (the three grouped by project), `experience`, `reference`. Schemas live
under the store's `schemas/`, versioned with the store, editable by the owner.

## Units

1. **Design.** `storage.md` (schema, path convention, two states, provenance as ranges,
   sessions with message boundaries), `write.md` (triggers, six-step pipeline, agent
   contract), `manage.md` (two tiers, reasoner writes content, no human gate, rate limits),
   `recall.md` (history surface, evidence list carries citations), `cli.md` / `hooks.md` /
   `mcp.md` endpoints, ADR-008 (schema-driven tree, supersedes ADR-005), ADR-009 (two
   states), root `CLAUDE.md` Invariant 6, `docs/testing.md` test map, `docs/design/index.md`.
2. **Types and records.** Schema registry (load, validate, factory set), path resolution
   (convention, source rules, slug, portable segments, depth cap), two-state record model
   and validation, `records` row for invalid files, migration of a four-domain store into
   the schema layout behind a config version. Tests: a schema with a `field`-sourced group
   is rejected; same key resolves to the same path; supersede leaves predecessor invalid
   with `invalid_at == successor.valid_from`; `--as-of` before that instant returns the
   predecessor; rebuild equivalence holds with invalid files present.
3. **Sessions and provenance.** `sessions/*.jsonl` with message index and time;
   provenance entries as `session#start-end` ranges, append-only per file; raw index
   anchored by message index; `--deep` hits carry `cited_by`. Tests: a range pointer
   survives re-chunking; provenance never shrinks through update or supersede.
4. **Reconcile and batch contract.** Rendering (numbered lines, session time), batching by
   input cap, reconcile sheet (BM25 over the increment, handles, directory menu, profile),
   `record_many` verbs and handle resolution, rejected → one repair round → `.state/pending`.
   Prompts render the slot table from schema descriptions. Tests: an operation naming a
   handle outside the sheet is rejected; a batch larger than the cap splits and the watermark
   advances per batch; a rejected item lands in pending and is retried at the next boundary.
5. **Triggers and executor.** Threshold and idle triggers beside the hooks; the boundary
   distillation call routed through the library executor; the `distill` and `trace`
   endpoints; config knobs. Tests: all three host hooks hand the same increment to the same
   executor call; a stubbed executor's operations pass the batch contract; the
   threshold path and the hook path produce the same set of memories from the same
   transcript; idle scan advances the watermark with hooks disabled.
6. **Manage.** T0 directory operations; proposals for split and for raw material hit but
   uncited; reasoner grammar extended to carry content; merge and split apply through the
   write path with library-computed fields; rate limits; git commit per sleep; the
   `authority` knob and human-only proposal kinds removed. Tests: after any sleep the set of
   files on disk never shrinks; merge produces one active file and two invalid ones with
   consistent instants; a reasoner answer naming a target outside the proposal is dropped;
   red-team: a memory body carrying an instruction does not change any verdict.
7. **Skill, harness, experiments.** Skill text from the same prompt module; harness arms
   for slot table / event lane / thresholds with R fixed; M on/off under the longitudinal
   protocol. Results under `experiments/`, TODO sweep.

## Config knobs added or removed

| knob | change |
|---|---|
| `storage.domains`, `storage.domain_types` | removed |
| `storage.schemas_dir`, `storage.max_depth` | added |
| `write.pending_token_threshold`, `write.pending_message_threshold`, `write.idle_seconds`, `write.max_distill_input_tokens` | added |
| `manage.authority` | removed |
| `manage.max_merges_per_sleep`, `manage.max_supersedes_per_sleep`, `manage.max_deletes_per_sleep` | added |
| `executor.model` (default Gemini 3.7 Flash), `executor.endpoint` | added |
| `recall.retrieval_weight_floor`, `weight.demote_penalty`, `manage.stale_after_days` | removed with the states they served |

## Acceptance

- `rm -rf .index && mem rebuild` loses nothing, with invalid files and history present.
- No code path under Manage can remove a file; `gc` is the only removal and is human-run.
- Same transcript through hook, threshold and idle triggers yields the same memories.
- Every memory written through the boundary path has non-empty provenance.
- Directory names never originate from a free field.

## Open questions carried into unit 1

- Abstract: rendered from key fields by default, agent may override. Decide in `write.md`.
- Type overlap (profile vs preference, entity vs reference) is settled by descriptions;
  the factory descriptions must say which wins.
- Depth cap default: 3.
