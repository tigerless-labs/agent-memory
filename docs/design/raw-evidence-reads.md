# Explicit raw evidence reads

A memory may cite a bounded range of archived conversation messages. Trace opens
only evidence cited by the named memory, preserves its original location and time,
and presents historical content as data. Missing, inconsistent, or unbound evidence
fails explicitly. An explicit historical memory remains readable with its validity
state; evidence from it does not become current truth.

Recall searches Memory only, using an explicit limit when more candidates are useful.
Requested path scope filters Memory before a candidate limit is applied, so unrelated
matches cannot hide a relevant scoped memory.
Trace remains an explicit read capability bound to a selected Memory citation. Archived
sessions stay available for audit and redistillation. Reused stores project their indexes
before an exam so retrieval sees the same truth files that a fresh store would.

Historical experiment scores remain attached to the reading policy and corpus under
which they were measured.

Native Manage does not receive this capability merely by selecting native tool mode. Its
experimental `manage.review_raw_session_evidence` switch defaults to false. When enabled, the
run-scoped reviewer may ask `read_evidence` for one complete raw Session pointer that was frozen on
the same proposal target. Proposal id, target name, and pointer must all match, and the Store traces
the current record again before returning structured message role, archived message time, and text.
There is no Session search, neighboring-message access, unrelated-Memory access, or fallback when
evidence is missing or damaged. Raw content remains untrusted historical data and is sent to the
configured review model only when requested.

The target Memory Source Hash includes its provenance pointer and is checked before and after the
trace. It does not hash the referenced Session bytes. The append-only Store API preserves cited
message indices during normal operation, but this mechanism does not claim to detect or defend
against malicious out-of-band edits to archived Session files.

Structured host messages preserve their original leading indentation and trailing whitespace in raw storage. Code excerpts and quoted text remain faithful evidence while projections retain their own formatting rules.

Truth-file fallback resolves the identity stored in frontmatter rather than assuming the filename is the identity. Explicit provenance reads survive externally renamed files and missing projection caches.
