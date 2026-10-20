# Bounded evidence recall for native Write

## Problem and target

Native Write can spend one model turn selecting a Recall candidate and another opening it before
submitting operations. That cost is useful when the abstract is ambiguous, but wasteful when a
small amount of body evidence would settle the decision immediately.

The target is an opt-in `recall_with_evidence` tool alongside Recall, Read, and Submit. It uses
the same current-memory ranking as Recall, returns only handles that become authorized on the
reconcile sheet, and spends a server-owned character budget on a small amount of body evidence.
The Agent keeps control of the ReAct loop and may continue recalling or reading whenever the
combined result is insufficient. Store writes, reconciliation, provenance, watermarks, and handle
authorization remain unchanged.

## Work units

1. Record a fixed four-case baseline on current `main`, including native tool traces, model turns,
   tokens when the Host exposes them, wall time, final memories, and authorization outcomes.
2. Update the Write negotiation and Host adapter contracts for the optional bounded tool. Add
   failing toolkit, MCP, endpoint, Host posture, configuration, and adversarial authorization
   tests before implementation.
3. Implement the combined result inside the Write toolkit by reusing Recall ranking and the
   existing Write result budget. Keep the ordinary context surface and all mutation paths out of
   the capability.
4. Run focused tests, Ruff, mypy, and the complete pytest suite. Then run a small paired Codex E2E
   on fixed cases and preserve the result whether it improves, regresses, or is neutral.
5. Commit meaningful green stages, push the isolated branch, open a Draft PR, inspect it for
   unrelated or sensitive content, and drive available CI checks green without merging.

## Promotion gate

The tool remains an additive choice only and defaults off. A follow-up may recommend broader
prompting only when
paired real-model traces show fewer model request/response turns without a correctness,
authorization, provenance, or latency regression. Tool-count reduction alone is insufficient.
