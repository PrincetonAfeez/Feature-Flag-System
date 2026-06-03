# Feature Flag System

[![CI](https://github.com/PrincetonAfeez/Feature-Flag-System/actions/workflows/ci.yml/badge.svg)](https://github.com/PrincetonAfeez/Feature-Flag-System/actions/workflows/ci.yml)

**Version 0.1.3** · **211 tests** · **100% coverage** · **Python 3.12–3.14**

A Django-backed feature flag MVP with a pure Python evaluation core.

The central idea: given a flag definition and an evaluation context, return a
**deterministic** `EvaluationResult` — not just a raw boolean — and do it the
same way across every surface (CLI, API, and the future client SDK).

**Academic report:** [docs/report.md](docs/report.md) · **Demo guide:** [docs/demo.md](docs/demo.md) · **Changelog:** [CHANGELOG.md](CHANGELOG.md)

## What ships in 0.1.x

This build delivers the [MVP scope](docs/scope-mvp.md):

| Layer | Package | Role |
|-------|---------|------|
| Core | `flags_core` | Pure evaluator, rules, bucketing, schema, serialization — **no Django** |
| Adapter | `flags_django` | ORM, services, audit log, snapshot versioning, admin, CLI, API |
| Example | `examples/minimal_consumer/` | Poll snapshot + evaluate locally (ADR 0001) |
| V1 placeholder | `flags_client/` | Source-only seam; **not installed** until the client SDK ships |

**Operator surface:** `python manage.py flagctl` — create, update, archive, enable/disable, kill switch, rollout, rules, eval, history, `env-list`.

**Read API:** `GET /api/v1/environments/<env>/snapshot/` with `ETag` / `304 Not Modified`.

**Debug API:** staff-only `POST .../eval/` for troubleshooting (“why this value?”).

**Quality:** 211 pytest tests, 100% line coverage on `flags_core` + `flags_django`, CI floor 99%, `pip-audit` on pinned runtime deps.

## Project layout

```text
flags_core/           Pure evaluation core (public API: flags_core.__all__)
flags_django/         Django adapter (models, services, API, flagctl, admin)
feature_flags_project/ Django project settings
examples/minimal_consumer/  Snapshot poll + local eval demo
scripts/              bootstrap.ps1|.sh, verify.ps1|.sh, capture-demo.*
tests/                core, django, E2E, and edge-case suites
docs/                 report, ADRs, API reference, scope, roadmap, demo guide
```

## Architecture

```
   CLI (flagctl)      JSON API        future: web admin / client SDK
        \                 |                       /
         \                |                      /
          v               v                     v
   +-------------------------------------------------+
   |            flags_django (adapters)              |
   +-------------------------------------------------+
        |                                   ^
        v                                   |
   +----------------------+          +----------------------+
   |      flags_core      |          |  flags_django.models |
   |  (pure, no Django)   |          |   (source of truth)  |
   +----------------------+          +----------------------+
```

`flags_core` is reused by every surface and must never import Django. See
[docs/architecture.md](docs/architecture.md) and [docs/adr/](docs/adr/).

## Quick start

### One-command bootstrap

```powershell
.\scripts\bootstrap.ps1
python manage.py createsuperuser
.\scripts\verify.ps1
```

```bash
chmod +x scripts/bootstrap.sh scripts/verify.sh scripts/capture-demo.sh
./scripts/bootstrap.sh
python manage.py createsuperuser
./scripts/verify.sh
```

`verify` runs the same gates as CI: ruff, mypy, migration check, pytest with 99% coverage floor.

### Manual setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # pinned runtime (Django 5.2.x)
pip install -e ".[dev]"                  # tests, lint, typecheck, pip-audit
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

- **`pip install -e ".[test]"`** — pytest only
- **Runtime lock:** `requirements.txt` (regenerate with `python -m piptools compile pyproject.toml -o requirements.txt --strip-extras`)
- **Python:** 3.12–3.14 (CI matrix on Ubuntu)

## Run

```powershell
python manage.py runserver             # snapshot + eval API
python manage.py flagctl list --env production
pytest                                 # full suite (config in pyproject.toml)
pytest --cov=flags_core --cov=flags_django --cov-fail-under=99
ruff check .
ruff format --check .
mypy                                   # flags_core only
```

Or use `.\scripts\verify.ps1` / `./scripts/verify.sh` for all checks at once.

## Example consumer (local evaluation)

With the server running:

```bash
python examples/minimal_consumer/poll_and_eval.py http://127.0.0.1:8000 production new_checkout user_123
```

See [examples/minimal_consumer/README.md](examples/minimal_consumer/README.md).

## CLI examples

```powershell
python manage.py flagctl create new_checkout --env production --default false
python manage.py flagctl enable new_checkout --env production
python manage.py flagctl rollout new_checkout 25 --env production
python manage.py flagctl rule-add new_checkout --env production `
    --attribute plan --operator equals --value premium --result true
python manage.py flagctl eval new_checkout --env production --user user_123 --attr plan=premium
python manage.py flagctl history new_checkout --env production --limit 10
python manage.py flagctl list --env production --strict
python manage.py flagctl env-list
```

Also: `get`, `update`, `delete`, `disable`, `kill` / `unkill`, `rule-delete`.
Run `python manage.py flagctl --help` and `flagctl --version` (reports **0.1.3**,
not Django’s version). `create` prints `created` or `recreated` when reusing an
archived row.

### CLI exit behavior

`flagctl` exits with `0` when a command succeeds. It exits non-zero for usage errors,
validation errors, missing environments, missing flags, missing rules, or runtime
command failures. Errors are reported through Django `CommandError`; normal CLI use
does not show raw debug tracebacks.

## API

See [docs/api.md](docs/api.md) for request/response shapes and status codes.

**Snapshot** (unauthenticated, for client polling):

```text
GET /api/v1/environments/<env>/snapshot/
If-None-Match: "production-1"      # 304 when unchanged
```

Unknown environments return **404** — reads never create environments.

**Debug eval** (staff session required):

```text
POST /api/v1/environments/<env>/eval/
{ "flag_key": "new_checkout", "context": { "user_id": "u1", "plan": "premium" } }
```

| Status | Meaning |
|--------|---------|
| `403` | Not staff |
| `400` | Bad JSON, missing `flag_key`, invalid `context` |
| `404` | Unknown environment or flag |
| `413` | Request body exceeds 64 KB |
| `500` | Corrupt stored flag data (configuration error) |

## Evaluation order

1. `kill_switch` → `false` (before schema validation — safety override)
2. disabled flag → `default` (`flag_disabled`)
3. targeting rules → first match wins (`targeting_match`)
4. percentage rollout via `sha256(flag_key:user_id) % 100`
5. otherwise → `default`

When `rollout_percentage` is **100**, evaluation returns `true` for every user
(`percentage_rollout`) — not the flag `default`. Evaluation **fails safe** on
unexpected errors (`reason: error`).

## Testing

| Suite | Location | Covers |
|-------|----------|--------|
| Core unit | `tests/core/` | evaluator, schema, rules, bucketing, serialization |
| Django | `tests/django/` | services, CLI, API, admin, converters, E2E |
| Architecture | `tests/core/test_decoupling.py` | `flags_core` has zero Django imports |

CI (`.github/workflows/ci.yml`): ruff, mypy, migration check, `pip-audit`, pytest
on Python 3.12–3.14, coverage HTML artifact. Tag `v*` triggers the release workflow.

## Threat model (MVP)

Intended for **trusted local / development** use:

- Snapshot reads are unauthenticated (no secrets in flags)
- Debug eval requires a **staff** user; 64 KB body cap
- CLI is a trusted operator tool; `AuditLog.actor` is a free-form label
- Strict validation on writes; fail-safe evaluation at runtime

See [SECURITY.md](SECURITY.md). Production hardening (auth tokens, rate limiting,
PostgreSQL) is [roadmap](docs/roadmap.md) V1+.

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/report.md](docs/report.md) | Academic project report + evidence index |
| [docs/scope-mvp.md](docs/scope-mvp.md) | Canonical MVP in/out scope |
| [docs/roadmap.md](docs/roadmap.md) | V1+ planned work |
| [docs/architecture.md](docs/architecture.md) | Diagrams and flows |
| [docs/api.md](docs/api.md) | HTTP API reference |
| [docs/glossary.md](docs/glossary.md) | Term definitions |
| [docs/demo.md](docs/demo.md) | Screenshot / video checklist |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev workflow |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Service API notes

- `FlagService.create_flag(...)` → **`FlagCreateResult(flag, action)`** (`create` / `recreate`)
- `FlagService.list_flags(env, strict=False)` — empty queryset for unknown env; `strict=True` raises
- `FlagService.get_history(env, key, limit=None)` — includes archived flags
- `flags_django` is excluded from mypy; `flags_core` is fully typed (`pyproject.toml`)

## Deferred to V1

See [docs/roadmap.md](docs/roadmap.md):

- `flags_client` SDK (polling, SSE, local cache)
- SSE live stream (`flags_django/sse.py` is a no-op seam today)
- Django + HTMX operator UI
- `rule-update` / `rule-move` CLI commands

## Architecture rule

`flags_core` must not import Django and must load without `DJANGO_SETTINGS_MODULE`.
Enforced by `tests/core/test_decoupling.py`.
