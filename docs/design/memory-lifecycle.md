# Memory lifecycle and management

Memory has two states: active and invalid. Supersession invalidates a predecessor with a
successor reference; deletion invalidates without one. Archive is a physical location,
not a third state. Invalid memories retain content, identity, validity dates, links and
provenance inside the existing Archive, separate from append-only raw evidence.

Store persists invalidity before moving a file. Failed moves leave invalid truth available
for retry; failed projections leave file truth authoritative. Retrying deletion completes
archival and projection without changing the original invalidation time or successor.
Normal reads and recall check current truth; explicit history reads and temporal recall
retain history. Rebuild includes archived history. Existing invalid files remain readable
as history without an automatic bulk migration. Raw evidence remains independently available.

Relationship additions require distinct active endpoints in the same store. Existing links
may remain as historical references. Correct replaces the complete link list, so removal
requires supplying the intended remaining list. Manage's automatic linking remains enabled.
Corrections require active memories and active successors. These are data validations,
not identity authorization or a scope permission system.

Manage retains deterministic maintenance and capped executor decisions over existing
proposals. Reports and the decision ledger record outcomes; Git recovery depends on a
successful commit. Split and in-place corrections do not unconditionally preserve previous
content. Permanent collection remains outside the Manage and MCP menus; its human-only
label is not enforced authentication. Deployment owners must control shell/file access.
