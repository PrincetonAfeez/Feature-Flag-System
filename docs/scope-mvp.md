# MVP scope

This document is the **canonical public specification** for the 0.1.x MVP.
Private planning files (`FFS full_scope.txt`, etc.) are gitignored development
notes and are **not** part of the submission deliverable.

## In scope (built)

- **`flags_core`** — pure deterministic evaluator, rules engine, bucketing,
  schema validation, snapshot serialization (no Django imports)
- **`flags_django`** — ORM models, validating service layer, audit log,
  snapshot versioning, read-only admin
- **`flagctl` CLI** — create, update, delete (soft-archive), enable/disable,
  kill switch, rollout, rules, eval, history, `env-list`
- **Snapshot API** — `GET /api/v1/environments/<env>/snapshot/` with `ETag` /
  `304 Not Modified`
- **Debug eval API** — staff-only `POST .../eval/` for troubleshooting
- **Tests** — core, services, CLI, API, admin, decoupling; CI on Python 3.12–3.14
- **ADRs** — architecture decisions under `docs/adr/`

## Out of scope (V1+)

See [roadmap.md](roadmap.md) for planned follow-ups:

- Python client SDK (`flags_client/`) with polling and SSE refresh
- Live SSE push stream (the `notify_flags_changed` seam exists as a no-op)
- Django + HTMX operator UI
- `rule-update` / `rule-move` commands
- Auth tokens, rate limiting, environment permissions

## MVP boundaries (by design)

- Snapshot reads are **unauthenticated** (read-only public config)
- SQLite is the default database; row locking is best-effort on SQLite
- `flags_django` is not mypy-checked (see README); `flags_core` is fully typed
- Evaluation **fails safe** to the flag default at runtime; writes fail loudly
- Environment rows **persist** after all flags are archived (snapshot returns an
  empty `flags` object). Use `flagctl env-list` to inspect environments and active
  flag counts; automatic environment cleanup is out of MVP scope.
