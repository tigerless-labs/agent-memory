# Batch write boundaries

Store handles a batch under one writer lock. Invalid input rejects its own item with
an index and field error; accepted siblings share one projection. Single-record
writes use the same validation and persistence boundary. A check prepares each item
exactly as a write does and persists nothing, so its verdicts are the write's.

An operational failure during writing or projection aborts the batch. Store restores
touched canonical memory files to their pre-batch contents and projects the restored
truth before propagating the error, provided storage remains available for recovery.
Repeated changes to one file preserve its earliest snapshot. Missing predecessors
retain their existing error category and also abort the batch.

Archived evidence remains append-only, including evidence appended by an aborted
batch. Recovery covers canonical files and their projections; interrupted distillation
processes are recovered by the [Write jobs](write-jobs.md) queue, and persistent
storage failures remain out of scope. Projection
continues to discover changes made outside Store.
