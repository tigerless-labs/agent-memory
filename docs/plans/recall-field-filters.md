# Recall across types within one project

The store groups memories by type before project. A path scope selects one type/project
branch, while a shared project can have decisions, facts and experiences in separate branches.

1. Define exact schema-field eligibility in the read design, without changing default ranking.
2. Add failing core and CLI/MCP tests for cross-type retrieval, candidate limits, history,
   vector eligibility, conjunction, literal values and index recovery.
3. Project schema fields through the existing index pipeline and filter before candidate limits.
4. Expose the same core option in Recall, Context, CLI and MCP; verify a local shared store.
5. Run the relevant suites and repository checks, then publish a Draft for review.
