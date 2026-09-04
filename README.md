<div align="center">

### agent-memory: the long-term memory runtime for AI agents

<a href="docs/design/index.md">Design</a> · <a href="CLAUDE.md">Invariants</a> · <a href="experiments/results/index.md">Experiments</a> · <a href="docs/testing.md">Testing</a> · <a href="https://github.com/tigerless-labs/agent-memory/issues">Issues</a>

![](https://img.shields.io/badge/version-0.1.0-369eff?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/python-3.12+-ffcb47?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/hosts-Claude%20Code%2C%20Codex%20CLI-ff80eb?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/dependencies-zero%20API%20keys-c4f042?labelColor=black&style=flat-square)

</div>

***

## What is agent-memory

agent-memory is a local-first, agent-agnostic long-term memory runtime. Memories are plain
markdown files in one store — the single source of truth — and the SQLite index beside them is
a cache you can delete at any time. Writes are triggered at conversation boundaries, not at the
agent's discretion; an independent sleep-time Manage pass then consolidates, ages, and forgets
by value, while nothing it touches is destroyed. Claude Code, Codex CLI, and any agent that can
run a shell command share the same store.

## Why agent-memory

- **Files are the truth; every index is a rebuildable cache.** `rm -rf .index/ && mem rebuild`
  loses zero knowledge — enforced by a test, not promised in a doc. Your memory stays greppable,
  git-able, and portable off this system. → [Storage](docs/design/domains/storage.md) ·
  [ADR-001](docs/design/decisions/adr-001-file-truth.md)
- **A real Manage layer, on its own clock.** Sleep-time consolidation with authority tiers:
  an unattended pass may add and update, deletion only ever arrives as a proposal you confirm.
  Every competitor either has no M, or buries it in the write path. →
  [Manage](docs/design/domains/manage.md)
- **Updating never destroys.** Supersede leaves the chain intact, `recall --as-of` answers as of
  a date, and `archive/` keeps the raw material append-only — so "missed by the distiller" never
  means "lost by the system". → [Storage](docs/design/domains/storage.md)
- **No LLM client inside the library.** Zero keys to install and no billing surface: judgement is
  borrowed from the host agent's own CLI, which keeps every write visible in your transcript. →
  [ADR-002](docs/design/decisions/adr-002-no-llm-in-core.md)
- **Three read tracks, so a miss on one is not a miss.** Deterministic `MEMORY.md` injection at
  session start, BM25 recall with progressive disclosure, and the plain directory tree reachable
  with `ls` and `grep`. → [Recall](docs/design/domains/recall.md)
- **One write path, one answer per door.** Agent writes and Manage rewrites both go through
  validate → hash-diff → reindex, and CLI, MCP, and hooks carry zero algorithm between them. →
  [Architecture](docs/design/architecture/overview.md)

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
host, one calibrated Sonnet 5 judge, two exam replays per arm. Protocol, every known difference
between the arms, and the noise floor that decides what counts as a result are in
[docs/experiments.md](docs/experiments.md); the full ledger is
[experiments/results/](experiments/results/index.md).

| arm | pooled accuracy | paired vs agent-memory |
|---|---|---|
| agent-memory W2 | **127/240 = 52.9%** | — |
| [MemCore](experiments/results/p10-memcore.md) W2 | 86/240 = 35.8% | +37/−17, p=0.009 · +35/−14, p=0.004 |
| no memory | 7/120 = 5.8% | +61/−4 · +60/−4, p<0.001 |

Absolute numbers are not comparable to published LongMemEval scores — the haystack is bounded
to 12 sessions per episode, which makes this a write-strategy study rather than a corpus-size
one. The system-to-system row differs in write and read together, so it is an end-to-end
comparison and licenses no attribution to either half.

**One store, three hosts** ([P1](experiments/results/p1-generality.md)): all 9 ordered
writer/reader pairs across Claude Code, Codex CLI, and Hermes pass — what one host's shell
writes, another's finds, specifics intact. Pooled net contribution over no memory:
2/36 → 13/36, p=0.0074.

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
fallback. → [CLI](docs/design/api/cli.md) · [MCP](docs/design/api/mcp.md) ·
[Hooks](docs/design/api/hooks.md)

## Let it sleep

```bash
uv run mem sleep --reason host   # consolidate; T0 applies, T1 files a proposal
uv run mem proposals             # what is waiting on you
uv run mem decide <id> --accept
```

Manage borrows its reasoning from the host CLI you point it at, writes a dream report for the
pass, and cannot delete anything unattended. → [Manage](docs/design/domains/manage.md)

## Develop

```bash
uv run pytest -q && uv run ruff check . && uv run mypy
```

The task lifecycle, the invariants a change must not break, and the docs to read before
touching an area are in [CLAUDE.md](CLAUDE.md).
