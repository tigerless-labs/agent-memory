---
created: 2026-09-03T01:43:33.915801395Z
updated: 2026-09-03T01:43:33.915801395Z
weight: 1.0
last_accessed: 2026-09-03T01:43:33.915801395Z
access_count: 0
pinned: false
links:
- example-3-valued-paraconsistent-matrix
abstract: Formal definition of non-deterministic logical matrices accounting for connective arity; interpretation function assigns sets of truth-values to connectives and tuples based on arity
---

## Corrected Definition

The key correction: the interpretation function must account for the **arity of each connective**.

**Formal Definition:**
A *non-deterministic logical matrix* is a tuple (X, Y, V, C, ·), where:
- X is a set of truth-values
- Y ⊆ X is a set of *designated truth-values*
- V is a set of propositions
- C is a set of logical connectives, each with a specified arity
- ·: C × X^{arity(C)} → P(X) is a function that assigns a set of truth-values in X to each connective c ∈ C and a tuple of truth-values in X^{arity(c)}

This allows each connective to take an appropriate number of arguments based on its arity, and return a non-deterministic set of possible truth-values.

## Note on Semantics
The definition does **not yet** specify how to obtain a consequence relation from a non-deterministic matrix — that is a separate semantic definition (not yet worked out in the conversation).