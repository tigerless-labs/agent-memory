# P2 — write options on LongMemEval-S (bounded haystack)

Run `p2-lme-s12`, 2026-09-01. Protocol and deviations: [../README.md](../README.md).
120 runs, 0 host failures. Attribution licensed: recall fingerprint `51298412bdabe94f` and
episode fingerprint `a39325b0a9a1d536` are single-valued across all five arms.

## Headline

| arm | mechanism | correct | accuracy | 95% CI | vs W0 (paired) |
|---|---|---|---|---|---|
| W0 | no memory (control) | 3/24 | 12.5% | 4.3–31.0 | — |
| W1 | boundary self-write, blocking | 10/24 | 41.7% | 24.5–61.2 | +7 / −0, p=0.016 |
| W2 | boundary fork, non-blocking | 11/24 | 45.8% | 27.9–64.9 | +8 / −0, p=0.008 |
| W3 | cold read of archived transcript | 6/24 | 25.0% | 12.0–44.9 | +5 / −2, p=0.45 |
| W4 | inline write during the session | 9/24 | 37.5% | 21.2–57.3 | +6 / −0, p=0.031 |

Paired McNemar exact test on the identical episode set; "+7 / −0" means the arm answered 7
questions W0 missed and lost none it had.

On the 22 answerable questions alone (excluding the 2 abstention items), the control gets
1/22 and the best write arm 9/22.

## What the numbers support

**Memory pays, and the effect is not marginal.** Three of four write arms beat the blank
control at p < 0.05, each with zero regressions — every question they won was one the control
had no way to answer. This is the net-contribution floor the roadmap asked W0 to establish.

**The boundary-versus-inline question is not settled by this run.** W1, W2 and W4 are
statistically indistinguishable from one another (all pairwise p ≥ 0.6). At n=24 a single
answer moves an arm by 4.2 points, so the ordering W2 > W1 > W4 is noise. Deciding between
them needs a larger n, and the roadmap's P2 default should not be set from this run alone.

**W2 is nonetheless the arm to ship.** It matches W1's accuracy at zero blocking time —
141s of task tail on W1, 0s on W2 — so it dominates on the axis that is actually resolved
here. Choosing it costs nothing that this run can measure.

**W3 is the one real negative result, and more writing is why.** Cold-reading the archived
transcript produced the *most* memories per episode (13.2, versus 8.7 for W1) and the worst
accuracy of any write arm. It is also the only arm that lost ground to the control: both
abstention questions, where W3's store contained enough plausible-looking material to
manufacture an answer instead of saying it did not know. Volume of writes is not a proxy for
quality of writes, and a distiller working without the live context appears to write more and
mean less.

## By question type

| question type | W0 | W1 | W2 | W3 | W4 |
|---|---|---|---|---|---|
| knowledge-update | 25.0% | 75.0% | 100.0% | 50.0% | 75.0% |
| multi-session | 25.0% | 25.0% | 50.0% | 0.0% | 25.0% |
| single-session-assistant | 0.0% | 0.0% | 25.0% | 25.0% | 25.0% |
| single-session-preference | 0.0% | 0.0% | 25.0% | 25.0% | 25.0% |
| single-session-user | 25.0% | 100.0% | 75.0% | 50.0% | 50.0% |
| temporal-reasoning | 0.0% | 50.0% | 0.0% | 0.0% | 25.0% |

Four episodes per cell: read these as direction, not magnitude. The one pattern worth
following up is knowledge-update, where every write arm improves and the supersede discipline
is the mechanism under test.

## Cost

| arm | memories/episode | experience s | blocking s | exam s |
|---|---|---|---|---|
| W0 | 0.0 | 0.0 | 0.0 | 6.0 |
| W1 | 8.7 | 141.3 | 141.3 | 13.5 |
| W2 | 9.9 | 132.6 | 0.0 | 13.9 |
| W3 | 13.2 | 124.6 | 0.0 | 13.1 |
| W4 | 11.6 | 108.8 | 108.8 | 13.8 |

Memory roughly doubles exam latency (6.0s → ~13.5s): the cost of searching and reading before
answering. Blocking time is the number that separates W1 from W2 and is the whole argument
for the fork.

## Limits

- **n=24 per arm.** Enough to separate memory from no-memory, not enough to rank write arms.
- **12-session haystack.** Absolute accuracy is not comparable to published LongMemEval
  numbers; every arm saw the identical bounded corpus, so the comparison holds.
- **One host, one model.** Haiku 4.5 throughout. Generality across hosts is P1/P3 work; the
  Hermes row is unfilled by decision.
- **LLM judge.** Sonnet 5, one rubric, identical across arms — judge bias shifts all arms
  together and does not touch the paired differences.

## What this changes

- W2 becomes the default write option, on cost rather than on accuracy.
- W3 needs investigation before it can be the cron fallback the design assumes; the abstention
  regression is the thread to pull.
- Ranking W1/W2/W4 needs a larger P2 run.
