# Invalid memory archival

Baseline: `34d12a2f8678d5561aba27bd8ff73c5ae4b6a258` (main).

Invalidation uses the existing Archive and shared persistence path. Normal Read, Recall,
Trace and Context exclude invalid memories; explicit history remains available. Index
rebuild retains archived history, and Raw/provenance survives invalidation.

Lifecycle, adapter, failure recovery, idempotence and shared-evidence tests verify this
scope. No store migration, production cleanup or unrelated index feature is included.
