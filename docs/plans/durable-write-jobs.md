# Durable Write jobs and the per-run Write trace

## Baseline

The shared `main` baseline launches a detached distiller at every boundary and keeps no durable
record of the request. A worker that dies leaves the backlog to the next boundary of the same
session or to a manual run; duplicate boundaries spawn duplicate workers that queue on the
distill lock; `hooks.log` is the only record of what a run did. Dream already recovers through
claim, lease, and report; Write has none of that. The dreaming plan records that a full
persistent job queue was deliberately out of its scope.

This implementation adds no server, listener, supervisor, or resident process, and the core
still holds no model client.

## Decisions

1. Record each requested distillation as a Write job in Store state: session, target message
   index (the archive watermark's consumed value at enqueue), state, attempt, lease, owner,
   host, trigger source, and bounded redacted failure detail.
2. Enqueue is idempotent per session: a queued job for the same session is extended to the
   newest target instead of duplicated, so duplicate boundaries coalesce into one run. A
   boundary arriving during a run records a follow-up queued job instead of raising the
   running job's target, because the running worker distills the snapshot it took; the
   success fence completes the follow-up without reasoning once that run has covered it.
3. Claim atomically under a Store-local jobs lock: the oldest due queued job first, then a
   running job whose lease expired while its session's distill lock is free. A live worker
   extends its lease by heartbeat.
4. The watermark is the success fence: a job whose session already distilled through the job's
   target completes without a reasoner call, before running and again on recovery.
5. Bounded attempts with exponential backoff carrying a bounded, per-job deterministic jitter;
   an exhausted job dies and returns to the queue only by an explicit retry command.
6. Every run appends one per-job trace: transport, batches, rounds, tool-call digests, applied
   and rejected operations, repair rounds, usage when the reasoner reports it, and finish
   counts. Strings pass the existing redaction; bodies are digests unless explicitly enabled;
   size and retention bounds come from config.
7. The hook enqueues before it spawns the detached worker with the job id; a failed spawn
   leaves the job queued. SessionStart and empty boundaries — where Dream recovery already
   runs — launch one detached drain worker when due jobs exist.
8. `mem distill --job` runs one job; `--drain` claims and runs due jobs; `mem jobs` lists,
   inspects, retries, cancels, and collects; doctor reports dead, failed, and lease-expired
   jobs. No MCP maintenance surface exists today, so none is added.
9. The queue, fence, trace, and run loop live in the core and receive the reasoner as a
   callable; adapters stay algorithm-free.

## Verification

- Unit: enqueue coalescing, follow-up jobs for boundaries arriving during a run, claim order,
  lease reclaim gated by the distill lock, heartbeat, backoff determinism and bounds, death at
  the attempt cap, fence no-op, crash-after-settle recovery, quarantine of a corrupt job file,
  retry/cancel/gc, config knob types, trace event sequence, redaction, digest-only bodies,
  size-cap truncation, and unchanged distill output without a trace.
- System: hook enqueue and spawn, spawn failure leaving a queued job, `mem distill --job` and
  `--drain` end to end with the deterministic host fixture, `mem jobs` commands and trace
  output, doctor reporting a dead job, a worker killed mid-run recovering with exactly one
  Write, an expired lease reclaimed only once another process released the distill lock, two
  drain workers and a hook enqueue racing with each job run exactly once, and tool calls
  traced through both native-tool transports.
- Red team: traversal and absolute paths in job ids, session names, and CLI job arguments are
  refused; a job file pointing its trace outside the store is not followed; poisoned tool-call
  arguments reach the trace only redacted and digested; oversized failure messages are bounded.
- Regression: full unit, system, red-team, lint, and type checks.

## Recovery boundary

A caught worker error fails the job immediately with a bounded, redacted message and schedules
the retry. An uncatchable exit leaves the job running until its lease; the next lifecycle
event, `mem distill`, or a drain reclaims it after confirming the distill lock is free. A
watermark that settled before the crash completes the job as a no-op. A corrupt job file is
renamed aside and reported, never crashes a hook. Collecting terminal jobs and expired traces
is an explicit gc command; the queue never discards a queued or running job.
