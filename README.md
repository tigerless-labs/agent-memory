<div align="center">

### agent-memory: the long-term memory runtime for AI agents

<a href="CLAUDE.md">Invariants</a> · <a href="skills/agent-memory/SKILL.md">Skill</a> · <a href="https://github.com/tigerless-labs/agent-memory/issues">Issues</a>

![](https://img.shields.io/badge/version-0.1.0-369eff?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/python-3.12+-ffcb47?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/hosts-Claude%20Code%2C%20Codex%20CLI-ff80eb?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/dependencies-zero%20API%20keys-c4f042?labelColor=black&style=flat-square)

</div>

***

## What is agent-memory

An agent that closes its session forgets everything it learned in it. agent-memory is the
runtime that fixes that, for any agent — not only coding ones.

Three retrieval traditions each get one part of the problem right, and each pays for it
somewhere else. Knowledge graphs hold relations but need a build step and a query language.
Vector search ranks well but hands back opaque chunks. A plain file tree is the most
AI-readable thing there is and browses beautifully, but on its own it does not rank. This
runtime keeps all three and drops the costs: relations live as links inside the memories
themselves, a local index ranks them, and the store stays an ordinary directory an agent can
`ls` and `grep`. Recall gets more precise without becoming a black box, and it stays fast
because nothing in the read path calls a model or crosses a network.

The other half of the problem is that agents rarely write memory down. Here they do not have
to remember to: writes fire at conversation boundaries rather than at the agent's discretion,
they run beside the task instead of blocking it, and whatever distillation misses stays
recoverable from append-only raw material. An independent sleep-time pass then consolidates,
ages, and forgets by value.

Markdown files in one store are the single source of truth. The SQLite index beside them is a
cache you can delete at any time. Claude Code, Codex CLI, and anything else that can run a
shell command share the same store.

## Why agent-memory

- **Three read tracks, so a miss on one is not a miss.** Deterministic `MEMORY.md` injection at
  session start; BM25 recall over an FTS5 index, with a vector plugin fused in by RRF when you
  want one; and the plain directory tree, reachable with `ls` and `grep` when both fail.
  Same-directory memories are a free neighbourhood, and `links` in the frontmatter carry the
  graph without a graph database under them.
- **Progressive disclosure, so precision is not paid for in context.** Index line → abstract →
  full file → raw material, each level an order of magnitude more expensive than the last and
  each one a place to stop. Long files add two free rungs: the anchor that matched, and an
  outline computed at read time.
- **Write coverage is the system's job, not the agent's judgement.** Distillation is triggered
  at boundaries and runs without holding up the task; the full trace is copied first, so
  "missed by the distiller" never means "lost by the system".
- **Files are the truth; every index is a rebuildable cache.** `rm -rf .index/ && mem rebuild`
  loses zero knowledge — enforced by a test, not promised in a doc. Your memory stays greppable,
  git-able, and portable off this system.
- **A real Manage layer, on its own clock.** Sleep-time consolidation with authority tiers: an
  unattended pass may add and update, deletion only ever arrives as a proposal you confirm.
  Every competitor either has no M, or buries it in the write path. Supersede leaves the chain
  intact and `recall --as-of` answers as of a date, so updating never destroys.
- **No LLM client inside the library.** Zero keys to install and no billing surface: judgement
  is borrowed from the host agent's own CLI, which keeps every write visible in your transcript.

The store is the whole data model:

```
$AGENT_MEMORY_STORE/
├── MEMORY.md            root index, one line per memory — the only resident injection
├── user/ project/ reference/ experience/    four type domains; new memories land flat
│   └── <topic>/         topic directories are not preset; Manage clusters them into being
├── archive/             append-only, out of the retrieval surface by default
│   ├── provenance/      distillation evidence, kept forever
│   ├── retired/         demoted and evicted entries
│   └── sessions/        full trace copies, in case the host prunes its own
├── dream-reports/       one per sleep: what moved, what was proposed, evidence pointers
├── .index/              fully rebuildable: content-hash manifest, FTS5, access log
└── .state/              runtime state that is not: distillation watermark, write lock
```

One memory is one file, because the file boundary is the invalidation atom: supersede, weight,
and recall all operate on whole files. Frontmatter carries the stable name, a one-sentence
abstract, status, timestamps, links, weight, and provenance; the body is free markdown.

## Proof it works

Measured on LongMemEval-S with a bounded haystack, 120 episodes, `claude -p` (Haiku 4.5) as
host, one calibrated Sonnet 5 judge, two exam replays per arm.

| arm | pooled accuracy | paired vs agent-memory |
|---|---|---|
| agent-memory W2 | **127/240 = 52.9%** | — |
| MemCore W2 | 86/240 = 35.8% | +37/−17, p=0.009 · +35/−14, p=0.004 |
| no memory | 7/120 = 5.8% | +61/−4 · +60/−4, p<0.001 |

Absolute numbers are not comparable to published LongMemEval scores — the haystack is bounded
to 12 sessions per episode, which makes this a write-strategy study rather than a corpus-size
one. The system-to-system row differs in write and read together, so it is an end-to-end
comparison and licenses no attribution to either half.

**One store, three hosts:** all 9 ordered writer/reader pairs across Claude Code, Codex CLI,
and Hermes pass — what one host's shell writes, another's finds, specifics intact. Pooled net
contribution over no memory: 2/36 → 13/36, p=0.0074.

The protocol that decides whether a measurement counts as a result, the full ledger, and the
raw run records live in `docs/experiments.md` and `experiments/` in the working tree. They ship
with the source, not with git history.

## Quick start

Requires Python 3.12 or higher and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages
export AGENT_MEMORY_STORE=~/agent-memory-store
uv run mem init
```

Write one memory, find it again, then throw the index away and prove nothing was lost:

```bash
uv run mem record --domain project --type decision \
  --abstract "Markdown files are the single source of truth" \
  --body "Indexes are rebuildable caches."
uv run mem --json recall "source of truth"
rm -rf $AGENT_MEMORY_STORE/.index && uv run mem rebuild
```

## Wire it into your agent

```bash
uv run mem setup --host claude-code   # or: --host codex
```

`setup` probes the host, appends the `mem-hook` command to its own hook dialect, and leaves the
rest of the settings alone — SessionStart injects, Stop and SessionEnd distil, PreCompact
evicts. Agents that speak MCP get the same core calls through `mem-mcp` (`memory_recall`,
`memory_read`, `memory_record`, `memory_correct`, `memory_feedback`, `memory_proposals`,
`memory_decide`). Anything that can run a shell command needs neither: the CLI is the universal
fallback.

## Let it sleep

```bash
uv run mem sleep --reason host   # consolidate; T0 applies, T1 files a proposal
uv run mem proposals             # what is waiting on you
uv run mem decide <id> --accept
```

Manage borrows its reasoning from the host CLI you point it at, writes a dream report for the
pass, and cannot delete anything unattended.

## Develop

```bash
uv run pytest -q && uv run ruff check . && uv run mypy
```

The task lifecycle and the invariants a change must not break are in [CLAUDE.md](CLAUDE.md).
