# Management operation boundaries

The presence of `invalid_at` ends a memory's current validity. Its retained file and
`valid_from`/`invalid_at` interval serve historical queries; `superseded_by` records a
replacement link. Old files with stored status remain readable, while new writes derive
eligibility from the interval alone. Current indexes and MEMORY.md project only files
whose interval has no end. Archived sessions and provenance are independent of this state.
An in-place correction changes the file within its existing interval; creating a successor
preserves distinct historical facts as separate files.

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

Agents may correct a named active memory, create a successor, replace an old memory with
an existing active successor, merge named memories atomically, or delete a named memory
through Store. Both adapters expose these explicit operations. Sleep retains proposal
review and per-kind caps for unattended
merge, split, supersede, and deletion decisions. File scope, links, provenance, locks,
validation, and projection remain Core responsibilities.

T0 duplicate supersession requires identical parsed abstract and body, type, all semantic
fields, effective validity start, author, relationships and provenance. Text comparison
preserves Unicode, case, order, repetition, punctuation and internal whitespace. Names,
paths, weights and bookkeeping timestamps do not establish semantic identity. The oldest
duplicate remains active, with name breaking creation-time ties; other copies retain their
files and point to it. Similarity alone belongs to the reviewed proposal path.
