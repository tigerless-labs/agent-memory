# Host adapters

Host support has two boundaries. Lifecycle adapters translate host events into injection,
eviction, and pause moments. Executor dialects translate a prompt and tool posture into one
headless host invocation and normalize only its final answer. Capture, archive, distillation,
Memory, Recall, and Manage stay host-neutral.

For Write negotiation, Claude Code, Codex, Hermes, and Muse run tools-only: the only tools are the Write
toolkit's, served by the per-batch MCP adapter ([Write negotiation](write-negotiation.md)); the
host's built-in tools, user configuration, rules and native memory are off. Claude and Codex
replace their system instructions; Hermes and Muse put the same ordered material in one prompt file.
Claude's bare mode stays unused because it drops OAuth and would break zero-key install.

Manage native review reuses the same one-process Host transport, not the Write toolkit or a
library-side ReAct loop. It is opt-in under `[executor.manage]` for `codex` and `muse-code` and
exposes one separately named per-run MCP server with only proposal listing, proposal-scoped
evidence reads, and structured verdict submission. Codex runs ephemeral with user config, rules,
built-in tools, personal memory, and filesystem writes disabled. Muse reuses its isolated
HOME/XDG profile, staged authentication and routing, exact `run.toolset` selection, eight-step
bound, disabled shell/web/write capabilities, and scoped OpenRouter namespace bridge. Neither
Host receives a Store mutation tool. The MCP adapter persists the tool trace across the process
boundary; it never applies a verdict. Manage rechecks source versions, proposal membership,
per-kind caps, and Store rules before the existing decision path writes anything. Endpoint and
other Host Manage reasoners retain the text protocol.

Muse native Write is the automatic Write posture. Muse 1.4.4 added exact MCP selection through
`run.toolset`; native mode supplies that selection as a one-run override and stages one required
server in the already-isolated Muse settings. Older CLIs fail with a version-specific error in
the same attempted process rather than silently changing transport. An explicit
`tool_mode = "text"` retains the compatibility protocol. Muse/OpenRouter namespace calls pass
through a per-run loopback compatibility bridge before the existing pproxy: it flattens only the
model request's tool schema, passes authentication through, and leaves Agent execution and MCP
dispatch with Muse. A Muse native run is limited to eight model steps and fails closed without an
accepted submission. Muse Code 1.4.4 is the minimum for both native Write and native Manage because
both depend on the same exact MCP selection flag.

Hermes native Write uses a fresh profile below the active Hermes data root per batch and a
collision-free dynamic MCP toolset named `agent-memory-write`. Its staged config contains only that stdio server and
whitelists `recall`, `read`, and `submit_operations`; resources and prompts are disabled. The
provider is explicit and independent of the model, so `openrouter` consumes
`OPENROUTER_API_KEY` directly and does not construct or mint Vertex credentials. Hermes Agent
0.22.2 is the tested minimum. Contributor-tier models additionally require the explicit
`host_allow_data_training` opt-in. Its compatibility text protocol remains available only when
selected explicitly.

Authenticated validation on 2026-10-17 used Hermes Agent 0.22.2, OpenRouter, and
`meta/muse-spark-1.3-contributor`. Four isolated runs completed New,
Recall → Read → Supersede, Skip, and an invalid Read whose error returned to the same Agent before
an accepted Skip. They made 9 Memory tool calls and took 47.767 s, 31.967 s, 31.280 s, and
28.321 s respectively. A paired New sample took 44.102 s in native mode versus 22.525 s through
the text compatibility protocol; both happened to use one Host process because the text model
submitted immediately. This sample establishes behavior, not a native speed advantage.

Write and Manage have independent Store-level reasoner policies. Explicit CLI choices override
the operation policy, which overrides the legacy executor policy. Without an operation policy,
automatic Write uses the host that produced the source session while Manage uses the legacy
Store executor. The source host remains capture metadata and never overrides an explicit Write
reasoner.

Each operation may use a supported host CLI or a user-owned model endpoint. Authentication,
transport, host-process, and response-shape failures are attributed to that operation and stop
the attempt without selecting another host or endpoint. Write retains the unsettled archive
backlog, and every accepted memory continues to cite the original source session. Headless
reasoner sessions carry the executor marker so their lifecycle hooks remain inert.

Automatic Manage deliberately uses the Store's configured Manage reasoner, not the lifecycle
source Host. The selected reasoner kind, Host, and model are recorded in the claim and reported by
the worker; failure never falls back to another transport. On a fresh Host-backed Store, the first
successful Host setup also supplies the default Manage policy. Explicit operation policies and
legacy endpoint configuration are preserved.

`muse-code` is the canonical Muse Code identity and `muse` is only a setup alias and binary
name. Muse lifecycle events use the existing moments, and only root-session material enters the
archive. Muse's native memory remains independent and is never copied, synchronized, or treated
as Recall evidence.

Host setup is a preserving merge. Muse settings require their schema version, retain unknown
settings, hooks, and MCP servers, and are replaced atomically only after valid JSON is read.
The setup path installs lifecycle hooks and the canonical agent-memory skill; MCP remains an
explicit use of the shared server.

Muse 1.4 lifecycle payloads identify the session but set `transcript_path` to null. The Muse
adapter resolves that identifier to the root durable log under Muse's XDG data directory and
normalizes only user and assistant conversation records. Child and observer logs remain excluded.

Muse reasoning runs through the host CLI. Prompts use temporary files, model and reasoning
overrides are opt-in, and Muse JSONL is normalized inside its executor dialect. Experiment
metadata fixes host identity, CLI version, model, reasoning effort, workspace, and revision.

Muse's sandbox remains enabled. Experiment Stores and workdirs must share a bounded workspace;
ordinary external Stores are read-only to the agent shell. Controlled runs isolate HOME and XDG
state while reusing only an explicit auth file. Hook and MCP writes require a live compatibility
preflight. Results are not attributable until native memory is isolated and the tested build
passes that preflight.

Failed regrading marks the saved run failed and retains the grader error instead of publishing a valid-looking incorrect score. Existing transport-success vote interpretation is preserved.

Benchmark fingerprints include complete episode content, reference answers and evidence, preserving resume and attribution guards when a dataset changes without changing its identifiers.

Benchmark attribution requires each compared arm to contain the same episode IDs exactly once. Shared corpus and retrieval fingerprints cannot license a comparison built from unpaired or duplicated episode results.

Benchmark session timestamps preserve ISO instants, timezone offsets and second precision alongside the existing LongMemEval date format. Valid evidence dates no longer degrade into empty timestamps or the replay clock.
