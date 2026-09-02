# P6 — recall list width: retracted

**This write-up previously reported list width as "the first positive" (+6.7 points, p=0.0433).
That result was confounded and does not hold. `recall.default_limit` has been returned to 8.**

## What went wrong

The wide arm (`w24a`/`w24b`, `default_limit=24`) was compared against `ctxa`/`ctxb`. Those two
runs differ from the wide arm in **two** ways, not one:

| | exam mode | `default_limit` |
|---|---|---|
| `w24a` / `w24b` | fixed — the store builds the context, host answers once (9.1s, 9.4s) | 24 |
| `ctxa` / `ctxb` | **agentic** — host drives its own tool loop (15.8s, 15.5s) | 8 |
| `fxa` / `fxb` | fixed (9.0s, 8.6s) | 8 |

Exam mode is worth +23/−4 on its own ([P9](p2-optimisation.md)), so a comparison that varies it
alongside width measures mostly the mode. The like-for-like baseline is `fxa`/`fxb`.

The recall fingerprints were checked and found to differ, which is what the guard is for — but a
differing fingerprint was read as "the width differs" rather than "something differs", and the
exam mode is not in the fingerprint at all.

## The clean comparison

Same exam mode, width 8 against 24, every replay pairing, paired McNemar over the 119 episodes
graded in all runs:

| baseline (width 8, fixed) | wide (width 24, fixed) | | p |
|---|---|---|---|
| `fxa` | `w24a` | +12 / −7 | 0.359 |
| `fxb` | `w24a` | +14 / −6 | 0.115 |
| `fxa` | `w24b` | +7 / −10 | 0.629 |
| `fxb` | `w24b` | +9 / −9 | 1.000 |

Pooled 160/238 against 155/238. Nothing reaches significance and the direction reverses across
pairings — one of the four has the wide arm behind. **Width 24 is not established, and the
default should not have moved.**

For contrast, the confounded pairings that produced the retracted claim:

| baseline (width 8, **agentic**) | wide (width 24, fixed) | | p |
|---|---|---|---|
| `ctxa` | `w24a` | +18 / −5 | 0.011 |
| `ctxb` | `w24a` | +19 / −8 | 0.052 |
| `ctxa` | `w24b` | +16 / −11 | 0.442 |
| `ctxb` | `w24b` | +16 / −13 | 0.711 |

Significance appears only where the wide arm's luckiest replay (84) meets the agentic baseline.

## Two method faults this exposed

**The exam mode is not in the recall fingerprint.** The guard that exists to stop exactly this
comparison could not see the variable that dominated it. Recorded in TODO.

**"Majority across replays" was a union for two-replay arms.** The aggregation used here and in
P8/P9 counted an episode correct if *any* replay got it, which for two replays is a union rather
than a majority. A union inflates both arms and flatters whichever has the larger spread — and
the wide arm's spread (8) is the largest measured. The pairwise table above uses no aggregation
at all.

## What would settle it

Width 8 against width 24, both in fixed exam mode, on the current config, two replays each,
compared pairwise. That run does not exist; `fxa`/`fxb` predate config changes and their exact
recall configuration can no longer be reconstructed from the config space.
