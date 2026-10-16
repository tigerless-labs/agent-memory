<div align="center">

### agent-memory: the long-term memory runtime for AI agents

<a href="CLAUDE.md">Invariants</a> · <a href="skills/agent-memory/SKILL.md">Skill</a> · <a href="https://github.com/tigerless-labs/agent-memory/issues">Issues</a>

![](https://img.shields.io/badge/version-0.1.0-369eff?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/python-3.12+-ffcb47?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/hosts-Claude%20Code%2C%20Codex%20CLI%2C%20Muse%20Code-ff80eb?labelColor=black&style=flat-square)
![](https://img.shields.io/badge/dependencies-zero%20API%20keys-c4f042?labelColor=black&style=flat-square)

</div>

***

An agent that closes its session forgets everything it learned in it. agent-memory is the
runtime that fixes that, for any agent — not only coding ones. Markdown files in one store are
the single source of truth, the SQLite index beside them is a cache you can delete at any time,
and Claude Code, Codex CLI, Muse Code, and anything else that can run a shell command share
that store.

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
mem recall "why files instead of a database" --limit 20  # more Memory candidates
mem read <name> --level outline                 # headings only; or abstract, or full
mem context "why files instead of a database"   # both in one call, top few expanded in full
mem trace <name>                                 # cited raw messages, when needed
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

One memory is one file. `valid_from` and optional `invalid_at` define its validity interval;
replaced and deleted files stay in the store for `recall --as-of` and trace. Current recall,
MEMORY.md, BM25, and Vector use files without `invalid_at`. Frontmatter carries the stable
name, a one-sentence abstract, the type and its schema fields, timestamps, links, weight,
and provenance; the body is free markdown. Existing files with `status` load without a reset.

Explicit links must name distinct active memories in the same store. `correct --link`
replaces the full list; `correct --clear-links` removes every link. MCP `memory_correct`
uses `links: [...]` and `links: []` for the same operations. Omitting links preserves
historical relationships during unrelated correction. See the
[operation boundary design](docs/design/management-operation-boundaries.md).

Agents can use `mem correct <name>` to revise a memory, `mem record --supersedes <old>`
to create a successor, `mem supersede <old> <new>` to use an existing successor,
`mem merge <first> <second> --abstract ... --body ...` to combine memories atomically,
and `mem delete <name>` to end current validity. Splitting uses new `record` calls
followed by `delete` of the original. Core checks file scope, relationships, provenance,
and concurrent writes; Sleep keeps its proposal and cap limits for unattended actions.

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
reaches them; put the directory on your `PATH` so your shell can too:

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
mem setup --host claude-code
mem setup --host codex
mem setup --host muse-code --provider openrouter
```

All three commands use the same pipeline: probe the host, initialize or check the Store, safely
merge host settings, install lifecycle hooks and the skill, perform provider-specific setup,
then run preflight. A successful command ends with `status: READY`; a written configuration is
not by itself considered ready. Re-running setup is safe and does not duplicate managed hooks,
skills, provider routing, or MCP entries. Existing unrelated host settings are retained, and a
conflicting setting fails closed instead of being replaced.

Use a non-default Store in the usual way; setup pins its absolute path into every installed hook:

```bash
AGENT_MEMORY_STORE=/absolute/path/to/store mem setup --host codex
```

Run the same checks later, or get a precise failure layer after setup fails:

```bash
mem doctor --host claude-code
mem doctor --host codex
mem doctor --host muse-code --provider openrouter
```

Diagnostics distinguish host/config/Store/hook/reasoner failures and, for Muse, credential,
proxy, authentication, model-catalog, model-availability, and live-request failures. Codex also
reports disabled hooks, a read-only default sandbox, and the one-time hook trust review. Codex
user hooks remain subject to Codex's trust prompt. Setup and doctor perform a minimal live
reasoner request by default; `--no-live` is available for offline inspection but deliberately
reports `FAILED` because readiness was not proven.

When the Store is outside the Codex workspace, SessionStart injection and boundary hooks still
run, but agent-initiated CLI recall needs write access for the Store access log. Doctor reports
`CODEX_STORE_ACCESS_REVIEW` until the Store is covered by
`sandbox_workspace_write.writable_roots`, or Codex is launched with `--add-dir <store>`.
Setup does not silently expand sandbox permissions.

Pass `--mcp` to setup when the host should also receive the `agent-memory` stdio MCP server.
Agents that speak MCP get the same core calls through `mem-mcp` (`memory_recall`,
`memory_read`, `memory_trace`, `memory_record`, `memory_correct`, `memory_supersede`,
`memory_merge`, `memory_delete`, `memory_feedback`). Anything that can run a
shell command needs neither: the CLI is the universal fallback, and it is the wider surface —
`context`, `sleep`, and the proposal ledger have no MCP tool yet.
Codex keeps its normal MCP approval boundary; the first tool call can still require explicit
user approval even after setup has configured and verified the server.

SessionStart injects, Stop and SessionEnd distil where supported, and PreCompact evicts.
By default, Write reasons through the host that produced the source session while Manage uses
the Store's legacy `[executor]` policy. They can be configured independently without changing
which source session is archived or cited:

```toml
[executor.write]
reasoner = "host"
host = "muse-code" # or "source", "hermes", "codex", or "claude-code"
host_provider = "" # Hermes can pin "openrouter" independently of its model
tool_mode = "auto" # supported Hosts use native tools; use "text" for compatibility

[executor.manage]
reasoner = "host"
host = "codex"
```

For `mem distill` and `mem sleep`, `--reason`, `--reason-host`, and `--reason-model` override the
corresponding operation policy. Operation policy overrides legacy `[executor]` values. Hooks pass
the producing host only as `--source-host`, so it supplies the default or resolves `host =
"source"` but never replaces an explicit Write host. A headless reasoner carries an executor
marker that prevents recursive capture.

Write runs the reasoner as a standard tool-use agent over one toolkit — `recall`, `read`, and
`submit_operations`. An endpoint reasoner drives that loop through native function calling.
Claude Code, Codex, Hermes, and Muse Code run their own loop in one headless process per batch by
default: the toolkit is served by a per-batch stdio MCP server, their built-in tools, user
configuration and native memory are off, and the distillation instructions replace their system
prompt where the Host supports replacement. Hermes and Muse use one combined prompt file and an
isolated process with only that batch's MCP `recall`, `read`, and `submit_operations` tools. Muse native
mode requires Muse Code 1.4.4 or newer, caps a run at eight model steps, and fails explicitly on
older versions; it never falls back to text. When Muse is routed through the supported local
pproxy bridge, a scoped loopback
adapter expands Responses API namespace tools to Muse's canonical MCP ids; it neither executes
tools nor holds credentials. Hermes uses a temporary profile, an exact dynamic MCP toolset,
and a provider selected independently of the model; OpenRouter therefore needs no Vertex project
or gcloud authentication. `tool_mode = "text"` forces the compatibility protocol for a Host. A run that ends
without an accepted submission writes nothing and leaves the backlog for retry. `tool_mode`
applies only to Write Host reasoners; endpoint Write remains native function calling and Manage
review remains the bounded text-verdict path.

Either operation can select its own model endpoint by setting `reasoner = "endpoint"` and the
usual `model`, `endpoint`, `project`, `location`, or `timeout_seconds` values in that operation's
table. Unset operation values inherit the legacy `[executor]` value, preserving existing Store
configuration. Endpoint use is opt-in and never carries a Tigerless project or credential. A
failed selected host, credential, request, or endpoint response never switches transport; Write
leaves the original archived backlog eligible for retry. Detached boundary failures are recorded
in the Store's `.state/hooks.log`.

After a boundary Distillation catches up, the same short-lived process checks whether Manage is
due. It counts distinct completed sessions, waits for all captured Write work to settle, claims the
Dream once across Hosts, and starts a detached one-shot worker using the configured Manage
reasoner. The source Host never overrides `[executor.manage]`. The worker enters the same
`Manage.sleep()` T0/T1 pipeline as manual sleep, writes the normal Dream report and decision
ledger, then exits. Repeated Stop, SessionEnd, or PreCompact events do not inflate progress or
duplicate the Dream. Inspect an active claim or failure with `mem --json dream-status`; a later
lifecycle event retries failed or stale work. Manual `mem sleep` remains available and always
runs when explicitly requested.

Automatic Dreaming is enabled by `manage.auto_dream` and can be rolled back by setting it to
`false`. `manage.claim_lease_seconds` controls crash-recovery eligibility. Default setup installs
no timer or resident Memory process: if every Host is inactive when the time threshold passes,
work runs only after the next SessionStart or boundary event. An explicitly installed user cron
entry can provide an independent wall-clock wake-up.

An external scheduler can supply that optional wake-up without running a Memory Backend. The
due-aware command derives new completed sessions and elapsed time from Store state; it does not
accept a caller-provided session count:

```bash
# Install the default hourly check for one initialized Store.
mem --store /absolute/path/to/store --json cron install \
  --mem-path /absolute/path/to/mem

# Or check every 15 minutes. Repeating install updates the same Store entry.
mem --store /absolute/path/to/store --json cron install \
  --interval-minutes 15 --mem-path /absolute/path/to/mem

# If the configured Reasoner needs environment-only settings, source a private file.
chmod 600 /absolute/path/to/reasoner.env
mem --store /absolute/path/to/store --json cron install \
  --mem-path /absolute/path/to/mem --env-file /absolute/path/to/reasoner.env

# Inspect the managed entry and whether cron is running, then remove only this Store's entry.
mem --store /absolute/path/to/store --json cron status
mem --store /absolute/path/to/store --json cron remove
```

The installer writes one Store-identified block to the current user's crontab and preserves all
unrelated entries. It records absolute Store and `mem` paths, `HOME`, and `PATH`, quotes spaces and
cron-special percent characters, and appends output to `STORE/.state/cron.log` by default. It does
not copy secrets into the crontab: Codex and Muse should use their normal files under `HOME`;
environment-only proxy or endpoint settings can come from an explicit mode-600 `--env-file`, whose
contents are never included in CLI diagnostics. On WSL, status
warns when the distribution's cron service is not running. Unsupported systems report that
`crontab` is unavailable instead of pretending scheduling is active.

A not-due invocation returns `status: skipped` and creates no report. Hook and cron triggers share
the Store claim/lease, maintenance locks, reasoner selection, and `Manage.sleep()` runner, so a
concurrent wake-up can produce only one effective Dream. The check interval is only a wake-up
frequency: a Dream still requires the configured elapsed-time and completed-session thresholds.
Installing, updating, or removing cron never disables lifecycle Hook triggering.

To use Vertex AI, enable it in a Google Cloud project you control, grant the calling identity
prediction access, authenticate the `gcloud` CLI, and configure that project explicitly:

```toml
[executor]
reasoner = "endpoint"
project = "your-google-cloud-project"
location = "global"
model = "google/gemini-3.7-flash"
```

The legacy form above continues to apply to both operations unless an operation table overrides
it. Put the same endpoint fields under `[executor.write]` or `[executor.manage]` to scope them.
`mem setup` and `mem doctor` report configuration and live-preflight results separately as Write
and Manage reasoner checks.

`GOOGLE_CLOUD_PROJECT` and `VERTEX_LOCATION` override the Store values. Alternatively, an
OpenAI-compatible endpoint can be selected with `endpoint` and a `GEMINI_API_KEY` supplied in
the environment. Store configuration contains no secret, and service-account keys must not be
committed to the repository.

### Hermes Agent

Hermes native Write requires Hermes Agent 0.22.2 or newer. Hermes may still use Gemini/Vertex,
but it is not coupled to it. To run Hermes through OpenRouter without gcloud, export the key and
pin the provider and model in the Write policy:

```bash
export OPENROUTER_API_KEY="..."
```

```toml
[executor.write]
reasoner = "host"
host = "hermes"
host_provider = "openrouter"
host_model = "meta/muse-spark-1.3-contributor"
host_allow_data_training = true # required explicit consent for contributor-tier data use
tool_mode = "auto"
```

Each batch gets a fresh Hermes profile containing only an `agent-memory-write` stdio MCP server.
The exact toolset prevents Shell, Web, Hermes memory, skills, delegation, plugins, and personal
MCP servers from entering the run. Secrets remain in the process environment and are never
written to the temporary profile. `tool_mode = "text"` explicitly retains the compatibility
loop; native failures never switch to it automatically.

The contributor model permits Meta to use prompts and completions for training. Memory refuses
Hermes' unattended contributor route unless `host_allow_data_training = true` is explicitly set;
use the non-contributor model for sensitive or proprietary sessions.

### Muse Code

Install [Muse Code](https://dev.meta.ai/docs/muse-code), make sure `muse` is on `PATH`, and make
an OpenRouter credential available either as `OPENROUTER_API_KEY` or in Muse's credential store.
Setup recognizes an already provisioned credential and never prints or replaces it:

```bash
export OPENROUTER_API_KEY="..."  # omit when Muse auth is already provisioned
mem setup --host muse-code --provider openrouter
muse
```

The provider step configures Muse's `meta` transport to the local pproxy bridge, selects the
Muse model, starts or reuses pproxy, validates OpenRouter authentication and model availability,
then asks Muse to complete a minimal real request. It merges `SessionStart`, `PreCompact`,
`Stop`, and `SessionEnd` into `$XDG_CONFIG_HOME/muse/settings.json` (or
`~/.config/muse/settings.json`) without replacing unrelated settings. Managed hooks pin that
exact settings path as well as the Store and Muse data directory, so background distillation
does not depend on Muse preserving the launching shell's XDG environment.

pproxy remains a separate, pinned external dependency. Setup never silently installs system
software. If it is missing, the FAILED report prints the exact `uv tool install` command; run it
and repeat setup. pproxy is launched as a user process and recorded under
`$XDG_STATE_HOME/agent-memory` (or `~/.local/state/agent-memory`). After a reboot, repeat setup
or run doctor if the proxy is no longer reachable. Use `--mcp` to merge the MCP server too:

```bash
mem setup --host muse-code --provider openrouter --mcp
```

Muse native memory and agent-memory's `AGENT_MEMORY_STORE` are separate systems. Setup does not
read, write, copy, or synchronize Muse native memory. For attributable experiments, use a clean
workspace with no `.agents/memory` content and isolated `HOME`, `XDG_CONFIG_HOME`, and
`XDG_DATA_HOME`; the included `tools/muse_sandbox_probe.py` does this while reusing only the
explicit Muse auth file.

Muse's default sandbox can read outside the workspace but writes only to the workspace and temp
directories. Muse documents user hooks as outside the agent shell sandbox and MCP servers as
external processes; use the included live preflight to verify both write paths on your Muse
build before relying on the default external `~/agent-memory-store`. A Muse shell command such
as `mem --json recall ...` can read it, but `mem record` from the shell cannot write it.
The experiment adapter keeps the sandbox enabled and roots its temporary Store and workdir under
one explicit experiment workspace. It never adds `--yolo` or `--disable-sandbox`.

```bash
AGENT_MEMORY_LIVE_MUSE=1 uv run python tools/muse_sandbox_probe.py
```

Start with the three ordered portability mechanics before a full four-host matrix:

```bash
mem-exp interop --workspace /tmp/muse-memory-smoke \
  --pairs muse-code:muse-code,muse-code:codex,codex:muse-code
```

Then omit `--pairs` and pass `--hosts claude-code,codex,hermes,muse-code` for the 4×4 matrix.
Current limitations: only the root Muse session log is captured; child/observer logs are ignored,
setup installs MCP only when `--mcp` is requested, and live hook/MCP/sandbox behavior must be
verified on a machine with Muse Code installed and authenticated. Muse 1.4.3 does not support the
exact `run.toolset` MCP selection required by native Write mode. Muse 1.4.9 plus OpenRouter emits
Responses namespace calls as a namespace and child name while Muse dispatches canonical flat MCP
ids; native Write bridges that local pproxy transport for the duration of the run. The live matrix
is opt-in with `AGENT_MEMORY_LIVE_MUSE_NATIVE=1`, selects Muse through the default `auto` posture,
and covers New, Recall/Read/Supersede, Skip, and tool-error observation. Lifecycle hooks and
SessionStart injection do not depend on native Write.
Echo or mocked providers do not count as live E2E evidence.

## Let it sleep

```bash
mem sleep                 # host-backed consolidation; T0 applies, T1 files a proposal
mem sleep --if-due        # persisted thresholds; skip normally when not due
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

## Optional vector recall index

BM25 is the low-latency baseline retrieval path. Install `agent-memory-core[vector]` (or run
`uv sync --extra vector` from this workspace), then set `vector_enabled = true`
in the store's `[index]` configuration. `vector_model` defaults to
`BAAI/bge-small-en-v1.5`. The first enabled Store loads FastEmbed/ONNX and may
need network access to download the model; disabled stores never load FastEmbed.
Set `AGENT_MEMORY_OFFLINE=1` to load strictly from the FastEmbed cache
(`FASTEMBED_CACHE_PATH`, default `~/.cache/fastembed_cache` on most systems) —
useful for air-gapped hosts or caches populated from a mirror.

Run `mem --store /path/to/store rebuild` to rebuild the SQLite cache from Markdown.
The existing indexing path catches changed and deleted files, enabling vectors
on an existing store, and changes to `vector_model`. Recall fuses BM25 and vector
chunk candidates with reciprocal-rank fusion, then applies the existing lifecycle,
scope, as-of, weight and recency rules. Raw sessions are retained for audit and
provenance-bound trace; they do not enter Recall ranking. Recall never modifies Markdown truth.

This implements the existing optional-index design (ADR-003), using SQLite and
exact cosine search. On the fixed 120-query retrieval acceptance set, optional
vector fusion improved Recall@5 from 79.0% to 86.6% (+7.6 percentage points),
while median retrieval latency increased from 5.1ms to 139.2ms. This establishes
a retrieval-coverage/latency trade-off. Fixed-context answer replays scored
17/24 versus 18/24 and, on the expanded set, 28/36 versus 27/36. The existing
answer-level experiments do not establish an end-to-end accuracy improvement,
so vector retrieval remains optional.

## CJK (Chinese) memory

The default tokenizer extracts ASCII literals only, and the FTS5 unicode61
tokenizer keeps an unsegmented CJK run as one token, so a Chinese query matches
nothing a Chinese body wrote. Install `agent-memory-core[cjk]` (or run
`uv sync --extra cjk` from this workspace) and set `tokenizer = "cjk"` in the
store's `[index]` configuration:

```toml
[index]
tokenizer = "cjk"
vector_enabled = true
vector_model = "BAAI/bge-small-zh-v1.5"
```

`cjk` segments chunk text with jieba before it enters the FTS5 projection and
adds CJK words (two or more characters) to the query expression; ASCII literals
keep their current behavior. Headings stay untouched — they are read back from
the surface. The tokenizer the projection was built with is recorded in
`index_meta`; changing it is detected on the next sync and the whole projection
rebuilds, so no stale FTS rows survive a switch. For paraphrased Chinese queries
that share no surface tokens with the memory, pair the tokenizer with the
optional vector index and a Chinese-capable model such as
`BAAI/bge-small-zh-v1.5`. On a 5-memory / 10-query Chinese check, ASCII-only
recall answered 2/10, the cjk tokenizer 9/10, and cjk plus Chinese vectors
10/10.

## Explicit raw evidence reads

`mem --json read <name>` includes a memory's provenance. To inspect a cited raw
message range, call `mem --json trace <name> --pointer 'sessions/<session>#<start>-<end>'`.
The pointer can select a smaller range within one citation; omitting it reads all
sources cited by the memory. Trace reports source, original message indices, roles,
times, validity, and a warning that historical content is data. Missing or unbound
evidence fails explicitly. Ordinary `context` and `recall` search Memory only; an agent
can increase `--limit` or reformulate its query before tracing a selected memory.

## Read evaluation with Codex

The experiment runner selects the tested host and judge independently. Pass
`--host codex --judge-host codex` and explicit `--model` / `--judge-model` values
for a Codex-only run. Omitting `--judge-host` retains the Claude Code judge and
its historical default model. `calibrate` and `regrade` also accept `--judge-host`.
Use `calibrate --cases <labelled-cases.json> --output <calibration.json>` to retain
individual votes and distinguish transport failures from label disagreements.

`run --observe-reads` retains bounded exam host output and CLI/read evidence in
`observations/`, outside store truth. Observation is off by default; missing or
truncated evidence is not proof of no tool calls. `run.json` fixes both host/model
pairs, configuration, source stores, code revision and episode identity. Replay
with `--reuse-stores` and a separate workspace for each configuration. Small panels
check execution and exploratory behavior, not a statistically established improvement.
Before scaling a read-side comparison, check that each copied store has a populated
Memory index and that a known query returns hits. Then run a small observed
agentic pilot and count *successful, nonempty* retrievals for each arm's intended
path (for example, vector candidates or bound Trace messages).
An enabled setting, a prompt instruction, or a tool call with zero hits does not
show that the intervention was used. Stop when the pilot does not exercise both
paths; report the exposure rate alongside scores when it does. Codex can also
read store files directly through its shell, so check the host command transcript
for bypasses before attributing an answer to a `mem` retrieval path.

## License

[MIT](LICENSE).
