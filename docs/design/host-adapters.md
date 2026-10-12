# Host adapters

Host support has two boundaries. Lifecycle adapters translate host events into injection,
eviction, and pause moments. Executor dialects translate a prompt and tool posture into one
headless host invocation and normalize only its final answer. Capture, archive, distillation,
Memory, Recall, and Manage stay host-neutral.

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

The stdio adapter returns JSON-RPC parse or invalid-request errors for malformed frames and continues reading subsequent requests. An explicit null request ID receives a response, while requests without an ID retain notification behavior. Error codes and envelope rules follow https://www.jsonrpc.org/specification.
