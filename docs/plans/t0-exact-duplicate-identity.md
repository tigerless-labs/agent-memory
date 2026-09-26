# T0 exact duplicate identity

## Goal

Prevent unattended Sleep from invalidating distinct memories through a lossy token-set
fingerprint. Keep deterministic supersession for genuine duplicates and retain both files.

## Units

1. Update the management design contract and its index before tests or implementation.
2. Add failing unit regressions for multilingual text, word order, repeated words, case,
   punctuation, whitespace, type, semantic fields, validity, relationships and evidence.
   Make the positive fixture explicitly copy semantic fields; test deterministic keeper
   selection and repeat-Sleep behavior.
3. Add a failing CLI Sleep regression with reasoning disabled, checking retained active
   memories, projections and genuine duplicate supersession.
4. Replace the T0 token fingerprint with a structured exact identity. Compare parsed text
   without further normalization, type, all extra fields, effective validity start, author,
   links and provenance. Exclude name, path, weight and bookkeeping timestamps. Keep T1
   similarity, Store persistence and invalidation behavior unchanged.
5. Run targeted regressions, CLI verification, lint, types and the CI test/coverage command.
   Review the diff, commit, push to a fork, open an upstream PR and monitor CI.

## Acceptance

- Distinct content or semantic metadata remains active after rule-only Sleep.
- Exact duplicates still choose the oldest record, breaking creation-time ties by name.
- Superseded duplicates remain on disk and in historical projections; a second Sleep
  adds no duplicate action.
- No model calls, index migration or external-file synchronization changes are required.

## Trade-off

More conservative matching leaves ambiguous copies for proposal review. This change does
not repair already-invalidated records or change the existing T1 proposal heuristic.

## Verification

- Before the fix: 22 unit cases and two CLI cases fail through incorrect invalidation.
- After the fix: all 102 targeted Manage, reasoning, CLI and Sleep-store tests pass.
- Full suite: 597 tests pass; coverage is 93.11%, above the required 85%.
- Ruff and mypy pass. A separate CLI process check confirms distinct Chinese memories,
  exact-copy supersession, historical recall, index rebuild and repeated Sleep.
- Independent review found no blocker. Keeper revalidation during concurrent writes is
  tracked separately in the management follow-ups.
