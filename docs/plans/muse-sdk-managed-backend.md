# Managed Muse SDK backend

## Problem and target

The Muse SDK can own `muse serve`, but an OpenRouter-backed agent-memory session still requires
the caller to arrange Muse routing, credentials, lifecycle hooks, MCP, a compatible model catalog,
and a proxy lifetime. Background distillation also outlives the backend that triggered it.

The target is one SDK setting: use `mem-muse` as `museBin`. An existing Muse credential or
`OPENROUTER_API_KEY` is sufficient; no second terminal, manual `muse serve`, `muse auth`, persistent
proxy, or user-settings mutation is required.

## Work units

1. Document ownership, isolation, credential, MCP, and detached-distillation boundaries.
2. Add fixture tests for missing binaries and credentials, private runtime configuration,
   OpenRouter catalog translation, transparent protocol I/O, signal forwarding, cleanup, and the
   background `muse exec` path.
3. Add a managed Muse launcher and in-process OpenRouter bridge, reusing the existing preserving
   setup pipeline for hooks, skill, Store, and optional MCP configuration.
4. Document the Node and SDK version requirements and the minimal `MuseClient.spawn` integration.
5. Verify unit/static gates and run a live two-session SDK closure when credentials are available.
6. Commit, publish a dedicated PR, and drive required CI checks green.

## Acceptance

The official SDK can spawn and close the managed launcher without an orphan backend or bridge.
SessionStart injection and boundary capture/distillation work across two fresh sessions, generated
state never changes Muse user configuration, credentials never appear in output, and every failure
layer is actionable on stderr.
