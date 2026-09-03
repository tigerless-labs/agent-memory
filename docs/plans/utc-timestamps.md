# Plan: UTC instants in frontmatter

> Working artifact. Owner request (2026-09-02): memory records need a time of day, and the
> value must not change with the host's time zone.

## Change

`created` / `updated` / `valid_from` become time-zone-aware instants rendered in UTC
(ISO 8601, second precision, `Z` suffix). The day-granular form was chosen to keep same-day
rewrites out of git diffs; the owner has traded that for intra-day ordering.

## Contract

- One module owns the format: parse, render, canonicalise. Clock, record validation, store,
  Manage and recall all call it; no second parser anywhere.
- Validation accepts a calendar day (legacy files, human-typed `valid_from`) or an aware
  instant in any offset. It rejects a naive datetime: without an offset the instant is
  ambiguous, which is the failure mode this change exists to remove.
- The single write path canonicalises every date field before persisting, so any file that
  passes through it comes out in the one UTC form.
- Manage T0 "date normalisation" now means: upgrade legacy calendar days and foreign
  offsets on disk to the canonical form.
- Recall's `as_of` and Manage's idle computation compare instants, not days.

## Units (docs → tests → code)

1. `docs/design/domains/storage.md` frontmatter sentence; `manage.md` T0 row;
   `docs/testing.md` test-map row.
2. `tests/unit/test_timestamps.py`: format round-trip, offset independence through the
   store, legacy day accepted and upgraded, naive and malformed payloads rejected, Manage
   upgrade, intra-day supersede visible to `as_of`, `correct` moving `updated` by minutes.
   Retire the Manage test that asserted truncation to calendar days.
3. `core/timestamp`, `core/clock`, `core/record`, `core/store`, `core/manage`, `core/recall`.
4. Full suite, lint, types; end-to-end via CLI under a non-UTC `TZ`.
