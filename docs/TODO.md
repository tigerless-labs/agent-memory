# Follow-ups

## Read policy follow-up

- Evaluate the memory-first reading policy with observed exposure before attributing
  answer changes to bounded Trace or optional Vector candidates.

## Management follow-ups

- Decide explicit confirmation and host-level authorization for permanent GC, import and
  cross-store changes; CLI labels alone do not identify a human.
- Decide preimage retention and recovery guarantees for split and in-place correction,
  including stores outside Git and multi-file Manage failures.
- Decide whether direct link/unlink delta commands, relation audit history and per-operation
  bounds are needed; current correct replaces the complete list.
- Review recovery of interrupted multi-file operations outside Git-backed stores.

## Executor follow-ups

- Replace the host-CLI reasoner with an executor-owned agent loop: native tool use, a
  persisted per-run trace (messages, tool calls, operations, usage), explicit prompt caching,
  a context provider per job, and a durable job queue in place of the fire-and-forget launch.
  The host CLI stays the zero-key fallback.
- Boundary distillation through the host CLI takes 80–100 s per boundary on Haiku (three
  negotiation rounds, one cold process each); measure again once the executor loop lands.
- Verify the Codex dialect end to end, including the one-time hook trust review; it is
  covered by unit tests only.
