# Memory archive and management

Baseline: `34d12a2f8678d5561aba27bd8ff73c5ae4b6a258` (origin/main).
Branch: `feat/memory-archive-management`; isolated worktree, no experimental dependencies.

1. Document lifecycle and management boundaries.
2. Add failing lifecycle, failure-recovery and adapter regression tests.
3. Extend the existing Archive and shared persistence path; isolate normal reads.
4. Validate relationship additions and active correction endpoints without a new permission model.
5. Run related tests, full CI checks and a temporary-store CLI scenario; review and commit.

No real store migration, cleanup, deployment or merge is authorized by this plan.
