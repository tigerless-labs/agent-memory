---
created: 2026-09-03T01:43:46.528717595Z
updated: 2026-09-03T01:43:46.528717595Z
weight: 1.0
last_accessed: 2026-09-03T01:43:46.528717595Z
access_count: 0
pinned: false
links:
- example-3-valued-paraconsistent-matrix
abstract: Real-world scenario modeling a person's party decision with uncertainty using non-deterministic matrix; truth-values 0=false, 1=possible true, 2=possible false
---

## Real-World Scenario: Party Decision

**Context:** A person is deciding whether to go to a party or stay home. The decision involves uncertainty about preferences, circumstances, and outcomes.

**Non-deterministic Matrix for Party Decision:**

- X = {0, 1, 2}
- Y = {1, 2}  (designated values: decisions that are actually possible/viable)
- V = {go, stay}
- C = {¬, or}
- arity(¬) = 1
- arity(or) = 2

**Truth-Value Interpretation:**
- 0 = certainty that proposition is false (ruled out)
- 1 = possibility that proposition is true (viable option)
- 2 = possibility that proposition is false (but still uncertain/viable)

**Negation semantics:**
- ·(¬, 0) = {1, 2}  (if it's certain to be false, it's now possible to be true or uncertain)
- ·(¬, 1) = {0, 2}  (if possibly true, it could be false or uncertain)
- ·(¬, 2) = {0, 1}  (if possibly false, it could be false or possibly true)

**Disjunction (or) semantics:**
- ·(or, 0, 0) = {0}  (neither option viable → ruled out)
- ·(or, 0, 1) = {1}  (one option possible)
- ·(or, 0, 2) = {2}  (uncertain option)
- ·(or, 1, 1) = {1}  (both options possible → both possible)
- ·(or, 1, 2) = {1, 2}  (mixed: one certain possible, one uncertain)
- ·(or, 2, 2) = {2}  (both uncertain)
- ·(or, 1, 0) = {1, 2}  (symmetric)
- ·(or, 2, 0) = {2}
- ·(or, 2, 1) = {1, 2}

**Intuition:** The person may value different aspects (fun, rest, friend connections), leading to non-deterministic evaluation of whether they should go or stay. The matrix captures that multiple outcomes are genuinely possible depending on which values or circumstances end up mattering most.