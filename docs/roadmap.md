# Roadmap

Planned work beyond the 0.1.0 MVP. Nothing here is required for the current
academic deliverable; it documents intentional gaps for portfolio reviewers.

## V1 — client SDK and refresh

| Item | Status | Notes |
|------|--------|-------|
| `flags_client` package | Placeholder (not installed in 0.1.x) | V1 SDK; see `flags_client/` source tree |
| Local snapshot evaluation | Core ready | `evaluate_snapshot` in `flags_core` |
| Polling refresh with `ETag` | Not started | ADR 0002 |
| SSE `flags_changed` events | Seam only | `flags_django.sse.notify_flags_changed` is a debug no-op |
| `StaleConfigError` | Reserved | For callers that require a fresh snapshot |

## V1 — operator experience

| Item | Status |
|------|--------|
| Django + HTMX web admin | Not started |
| `rule-update` / `rule-move` CLI | Not started |
| Live SSE demo page | Not started |

## Production hardening (post-MVP)

- SDK read tokens and environment-scoped auth
- Rate limiting on snapshot and eval endpoints
- CSRF policy for debug eval (replace MVP `@csrf_exempt`)
- PostgreSQL as the recommended deployment database (full `select_for_update` semantics)
- Structured logging and metrics
- Optional `django-stubs` coverage for `flags_django`

See [scope-mvp.md](scope-mvp.md) for what is already shipped.
