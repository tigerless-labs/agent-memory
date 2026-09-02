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

## P11 — what a sleep is worth

**Question.** Holding the write side and retrieval fixed, does a sleep change end-to-end
accuracy — and does a sleep that can reason change it more than one that cannot?

**Why this licenses attribution.** Every arm replays one byte-identical store tree under one
recall config; the only thing that differs is what happened to the copy between writing and
being asked. The run stamps the same fingerprints P2 does, and additionally labels the sleep,
so the report can put three sleeps of one write option on three lines.

### Arms

| label | what the copy went through |
|---|---|
| `off` | nothing — the frozen tree as written |
| `det` | the shipped unattended sleep: dates, weight, staleness, links, exact duplicates |
| `llm` | the same, plus a reasoner ruling on proposals at confirmed authority, with the merge candidate band widened so there is something to rule on |

The widened band is part of the arm, not a bug in it. At the shipped threshold the drafter
found **1 merge proposal across 120 stores** — a reasoner has nothing to decide, so an arm
holding the band fixed would measure the drafter's filter rather than the reasoning.

### Protocol

| | |
|---|---|
| Source stores | a finished W2 run's tree, copied once per arm |
| Suite | the same episodes the source tree was built from, same seed |
| Host / judge | as P2 — the comparison is only valid against the same instrument |
| Sleep clock | not advanced, so consolidation is isolated from forgetting |

### What this protocol still cannot see

One write pass produces no staleness, no superseded values and no topic density, so `det` can
only move the score through weight and links. The longitudinal protocol — session batch,
sleep, session batch, sleep, exam, with the clock advancing between batches — is what makes
the falsifiable claim in `docs/design/domains/manage.md` executable, and it does not exist yet.
P11 is the cheap half of the question, run first because it is cheap.

### Reproducing

```bash
uv run mem-exp sleep-stores --stores runs/p4sup/stores --target runs/p11det/stores
uv run mem-exp sleep-stores --stores runs/p4sup/stores --target runs/p11llm/stores --reason host --set manage.authority=T1 --set manage.merge_proposal_similarity=0.35
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p11/off --reuse-stores runs/p4sup/stores --arms W2 --per-type 4 --manage off
uv run mem-exp report --workspace runs/p11/off
```

## LoCoMo as a second suite

LoCoMo converts into the same episode shape rather than being adapted for, so the driver, the
isolation gate and the report never learn there are two suites. Its unanswerable category
carries the abstention marker the harness already reads, which is the part LongMemEval covers
thinnest. The release is not in this repo — convert it in from wherever it was downloaded:

```bash
uv run mem-exp convert-locomo --source /path/to/locomo10.json --target data/locomo.json
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

| `p11llm/stores` | 120 stores | `p4sup` after a reasoned sleep. Rebuilding it costs 120 host calls, and the accept/reject ledger inside it is the only record of what a reasoner actually did with a widened candidate band. Its sibling `p11det/stores` is deterministic and can be regenerated in a minute. |

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
