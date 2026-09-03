# Experiments

Measurements that back empirical claims. Data and run artifacts stay out of git
(`experiments/data/`, `experiments/runs/`); protocols and results live here.

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

## What in `experiments/runs/` may be deleted, and what may not

`experiments/runs/*/stores/` holds the memory stores a run built. They are gitignored — 464 MB
of them — so git protects none of it, and the most expensive artefact this project has produced
is the part a routine directory cleanup would take first. Two worktree removals nearly did.

**Keep. A write pass costs hours and these are the frozen corpora every read-side comparison is
anchored to.**

| corpus | size | why it cannot be rebuilt |
|---|---|---|
| `p4sup/stores` | 101 MB, 120 stores | Every read-side result — P5 through P9 — is a replay against exactly these. A new write pass produces different stores, so a future read-side number measured elsewhere is not comparable to any of them. |
| `p7slept/stores` | 96 MB, 120 stores | The same corpus after one Manage sleep. The before/after pair is the only evidence about M's net effect that exists; regenerating the "after" needs the "before" intact. |
| `p10am/stores`, `p10mc/stores` | 120 stores each | The P10 pair: one agent-memory write pass and one MemCore write pass on the same episodes. Every P10 replay is anchored to exactly these, and the cheap follow-ups (a MemCore replay with a changed preamble) need them intact. |

**Disposable.** The n=24 optimisation rounds (`p2`, `p2v2`, `p2v3`, `p2v4`, `p2v5*`), the smoke
runs, the discarded `fx1`/`fx2`, and the per-host slices. Their conclusions are recorded and
nothing replays against them. `p3on/stores` (90 MB) sits between the two: P3 is settled and no
run is anchored to it, so it is archival rather than load-bearing.

**Not corpora at all.** A run started with `--reuse-stores` leaves a `stores/` of about 968 KB —
scaffolding, not memories. `fxa`, `fxb`, `ctxa`, `ctxb`, `w24a`, `w24b`, `p5*`, `p3off` and `p7a`
are all of this kind. Size tells them apart: under a megabyte means the run borrowed its corpus.

Deleting a frozen corpus does not lose a *finding* — the records and write-ups are committed.
It loses the ability to run one more arm against the same write pass, which is the only way a
read-side change can be measured at all.

Run records (`experiments/runs/*/runs.jsonl`) are committed as evidence. The stores they were
built from are not — 468 MB — so a write-up's claims are checkable from the records while the
corpora stay reproducible from `mem-exp prepare`.
