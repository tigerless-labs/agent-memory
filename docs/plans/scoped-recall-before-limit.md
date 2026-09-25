# Scope eligibility before Recall candidate limits

## Problem and target

Recall currently truncates FTS candidates before checking the requested path scope. A
matching memory inside a narrow scope can disappear when enough higher-ranked memories
outside that scope occupy the candidate pool. The target keeps the existing ranking and
scope boundary semantics while selecting the candidate pool from scoped memories.

## Work units

1. Update the read design contract to place scope eligibility before candidate truncation.
2. Add a regression test with more out-of-scope matches than the candidate pool, and
   retain the complete-path-component scope test.
3. Apply scope during FTS candidate selection, then run targeted tests and full checks.
4. Verify the CLI on a temporary store, commit, and open a PR against current main.
