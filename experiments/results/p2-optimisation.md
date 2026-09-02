# P2 optimisation round — what moved, what didn't, and what the instrument can see

Follows [p2-longmemeval.md](p2-longmemeval.md). Same suite, same 24 episodes, same episode
fingerprint `a39325b0a9a1d536` throughout. All numbers below are under the **calibrated**
judge; the numbers in the earlier write-up were not, and are superseded.

## The instrument was wrong first

LongMemEval's abstention items have gold answers that say the information was never provided —
declining is the correct answer. The original rubric said a candidate that declines is
incorrect, so correct behaviour was graded as failure. Every number in the first write-up was
affected.

The judge is now treated as an instrument:

- `experiments/judge-calibration.json` — twelve hand-labelled cases covering answered-right,
  answered-wrong, rightly-declined, wrongly-declined. `mem-exp calibrate` reports agreement.
- A single judge call disagreed with the labels ~10% of the time. Grading now takes a majority
  of three votes; agreement at that setting is ~97%.
- `mem-exp regrade` re-decides stored answers offline, so a rubric change costs no host run.
  Both earlier runs were regraded rather than repeated.

## W2 across six configurations

| config | change from the previous row | correct | accuracy |
|---|---|---|---|
| v1 | baseline | 10/24 | 41.7% |
| v2 | capture-fidelity prompt + injection track | 8/24 | 33.3% |
| v3 | one session per distill call | 9/24 | 37.5% |
| v4 | raw-material fallback | 14/24 | 58.3% |
| v5 raw on | v4 settings, independent re-run | 10/24 | 41.7% |
| v5 raw off | v5 settings, fallback disabled | 8/24 | 33.3% |
| W0 | no memory (control) | 4/24 | 16.7% |

## The finding that governs the rest

**Two runs of an identical configuration differ on 6 of 24 episodes — 14 correct versus 10.**
That is the noise floor of the end-to-end pipeline, and every effect chased in this round is
smaller than it. v4's 58.3% was not a result; it was the same configuration having a good day.

The single-variable A/B bears this out: with everything else held fixed and only the raw
fallback flipped, raw-on gained 5 and lost 3 against raw-off (p=0.73).

Sources of that variance, none of them removable by tuning: the distilling agent chooses what
to write, the answering agent chooses what to search for and when to stop, and the judge
carries its own ~±1/24. At n=24 the design can detect "memory versus no memory" and nothing
finer.

## What survives at this n

Memory versus no memory, in every configuration:

| config | vs W0 | p |
|---|---|---|
| v1 | +6 / −0 | 0.031 |
| v4 | +12 / −2 | 0.013 |
| v5 raw on | +9 / −3 | 0.146 |
| v5 raw off | +7 / −3 | 0.344 |

Pooled across all six W2 runs: 59/144 (41.0%) against 4/24 (16.7%) for the control. The
memory system's net contribution is the one claim this experiment supports.

## Three measured negative results

**Write volume is not the bottleneck.** Memories per episode went 9 → 15 → 31 across v1/v2/v3
— a 3.5× range — while the share of questions whose answer was anywhere in the store stayed
flat at roughly a third, and retrieval of what *was* stored stayed at 100%.

| config | memories/episode | answer in store (of 22) | retrieved when present |
|---|---|---|---|
| v1 | 8–13 | 5–8 | 100% |
| v2 | 15–17 | 7–8 | 100% |
| v3 | 31–33 | 7–9 | 100% |

**Retrieval is not the bottleneck either.** Whenever the answer was in the store, BM25 surfaced
it in the top-8, in every configuration. Tuning retrieval — vector plugin included — has
nothing to bite on at this scale.

**Capture is a targeting problem, not a capacity problem.** The distiller decides what matters
without knowing what will be asked, and the questions ask about arbitrary specifics. No
unsupervised write policy covers that space at any budget; the answer has to come from keeping
the raw material, which is what Invariant 4 always said.

## What was fixed regardless of the score

- **Raw material became reachable.** Transcripts sat in `archive/sessions/` with no path from a
  query to them: the backstop existed on disk and nowhere else. Raw material now has its own
  FTS table, answers only to `--deep`, carries no weight or recency, and is deliberately
  outranked by distilled memory.
- **The injection track reached the exam.** The design calls for three read tracks; the harness
  exercised one.
- **`--type` errors became repairable.** An agent that guessed a wrong type was told only that
  it was wrong, and burned its turn budget guessing.
- **Arms are config, not code.** `mem-exp run --set section.knob=value` makes a W option a knob
  (ADR-006), and the recall fingerprint changes with it so the attribution guard sees it.

## What it would take to resolve the rest

Discordant pairs run ~33% of episodes. Detecting a 15-point difference at 80% power needs on
the order of 250 episodes per arm — roughly ten times the compute used here per arm.
LongMemEval-S has 500, so this is affordable; it is simply not something n=24 can be argued
into. Until then, configuration-level claims should be reported as unresolved rather than
ranked.
