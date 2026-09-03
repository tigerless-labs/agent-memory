---
name: non-deterministic-matrix-semantics-arity-aware-interpretation-function
abstract: "Non-deterministic matrix semantics: arity-aware interpretation function"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2022-10-29
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Avron's Non-Deterministic Matrix Semantics (Revised Definition)

A *non-deterministic logical matrix* is a tuple (X, Y, V, C, ·), where:

- X is a set of truth-values
- Y ⊆ X is a set of designated truth-values
- V is a set of propositions (universe of discourse)
- C is a set of logical connectives, each with specified arity
- ·: C × X^arity(C) → ℘(X) is the interpretation function

## Key Correction vs. Original

The interpretation function must properly account for connective arity:
**·: C × X^arity(C) → ℘(X)**

This assigns sets of truth-values to each (connective, input-tuple) pair, not to propositions and connectives separately.

## Real-World Application: Decision-Making Under Uncertainty

Non-deterministic matrices can model situations with multiple possible outcomes:

- Truth-value 0: certainty that proposition is false
- Truth-value 1: possibility that proposition is true  
- Truth-value 2: possibility that proposition is false

Example: Person deciding whether to attend a party has non-deterministic truth-values for "go" and "stay" propositions, where negation flips the possibility sets.

## References

- Avron, Arnon. Non-deterministic matrix semantics.
