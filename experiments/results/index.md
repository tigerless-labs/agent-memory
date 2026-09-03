# Results index — every configuration that was measured

The write-ups below carry the reasoning. This page is the ledger: every configuration run at
n≥100, what it scored, and how many times it was replayed. Raw records are committed beside
them (`experiments/runs/*/runs.jsonl`); the stores they were built from are not, being 468 MB.

## Read this before reading a number

The rules that decide whether a row here is a result — the noise floor, the replay and pairing
requirements, and what licenses attribution — are in **[docs/experiments.md](../../docs/experiments.md)**.
Two consequences bite hardest on this page:

- **A row is a configuration, not a variable.** Rows differ in the recall fingerprint *and* in
  exam mode, and exam mode is not in the fingerprint. Comparing two rows measures whatever
  differs between them, which is not always the knob you had in mind.
- **A row with one replay establishes nothing**, and rows differing by less than about seven
  answers are not distinguishable.

## Ledger

All rows are the W2 arm on the same 120 episodes (fingerprint `213e6dcab30264e7`), Claude Code
host, calibrated judge.

| recall fingerprint | pooled | replays | runs | what it was |
|---|---|---|---|---|
| `e82efb90` | 160/240 = 66.7% | 2 | w24a 84, w24b 76 | list width 24, fixed exam — [p6](p6-list-width.md) **(claim retracted)** |
| `1c553b61` | 155/240 = 64.6% | 2 | fxa 79, fxb 76 | fixed exam, width 8 — config no longer reconstructible |
| `d231843a` | 221/359 = 61.6% | 3 | ctxa 71, ctxb 73, p7a 77 | list width 8, **agentic** exam (ctx) / slept store (p7a) |
| `1cc92424` | 128/240 = 53.3% | 2 | p5read 71, p5read2 57 | synthesis hint + wider list, together — [p5](p2-optimisation.md) |
| `eb1274cd` | 126/240 = 52.5% | 2 | p5base 60, p5base2 66 | P5 baseline |
| `b7194819` | 59/120 = 49.2% | 1 | p3off 59 | raw fallback off — [p3](p2-optimisation.md) |
| `361ded7e` | 116/240 = 48.3% | 2 | p3on 54, p4sup 62 | raw fallback on; supersede-on-write |

Smaller runs — the n=24 optimisation series and the n=12 per-host slices — are in
[p2-optimisation.md](p2-optimisation.md) and [p1-generality.md](p1-generality.md). The n=24
sleep comparison, and what it found about the drafter before it got to the exam, is in
[p11-manage.md](p11-manage.md).

## System-to-system rows

Same 120 episodes, same host and judge, agentic exam; a fresh write pass per system, two exam
replays each. These rows are end-to-end: the two systems differ in write and read together,
so the guard refuses attribution between them by design — [p10](p10-memcore.md).

| system | fingerprint | pooled | replays | runs | coverage |
|---|---|---|---|---|---|
| agent-memory W2 | `d231843a` (new write pass, not the ctx corpus) | 127/240 = 52.9% | 2 | p10am 64, p10am2 63 | 32/110 |
| MemCore W2 | `memcore:52e6e1dc` | 86/240 = 35.8% | 2 | p10mc 44, p10mc2 42 | 37/110 |
| W0 control | — | 7/120 = 5.8% | 1 | p10am | — |

## Two rows that had no write-up until now

**`1c553b61` — the fixed exam (fxa, fxb).** The harness performs the recall itself, builds one
context, and asks the host a single question with no tools, removing the host's search
behaviour as a source of variance. At 155/240 it sits between the wide-list and narrow-list
configurations. Its own replays are 79 and 76 — a spread of 3, against 8 for the wide arm and
14 for the P5 arms, so it does appear to be the lower-variance instrument it was built to be.
That is a claim about the instrument, not about memory: an earlier attempt at the same idea
(`fx1`, `fx2`) failed environmentally with every host call exiting non-zero, and is excluded.

**`d231843a`, third replay — after a sleep (p7a).** Run id `p7a-slept`: the same configuration
as ctxa/ctxb, measured after a Manage pass. It scored 77 against their 71 and 73. Three replays
of one configuration spanning 71–77 is the noise floor doing exactly what it is documented to
do, so **this is not evidence that sleep helps**; it is a third sample of the same row.

## A limitation of the attribution guard

The recall fingerprint identifies a configuration but is **not reverse-mappable across config
schema changes**. Adding or moving a knob changes every fingerprint, so runs from before a
schema change cannot have their settings reconstructed by searching the current config space —
`1c553b61` and `361ded7e` resisted exactly that. The guard still does its job, which is to
refuse attribution when arms differ; it cannot serve as a record of what a past arm *was*.
Runs whose settings matter should state them in their write-up.
