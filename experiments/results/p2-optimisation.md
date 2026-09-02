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

## P3: the certification run, n=120

The n=24 comparisons above could not resolve anything, so the one change with a real mechanism
behind it — the raw-material fallback — was run properly. 120 stratified episodes, W2, the
raw-on arm building the stores and the raw-off arm **replaying those same stores** with only
the read flag flipped, so the write side is identical by construction rather than by luck.

| | correct | accuracy | 95% CI |
|---|---|---|---|
| raw fallback on | 53/120 | 44.2% | 35.6–53.1 |
| raw fallback off | 54/120 | 45.0% | 36.4–53.9 |

Paired McNemar: gained 13, lost 14, 27 discordant pairs, **p=1.000**. At this n a real effect
would have shown as roughly an 18/27 split. This is a well-powered negative, not an unresolved
comparison.

### Why it is negative, measured

The fallback is not broken — it does exactly what it was built to do:

| on the 110 answerable episodes | count | share |
|---|---|---|
| gold answer surfaced by plain recall | 22 | 20% |
| gold answer surfaced by `--deep` | 41 | 37% |
| answered correctly | 46 | 42% |

Deep search nearly doubles the rate at which the gold answer is retrievable, and the score does
not move. Splitting the outcomes says where it goes:

| | count |
|---|---|
| gold retrievable and answered right | 26 |
| gold retrievable and answered wrong | 15 |
| gold not retrievable and answered right | 20 |
| gold not retrievable and answered wrong | 49 |

**The memory system has stopped being the limiting factor at this scale.** Fifteen episodes had
the answer sitting in the returned list and were still answered wrong; twenty were answered
right without the gold being lexically retrievable at all. Both columns are about what the host
does with what it is handed, not about what the store holds or returns.

(The "surfaced" test is lexical — 60% content-word overlap between the gold answer and a
returned entry — so it errs in both directions. The direction and size of the gap survive that.)

### What this settles

Four routes to a higher score were tried and measured: capture-fidelity prompting, the
injection track, per-session distillation at 3.5× the write volume, and raw-material fallback.
None produced an effect distinguishable from noise, and the last one was ruled out with power.
Together with the earlier negatives — write volume flat against coverage, retrieval already at
100% of what is stored — the remaining loss on this benchmark sits downstream of memory.

Optimising the memory system further against LongMemEval would be measuring the host.

## P4: supersede-on-write — a latent defect, and a fifth negative

The P3 diagnostic left one thread: fifteen episodes had the answer in the returned list and
were answered wrong anyway, several of them counting questions where the store held two
entries claiming different values, both current. So the supersede chain was checked directly.

**Across 3,744 memories written in 120 stores, the supersede edge count was zero.** The
mechanism the "nothing is destroyed" guarantee rests on, and that `--as-of` reads, had never
fired once.

The cause was the shape of the API rather than the discipline. Superseding cost three calls —
recall the old name, record the new entry, correct the old one to point at it — so an agent
working through a session with a turn budget wrote the new value and left the old one standing
beside it. `mem record --supersedes <name>` makes it one call.

The mechanism came alive: 25 edges across 120 stores, 15 episodes with at least one.

| | correct | accuracy | 95% CI |
|---|---|---|---|
| p3 raw-on (no supersede) | 54/120 | 45.0% | 36.4–53.9 |
| p3 raw-off (no supersede) | 59/120 | 49.2% | 40.4–58.0 |
| p4 supersede-on-write | 62/120 | 51.7% | 42.8–60.4 |

Paired against p3 raw-on: gained 24, lost 16, p=0.27. And the internal check settles it — on
the 15 episodes where supersede actually fired, p4 scored 9/15 and p3 scored 9/15, *identical*.
The entire +8 came from episodes where the mechanism never engaged, which is another way of
saying it came from run-to-run variance.

## P5: read discipline — and the measurement that ends the search

The P3 diagnostic put the remaining loss at the answering step, which had been treated as the
host's business. It is not: the exam preamble, the recall list width, and whether the agent is
told to work across entries are the memory system's read-side surface, and none had been
varied. The category saying so loudest was single-session-preference, stuck at 5–15% in every
run — those questions ask what would suit this person, answered from the pattern a set of
entries makes together, not by retrieving the one entry that mentions the topic.

Both knobs became config (`recall.synthesis_hint`, `recall.default_limit`), and both arms
replayed **the same stores** from P4, so the write side was identical by construction.

The first replay pair looked like the result the whole round had been chasing:

| replay 1 | correct | accuracy |
|---|---|---|
| baseline (hint off, list 8) | 60/120 | 50.0% |
| wide read (hint on, list 20) | 71/120 | 59.2% |

Paired: +21 / −10, p=0.071. Five of six categories up, temporal-reasoning +7/−1.

Then both arms were replayed a second time, against the same stores, with the same config:

| | replay 1 | replay 2 | pooled |
|---|---|---|---|
| baseline | 60/120 | 66/120 | 126/240 (52.5%) |
| wide read | 71/120 | **57/120** | 128/240 (53.3%) |

Pooled paired: +30 / −28, p=0.90. Scoring each episode by its majority across both replays:
wide better on 25, worse on 24, p=1.00.

**The exam phase alone swings ±7 per 120 episodes with the stores frozen, the config frozen,
and one judge.** That is what the p=0.071 was. A single replay pair cannot measure a read-side
change at all, and by extension neither could any of the single-run comparisons earlier in this
document — which is why every one of them needed the paired, repeated design to be believed.

## Six routes, six negatives

| route | result |
|---|---|
| capture-fidelity prompting | no effect |
| injection track in the exam | no effect |
| per-session distillation, 3.5× write volume | no effect |
| raw-material fallback | n=120, p=1.000 — powered negative |
| supersede-on-write | n=120, p=0.27; identical where the mechanism fired |
| read discipline (synthesis hint + wider list) | n=240 paired over two replays, p=0.90 |

Best measured configuration: **62/120 (51.7%)** against a no-memory control of 4/24 (16.7%).
The memory system's contribution is large and certain; the differences between its
configurations are not.

## Where a further gain would have to come from

Not from the memory system. The measured ceiling on this suite is the host's use of what it is
given, so the levers that remain are the answering step — how many searches it runs before it
settles, whether it reads entries or stops at abstracts, how it aggregates across entries for
counting questions — and the host model itself. Those are worth studying, but they are not
claims about memory, and a memory benchmark cannot be used to make them.

Read-side experiments are now cheap: `--reuse-stores` replays another run's stores, so a read
variant costs one exam per episode instead of a full experience phase.

## P6: who climbs the disclosure ladder — the one change that replicated

Every earlier comparison in this document failed for the same reason: a single run per
configuration, against a pipeline whose noise floor is larger than the effect. So this one was
run the way the earlier ones should have been — **replicated on both sides**, against the same
120 frozen stores from P4, with the write side identical by construction.

| exam mode | replays | within-arm spread |
|---|---|---|
| agent drives its own retrieval | 62, 60, 66 | 6 |
| store builds the context | 79, 76 | 3 |

**The distributions do not overlap: the worst fixed run beats the best agentic run by 10.**
Five of the six cross-arm pairings are significant (p from 0.0013 to 0.035; the sixth, p=0.11).
Scoring each episode by its majority across replays: +24 / −5, p=0.00055. Every within-arm
pairing is non-significant (p 0.33–0.86), which is the noise floor measured rather than assumed.

Pooled: 188/360 (52.2%) against 155/240 (64.6%). The exam also got cheaper — 9.0s against 14.8s.

### What changed, precisely

Not retrieval. Same recall, same scoring, same eligibility, same fingerprint. What moved is who
decides when to stop climbing the ladder: `recall` returns the L0 list and leaves that to the
caller; `mem context` runs the recall, opens the top entries to full text, and returns a block
ready to be reasoned over. The host does strictly less than before, not something new.

Progressive disclosure is an R-layer responsibility in the design. Delegating it to the host was
an implementation choice, and it was the expensive one.

### What this does and does not claim

It claims: on this suite, with writes frozen, the read surface deciding disclosure is worth
about twelve points, replicated, non-overlapping. It is a change to the memory system, lives in
the core as `mem context`, and reaches every host through the same CLI and MCP surface.

It does not claim: that the W options are ranked — they remain unresolved and the default stays
W2 on cost. That this generalises past LongMemEval. That M's net value is measured; it is not,
and that remains the largest untested claim in the project.

A caveat that cuts the other way: an agent that knows what it is looking for should keep the
ladder. `recall` was not replaced, and both surfaces stay.

