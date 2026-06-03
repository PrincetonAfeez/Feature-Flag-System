# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (MVP / academic) |

## Reporting a vulnerability

This is an academic portfolio project. If you discover a security issue, please
open a private disclosure via your course instructor or repository owner — do not
open public issues with exploit details.

## Threat model (MVP)

The MVP targets **trusted local / development** use. See README **Threat model**
and [docs/api.md](api.md).

**In scope for MVP:**

- Read-only unauthenticated snapshot endpoint (no secrets in flags)
- Staff-only debug eval endpoint with 64 KB body limit
- Validated writes through the service layer
- Dependency scanning via `pip-audit` in CI

**Known MVP trade-offs (not vulnerabilities for the stated scope):**

- No auth tokens on snapshot reads
- No rate limiting
- SQLite without full concurrent locking guarantees
- Debug eval endpoint uses `@csrf_exempt` for staff session POST (documented in API)

**Out of scope:**

- Storing secrets or credentials in flag values
- Multi-tenant production deployment without additional hardening (see roadmap)

## Dependency audit

CI runs `pip-audit -r requirements.txt` on every push. Run locally:

```bash
pip install pip-audit && pip-audit -r requirements.txt
```
