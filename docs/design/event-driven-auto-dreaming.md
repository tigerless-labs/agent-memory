# Event-driven automatic Dreaming

Automatic Dreaming extends the file-first lifecycle rather than adding a Memory service.
Lifecycle activity supplies opportunities to inspect durable progress. A completed boundary
distillation may claim due work and start one detached, short-lived worker; an otherwise empty
boundary or a later SessionStart is also a recovery and elapsed-time opportunity. The same
opportunities drain due [Write jobs](write-jobs.md).

A session counts once when captured material exists, its distillation watermark has caught up,
and no pending or redistill work remains. Hook frequency is not progress. The first Dream uses
the configured session threshold. Later Dreams require both the configured elapsed-time and new
session thresholds. Manage waits while any captured Write remains unsettled.

Claims are Store-local persistent state. A claim binds a stable decision identity, the covered
session set, trigger source, actual Manage reasoner, attempt, and lease. Store-local advisory locks
serialize claiming and execution; Distillation and Manage share a maintenance gate. A completed
report is the success fence, so recovery after a state-write crash does not repeat Manage. A
missing report after a failed process remains retryable when the lease expires and another
lifecycle event arrives.

The configured Manage policy supplies the reasoner; the lifecycle Host remains only the Write
source and trigger opportunity. This keeps an explicit Codex, Muse, or endpoint selection stable
across shared-Store Hosts and never falls back to another transport. On a fresh Host-backed Store,
the first successful Host setup supplies the default Manage policy; explicit operation policies
and legacy endpoint configuration are preserved.

Both a detached Hook worker and `mem sleep --if-due` enter the same path:

```text
persisted settled sessions -> Manage.due() -> atomic claim -> run_worker()
  -> Manage.sleep() -> T0 actions -> T1 proposals/judgements
  -> Store mutations -> decision ledger -> Dream Report -> success state
```

`mem sleep` remains an unconditional manual run. `mem sleep --if-due --trigger-source cron` is the
safe optional scheduler entry: it computes progress from watermarks and pending state, returns a
normal skipped result when not due, and shares claim/lease recovery with Hooks. `mem cron
install/status/remove` manages one Store-scoped block in the user's crontab; the block only invokes
that existing scheduler entry. It captures absolute Store and executable paths plus the non-secret
`HOME` and `PATH` needed by configured Host reasoners. A private, explicit `--env-file` can supply
environment-only transport settings without copying their contents into crontab diagnostics.
Default setup does not install it.

There is no Memory timer, listener, supervisor, or resident process. Without an external cron
entry, elapsed-time eligibility remains dormant while Hosts are inactive and the next lifecycle
event checks it. With an explicitly installed entry, the operating system can wake the same CLI
path on wall-clock time. The interval controls checks, not Dream frequency; Manage still enforces
both thresholds. Claim and maintenance locks make Hook/cron races no different from duplicate Hook
events.
