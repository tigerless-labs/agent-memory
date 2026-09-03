# P10 — agent-memory vs MemCore on one host

Run 2026-09-02. Protocol, the list of every known difference between the arms, and the
environment note are in [../README.md#p10](../README.md#p10--agent-memory-vs-memcore-on-one-host).
Host `claude -p` Haiku 4.5, agentic exam, calibrated Sonnet 5 judge, 120 episodes
(fingerprint `213e6dcab30264e7` — the same episode list as every n=120 row in the ledger).
Each system had one write pass and two exam replays against its frozen stores.
Zero host failures in the records that count; the MemCore write pass hit the account's
session limit at 62/120 and was resumed after the reset, so 58 of its stores were written
in a second window (`--resume`; the failed records were discarded, not counted).

## Headline

| arm | replay 1 | replay 2 | pooled | memories/episode | experience s/episode |
|---|---|---|---|---|---|
| W0 no memory | 7/120 | — | 5.8% | 0 | 0 |
| agent-memory W2 | 64/120 | 63/120 | **127/240 = 52.9%** | 30.6 | 483 |
| MemCore W2 | 44/120 | 42/120 | **86/240 = 35.8%** | 17.0 | 350 |

Paired per replay on the identical episodes (McNemar exact):

| pair | replay 1 | replay 2 |
|---|---|---|
| agent-memory vs MemCore | +37 / −17, p=0.009 | +35 / −14, p=0.004 |
| agent-memory vs W0 | +61 / −4, p<0.001 | +60 / −4, p<0.001 |
| MemCore vs W0 | +41 / −4, p<0.001 | — |
| MemCore replay 2 vs replay 1 | +13 / −15, p=0.85 | |
| agent-memory replay 2 vs replay 1 | +5 / −6, p=1.0 | |

Both systems beat the control by a wide margin. Between them the gap is about twenty answers
in both replays, three times the documented noise floor, and the same direction each time.
**This is an end-to-end result and nothing finer**: write and read differ together (see the
difference list in the README), so it does not say which side of either system is responsible.

## Write coverage — the one quantity that separates

`mem-exp coverage`, lexical cover of the gold answer over every record, abstention items
excluded, one pass:

| system | answer reached a record | accuracy when it did (pooled) | accuracy when it did not |
|---|---|---|---|
| agent-memory | 32/110 = 29.1% | 50/64 = 78% | 74/156 = 47% |
| MemCore | 37/110 = 33.6% | 42/74 = 57% | 38/146 = 26% |

**Coverage does not explain the score.** MemCore wrote 44% fewer nodes and covered five more
answers. The twenty-answer gap sits entirely downstream of what reached disk: on the 21
episodes both systems covered, agent-memory scored 30/42 and MemCore 21/42; on the episodes
neither covered by this probe, 47% against 26%. What "downstream" contains — retrieval,
reading, synthesis, the raw-material fallback, the exam preamble — cannot be split in a
system-to-system row.

## Where the gap is, by question type

Pooled over both replays, out of 40 (34 or 36 for the types with abstention items):

| type | agent-memory | MemCore | covered (am / mc) |
|---|---|---|---|
| knowledge-update | 33/36 | 18/36 | 7 / 6 |
| multi-session | 20/32 | 5/32 | 2 / 4 |
| temporal-reasoning | 18/38 | 8/38 | 6 / 6 |
| single-session-user | 30/34 | 23/34 | 10 / 9 |
| single-session-assistant | 13/40 | 17/40 | 7 / 12 |
| single-session-preference | 10/40 | 9/40 | 0 / 0 |

The gap is concentrated in the three types that need more than one entry: the current value
of something that changed, a total across sessions, a date worked out from several. The
single-session types are level, and MemCore is ahead on single-session-assistant, where it
also covered more. Two of the listed differences bear directly on those three types —
agent-memory's supersede chain with `valid_from` dates, and the synthesis paragraph in its
exam preamble — and MemCore has neither. That is a hypothesis this run cannot test, and the
cheap next step is read-side: replay MemCore's frozen stores with the synthesis paragraph
added to its preamble, which changes one thing and needs no write pass.

## Cost

MemCore's write pass is 28% cheaper in host time and writes 44% fewer nodes; exam time is
level (14.1 s vs 15.5 s). Abstention is poor on both sides (agent-memory 2/10 and 1/10,
MemCore 3/10 and 3/10) — the [known instability](p2-optimisation.md).

## What this does and does not license

- **Licensed.** On this host and this suite, agent-memory answers more than MemCore, by a
  margin that survives replay; MemCore is a working memory system that beats no-memory
  handily; write coverage is not where the difference comes from.
- **Not licensed.** Any statement about *which component* is better. Any generalisation to
  another host (P1 showed a 13× write-volume spread across hosts on identical instructions)
  or to MemCore driven by its OpenClaw plugin rather than its skill text.
- **Instrument caveat.** The coverage probe is lexical at threshold 0.6; "not covered" means
  the probe did not find the gold words in one record, not that the store cannot answer —
  agent-memory answered 47% of those.

## Smoke and mechanics

`p10mech` (6 episodes) and `p10am24` / `p10mc24` (n=24) ran first, with zero failures;
at n=24 the systems were 10/24 vs 9/24, +4/−3, p=1.0 — indistinguishable, as n=24 always is.
Their records are committed beside this file's.
