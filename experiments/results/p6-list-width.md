# P6 — recall list width: the first positive

Seven routes had been tried and had all come back negative. This one did not, and it clears
the evidentiary bar that the earlier failures forced us to set.

## The comparison

One knob, `recall.default_limit`, 8 against 24. Everything else identical — same 120 episodes
(fingerprint `213e6dcab30264e7`), same stores, same host, same calibrated judge. The two
configurations differ in exactly one value, confirmed by reconstructing each run's recall
fingerprint from the config space rather than by trusting a label.

Crucially, **each arm was replayed twice**. [p2-optimisation.md](p2-optimisation.md) established
that a single replay of a frozen configuration swings ±7 per 120 episodes, so a single pair
cannot measure a read-side change. Two replays per arm, scored per episode by majority, is the
design that failure demanded.

| configuration | replays | pooled | |
|---|---|---|---|
| `default_limit = 24` | 84, 76 | **160/240** | **66.7%** |
| `default_limit = 8` (previous default) | 71, 73 | 144/240 | 60.0% |

Per-episode majority across replays: wider is better on 18 episodes, worse on 7, **p=0.0433**.
Both replays of the wide arm beat both replays of the narrow one, which is what makes this
different from the p=0.071 that evaporated in P5.

## By question type

| question type | wide | narrow |
|---|---|---|
| temporal-reasoning | 34/40 | 26/40 |
| single-session-assistant | 25/40 | 20/40 |
| multi-session | 23/40 | 19/40 |
| knowledge-update | 31/40 | 29/40 |
| single-session-preference | 15/40 | 16/40 |
| single-session-user | 32/40 | 34/40 |

Four of six up, and the two that are down are down by one. The largest gain is
temporal-reasoning, which fits the mechanism: those questions need several dated entries at
once, and a list of eight truncates the set before the agent can compare them.

## It is also cheaper

| | exam seconds |
|---|---|
| `default_limit = 24` | 9.2 |
| `default_limit = 8` | 15.5 |

A wider list costs more tokens in one response and saves the repeated searches that a short
list forces. There is no accuracy-versus-latency trade to make here; the wide setting wins on
both.

## Shipped

`recall.default_limit` now defaults to 24. The recall fingerprint changes with it, so every
prior run remains distinguishable and the attribution guard sees the difference.

**Not established:** whether 24 is the best value. 16 and 32 were never run, and finding the
optimum means more runs. 24 is the best-evidenced value, not a tuned one.

## Why the earlier read-side attempt missed this

P5 varied the list width *and* the synthesis hint together, in a single replay pair, and got
p=0.071 that reversed on the second replay. The width was doing work the whole time; the
design could not see it. What changed is not the idea but the number of replays.
