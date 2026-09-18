# Evidence-linked Write plan

1. Define the evidence chain and read boundary in the design document.
2. Add tests for multiple validated write ranges, exact trace safety, bounded search, and lifecycle preservation.
3. Reuse the safe trace primitives from PR #28; implement write validation and source-bounded sparse search.
4. Run the complete local checks and 3–4 real mechanics probes. Run the fixed 12×2 comparison only if the probes recover new evidence.
5. Commit, open a new PR, and check CI.
