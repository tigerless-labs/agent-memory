---
name: non-deterministic-matrix-semantics-correct-interpretation-function-and-structure
abstract: "Non-deterministic matrix semantics: correct interpretation function and structure"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

The interpretation function for non-deterministic logical matrices should be:

```
· : C × X^arity(C) → ℘(X)
```

Where:
- C is a set of logical connectives, each with specified arity
- X is a set of truth-values
- ℘(X) is the power set of X

A non-deterministic logical matrix is a tuple (X, Y, V, C, ·), where:
- X is a set of truth-values
- Y ⊆ X is a set of designated truth-values
- V is a set of propositions (universe of discourse)
- C is a set of logical connectives, each with specified arity
- · maps connectives and arity-tuples of truth-values to sets of truth-values

This formulation properly accounts for the arity of connectives, unlike earlier definitions that treated connectives uniformly.
