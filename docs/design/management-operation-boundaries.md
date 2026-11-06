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

Automatic directory clustering, spelling-based group merging, and empty-group cleanup
apply only to schema group fields whose configured source is menu. System-sourced
groups preserve their values and paths, maintaining project ownership and event date
boundaries. Custom schemas and field-source overrides follow the same rule.
Regrouping preserves memory identity, content, provenance, relationships, creation
time and validity, including for add-only schemas. It changes only the menu group,
path and update time. Store validates the source and destination under its writer
lock; stale sources, occupied destinations and projection failures leave truth intact.

T0 duplicate supersession requires identical parsed abstract and body, type, all semantic
fields, effective validity start, author, relationships and provenance. Text comparison
preserves Unicode, case, order, repetition, punctuation and internal whitespace. Names,
paths, weights and bookkeeping timestamps do not establish semantic identity. The oldest
duplicate remains active, with name breaking creation-time ties; other copies retain their
files and point to it. Similarity alone belongs to the reviewed proposal path.

Configuration persistence preserves strings and field names exactly, including backslashes, quotation marks and control characters. A saved configuration remains readable without changing executor commands or field-source identities.

Custom memory types occupy the truth namespace exclusively. Schemas cannot reuse archive, projection, schema or report directory names and silently write knowledge outside the discoverable truth tree.

Memory identity and type identifiers match their complete slug grammar. No rendered frontmatter value carries a line break, so a caller-supplied string cannot end its line early and be read back as a different field.

Malformed final operations or exhausted executor negotiation cannot mark an archived batch as distilled. The boundary reports validation failure before draining pending operations or publishing projection writes, preserving the raw backlog for a later retry.

The implicit fact date selects the latest cited instant by parsed timestamp rather than string order. Evidence using different UTC offsets retains its actual chronological meaning.

Dense projections validate nonempty, finite and consistently sized backend vectors and pack them before replacing the previous projection. A malformed embedding response cannot delete a valid cached representation.

Direct rewrites and corrections enforce the same evidence-date relationship as new records. A fact cannot be moved later than the conversation it cites, and rejected corrections leave truth unchanged.

Automatic links count memories returned together in individual recall events. Repeating the same query can supply multiple observations, while unrelated calls sharing query text cannot manufacture cooccurrence. Recall records one shared timestamp per result batch.

Legacy configuration migration removes obsolete knobs while preserving supported storage customizations. Abstract limits, default project identity and lock timing are retained instead of being silently reset to factory defaults.

Legacy migration distinguishes current reference and experience schemas from old domain directories with the same names. Rerunning migration leaves current truth untouched and no longer reports a fully migrated store as needing migration.

Import preflights all file entries before publishing any imported file. A malformed late entry leaves earlier truth unchanged.

MCP dispatch validates the scalar and mapping types advertised by its tool catalogue before coercion or core execution. Recall limits must be positive integers, so invalid requests return validation errors without writing truth or terminating the server.

An externally edited memory that fails validation leaves the retrieval projection immediately while its truth file remains intact. Repairing the file restores eligibility through the ordinary projection path.

A memory validity interval cannot end before its start. Direct writes reject reversed intervals before publishing the Markdown projection and preserve the previous truth file.

The in-memory schema projection tracks schema file content. A long-lived store observes external edits, additions and removals instead of continuing to route writes using stale schema definitions.

The injected index keeps fitting lower-priority memories when an earlier entry exceeds the remaining byte budget. Oversized entries cannot suppress the entire remaining recall surface.

The root index byte budget includes its header. If a configured header cannot fit, the projection is empty rather than exceeding the budget.
