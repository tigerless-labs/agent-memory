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
