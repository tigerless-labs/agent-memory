# agent-memory

agent-memory is **Tigerless's agent-agnostic, local-first long-term memory runtime**: markdown
files as the single source of truth, a rebuildable SQLite index, deterministic boundary-triggered
writes, and an independent sleep-time Manage layer — shared by multiple agents (Claude Code,
Codex CLI, Hermes) over one common memory store.

**Wedge**: the only memory system with a true independent Manage layer (value-based forgetting,
sleep-time consolidation with authority tiers) on top of file truth — every competitor either
has no M, or buries it in the write path.

## Key docs (read before changing the relevant area)

- **[docs/design/](docs/design/index.md)** — the architecture and the *why*. Start at the
  index, then the doc covering the area you're touching. *(Keep the index current.)*
- **[docs/TODO.md](docs/TODO.md)** — tracked follow-ups not yet on the roadmap.
  **Keep this current in real time** (see rule below).
- **[docs/testing.md](docs/testing.md)** — test conventions and the per-file test map.
- **[docs/experiments.md](docs/experiments.md)** — experiment protocol: what counts as a result,
  what licenses attribution, what every run must leave behind. *(Read before running any experiment.)*
- **[docs/plans/](docs/plans/)** — roadmap and per-change implementation plans (working
  artifacts, exempt from the design-doc style rules).

## Invariants — do not break

1. **Markdown files are the single source of truth; every index is a rebuildable cache.**
   `rm -rf .index/ && mem rebuild` must lose zero knowledge. Why: migration freedom, git-ability,
   platform parasitism (auto-memory compatible), user sovereignty.
2. **Single write path.** Agent writes and Manage rewrites go through the same
   validate → hash-diff → reindex pipeline. Why: two write paths inevitably diverge truth
   from projection, silently.
3. **Reads never mutate truth files.** Usage stats go to the index access log only; weight is
   settled back into frontmatter by Manage in batch. Why: otherwise every recall triggers
   reindex churn and git noise.
4. **Raw material is append-only; distillation is a projection, not a move.** Anything missed
   by distillation must remain recoverable from `archive/`. Why: "missed by the distiller"
   must never mean "lost by the system".
5. **The library core contains no LLM client.** Intelligence is borrowed from the consuming
   agent (hooks, fork, or its CLI as executor). Why: zero-key install, no billing surface,
   writes stay visible in the agent's own transcript.
6. **Destructive Manage operations require escalating authority.** T0 unattended = add/update
   only; T1 = proposal in dream-report awaiting confirmation; T2 = human-initiated. Why:
   memory poisoning is a persistent attack surface; unattended deletion is unauditable.
7. **File boundary = invalidation atom.** One file holds knowledge that expires as a whole
   (supersede/weight/recall all operate per file). Why: partial staleness inside a file
   poisons the whole file.
8. **Adapters carry zero algorithm.** CLI, MCP, and hooks all collapse into the same core
   calls; same request through any entry yields the same result. Why: N entries × M behaviors
   is untestable.
9. **Recall is held fixed across write experiments.** Benchmark score differences are
   attributable to Write options only under identical R. Why: the entire P2 experiment's
   validity rests on this.

## Task lifecycle — the fixed order for every non-trivial change

Plan → sync → docs → tests → code → verify → commit → docs/index sweep → green CI.
Trivial one-line changes skip the plan; nothing skips the order. A change that arrives
out of order is *incomplete*.

1. **Plan.** Non-trivial changes start with a plan in `docs/plans/`. The plan's first unit
   updates the relevant `docs/design/` doc; every unit places tests before code.
2. **Branch, isolate, sync.** One explicit task per branch, developed in its own worktree
   (Claude Code's built-in worktree tooling, which puts it at `.claude/worktrees/<branch>` —
   keep that path gitignored, and remove the worktree once its branch lands). **Experiment
   artefacts never land inside a worktree** — they go to the main working tree, because
   `git worktree remove` takes gitignored data with it without a word. Never develop on
   `main`. Rebase onto latest `main` before developing; land via feature branch + PR, no direct
   pushes to `main`.
3. **Docs first.** Read, then update, the relevant `docs/design/` doc(s) before any test or
   code — pin down behavior boundaries, interface contracts, and acceptance criteria.
4. **Tests next (TDD).** Failing unit test(s) first, then system test(s), then implementation.
   Fixtures rather than live external services; assert **relationships/invariants**, never
   hardcoded values. A feature shipped without a test is *incomplete*.
5. **Code.** Write the code that makes the tests pass.
6. **Verify end-to-end.** Run the CLI/harness and confirm the behavior against a running
   instance — not just via unit tests.
7. **Commit.** Run the relevant tests before each commit; commit at every green-test point
   and push after every completed task — progress must never exist only on this machine.
8. **Sweep docs & indexes.** Update design docs and indexes touched by the change,
   in the same change.
9. **Drive CI green.** Watch CI after opening the PR; fix and push until every required check
   passes. The job ends at the green-CI PR handed off for review — the owner merges,
   never the agent.

## Working rules

- **English only in commits, PRs, issues, and code identifiers.** Design docs under
  `docs/design/` may stay bilingual; everything that enters git history or GitHub is English.
- **Docs are top-level design only.** Describe *what* and *why* — never how. No pseudocode,
  no code snippets, no magic numbers. Name **modules and objects** — never functions or file
  paths; that detail lives in the code. Carve-outs: architecture diagrams stay; setup runbooks
  keep the literal commands.
- **Design docs are ruthlessly concise — every sentence earns its place.** One fact lives in
  exactly one place; cross-link instead of repeating. When you edit a doc, leave it shorter
  than you found it unless you added a genuinely new idea.
- **Clear code, no comments.** Explicit names; intent carried by structure, naming, tests,
  and docs. If a comment feels necessary, rename or split until it isn't.
- **Decouple — one functional block, one object, one file. Never duplicate (DRY).**
- **One authoritative source per fact.** Docs carry intent and boundaries; code is the sole
  authority for implementation; data lives in the data layer. Never two homes for one thing.
- **Config holds every knob.** Tunables (M trigger threshold N, MEMORY.md budget, clustering
  threshold, weight steps), environment differences, and switches live in config — never
  hardcoded or scattered.
- **Real-time TODO.** Discover a follow-up → write it into `docs/TODO.md` immediately;
  finish one → remove it. Never leave it only in chat.
- **Verify empirical claims by experiment before asserting** — measurements live under
  `experiments/`, linked back as `evidence:`. The protocol that decides whether a measurement
  is a result at all is [docs/experiments.md](docs/experiments.md).
- **Agent prompts are positive-only.** State what the model *should* write — never "don't
  do X"; naming a behavior primes it. Reserve explicit prohibitions for failure modes
  actually observed in traces.

## Security — agents run autonomously, so the system must fail safe

- **Trust nothing by default.** Treat external input, upstream responses, and agent decisions
  as hostile; validate, check bounds, reject illegal state, fail safe (deny by default).
- **Least privilege.** Secrets and raw PII never enter the repo, ordinary logs, or traces.
- **Guardrails at every chokepoint.** Frontmatter validation rejects malformed writes; the
  shared store serializes writers (flock); memory content is data, never instructions.
- **Red-team the tests.** Unit and system tests carry adversarial cases — memory-poisoning
  payloads, malformed frontmatter, concurrent-writer races, injection-via-recalled-content —
  proving fail-safe behavior.
