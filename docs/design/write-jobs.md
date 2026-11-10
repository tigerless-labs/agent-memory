# Write jobs

A boundary hands distillation to a detached worker; the hand-off is a durable Write job, not a
process that may vanish. The job queue is runtime state beside the watermarks and the pending
queue: one file per requested distillation, written atomically under one Store-local advisory
lock. Truth files stay untouched, and losing the queue costs retries, never memories.

## Jobs

A job records its session, the target message index it must distill through — the archive
watermark's consumed value when the job was created — and its state: queued, running,
succeeded, failed, dead, or cancelled. Enqueueing is idempotent per session, and it respects
what a run can honestly claim: a queued job for the same session is extended to the newest
target, so duplicate boundaries coalesce into one run, while a boundary arriving during a run
records a follow-up queued job instead — the running worker distills the backlog snapshot it
took, and the success fence lets the follow-up complete without a reasoner call once that run
has already covered the ground.

Claiming is atomic. A worker takes the oldest due queued job, or reclaims a running job whose
lease expired while that session's distill lock is free — a lock still held means a worker is
alive and the claim stands down. A running worker extends its lease by heartbeat. A caught
failure marks the job failed with exponential backoff carrying a bounded, per-job deterministic
jitter, and it re-enters the claimable pool when the backoff elapses; a job that exhausts its
attempt cap dies and returns to the queue only by an explicit retry command.

The watermark is the success fence. Before a worker reasons, and again once it holds the
distill lock, a job whose session has already distilled through the job's target completes
without a reasoner call. A crash after the watermark settles but before the job closes
therefore never repeats a Write — and neither does a crash after claiming, before reasoning,
or mid-trace: the recovery run closes the job, and a trace torn mid-write is sealed by the
next append. A corrupt job file is renamed aside and reported; a broken record never crashes
a hook.

## Traces

Every job run appends one JSONL trace: the run's target and transport, each batch and round,
every tool call as an argument digest and length, applied and rejected operations with their
field errors, repair rounds, usage when the reasoner reports it, and the finish counts. Every
string passes redaction before it is written and again when it is read back; bodies are
digested unless explicitly enabled; the trace stops at its size bound and expires with the
retention period. The trace records what a run did; it is runtime state, not memory truth.

## Surface

The hook enqueues before it spawns the detached worker, which runs that one job; a failed
spawn leaves the job queued for the next opportunity. SessionStart and empty boundaries —
where Dream recovery already runs — launch one detached drain worker when due jobs exist.
`mem distill --job` and `--drain` run the same path a hook spawn runs; `mem jobs` lists,
inspects — with the job's trace on request — retries, cancels, and collects; doctor reports
dead, failed, and lease-expired jobs, plus quarantined job files. There is no resident service
and no supervisor: lease expiry and re-entry do the recovery.
