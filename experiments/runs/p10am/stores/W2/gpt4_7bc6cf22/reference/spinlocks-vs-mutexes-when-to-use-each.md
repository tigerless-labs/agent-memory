---
name: spinlocks-vs-mutexes-when-to-use-each
abstract: "Spinlocks vs mutexes: when to use each"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-03-07
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

**Spinlocks:** Best for kernel-space where lock held briefly (e.g. interrupt handlers). Process doesn't sleep; keeps spinning until acquired. Higher performance for short critical sections, lower latency.

**Mutexes:** Used when process may sleep waiting for lock. Preferred in user-space threads and longer-held locks. Process yields CPU while waiting.

Choice depends on: performance requirements, latency sensitivity, expected contention, resource patterns.
