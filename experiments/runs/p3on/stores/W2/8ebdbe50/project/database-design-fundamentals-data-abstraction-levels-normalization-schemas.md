---
name: database-design-fundamentals-data-abstraction-levels-normalization-schemas
abstract: "Database design fundamentals: data abstraction levels, normalization, schemas"
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Studied core database design concepts:

**Data Abstraction Levels:**
- Physical: Storage details, disk access, memory organization
- Logical: Data types, relationships, constraints
- View: User-facing presentation, column visibility, access methods

**Normal Forms (based on functional dependencies):**
- 1NF: No repeating groups/arrays, single value per cell
- 2NF: Full dependency of non-key attributes on entire primary key
- 3NF: No transitive dependencies (A→B→C problem avoided)
- BCNF: Every determinant is a candidate key
- 4NF: No multi-valued dependencies

**Schema vs Instance:**
- Schema: Structural blueprint (tables, columns, types, constraints)
- Instance: Actual data at a moment in time (changes as data is added/removed)

**Visual Representation:**
Database schemas are typically shown as Entity-Relationship Diagrams (ERDs) with tables as rectangles, attributes listed, primary keys underlined, and relationships shown as connecting lines with cardinality (one-to-many, etc.).
