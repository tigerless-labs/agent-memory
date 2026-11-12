# Write negotiation

Write turns one archived batch into memory operations. The reasoner is a standard tool-using
agent: it decides what to look at, how often, and when it is done. The library supplies the tools,
validates what comes back, and owns every write.

## One toolkit

The Write toolkit is the only definition of what the reasoner may do during a batch:

- **recall** searches current memory and lists matches by handle;
- **read** opens one active memory in full;
- **submit operations** hands back the batch's operations under the operation schema.

A handle becomes nameable in update and supersede once the reconcile sheet or a tool result has
shown it; any other handle stays refused, so steering by conversation or recalled content can at
most produce a new file. A submission is checked against the reconcile sheet and then by the
Store's own write preparation, so the reasoner learns every refusal the write would raise inside
the same run; the latest accepted submission is the batch's answer. Tools never write the Store:
accepted operations reach it through the single write path, and only what a check cannot see —
siblings that collide with each other, or the Store changing underneath — falls to the repair
path.

The toolkit imposes no look budget or forced final turn. Request and process timeouts detect
transport failure. A Host may additionally impose a declared safety bound: Hermes and Muse native
Write allow eight model steps, then fail closed if no operation was accepted. Why: these are the
industry-standard mechanics of a tool-use agent, while a bounded third-party compatibility route
must not retry malformed calls indefinitely.

## Two transports

| Reasoner | Who runs the loop | How the tools arrive |
|---|---|---|
| Model endpoint | The executor | Native function calling over a structured message history |
| Monid | The executor | Line-oriented text through DataForSEO Claude responses |
| Claude Code, Codex | The host CLI, one headless run per batch | A per-batch stdio MCP adapter over the same toolkit |
| Hermes | The isolated host CLI, one headless run per batch | A whitelisted per-batch stdio MCP adapter selected as the complete dynamic toolset |
| Muse Code | The isolated host CLI, one headless run per batch | A required per-batch stdio MCP adapter selected as Muse's complete toolset |

The endpoint, Claude Code and Codex transports send the distillation instructions and type table
as the system prompt and the batch's reconcile sheet and conversation as the user message,
constant material first so prefixes stay cacheable. Hermes and Muse preserve the same order in one
prompt file because their CLIs have no system-prompt replacement flag. No transport carries tool semantics
(Invariant 8). On a host transport the toolkit state crosses the process boundary through the
batch's private scratch directory: seeded before the run, absorbed after it.

A run that ends without an accepted submission writes nothing and leaves the archive backlog and
Watermark untouched. Host and endpoint failures follow the attribution rules in
[Host adapters](host-adapters.md).

Hosts without a verified MCP posture keep the line-oriented text protocol: the library runs the
loop, parses looks and operations from plain text, and calls the same toolkit for recall and read.
`tool_mode = "auto"` selects native tools for Hermes, Muse, Claude Code, and Codex. `native` and `text`
select a Host path explicitly; an unsupported or invalid selection fails rather than changing
transport. Muse native mode requires 1.4.4 because
that release added exact MCP names to `run.toolset`. Its isolated settings contain only provider
routing and the required batch server; Shell, Web, file writes, reminders, personal context and
session persistence are disabled. Muse has no system-prompt replacement flag, so the same system
instructions and batch material are placed, in that order, in its one prompt file.

Monid is an explicit executor selection, independent of host and endpoint credentials.
It uses the same text protocol; provider and transport failures stop projection through
the existing reasoner failure boundary. Host defaults and local retrieval remain unchanged.

### Monid setup

Set `MONID_API_KEY`, then configure `[executor.write]` or `[executor.manage]` with
`reasoner = "monid"`, `model = "claude-sonnet-4-0"`, and `tool_mode = "text"`.
Prompts must fit the provider's input limit. This sends reasoning material to DataForSEO
through Monid (one API key, pay per call).
See [Monid docs](https://docs.monid.ai?utm_source=github&utm_medium=oss-pr&utm_campaign=tigerless-labs-agent-memory).

Hermes native mode requires Hermes Agent 0.22.2. One temporary profile contains only the batch
server, and the dynamic `agent-memory-write` toolset avoids collision with Hermes' built-in
`memory` toolset. The provider is pinned separately from the model. In particular, OpenRouter
uses its own API key and never enters the Vertex/gcloud credential path. Rules, personal memory,
plugins, skills, delegation, Shell, Web, and unrelated MCP servers are absent from the run.
Contributor-tier models require `host_allow_data_training = true`; the adapter does not infer
consent from the model name.

The profile lives below the active Hermes data root's `profiles/` directory, so the official
launcher reuses its installed dependency environment; it is removed after the run. An unrelated
empty `HERMES_HOME` is intentionally avoided because Hermes treats it as a new installation and
may provision dependencies instead of starting the batch.

## Hermes live comparison

An authenticated Hermes Agent 0.22.2 run through OpenRouter and
`meta/muse-spark-1.3-contributor` exercised the complete native matrix in 139.47 seconds. A fixed
New pair produced valid memory with the expected source provenance:

| Mode | Wall time | Host starts | Model requests | Memory tool calls |
|---|---:|---:|---:|---:|
| Text protocol | 22.525 s | 1 | 1 | 0 |
| Native MCP | 44.102 s | 1 | not exposed by Hermes CLI | 2 |

This sample does not show a latency win: native execution was 21.577 seconds slower. Its measured
benefit is that Recall and submission occurred as tool calls inside one continuing Agent session;
the text model submitted directly and therefore did not exercise retrieval.

Muse's OpenRouter route has one transport-only compatibility step. Muse 1.4.9 serializes the MCP
catalog as a Responses API namespace, OpenRouter returns the child name plus that namespace, and
Muse's local dispatcher looks up only a canonical flat id. During one native run, a scoped
loopback bridge between Muse and the configured local pproxy expands each namespace child to its
canonical `mcp__server__tool` function name. It forwards the existing bearer header, never holds a
credential, never executes a tool, and stops with the Host run. Direct Meta routes are unchanged.

## Muse live comparison

An authenticated Muse Code 1.4.9 run through pproxy and
`meta/muse-spark-1.3-contributor` exercised New, Recall/Read/Supersede, Skip, and a failed Read
whose observation was corrected in the same native session. The full live matrix completed in
120.93 seconds. A fixed New pair produced the same active Fact and Event with the same source
provenance:

| Mode | Wall time | Host starts | Model requests | Memory tool calls | Input / cached / output tokens | OpenRouter cost |
|---|---:|---:|---:|---:|---:|---:|
| Text protocol | 30.515 s | 1 | 1 | 0 | 25,794 / 0 / 3,600 | $0.0032994 |
| Native MCP | 44.782 s | 1 | 3 | 2 | 57,716 / 37,218 / 2,960 | $0.0027162 |

This one New sample does not show a latency win: native execution was 14.267 seconds slower. It
did perform a Recall before submitting and cost less in the observed run because later requests
reused cached input. Tool calls, not model requests, remain the core's `rounds` metric.
