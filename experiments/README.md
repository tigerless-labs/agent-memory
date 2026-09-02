# Experiments

Measurements that back empirical claims. Data and run artifacts stay out of git
(`experiments/data/`, `experiments/runs/`); protocols and results live here.

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

Results: [results/p2-longmemeval.md](results/p2-longmemeval.md).
