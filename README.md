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

## Optional local navigation

After recall finds a memory, Virtual Topic Overview (Virtual L1) lets an agent inspect
nearby abstracts before choosing a full read:

```bash
uv run mem --json overview switch-to-uv --limit 8
uv run mem read ci-change
```

`overview` lists the seed, memories in its exact physical topic directory, then its outgoing
explicit links. It does not expand a flat domain root, recurse, or open neighbor bodies/raw.
The view is generated from current files without an LLM, embeddings, a cache, or a new summary
Memory. Ordinary recall, read, context, and default host prompts remain unchanged.

The seed counts toward `--limit` (default: `recall.default_limit`, 8); abstracts use the existing
length cap. Results carry relation, path, status and updated time, with deterministic ordering
and a `truncated` flag. `--scope` and `--as-of` reuse Recall's eligibility rules; retired and
archived entries are excluded, superseded entries are excluded by default, and an ineligible
seed produces an error. Historical views are explicitly labeled by `as_of`.

Limits: this is physical directory navigation, not semantic topic discovery or a full virtual
memory topology. There is no reverse-link/supersede traversal, query ranking, or deep mode.
As-of uses current metadata and successor validity, not historical file snapshots; scope
retains Recall's string-prefix semantics. Each call scans and parses all Memory files
(including archived successor metadata), but returns only bounded metadata. This trades scan
cost for immediate visibility of external edits without index synchronization. Fixture tests
verify navigation mechanics; no benchmark accuracy improvement is claimed.

### O1 host policy (explicit opt-in)

On this branch only, `--set recall.overview_enabled=true` enables a fixed **agentic**
exam instruction for both Codex and Claude Code: one ordinary recall (limit 1), one
Overview of its first hit (limit 8), then full reads of the first four returned entries
in their listed order. No second seed, recursive expansion, context call or raw fallback
is requested. No hit/ineligible seed means insufficient evidence. The switch defaults
to false; default Recall/Read and prompts stay equivalent to the common baseline.

```sh
mem-exp run --suite /absolute/path/fixture.json --workspace /absolute/path/o1-smoke \
  --arms W1 --per-type 1 --concurrency 1 --exam-mode agentic \
  --host codex --judge-host codex --model gpt-5.6-sol --judge-model gpt-5.6-sol \
  --set recall.overview_enabled=true
```

Use `--exam-mode agentic` for O1; fixed mode uses the original context builder and
cannot exercise this host instruction. For paired read experiments, reuse disposable
copies of the same frozen input stores and hold host/model and judge host/model fixed.
The run config records the switch. In agentic reuse runs, the copied store's config must
match the relevant CLI `--set` values: child `mem` processes read that config on disk.

This is a fixed instruction policy, not a forced tool executor. Check actual tool calls
in mechanics smoke before formal runs. Existing Observation fields remain unchanged;
Overview itself is not counted as a full read and has no new observation field.

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

## License

[MIT](LICENSE).
