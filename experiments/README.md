# Experiments

Measurements that back empirical claims. Protocols and results live here; the data behind
them — question sets under `experiments/data/`, every run's records and store truth files
under `experiments/runs/` — is committed too, with only rebuildable caches left out.

The rules every experiment follows — experiment types, what counts as a result, attribution
conditions, what a run must record, failure handling — are in
**[docs/experiments.md](../docs/experiments.md)**. This page carries the protocols and the
retention list; it does not restate the rules.

## P2 — write-option comparison on LongMemEval

**Question.** With retrieval held fixed, how much does each write strategy (W0–W4) change
end-to-end answer accuracy, and what does it cost?

**Why this licenses attribution.** Recall is identical in every arm, so a score difference can
only come from what reached the store. The harness enforces this rather than asserting it:
every run stamps the recall-config fingerprint and the episode-set fingerprint, and the report
refuses to license attribution unless both are single-valued across arms (Invariant 9).

### Protocol

| | |
|---|---|
| Suite | LongMemEval-S, haystack bounded to 12 sessions per episode |
| Sampling | stratified by question type, fixed seed, identical episode list for every arm |
| Host | `claude -p`, Haiku 4.5, native memory disabled, clean working directory per run |
| Judge | Sonnet 5, one rubric, identical across arms |
| Experience phase | sessions replayed in batches; the batch boundary is the W trigger point |
| Exam phase | fresh session, question only — enforced by the isolation gate |

### Deviations from the published benchmark

**The haystack is bounded to 12 sessions per episode** (evidence sessions always retained,
distractors filled in from the original order). Full LongMemEval-S carries ~500 sessions per
episode, which is a corpus-size study, not a write-strategy study. Absolute accuracy here is
therefore not comparable to published LongMemEval numbers; the arm-to-arm comparison, which is
what P2 asks, is unaffected because every arm replays the identical bounded corpus.

**Question types are equally weighted** by stratified sampling rather than following the
suite's natural distribution.

Both are recorded in the run's episode fingerprint, so a later run at a different bound is
visibly a different experiment rather than a silently different one.

### Reproducing

```bash
uv run mem-exp prepare --source data/longmemeval_s.json --target data/longmemeval_s12.json --sessions 12
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p2 --arms W0,W1,W2,W3,W4 --per-type 4
uv run mem-exp report --workspace runs/p2
```

Results: **[results/index.md](results/index.md)** is the ledger of every measured
configuration; the individual write-ups carry the reasoning.

## P10 — agent-memory vs MemCore on one host

**Question.** Same host, same episodes, same judge: how does agent-memory compare with
MemCore (`memcli` v0.2.0, its own `skill.md`) on write coverage and on end-to-end accuracy?

**What it can support.** A system-to-system row is end-to-end only — write and read change
together, so no score difference is attributable to either side. Write coverage is the one
quantity that separates: it looks only at what reached disk.

### Protocol

| | |
|---|---|
| Suite, sampling, host, judge | as P2 |
| Systems | `agent-memory` (W2, shipped defaults) · `memcore` (boundary replay, its `skill.md` as system prompt) · W0 control |
| Exam | agentic for both — the harness has no context builder for MemCore's retrieval |
| Coverage | `mem-exp coverage`: lexical cover of the gold answer over every record text, abstention items excluded, one pass |
| Score | n=120, two exam replays per system against the frozen stores, paired McNemar per replay |

### Every known difference between the two arms

| | agent-memory | MemCore |
|---|---|---|
| write discipline | the harness's discipline text in the experience prompt | its `skill.md` as system prompt; discipline slot empty |
| record command | `mem record` (single and batch) | `memcore create <name>` with a frontmatter body |
| exam preamble | the harness's preamble naming `mem context / recall / read`, plus the synthesis paragraph (a recall config knob) | a parallel preamble naming `memcore recall / search / get`, no synthesis paragraph |
| session-start injection | MEMORY.md byte prefix | output of `memcore recall --top-k 7`, as its hook injects |
| raw material | transcript archived, reachable with `--deep` | none — MemCore keeps no transcript |
| retrieval | BM25 + graph | BGE-small embedding + graph + weight |

Shared: boundary framing, the distill task text, host and model, turn budgets, episode list,
judge, exam prompt shell.

### Environment

MemCore is built from the local checkout with its embedding feature. On glibc 2.39 its
`__libc_single_threaded` shim is a read-only static that glibc writes at thread start, so the
unmodified binary segfaults on every command; the binary used here makes that static writable
(one line, no behaviour change). `MEMCORE_HOME` names the checkout; each per-episode store is
its own MemCore directory with the model linked in, and the daemon is stopped after each phase.

### Reproducing

```bash
export MEMCORE_HOME=/path/to/memcli
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p10am --arms W0,W2 --per-type 20 --run-id p10am
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p10mc --arms W2 --per-type 20 --system memcore --run-id p10mc
uv run mem-exp coverage --workspace runs/p10am
uv run mem-exp coverage --workspace runs/p10mc
```

## What is in git, and what a store needs before it can be replayed

Every run's evidence is committed: `runs.jsonl`, `questions.json`, the report, and the store
tree's truth files — memories, archives, config, MemCore nodes. What is not committed is what
Invariant 1 says is a cache: `.index/` and MemCore's `index/`, `graph.idx`, `wal.log`, the
`models` link, plus working directories and progress logs. A freshly cloned store therefore
answers `mem read` but not `mem recall` until `mem rebuild` (or, for MemCore, its first
daemon start) has projected the index again; a replay against a clone needs that step first.

**Frozen corpora.** These store trees anchor read-side results, so their truth files must
stay exactly as written; a new write pass produces a different corpus and a future number
measured on it is not comparable to any earlier one.

| corpus | stores | anchors |
|---|---|---|
| `p4sup/stores` | 120 | every read-side result P5 through P9 |
| `p7slept/stores` | 120 | the same corpus after one Manage sleep — the only before/after pair about M |
| `p10am/stores`, `p10mc/stores` | 120 each | the P10 pair; its replays and the read-side follow-ups |

The n=24 optimisation rounds, the smoke runs, the discarded `fx1`/`fx2`, the per-host slices,
and runs started with `--reuse-stores` (whose `stores/` is scaffolding, not memories) anchor
nothing. Their conclusions are recorded and their trees are kept only because keeping is free.

`experiments/data/longmemeval_s.json` — the published suite, 278 MB — is committed gzipped
because it exceeds GitHub's single-file limit; `gunzip -k` it before `mem-exp prepare`.
The bounded `longmemeval_s12.json` and the oracle are committed as they are.
