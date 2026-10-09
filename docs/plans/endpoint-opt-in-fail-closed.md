# Endpoint opt-in and fail-closed reasoning

## Problem and target

Host reasoning is the configured default, but the endpoint fallback still embeds a Tigerless
project, accepts incomplete configuration, and turns authentication, transport, and malformed
response failures into an empty model reply. Distillation can then settle its watermark without
writing the memory the conversation should have produced.

The target is one portable default and one explicit opt-in: boundary distillation and Manage use
the installed host unless the Store selects an endpoint; endpoint users supply their own endpoint
credential or their own Google Cloud project and IAM access; every reasoner failure is reported
without exposing credentials; failed distillation leaves the backlog unsettled for retry.

## Work units

1. Update the host-adapter design boundary, repository invariant, and setup runbook to define host
   defaulting, user-owned endpoint configuration, and fail-closed execution.
2. Add failing tests for blank portable endpoint defaults, explicit endpoint configuration,
   authentication and transport errors, host failures, CLI error rendering, and watermark
   preservation.
3. Implement structured reasoner failures, remove the organization project default, validate
   endpoint opt-in at execution and diagnostics, and keep failed backlog eligible for retry.
4. Run focused tests, the complete unit/system suite, lint, typing, and an offline CLI failure
   exercise; then commit, push, open the PR, and drive required CI checks green.
