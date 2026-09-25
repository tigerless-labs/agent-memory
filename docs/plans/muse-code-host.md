# Muse Code host adapter

## Scope

Add Muse Code as a fourth adapter without changing Store truth, Memory representation, Recall,
Manage, or the behavior of existing hosts.

## Work units

- Document lifecycle, executor, native-memory, and sandbox boundaries.
- Add fixture coverage for host identity, setup merge and failure behavior, lifecycle payloads,
  root-session capture, executor transport, independent judge selection, and provenance.
- Extend the lifecycle registries and preserving setup merge for Muse user settings.
- Extend the executor dialect registry with `muse exec`, prompt files, JSONL answer parsing, and
  explicit model and reasoning overrides.
- Extend experiment selection, metadata, and ordered portability smoke support.
- Document optional stdio MCP configuration and the separation from Muse native memory.
- Run unit/system checks and the live shell, hook, MCP, and portability probes when Muse is
  available.

## Acceptance

Offline tests and static checks must remain green for every host. Live Muse and cross-host smoke
evidence is required before claiming release-ready compatibility.
