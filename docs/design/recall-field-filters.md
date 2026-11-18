# Schema-field eligibility

A shared Store can hold several projects, and each project's memories can span types.
Recall accepts exact schema-field constraints independently of path scope. Every constraint
must match; a missing field does not match. Scope, validity and fields compose by intersection.
Values retain their stored spelling and case. Empty constraints preserve existing behavior.

SearchIndex applies fields before lexical candidate limits, and Recall passes the same
eligible names to VectorIndex. Ranking, disclosure levels and access logging remain unchanged.
Context and the CLI/MCP adapters use the same core eligibility.

Fields are a rebuildable projection of Markdown frontmatter. An old index is backfilled by
the existing Indexer on its next synchronization or first filtered recall. Reads never edit
truth files, and rebuilding the index preserves field-filtered results.
