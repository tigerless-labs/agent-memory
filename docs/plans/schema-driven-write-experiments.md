# Plan: measuring the schema-driven write path and the unattended Manage

Working artifact for the experiment half of [schema-driven-write.md](schema-driven-write.md),
unit 7. Rules: [docs/experiments.md](../experiments.md). Protocols, once run, live in
[experiments/README.md](../../experiments/README.md); this page is the order of work and the
harness changes the rounds need.

## What changed that the ledger cannot see

Every row in the results ledger was written by the host's own model under the four-domain
layout. PR #11 replaced the writer (library executor, Gemini 3.7 Flash through Vertex), the
prompt (numbered conversation, reconcile sheet, slot table, event lane), the layout (schema
tree) and the record model (two states). The config schema changed, so every recall
fingerprint changed with it; no frozen corpus can be replayed against the new write path.
Each round below therefore starts with a fresh write pass, and the ledger gets a new section
rather than new rows under old fingerprints.

The executor endpoint was verified on 2026-09-04: one chat call to
`google/gemini-3.7-flash` answered at both `global` and `us-central1` in project
`tigerless-lara`. Runs export `GOOGLE_CLOUD_PROJECT=tigerless-lara VERTEX_LOCATION=global`;
the harness mints and refreshes the token itself.

## Rounds, in the order they run

Round numbers continue the single sequence (P11 was the last).

### P12 — the new default writer against the old one, R fixed

Question: with retrieval identical, does the library executor's write pass (W3) reach the
score of the host self-write (W2) that every ledger row was built on, and what does each
leave on disk?

| | |
|---|---|
| Suite | `longmemeval_s12.json`, stratified, `--per-type 20` → n = 120, seed default |
| Arms | W0 (control), W2 (host self-write, Haiku 4.5), W3 (library executor, Gemini 3.7 Flash) |
| Host / judge | Claude Code, Haiku 4.5 / Sonnet 5, agentic exam |
| Measures, in order | coverage probe on both store trees (deterministic, one pass); then two exam replays per arm against the frozen stores; paired McNemar per replay |
| Known differences W2 vs W3 | writer model, prompt shape, reconcile sheet, provenance pointers. One row is one configuration: the write-up names all four |

Pre-registered reading: a W3 − W2 difference under about 7/120 in both replays is
"indistinguishable", and the coverage probe then decides whether the prompt devices are worth
P13. W3 below W2 beyond the noise floor in both replays sends the executor prompt back to the
design doc before anything else runs.

### P13 — the prompt devices, under W3 only

Question: does the slot table, or the event lane, change what reaches disk?

| | |
|---|---|
| Arms | W3 default; `--set write.slot_table=false`; `--set write.event_lane=false` |
| Order | coverage probe first on all three trees; exams only for an arm whose coverage differs from the default by more than the probe's own spread across the two P12 W3 trees |
| Everything else | as P12 |

Each knob is one boolean and the executor, suite, host and R are fixed, so a row here is a
single variable. Gate: runs only after P12 has cleared the reading above.

### P14 — Manage under the longitudinal protocol

Question, the falsifiable claim of [manage.md](../design/domains/manage.md): with sessions
and sleeps alternating and the clock advancing, is the staleness net value of a sleep
positive, and does a sleep that reasons beat one that does not?

| | |
|---|---|
| Write side | W3 stores from P12, rebuilt longitudinally: the sessions of each episode in batches, a sleep after each batch, the clock advanced between batches |
| Arms | `off` (no sleep), `det` (`--reason none`), `llm` (the executor reasoning, default caps), `llm-wide` (`--set manage.merge_proposal_similarity=0.35`, the P11 band question) |
| Report | touch rate before score: how many exam episodes any sleep changed. A round whose touch rate cannot carry a 7/120 effect is recorded as underpowered, not as a null |
| Score | two exam replays per arm, paired McNemar |

Gate: the harness units below must land first, on their own branch, with tests.

## Harness units P14 needs (tests before code, one PR)

1. **The sleep step's endpoint reasoner is the executor.** `sleep-stores --reason endpoint`
   builds its reasoner from `executor.model` the way the CLI does, so the experiment sleeps
   with the same model the product ships. Test: the model the step sends is the config's.
2. **Longitudinal run.** `run --sleep-every <batches> --clock-step-days <days>` interleaves
   the experience phase with sleeps on that episode's store, advancing a frozen clock per
   batch; `--manage` labels the arm as today. Tests: the sleep count per episode equals the
   batch count; the clock the sleep sees advances monotonically; the exam still passes the
   isolation gate.
3. **Touch rate in the report.** Per arm, the number of exam episodes whose store differs
   from the `off` copy after the sleeps, printed above the accuracy table. Test: an arm
   with no sleep reports zero touched.

## Runbook

Runs write only to the main working tree; the harness refuses a workspace under a worktree.

```bash
export GOOGLE_CLOUD_PROJECT=tigerless-lara VERTEX_LOCATION=global
cd ~/tigerless_ai/agent-memory/experiments
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p12 --arms W0,W2,W3 --per-type 20 --run-id p12a
uv run mem-exp coverage --workspace runs/p12
uv run mem-exp run --suite data/longmemeval_s12.json --workspace runs/p12b --reuse-stores runs/p12/stores --arms W2,W3 --per-type 20 --run-id p12b
uv run mem-exp report --workspace runs/p12 && uv run mem-exp report --workspace runs/p12b
```

P13 repeats the first line per knob (`--workspace runs/p13-slot --arms W3 --set write.slot_table=false`,
`--workspace runs/p13-event --arms W3 --set write.event_lane=false`) and probes coverage before
any exam. P14's commands are written when its harness units land.

Every run is launched in the background and read when it finishes; a host or endpoint quota
failure stops the round rather than running it to a failed matrix.

## What each round must leave behind

Per [experiments.md §4](../experiments.md): config snapshot, exam mode, host and judge, parent
run for replays, per-question records, and the store truth files, committed under
`experiments/runs/`. The write-up for each round goes to `experiments/results/p1<n>-*.md` and
one line per configuration into the ledger's new section.
