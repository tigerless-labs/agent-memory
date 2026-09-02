# P11 — what a sleep is worth, first pass

**Question.** Holding the write side and retrieval fixed, does a sleep change end-to-end
accuracy, and does a sleep that can reason change it more than one that cannot?

**Answer.** Not measurably, and this round could not have measured it. The finding that
matters came before the exam: at the shipped candidate threshold, a reasoner has almost
nothing to rule on.

Protocol and reproduction: [../README.md](../README.md#p11--what-a-sleep-is-worth).

## What the drafter offers a reasoner

One deterministic sleep over the frozen `p4sup` tree — 120 stores, ~3,600 entries:

| merge candidate band | proposals drafted |
|---|---|
| 0.75 (shipped) | **10** — of which 1 merge, 1 cluster, 8 abstract reviews |
| 0.35 | 132 |
| 0.25 | 378 |

Eight thousand deterministic actions fired (dates, weight, staleness, links), and **one** pair
of entries in the whole corpus was similar enough to propose merging. The band is a lexical
Jaccard over abstracts, and entries an LLM wrote about the same fact in different words do not
clear it. A reasoning pass bolted onto this drafter would have been handed an empty tray and
reported success.

This is the round's result. It is also the difference from Mem0's shape, which retrieves the
top-s most similar existing memories per candidate and lets the model decide: the filtering
happens after the reading, not before it.

## What the reasoner did with a widened band

At 0.35, with authority raised so acceptances could apply, Haiku ruled on all 132:

| verdict | count |
|---|---|
| rejected | 96 (73%) |
| accepted | 32 — 24 supersedes, 8 abstract rewrites |
| withheld by tier | 4 — cluster proposals it tried to accept, refused because directory moves stay T2 |
| left open | 4 |

Two things worth recording. The reasoner rejects three quarters of what a loosened band
drafts, which is the division of labour the design assumes and the first evidence that it
holds. And the tier gate fired in a live run, not only in the red-team test: a reasoner that
wanted to reorganise directories was told no by configuration rather than by prompt.

Mean entries per store is unchanged at 30.6 across every arm — a supersede marks, it does not
remove.

## The exam, and why its numbers say nothing

Same 24 episodes (`a39325b0a9a1d536`), same recall config (`d231843a7c9f0255`), one
byte-identical store tree copied three ways.

| arm | correct | accuracy |
|---|---|---|
| `W2+off` | 13/24 | 54.2% |
| `W2+det` | 14/24 | 58.3% |
| `W2+llm` | 14/24 | 58.3% |

| pair | discordant | p |
|---|---|---|
| det vs llm | 2 | 1.000 |
| det vs off | 1 | 1.000 |
| llm vs off | 1 | 1.000 |

The accuracy column shows a 4-point gap; the paired view shows arms that answered 23 of 24
episodes identically. Nothing here is distinguishable from nothing.

**And it could not have been.** Of the 24 exam episodes, **6 had any accepted decision at all**
(8 decisions between them). Three quarters of the exam replayed a store the sleep never
touched, so three quarters of the comparison was measuring one store against itself. This is
underpowered by construction — not a negative result about Manage, and not evidence that
consolidation is worthless.

## What would make the question answerable

1. **Report the touch rate before the score.** "How many exam episodes did this sleep change?"
   bounds the largest effect the run could detect. A sleep that touched 6 of 24 cannot produce
   a result at n=24, and n=120 at the same rate gets 30 — better, still thin. This belongs in
   the report, not in a note afterwards.
2. **The longitudinal protocol.** One write pass produces no staleness, no superseded values
   and no topic density; the sleep is being asked to tidy a corpus that was never untidy. Until
   sessions and sleeps alternate with the clock advancing between them, the layer's stated
   purpose is not on the table, and the falsifiable claim in
   [manage.md](../../docs/design/domains/manage.md) stays unexecutable.
3. **Decide the shipped band on evidence.** 0.75 drafts almost nothing; 0.35 drafts 132 and the
   reasoner rejects 73% of them. Whether the default should move depends on what those 27%
   were worth, which needs the protocol above to answer.

## Limits

Single run per arm, n=24 — below every bar in [experiments.md](../../docs/experiments.md), and
recorded here as a smoke test that the machinery works end to end, which it does. The reasoned
arm varies three things at once against `det` (band, reasoner, authority) by design: at the
shipped band there is no reasoning to measure. Store: `p11llm/stores`, kept.
