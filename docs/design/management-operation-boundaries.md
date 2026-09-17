# Management operation boundaries

Correction is a read-modify-write operation on a canonical memory file. Concurrent
corrections can silently discard one another when either reads before acquiring the store's
writer lock. A relationship mutation can also leave a memory pointing at a missing or
invalid target. CLI and MCP must expose the same operation rather than define separate rules.

The Store holds one writer lock from the correction read through validation, persistence,
and projection. Direct rewrites and corrections share one persistence path. Validation
failure leaves the canonical memory and its projections unchanged; after success, projections
can be rebuilt from canonical files.

An active source may link only to distinct, active targets in the same store. Omitted links
leave relationships untouched, including historical relationships whose targets later became
invalid. An explicit list replaces the complete set, validates every submitted target under
current rules, and may be empty to remove all relationships. CLI and MCP pass corrections to
the same Store boundary.

This change covers correction serialization, relationship replacement, and adapter parity.
It does not add RBAC, approvals, standalone unlink, archive management, feedback redesign,
retrieval changes, or a general rollback system.
