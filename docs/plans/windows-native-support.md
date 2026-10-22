# Native Windows support

## Goal

Run the CLI, hooks, MCP server and detached workers on native Windows so Claude Code and
Codex installed there share one Store. Today every entry point fails at import because core
serializes writers with a POSIX-only advisory lock, and every hook would fail on its POSIX-only
interval timer.

## Units

1. Update the host-adapter design with the platform contract: the same lock semantics,
   hook time bound and detached-worker lifetime on POSIX and Windows.
2. Add failing unit tests for one platform lock primitive: exclusive and shared modes,
   non-blocking contention across handles, blocking wait, release, and a locked file that
   stays readable and appendable by other handles. Existing lock, auto-Dream and
   concurrency tests keep their relationships.
3. Add failing unit tests for the hook time bound and detached launch on both platforms:
   the bound interrupts a stuck handler and is cleared afterwards; detached launches request
   a new session on POSIX and a new process group without a console window on Windows.
4. Implement the lock primitive (POSIX advisory lock; Windows byte-range lock far beyond end
   of file so ordinary reads and appends are never blocked) and route the Store, coordination
   and observation locks through it.
5. Implement the hook time bound with the POSIX interval timer where available and a
   watchdog thread elsewhere; route all detached launches through one launch posture.
6. Run the full suite, lint and types on Windows and fix remaining platform assumptions.
   Add a Windows job to CI.
7. Verify live: `mem setup` for Claude Code and Codex on Windows reaches `status: READY`;
   a memory written from one host's session is recalled from the other.

## Acceptance

- `uv run pytest`, `ruff` and `mypy` pass on Ubuntu and Windows CI.
- Shared maintenance holders still run concurrently and exclude an exclusive holder on
  both platforms.
- A hook never leaves the host waiting past its configured bound and always exits 0.
- A detached distillation or Dream worker outlives the hook process and opens no window.

## Trade-off

Opt-in cron scheduling stays POSIX-only and keeps reporting `crontab` as unavailable.
Lifecycle hooks still trigger Dreaming on Windows.
