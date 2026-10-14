# Codex Write reasoner session reuse — paired benchmark

Date: 2026-10-14. Code: this branch. Host: Codex CLI 0.162.0 with `gpt-5.6-sol`.
Raw results are in `write-session-reuse-2026-10-14.json`; the bounded reproducer is
`tools/write_session_benchmark.py` (one to three pairs only).

## Capability probes

- `codex exec resume <thread-id>` retained a secret supplied in the preceding headless turn.
  The resumed turn used the same thread id, including when `CODEX_HOME` contained only a staged
  copy of `auth.json` and new temporary session state.
- Every resume launched a new Codex CLI process. This is server/thread context reuse, not process
  reuse. The JSON usage counters were cumulative for the resumed thread.
- Codex continued to run with `--ignore-user-config`, `--ignore-rules`, a read-only sandbox and
  `AGENT_MEMORY_EXECUTOR=1`. The temporary `CODEX_HOME` was gone after every batch.
- Muse Code 1.4.3 accepted repeated headless `exec --session-id` turns with its echo provider, but
  the available isolated real-model credential was rejected. Real model context retention was
  therefore not established, and Muse is deliberately unsupported by this change.

## Method

Each arm started with a fresh Store, the same archived message and the same active historical
fact. A bounded instruction forced the model to issue Recall, then Read, then a SUPERSEDE. This
ensures that every sample exercises three library-controlled Agent Loop rounds. Pair order was
alternated. Host retries were disabled (`attempts=1`).

## Results

| Pair | Stateless seconds | Stateful seconds | Stateless prompt chars | Stateful prompt chars |
|---:|---:|---:|---:|---:|
| 1 | 45.064 | 48.476 | 17,882 | 6,156 |
| 2 | 44.880 | 50.580 | 17,882 | 6,156 |
| 3 | 41.493 | 45.835 | 17,882 | 6,156 |
| Mean | 43.812 | 48.297 | 17,882 | 6,156 |

Stateful reduced text passed across the Host boundary by 11,726 characters per batch (65.6%).
It did not reduce CLI process starts (3 vs 3), reasoner calls (3 vs 3), or Agent Loop rounds
(3 vs 3). Mean wall time increased by 4.485 seconds (10.2%) in this small sample, so no latency
improvement is claimed.

Stateless production calls do not request Codex JSON events, so comparable token counters were
not available without changing the baseline transport. Stateful cumulative input was
43,460–43,464 tokens, of which 36,864–39,808 were reported cached. This proves neither lower
model input tokens nor lower token cost; it only proves lower client-to-Host prompt characters.

All six arms made one Recall and one Read, wrote `deployment-window-saturday`, superseded the old
fact, retained valid archive provenance, and had no pending operations, rejection, transport
error or retry. The generated operations were byte-for-byte identical across arms.

## Interpretation

The feature is useful as an explicit experimental transport mode for larger multi-round prompts,
because it removes deterministic client-side replay while preserving Memory's Agent Loop. On the
tested Codex version it is not a wall-clock optimization and should remain opt-in. A future
process-scoped app-server transport could target CLI startup separately, but would require its own
safety and lifecycle design rather than being implied by resume support.
