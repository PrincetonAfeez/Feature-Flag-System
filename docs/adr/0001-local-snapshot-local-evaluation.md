# ADR 0001: Local Snapshot + Local Evaluation

- **Status:** Accepted
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

Feature checks happen frequently on application hot paths. Calling a remote
service per check adds latency and creates a hard dependency on control-plane
uptime. Industry systems (LaunchDarkly, Unleash) distribute configuration and
evaluate locally.

## Decision

Clients fetch a **versioned JSON snapshot** and evaluate flags **locally** using
`flags_core`. The server distributes configuration; applications decide outcomes.

## Consequences

**Positive**

- Fast evaluation without per-check HTTP calls
- Applications keep serving last-known config during brief outages
- Same evaluator used by CLI, API debug path, and future SDK

**Negative**

- Clients may briefly serve stale configuration between polls
- Requires snapshot versioning and refresh strategy (polling / future SSE)

**Follow-up**

- ADR 0002 defines polling + SSE behind one refresh interface
- `examples/minimal_consumer/` demonstrates the pattern
