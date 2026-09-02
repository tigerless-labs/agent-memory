# P1 — generality: three hosts, one store

Run 2026-09-02. Hosts: `claude -p` (Haiku 4.5), `codex exec` (gpt-5.6-sol),
`hermes -z` (gemini-3.7-flash on Vertex). Same suite, same 12 stratified episodes, same
calibrated judge for all three.

## Interop — what A writes, B reads

| writer \ reader | claude-code | codex | hermes |
|---|---|---|---|
| claude-code | pass | pass | pass |
| codex | pass | pass | pass |
| hermes | pass | pass | pass |

9/9 ordered pairs. Each pair runs on its own store, so a pass cannot borrow another pair's
write. This is the shared-store claim discharged: a memory written through one host's shell is
found, with its specifics intact, through another's.

## Net contribution, per host

| host | no memory | with memory | memories/episode | paired |
|---|---|---|---|---|
| claude-code | 1/12 | 3/12 | 6.2 | +3 / −1, p=0.63 |
| codex | 1/12 | 7/12 | 36.8 | +7 / −1, p=0.07 |
| hermes | 0/12 | 3/12 | 2.8 | +3 / −0, p=0.25 |
| **pooled** | **2/36 (5.6%)** | **13/36 (36.1%)** | | **+13 / −2, p=0.0074** |

No single host reaches significance at n=12 — the noise floor established in
[p2-optimisation.md](p2-optimisation.md) forbids it. Pooled across hosts the direction is
unanimous and significant: thirteen questions won, two lost.

Every host's native memory was disabled, and verified empty afterwards: no
`~/.claude/projects/*/memory/` for any run directory, `thread_goals` empty in Codex, and
Hermes's `memories/` directory and `state.db` carrying no memory rows at all. Without that,
a host writes into its own store, reports success, and the measurement is of nothing.

## The finding worth following

**Write volume differs 13× across hosts on identical instructions and identical episodes** —
2.8 memories per episode for Hermes, 6.2 for Claude Code, 36.8 for Codex.

The write discipline is one text, rendered once, handed to all three. The store, the schema,
the validation and the retrieval are the same code. What differs is how much of the instruction
each host actually carries out before it stops.

This is a sharper question than any of the score comparisons that preceded it. It is a 13×
effect rather than a four-point one, so it is measurable; and it bears directly on the
product's premise, because "agent-agnostic memory runtime" assumes one discipline produces
comparable behaviour across hosts. On this evidence it does not.

Whether the cause is compliance (the host judges fewer things worth recording), budget (it
stops when tool calls get expensive), or interface friction (each `mem record` costs a turn,
so hosts with tighter turn budgets write less) is not yet distinguished, and the three have
different fixes: prompt, configuration, and a batch write API respectively.

## Host capability, measured rather than assumed

`docs/design/domains/experiment-harness.md` guessed at which W options each host could run.
Measured: all three run W0 and W2. The harness invokes distillation as a subprocess, so
"boundary fork" needs nothing from the host beyond being startable — the availability
distinction the design anticipated does not apply at this layer.

## Cost note

Hermes answers a no-memory question slowly (118s mean) and a with-memory question faster
(60s), the opposite of the other two hosts, and it failed 3 of 24 runs. Its slice is the
least reliable of the three; the numbers above exclude failed runs from the denominator.

## Batch write — the seventh negative, and a conflation worth naming

The 13× capture spread suggested a testable cause: a host pays a turn per tool call, so a
one-memory-per-call write API taxes exactly the hosts with the tightest turn budgets.
`mem record --batch -` removes that tax. Whether the host is told about it is a config knob,
so this is an A/B against the same episodes rather than a before-and-after.

| host | memories/episode | answer in store | correct |
|---|---|---|---|
| claude-code | 6.2 → **14.5** | 1/10 → 1/10 | 3/12 → 3/12 |
| codex | 36.8 → 34.6 | 6/10 → 5/10 | 7/12 → 9/12 |
| hermes | 2.8 → **6.5** | 0/10 → 1/10 | 3/12 → 2/12 |
| **pooled** | | | **13/36 → 14/36** |

Paired: gained 6, lost 5, **p=1.000**.

**The mechanism works and buys nothing.** Both hosts with headroom wrote 2.3× more; Codex,
already writing 35 a run, was unchanged — exactly the prediction. And the score did not move.

### The conflation

Capture *volume* and write *coverage* are different quantities, and only the second one can
affect a score:

- **volume** — how many memories get written
- **coverage** — whether the fact the question asks about is among them

Claude Code doubled its volume and its coverage stayed at 1/10. The eight extra memories were
not the one that was asked about. This was already visible in earlier data — volume ran 8→31
across v1/v2/v3 while coverage stayed flat near a third — and that evidence should have been
weighed before this run rather than after it. The cross-host correlation that motivated it
(Codex writes most and scores best) is a property of the hosts, not of the volume.

Coverage is a targeting problem: the distiller decides what matters without knowing what will
be asked. No unsupervised policy covers arbitrary specifics at any budget, which is why the
design's answer is keeping the raw material rather than writing more of the distilled kind.

### What the batch API is actually for

Cost, not accuracy. Twenty memories become one lock and one reindex instead of twenty of each,
and one host turn instead of twenty — a real improvement for the hosts with the tightest
budgets, and the reason it stays. It is not a score lever and is not recorded as one.

## Seven routes, seven negatives

| route | result |
|---|---|
| capture-fidelity prompting | no effect |
| injection track in the exam | no effect |
| per-session distillation, 3.5× write volume | no effect |
| raw-material fallback | n=120, p=1.000 — powered negative |
| supersede-on-write | n=120, p=0.27; identical where the mechanism fired |
| read discipline (synthesis hint + wider list) | n=240 paired over two replays, p=0.90 |
| batch write (interface friction) | volume 2.3× on constrained hosts, p=1.000 |

Write-side and read-side are both exhausted on this suite. The measured ceiling remains the
host's use of what it is handed.
