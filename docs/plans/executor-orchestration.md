# Plan: the built-in agent — executor orchestration after OpenViking

Owner decision 2026-09-04: the Vertex endpoint of project `tigerless-seo` answers (verified at
`global` and `us-central1` with one chat call to `google/gemini-3.7-flash`), so it becomes the
library's built-in agent, and the agent's orchestration follows OpenViking's extraction loop.

## What is borrowed, and what is not

OpenViking's `ExtractLoop`: prefetch seeds the context; each round the model either calls a
tool (`read`, `search`) or returns the final operations; a tool call extends the budget by one
round; the last round carries an instruction to return operations now; one repair round each
for format, target resolution and patch errors; an unparseable final reply means "no
operations", never a crash; a file must be read before it is edited.

Kept as is: the write path's single write route, the reconcile sheet as the source of
handles, provenance as message ranges, the library computing dates, the core containing no
model client (the loop is deterministic text in the core; the executor package carries it
across the network). Not borrowed: SEARCH/REPLACE patches (an in-place write may reword, a
changed fact is a successor), page ids (handles are names), links from the model.

## Units

1. **Design.** `write.md` gains the orchestration paragraph and the knobs; ADR-002 gains the
   second amendment (built-in project). This document.
2. **Built-in project.** `executor.project` / `executor.location` defaults name
   `tigerless-seo` / `global`; the credential minter takes them from config when the
   environment does not override. Tests: the endpoint URL is built from config when no
   environment is set; environment still wins; an explicit key still short-circuits.
3. **Tool loop in the core.** A negotiation over rounds: the executor's reply is either tool
   calls (`recall`, `read`) or operations. Observations are appended to the transcript the
   next round sees; a handle that a tool returned becomes usable by `update` / `supersede`;
   the last round demands operations; a tool call on the last round earns one more round,
   once; an unknown tool is answered with the tool list; nothing parseable at the end is no
   operations. Tests: a recall round makes a handle usable that the sheet did not carry; a
   read round returns the body; the round cap holds with the one extension; an unknown tool
   does not end the loop; the transcript carries earlier observations; an empty final reply
   writes nothing and reports it.
4. **Wire it.** `distill` runs the negotiation before apply; the repair round stays as it
   is; `mem distill --json` reports rounds used per batch.

## Config knobs

| knob | default | meaning |
|---|---|---|
| `executor.project` | `tigerless-seo` | Vertex project the built-in agent bills to |
| `executor.location` | `global` | Vertex location |
| `write.max_rounds` | 3 | tool rounds per batch before operations are demanded |
| `write.tool_result_chars` | 4000 | cap on one observation's text |

## Acceptance

`mem distill --session <s>` against a store with an existing related memory lets the executor
find it by `recall`, read it, and supersede it — without the handle having been on the sheet —
and the same transcript is reproducible from a scripted executor in tests.
