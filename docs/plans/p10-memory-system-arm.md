# Plan: the memory-system dimension, and P10 (agent-memory vs MemCore)

> Working artifact. Closes the TODO "与 MemCLI 的对照实验". Branch `feat/memory-system-arm`.

## Question

Same host (Claude Code, Haiku 4.5), same episodes, same judge: how does agent-memory compare
with MemCore (the `memcli` repo, v0.2.0) on **write coverage** and on **end-to-end score**?

Per [docs/experiments.md §3](../experiments.md), a system-to-system row is end-to-end only —
W and R change together, so nothing licenses "who writes better". Write coverage is the one
quantity that separates, because it looks only at what reached disk.

## Units (each: design delta → failing tests → code → green → commit)

1. **Design.** `experiment-harness.md` gains the memory-system dimension: a system is a
   dialect (like a host), the matrix is system × host × W, the coverage probe is the offline
   subcommand the TODO asked for. `experiments/README.md` gains the P10 protocol.
2. **Systems module.** `harness/systems` — one object per memory system carrying: store
   preparation, host environment, tool allow-pattern, experience/exam system prompts, record
   hint, write discipline, injection payload, record texts, record count, fingerprint,
   release. Native = agent-memory; `memcore` = MemCore driven through its own `skill.md`.
3. **Driver + hosts + metrics.** Driver asks the system instead of `Store` directly; the
   Claude dialect takes the tool pattern from the system; `RunRecord` carries `system`;
   report groups by (system, arm). Fixed exam stays native-only (the harness has no context
   builder for another system's retrieval).
4. **Coverage probe.** `mem-exp coverage --workspace` — offline, deterministic, lexical
   cover of the gold answer over every record text, per (system, arm), abstention items
   excluded. Same algorithm the P3 diagnostic used, now a subcommand.
5. **Run.** Smoke n=24 (per-type 4) on both systems plus W0, agentic exam. Then n=120 write
   pass per system, two exam replays each, paired McNemar per replay; coverage once.
6. **Write-up.** `experiments/results/p10-memcore.md` + ledger rows + TODO sweep.

## Known differences between the two arms (the write-up must repeat this list)

| | agent-memory | MemCore |
|---|---|---|
| write discipline | `prompts.WRITE_DISCIPLINE` in the experience prompt | its `skill.md` as system prompt; discipline slot empty |
| record command | `mem record` (+ `--batch`) | `memcore create <name> <<'EOF'` |
| exam preamble | `prompts.exam` (mem context / recall / read, `--deep`) | a parallel preamble naming `memcore recall / search / get` |
| session-start injection | MEMORY.md byte prefix | `memcore recall --top-k 7` (what its hook injects) |
| raw material | transcript archived, reachable via `--deep` | none — MemCore keeps no transcript |
| retrieval | BM25 + graph, harness config | BGE-small embedding + graph + weight |

Shared: the boundary framing and the distill task text (what stays true, carry specifics
verbatim), host, model, turn budgets, episodes, judge, exam prompt shell.

## Environment notes

- MemCore binary is built from the local checkout with `--features embedding`. On glibc 2.39
  its `__libc_single_threaded` shim is a read-only static that glibc writes to at thread
  start, so the unpatched binary segfaults on every command; the build used here makes that
  static writable (one-line change, no behaviour change). Recorded in the write-up.
- `MEMCORE_HOME` names the checkout (binary under `target/release/`, `SKILL.md`, `models/`).
  Each per-episode store gets its own memcore directory with `models/` symlinked in, and the
  daemon is stopped after each phase so 120 daemons never hold 120 copies of the model.
