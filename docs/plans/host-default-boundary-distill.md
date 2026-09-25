# Boundary distillation that works out of the box

## Problem and target

On a fresh install, no conversation ever becomes a memory. The boundary hook launches the
executor with the store flag after the subcommand, which the CLI refuses, and the failure is
discarded. With that fixed, the default executor reaches a private model endpoint that outside
users cannot call. Around it: the session-start injection is rejected by Claude Code, setup
leaves out the skill that makes an agent recall, the Codex dialect names events Codex does not
emit, and the hook command resolves only on a shell PATH that desktop clients do not inherit.

Making the host's own CLI the default reasoner exposes two more failures, both observed: the
reasoner's own headless session fires the same hooks and distils itself recursively, and the
host injects the account email into that session, which then reaches a memory.

The target: after `mem init` and `mem setup`, a Claude Code or Codex conversation becomes
memories with no key and no further configuration, and a new session recalls them.

## Work units

1. Update CLAUDE.md Invariant 5 and the README: the host CLI is the default reasoner, an
   endpoint is opt-in configuration.
2. Tests first, then code, one per defect:
   - the launched executor call is accepted by the CLI and names its store and session;
   - the executor reasons through the host CLI unless configured for an endpoint;
   - a hook fired inside an executor session does nothing;
   - an email address absent from the distilled conversation is refused as unsupported;
   - the session-start response carries the host's required event-name field;
   - boundary hooks write nothing to stdout, which Codex parses strictly;
   - the Codex dialect and transcript format match what Codex emits;
   - setup writes an absolute hook command and installs the rendered skill for each host.
3. Verify end to end on a sandbox home: install, one conversation, a new session recalls it,
   a changed decision supersedes, and the executor's session produces no further sessions.
4. Commit, open a PR against current main, drive CI green.
