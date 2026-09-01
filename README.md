# agent-memory

Agent-agnostic, local-first long-term memory runtime. Markdown files are the single source of
truth; the SQLite index is a rebuildable cache; writes are boundary-triggered; an independent
sleep-time Manage layer consolidates and forgets by value.

Design lives in [docs/design/](docs/design/index.md). Invariants and the task lifecycle live in
[CLAUDE.md](CLAUDE.md).

## Install

```bash
uv sync --all-packages
```

## Use

```bash
export AGENT_MEMORY_STORE=~/agent-memory-store
uv run mem init
uv run mem record --domain project --type decision \
  --abstract "Markdown files are the single source of truth" \
  --body "Indexes are rebuildable caches."
uv run mem recall "source of truth" --json
```

`rm -rf $AGENT_MEMORY_STORE/.index && uv run mem rebuild` must lose zero knowledge — that is a
test, not a promise.

## Develop

```bash
uv run pytest -q && uv run ruff check . && uv run mypy
```
