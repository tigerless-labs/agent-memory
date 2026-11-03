# Preserve memory identity during regrouping

Menu-based add-only memories currently re-enter creation when Manage moves them.
The resulting record can lose its name, creation time and provenance.

1. Define regrouping's preservation and failure boundaries in the management design.
2. Add failing unit tests for add-only clustering and group merging, stale reads,
   occupied destinations and projection rollback.
3. Add a failing CLI Sleep regression for identity, evidence and index rebuilds.
4. Route regrouping through Store's locked rewrite path, preserving the existing
   record while changing its menu group and path.
5. Run focused tests, the full CI checks and an isolated CLI smoke test; remove the
   completed TODO and review the design index before committing.

Acceptance: regrouping preserves names, content, relationships, provenance and
validity across schema modes. Failed moves leave the original truth intact, and
ordinary add-only writes still create a new record.

Verification:

- Both add-only Manage regressions and both CLI regressions failed before the fix.
- Focused Manage, regrouping, schema and CLI checks: 144 passed.
- Full suite: 1103 passed, 12 skipped, 90.09% coverage. One existing username-sensitive
  path test was excluded after reproducing its failure on unchanged upstream.
- Ruff, mypy and diff whitespace checks passed.
- A separate CLI process preserved five add-only memories and their trace evidence
  through Sleep, rebuild and repeated Sleep in a temporary store.
