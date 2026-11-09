# Claude Code native parity

## Audit

Claude Code native Write already runs through `ClaudeCodeDialect`, `ToolHostReasoner`, and the
per-batch Write MCP adapter, and fake-host system tests drive that chain. Three gaps remain:

- No authenticated Claude Write matrix exists, so New, Supersede, Skip, tool-error recovery and
  fail-closed behaviour are unverified against a real model.
- Executor selection admits native Manage only for Codex, Hermes and Muse, although Claude's
  strict-MCP transport is the one native Write already relies on.
- Claude tool runs return plain text, so a Manage review records no turn or token totals.

Out of scope: Write prompt changes, the harness MCP posture, lifecycle hooks, and any change to
T0/T1, caps, locks, claims, the Decision Ledger or the Dream Report.

## Units

1. **Design docs.** `host-adapters` lists Claude among the native Manage Hosts and states what its
   isolation does and does not cover; the README Manage section follows.
2. **Tests first.** Selection admits `claude-code` for native Manage; the Claude tool posture asks
   for a structured result and its usage is parsed; fake Claude processes drive the real Manage MCP
   adapter (scoped reads, refused ids, refused then corrected submission, incomplete run, exit,
   timeout) and the Write no-submission and tool-error cases.
3. **Code.** Admit the Host in selection; Claude's tool posture emits its JSON result, from which
   the dialect reads the final answer and usage.
4. **Live suites.** Opt-in authenticated Claude Write and Manage suites, skipped without the
   binary or the opt-in variable, each case in its own temporary Store.
5. **Evidence and TODO.** Live results go under `experiments/`; open Claude follow-ups go to
   `docs/TODO.md`.

## Acceptance

Native Manage stays opt-in and fails closed: no accepted complete submission, a Host failure or a
timeout leaves every Memory, the Ledger and the report directory untouched, and never selects text
review. Existing Codex, Hermes, Muse and Claude text paths keep their tests green.
