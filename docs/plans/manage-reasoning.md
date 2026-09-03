# Plan: a reasoning pass inside Manage

> Working artifact. Owner ask (2026-09-02): put an LLM pipeline into M — host agent or a
> self-built Vertex pipeline — take what is worth taking from comparable projects, then
> measure M-on against M-off on two benchmarks.

## Reading of the ask, and one assumption

"两个 bench" is read as **LongMemEval-S** (already wired) and **LoCoMo** (new loader). They are
the two public multi-session suites the field actually compares on, and both carry
knowledge-update and temporal categories — the only question types where consolidation can
show up at all. The other benchmark discussed that day (obsidian-second-brain's synthetic
retrieval set) is excluded on purpose: it never exercises a write path, so an M arm and a
no-M arm would score identically by construction. **Assumption recorded, not resolved.**

## Why this is not "add an LLM call to sleep"

Three defects sit between today's M and any measurable M. The first is a prerequisite; the
plan fixes it in unit 1 whatever else changes.

1. **T1 proposals have no outlet.** `sleep` writes them into a dream-report and no code path
   — injection, context, CLI, MCP — ever reads one back. Merge, supersede, cluster therefore
   never happen. M today is five deterministic T0 actions and nothing else.
2. **weight settles from lifetime read counts** and re-applies them every sleep, so anything
   read three times climbs to the ceiling and stays. Value-based forgetting loses its input.
3. `manage.cluster_min_shared_tokens` is declared and never read.

## Where the intelligence lives

Core stays free of any LLM client (Invariant 5). The split:

- **core** owns the algorithm: which proposals are worth reasoning about, the prompt text, the
  response grammar, and the application of an accepted decision through the single write path
  (Invariant 2). It calls out through a `Reasoner` protocol — one method, text in, text out.
- **executor** (new package) owns the process work: shelling out to a host CLI, or speaking
  to Vertex's OpenAI-compatible endpoint with a `gcloud` token. `hosts.py` and
  `credentials.py` move here out of `harness`; the harness imports them instead of owning
  them, so a run and a sleep borrow intelligence the same way (DRY).
- **cli** wires one to the other and carries no algorithm (Invariant 8).

Two executors ship because they fail differently: the host executor is zero-key and leaves the
reasoning in the user's own transcript (ADR-002's whole point), while the Vertex executor runs
headless on a cron where no agent session exists.

## Authority stays where Invariant 6 put it

The reasoner never raises its own tier. `manage.authority` is a config knob, default T0:

| authority | what the reasoner may do |
|---|---|
| T0 (default, unattended) | rewrite a thin abstract against its own body; draft the reason and evidence on a proposal; nothing that removes a fact |
| T1 (explicitly set by a human, e.g. an experiment arm) | apply supersede and merge decisions it proposed |
| T2 | unchanged — human-initiated only |

Raising the knob is a human act, which is what "escalating authority" means. The experiment
arm that runs at T1 is therefore not a violation; a default that shipped at T1 would be.

## Taken from comparable projects

| source | taken | rejected |
|---|---|---|
| Mem0 | per-candidate decision against the top-s similar existing entries, one operation per fact (ADD/UPDATE/DELETE/NOOP) — the shape of the decision unit | doing it inline on every message pair, and physical DELETE unattended |
| auto-memory `consolidate-memory` | the durable/dated split as a prompt-level distinction, and the index-budget pass | unattended retire, and judging value with no usage statistics |
| obsidian-second-brain | additive-only background pass, destructive commands human-initiated with dry-run default, retire-as-redirect | scheduling as the product's answer to when consolidation happens |

What none of them has, and this plan keeps: the archive is available as evidence when two
entries disagree, so a contradiction is settled on the original transcript rather than on
recency.

## Units

Every unit: design-doc delta → failing tests → code → green → commit.

| # | scope | tests that must fail first |
|---|---|---|
| 1 ✅ | proposal outlet: stable ids, a decision ledger in the dream-report, `mem proposals` / `mem decide` | a proposal survives a sleep and is listed; deciding it applies through the write path; an already-decided proposal is not re-proposed |
| 2 ✅ | `weight` settles on reads since the last sleep; dead knob connected or removed | two sleeps with no new reads leave weight unchanged; a read between sleeps moves it once |
| 3 ✅ | `Reasoner` protocol in core, prompt + response grammar, decisions applied at T0 | a malformed response changes nothing; a decision naming an unknown entry is refused; T0 refuses a supersede decision |
| 4 ✅ | executor package: `hosts.py`/`credentials.py` moved, `HostReasoner`, `VertexReasoner` | harness keeps working off the moved modules; each reasoner is exercised against a fake process/endpoint |
| 5 ✅ | `mem sleep --reason` wiring, MCP parity for whatever the CLI gains | same request through CLI and MCP yields the same result (Invariant 8) |
| 6 ✅ | LoCoMo loader in the harness, `--manage` arm dimension, manage fingerprint in the attribution guard | a LoCoMo episode loads into the same `Episode` shape; a run mixing manage configs refuses to license attribution |

## Experiment (P11) — two protocols, cheap one first

**A. Shared-store replay.** Build the stores once with the current default W arm, fork a copy
per M arm, sleep each copy differently, then run the identical exam. Arms: `M-off`,
`M-deterministic` (today's T0), `M-reason-T0`, `M-reason-T1`. Because every arm starts from a
byte-identical store and the same recall config, a score difference is attributable to the
sleep alone. n=24 smoke, then 120, ≥2 replays per arm, pairwise McNemar
(docs/experiments.md).

**B. Longitudinal.** A is blind to everything M exists for: one write pass produces no
staleness, no superseded values, no topic density. B interleaves — session batch → sleep →
session batch → sleep → exam — with the clock advanced between batches so decay and staleness
thresholds can actually fire. B is the protocol manage.md's risk section says does not exist
yet; it is the deliverable that makes the falsifiable claim ("if the staleness net-value curve
trends to zero, cut this layer") executable for the first time.

Artefacts land in the main working tree, never in a worktree (docs/experiments.md §6).
