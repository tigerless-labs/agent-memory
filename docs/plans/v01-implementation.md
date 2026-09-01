# Plan: v0.1 implementation (M0 → M8)

> Working artifact. Drives roadmap-v01.md to code. Hermes host deferred by owner
> (2026-09-01): P1 runs on `claude -p` + `codex exec` only; Hermes rows stay unfilled.

## Branch / PR sequence (stacked; owner merges)

| PR | Branch | Scope |
|---|---|---|
| 1 | `feat/m0-m2-core` | M0 workspace+config+CI, M1 storage, M2 index pipeline |
| 2 | `feat/m3-cli-recall` | M3 CLI + recall pipeline |
| 3 | `feat/m4-m6-write-manage` | M4 triggers/hooks, M5 MCP, M6 sleep Manage |
| 4 | `feat/m7-m8-harness` | M7 replay driver + hosts, M8 W-option benchmark run |

Each branch is based on the previous one; every PR must be green before the next opens.

## Language

ADR-007 (Python 3.12 + uv) is still `proposed`. Implementation proceeds on it because the
roadmap's M0 presumes a uv workspace; if the owner signs a different language the core
contract is language-independent by construction. **Assumption recorded, not resolved.**

## Package split (M0)

`core` carries every algorithm and has **zero runtime dependencies** — that is what makes the
"no LLM client in core" CI check assertable rather than aspirational. `cli`, `mcp`,
`adapters`, `harness` depend on core and carry no algorithm (Invariant 8).

## Unit ordering

Every milestone: design-doc delta (if any) → failing tests → code → green → commit.
Per-file test map lands in `docs/testing.md` as each milestone closes.

## Benchmark scope (M8)

R held fixed across all runs (Invariant 9); only W varies. W0 (no memory) is the control.
Suite: LongMemEval-S sampled subset, stratified by question type, fixed seed. Judge is an
LLM host call, held identical across arms. Deliverable: per-arm accuracy + cost/latency
telemetry, plus the R-config hash equality assertion that licenses attribution.
