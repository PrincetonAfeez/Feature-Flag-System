# ADR 0002: Polling + SSE Behind Refresh Interface

- **Status:** Accepted (polling shipped; SSE deferred to V1)
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

Local snapshots must refresh when operators change flags. Polling is simple and
robust; SSE reduces latency but adds connection lifecycle complexity.

## Decision

**Polling with `ETag` / `304 Not Modified` is the MVP baseline.** SSE is deferred
to V1 and must sit behind the same snapshot refresh contract (`SnapshotService`,
`notify_flags_changed` seam).

## Consequences

**Positive**

- Cheap when configuration is stable
- Standard HTTP caching semantics (RFC 7232)
- SSE can be added without changing evaluator or persistence

**Negative**

- Worst-case staleness equals poll interval
- SSE not implemented in MVP (`flags_django/sse.py` is a no-op)

**Follow-up**

- V1: implement SSE consumer in `flags_client`
- See `docs/roadmap.md`
