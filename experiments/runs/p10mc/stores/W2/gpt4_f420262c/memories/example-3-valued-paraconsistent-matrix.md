---
created: 2026-09-03T01:43:38.858519857Z
updated: 2026-09-03T01:43:38.858519857Z
weight: 1.0
last_accessed: 2026-09-03T01:43:38.858519857Z
access_count: 0
pinned: false
links:
- non-deterministic-matrix-arity-corrected-definition
- party-decision-non-deterministic-model
abstract: Example non-deterministic matrix with 3 truth-values {1,2,3}, designated {2,3}, paraconsistent negation, and conjunction
---

## Example Matrix

Concrete non-deterministic matrix with negation and conjunction:

**Structure:**
- X = {1, 2, 3}
- Y = {2, 3}
- V = {p, q}
- C = {¬, and}
- arity(¬) = 1
- arity(and) = 2

**Interpretation:**

Negation:
- ·(¬, 1) = {2, 3}
- ·(¬, 2) = {1, 3}
- ·(¬, 3) = {1, 2}

Conjunction (and):
- ·(and, 1, 1) = {1}
- ·(and, 1, 2) = {1}
- ·(and, 1, 3) = {1}
- ·(and, 2, 1) = {1, 2}
- ·(and, 2, 2) = {2}
- ·(and, 2, 3) = {2}
- ·(and, 3, 1) = {1, 3}
- ·(and, 3, 2) = {2, 3}
- ·(and, 3, 3) = {3}

**Paraconsistent behavior:** The negation function returns multiple possible truth-values rather than a single opposite value, allowing for paraconsistency where a proposition and its negation can both hold.