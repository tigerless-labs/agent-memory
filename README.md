<div align="center">

### agent-memory: the long-term memory runtime for AI agents

<a href="CLAUDE.md">Invariants</a> · <a href="skills/agent-memory/SKILL.md">Skill</a> · <a href="https://github.com/tigerless-labs/agent-memory/issues">Issues</a>

![](https://img.shields.io/badge/version-0.1.0-369eff?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/python-3.12+-ffcb47?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/hosts-Claude%20Code%2C%20Codex%20CLI-ff80eb?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/dependencies-zero%20API%20keys-c4f042?labelColor=black&style=flat-square)

</div>

***

An agent that closes its session forgets everything it learned in it. agent-memory is the
runtime that fixes that, for any agent — not only coding ones. Markdown files in one store are
the single source of truth, the SQLite index beside them is a cache you can delete at any time,
and Claude Code, Codex CLI, and anything else that can run a shell command share that store.

Retrieval is local and ranked, and it answers with paths rather than pasted text — the agent
opens each hit only as deep as the task needs. Writes do not wait for the agent to remember to
make them: they fire at conversation boundaries. A sleep-time pass then consolidates and
forgets by value, on its own clock. None of it needs an API key.

## Two lines, one store

Agent memory has grown along two architectural lines. One builds a **retrieval engine** —
embeddings, a knowledge graph, a ranking pipeline — which finds the right thing, but hands the
agent an opaque chunk it cannot inspect and a store it cannot migrate off. The other hands the
agent a **filesystem** — markdown it reads directly, browsable with `ls` and `grep` — which is
legible and costs nothing to run, but does not rank, and stops scaling the moment the tree
outgrows a listing.

agent-memory is the two of them in one store: the retrieval engine indexes a filesystem the
agent can also just read. Relations live as links inside the memories, a local index ranks
them, and every hit resolves to a whole markdown file on disk. Recall gains the precision of a
graph and a vector search without giving up a plain directory an agent can walk — and it stays
fast, because nothing in the read path calls a model or crosses a network.

## Retrieve by path, then read by level

Recall does not paste text into your context. It answers with an L0 list — one-line abstract,
file path, anchor, score — and the agent opens what it wants at the depth the task needs:

```bash
mem recall "why files instead of a database"    # L0 list, 8 entries by default
mem read <name> --level outline                 # headings only; or abstract, or full
mem context "why files instead of a database"   # both in one call, top few expanded in full
```

Index line → abstract → full file → raw material: each rung costs an order of magnitude more
than the last, and each is a place to stop. Long files add two free rungs — the anchor that
matched, and an outline computed at read time.

## Design commitments

- **Three read tracks, so a miss on one is not a miss.** Deterministic `MEMORY.md` injection at
  session start; BM25 recall over an FTS5 index, with a vector plugin fused in by RRF when you
  want one; and the plain directory tree, reachable with `ls` and `grep` when both fail.
  Same-directory memories are a free neighbourhood, and `links` in the frontmatter carry the
  graph without a graph database under them.
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

## The store

```
$AGENT_MEMORY_STORE/
├── MEMORY.md              root index, one line per memory — the only resident injection
├── config.toml            every tunable; an unknown knob is refused at load
├── schemas/               one file per type: its key fields, the field it groups by, write mode
├── decision/              memories live at <type>/<group>/<name>.md, placed by the schema
│   └── agent-memory/        …/markdown-files-are-the-single-source-of-truth.md
├── archive/               append-only, out of the retrieval surface by default
│   ├── provenance/        distillation evidence, kept forever
│   └── sessions/          full trace copies, in case the host prunes its own
├── dream-reports/         one per sleep: what moved, what was proposed, evidence pointers
├── .index/                fully rebuildable: content-hash manifest, FTS5, access log
└── .state/                runtime state that is not: distillation watermark, write lock
```

One memory is one file, because the file boundary is the invalidation atom: superseding, weight,
and recall all operate on whole files, and a file is either active or invalid with nothing in
between. Frontmatter carries the stable name, a one-sentence abstract, the type and its schema
fields, status, timestamps, links, weight, and provenance; the body is free markdown.

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

## Install

Requires Python 3.12 or higher and [uv](https://docs.astral.sh/uv/). There is no release on
PyPI yet, so install from a checkout:

```bash
git clone https://github.com/tigerless-labs/agent-memory.git
cd agent-memory
uv sync --all-packages
```

That builds `mem`, `mem-mcp`, and `mem-hook` into `.venv/bin`. Inside the checkout `uv run mem`
reaches them; put the directory on your `PATH` so your agents can too — the hook installed in
the next section is a bare `mem-hook` command, and a host that cannot resolve it records
nothing:

```bash
export PATH="$PWD/.venv/bin:$PATH"
```

## Quick start

```bash
mem init
```

The store defaults to `~/agent-memory-store`; export `AGENT_MEMORY_STORE` only to put it
somewhere else, and export it everywhere your agents run, not just in this shell.

Write one memory, find it again, then throw the index away and prove nothing was lost:

```bash
mem record --type decision --field project=agent-memory \
  --abstract "Markdown files are the single source of truth" \
  --body "Indexes are rebuildable caches."
mem --json recall "source of truth"
rm -rf ~/agent-memory-store/.index && mem rebuild
```

## Wire it into your agent

```bash
mem setup --host claude-code   # or: --host codex
```

`setup` probes the host, appends the `mem-hook` command to its own hook dialect, and leaves the
rest of the settings alone — SessionStart injects, Stop and SessionEnd distil, PreCompact
evicts. Agents that speak MCP get the same core calls through `mem-mcp` (`memory_recall`,
`memory_read`, `memory_record`, `memory_correct`, `memory_feedback`). Anything that can run a
shell command needs neither: the CLI is the universal fallback, and it is the wider surface —
`context`, `sleep`, and the proposal ledger have no MCP tool yet.

## Let it sleep

```bash
mem sleep --reason host   # consolidate; T0 applies, T1 files a proposal
mem proposals             # what is waiting on you
mem decide <id> --accept
```

Manage borrows its reasoning from the host CLI you point it at, writes a dream report for the
pass, and cannot delete anything unattended.

## Develop

```bash
uv run pytest -q && uv run ruff check . && uv run mypy
```

The task lifecycle and the invariants a change must not break are in [CLAUDE.md](CLAUDE.md).

### Optional vector recall index

BM25 remains the default. Install `agent-memory-core[vector]` (or run
`uv sync --extra vector` from this workspace), then set `vector_enabled = true`
in the store's `[index]` configuration. `vector_model` defaults to
`BAAI/bge-small-en-v1.5`. The first enabled Store load loads FastEmbed/ONNX and may
need network access to download the model; disabled stores never load FastEmbed.

Run `mem --store /path/to/store rebuild` to rebuild the SQLite cache from Markdown.
The existing indexing path catches changed and deleted files, enabling vectors
on an existing store, and changes to `vector_model`. Recall fuses BM25 and vector
chunk candidates with reciprocal-rank fusion, then applies the existing lifecycle,
scope, as-of, weight and recency rules. Raw session material stays BM25-only;
`--deep` preserves its evidence role. Recall never modifies Markdown truth.

This implements the existing optional-index design (ADR-003), using SQLite and
exact cosine search. Functional tests and a small embedding smoke are not a
benchmark or evidence of retrieval gains; vector ablation remains pending.

## License

[MIT](LICENSE).
