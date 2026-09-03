---
name: hardware-atomic-operations-for-synchronization
abstract: Hardware atomic operations for synchronization
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

**Load-Link/Store-Conditional (LL/SC):** Pair of instructions; LL reads memory location and marks as reserved for current thread; SC writes only if unreserved since LL.

**Compare-and-Swap (CAS):** Atomically compares memory location with given value. If match, updates with new value; otherwise returns current value. Fundamental to lock-free algorithms.

**Test-and-Set (TSET):** Sets bit in memory to 1, returns original value. Used for implementing spinlocks.

**Load-Acquire/Store-Release:** Pair ensuring memory access ordering; Load-Acquire acts as fence ordering subsequent accesses after it; Store-Release orders prior accesses before it.
