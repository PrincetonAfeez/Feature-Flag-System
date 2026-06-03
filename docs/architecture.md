# Architecture

The system is built around one rule: **`flags_core` must not import Django.** The
pure evaluation core is a layer reused by every surface, never a surface itself.

```
   CLI (flagctl)      JSON API        future: web admin / client SDK
        \                 |                       /
         \                |                      /
          v               v                     v
   +-------------------------------------------------+
   |            flags_django (adapters)              |
   |   services.py  · converters.py  · api_views.py  |
   +-------------------------------------------------+
        |                                   ^
        | converts ORM models               | reads/writes
        v  into core dataclasses            |
   +----------------------+          +----------------------+
   |      flags_core      |          |  flags_django.models |
   |  (pure, no Django)   |          |   (source of truth)  |
   |                      |          |   Environment        |
   |  evaluator · rules   |          |   FeatureFlag        |
   |  bucketing · schema  |          |   FlagRule           |
   |  models · snapshot   |          |   AuditLog           |
   |  serialization       |          |   SnapshotVersion    |
   +----------------------+          +----------------------+
```

## Dependency direction

Surfaces depend on adapters; adapters depend on the core. Nothing flows back:
the core has no knowledge of Django, HTTP, the ORM, or management commands. The
test `tests/core/test_decoupling.py` enforces this by parsing every module under
`flags_core/` and asserting none of them import `django`.

## Request / write flow

- **Read (snapshot):** `GET /api/v1/environments/<env>/snapshot/` →
  `SnapshotService.serialize_with_etag` builds a snapshot from the ORM, converts
  each flag to a core `FlagDefinition`, and returns JSON plus an `ETag`. Clients
  poll with `If-None-Match` and get `304 Not Modified` when unchanged.
- **Write (admin):** CLI/services run inside `transaction.atomic()`, validate the
  proposed definition through `flags_core.schema`, bump the flag version and the
  environment `SnapshotVersion`, write an `AuditLog` row, and schedule the SSE
  notification with `transaction.on_commit()` (a no-op seam in the MVP).
- **Evaluate:** both the CLI `eval` command and the debug API call the *same*
  `flags_core.evaluator.evaluate`, so every surface agrees on the result.

## Key decisions

See `docs/adr/` for the full records:

- [0001](adr/0001-local-snapshot-local-evaluation.md) — local snapshot + local evaluation
- [0002](adr/0002-polling-and-sse-behind-refresh-interface.md) — polling + SSE behind one refresh interface
- [0003](adr/0003-deterministic-percentage-bucketing.md) — deterministic SHA-256 percentage bucketing
- [0004](adr/0004-django-orm-source-of-truth.md) — Django ORM as the source of truth
- [0005](adr/0005-fail-safe-to-default.md) — evaluation fails safe to the caller default
- [0006](adr/0006-core-has-zero-framework-imports.md) — the core has zero framework imports
