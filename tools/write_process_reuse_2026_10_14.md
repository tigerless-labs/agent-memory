# Codex Write single-process reuse — three-way paired benchmark

Date: 2026-10-14. Branch: `feat/write-reasoner-session-reuse`. Host: Codex CLI 0.162.0
with `gpt-5.6-sol`. Raw results: `write_process_reuse_2026_10_14.json` and the final
security-hardened C rerun in `write_process_reuse_hardened_2026_10_14.json`. Reproducer:
`write_process_reuse_benchmark.py`.

## Capability and safety probes

- The stable app-server stdio protocol supported one `initialize`, one ephemeral `thread/start`,
  and repeated `turn/start` calls in the same process. A two-turn nonce probe retained the first
  turn's value and used one process.
- An auth-only temporary `CODEX_HOME` worked without copying personal config, rules, memories,
  session history, state databases, or model cache. The temporary state was removed after close.
- The process received `AGENT_MEMORY_EXECUTOR=1`; Store and observation environment variables
  were removed. `HOME` and XDG directories pointed to the batch scratch directory.
- The thread used `approvalPolicy=never`, an ephemeral thread, a read-only sandbox with tool
  network disabled, and an empty scratch working directory. Codex apps, plugins, hooks, personal
  memory, multi-agent, shell/exec, skills, browser/computer, image and goal features were disabled.
- Any server-initiated request or item other than user text, agent text, or reasoning fails the
  turn. No Host tool item or server request appeared in the five real Write runs.
- Each batch starts the process directly over stdio and destroys it in `close()`; there is no
  daemon and no state is shared across batches.

The local sandbox used to run this investigation blocks Codex workspace-routing network calls,
so real probes were run with the approved unsandboxed command path. The app-server process itself
still enforced the explicit read-only/no-network tool sandbox above.

## Method

Every arm used a fresh Store, the same archived message, the same active historical fact, the same
model, and the same forced three-reply protocol: library Recall, library Read, then SUPERSEDE. The
Memory library executed both looks, validated the operation, wrote the Store, and advanced the
Watermark. Host retries were disabled. Five triplets used rotating A/B/C order to reduce order and
cache bias.

- A — production stateless `codex exec`: full accumulated prompt and a fresh process per round.
- B — PR #105 CLI-resume stateful: incremental prompt, but a fresh `codex exec resume` process per
  round.
- C — app-server: incremental prompt, one short-lived process and one ephemeral thread per batch.

Stateless now requests Codex JSON events so all three arms use the same native usage counters.
For B, counters are thread-cumulative, so the report subtracts the preceding call to obtain
per-turn increments. A and C already report per-request usage.

## Raw interleaved wall-clock results

| Pair | Order | A stateless | B CLI resume | C app-server |
|---:|:---:|---:|---:|---:|
| 1 | A → B → C | 48.367 s | 49.588 s | 15.695 s |
| 2 | B → C → A | 45.275 s | 50.827 s | 16.521 s |
| 3 | C → A → B | 43.330 s | 49.179 s | 15.066 s |
| 4 | A → B → C | 44.963 s | 49.448 s | 14.284 s |
| 5 | B → C → A | 46.772 s | 54.126 s | 17.644 s |
| **Mean** | | **45.741 s** | **50.634 s** | **15.842 s** |
| **Median** | | **45.275 s** | **49.588 s** | **15.695 s** |

After this interleaved run, C-only security hardening additionally isolated `HOME`/XDG, removed
Store/observation environment variables, and disabled remaining exec/image/Goal tool context.
A and B do not import or execute that code path, so they were not re-spent. Five final-code C
reruns were **17.098, 19.537, 14.719, 14.588, and 15.506 seconds** (mean 16.290, median 15.506).
The result below uses those final-code C values. Final C reduced median wall time by **65.8% vs A**
and **68.7% vs B**. Every final C sample was faster than every A or B sample; this is larger than
the 15% continuation target in this bounded task.

## Work and transport metrics

| Metric (median or invariant) | A stateless | B CLI resume | C app-server |
|---|---:|---:|---:|
| Wall time | 45.275 s | 49.588 s | 15.506 s |
| CLI/app-server process starts | 3 | 3 | 1 |
| Reasoner/model requests | 3 | 3 | 3 |
| Agent Loop rounds | 3 | 3 | 3 |
| Prompt characters sent | 17,882 | 6,156 | 6,156 |
| Incremental input tokens | 46,910 | 43,466 | 25,375 |
| Cached input tokens | 33,792 | 36,736 | 22,144 |
| Recall / Read | 1 / 1 | 1 / 1 | 1 / 1 |
| Writes | 1 SUPERSEDE | 1 SUPERSEDE | 1 SUPERSEDE |
| Host tool items | not exposed | not exposed | 0 |

C reduced median input tokens by **45.9% vs A** and **41.6% vs B**. Prompt characters are the
same as B; the further token reduction comes from replacing the generic coding-agent base prompt
with a bounded distillation instruction and disabling unrelated Host tools. Cached tokens still
count as model input and still incur request/compute latency; cache hits varied substantially and
did not explain away the wall-time result.

For final C, median process initialization was 3.485 seconds and median summed model-turn duration
was 12.066 seconds, 77.8% of median batch wall time. Thus model/network work remains the largest
residual cost. The optimization does not reduce the three necessary Memory decisions; it removes
two process/Host initializations and unrelated model context.

## Correctness and failure behavior

All 15 interleaved arms and all five final-code C reruns produced the same final operation and
durable result:

- exactly one Recall and one Read were executed by `agentic.negotiate()`;
- `deployment-window-saturday` was written and the prior fact was superseded;
- archive Provenance was present and valid;
- no pending or rejected operation, transport error, retry, or duplicate memory occurred;
- every C turn used the same thread id, and every batch released its temporary Codex home;
- C emitted no native tool item and accepted no server-side tool request.

Unit coverage rejects non-ephemeral threads, Host tool items, server-side tool requests, failed
turns, empty messages, mismatched/unsupported transports, and reuse after close. The existing
#80 regression suite continues to prove that empty/illegal output and exhausted tool rounds leave
the Watermark and backlog untouched, while explicit Skip completes normally. Process cleanup is
in the existing `negotiate()` `finally` path and in constructor failure cleanup.

Final validation: 821 tests passed, 1 skipped, total coverage 90.37%; `ruff check .` and full
package `mypy` both passed. The test suite's loopback cron acceptance test was run outside the
restricted tool sandbox because that sandbox forbids binding a local TCP socket.

## Interpretation

CLI resume was slower because it retained the server-side thread but still launched three CLI
processes. Its first/resume calls also restored thread state and resent the model-visible history;
median incremental input fell only 7.3% from A even though client prompt characters fell 65.6%.
Cached input remained part of every request. The resume arm therefore paid restoration and process
startup without reducing model request count or model-visible context enough to recover that cost.

App-server is a real process-reuse optimization: one process owns three turns. It also provides a
supported per-turn usage stream and permits the pure text reasoner to omit Codex coding tools and
instructions. It remains an explicit experimental mode because app-server is still marked
experimental by Codex CLI 0.162.0, and the optimization depends on feature flags that future CLI
versions may rename. Any protocol or feature mismatch fails closed; it never falls back to a new
context-less session.
