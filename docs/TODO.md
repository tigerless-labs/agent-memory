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

## Muse Code follow-ups

- Run the isolated Muse shell, lifecycle hook, and stdio MCP sandbox preflight on an installed,
  authenticated Muse build, then record the observed compatibility result.
- Run Muse-to-Muse, Muse-to-Codex, and Codex-to-Muse portability smoke before the full four-host
  matrix.
- Map `MUSE_SESSION_ID` into shared MCP source context only if provenance can accept it without a
  Muse-specific Store field.
- Validate the isolated root-session fixture against an exported log from the supported Muse
  version before treating raw-log fallback as release-ready.
