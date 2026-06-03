# Architecture Decision Record
## App — Feature Flag System
**Release Control Systems Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Release Control Systems group requires a feature flag MVP that can evaluate a flag deterministically across multiple surfaces. The system must support local evaluation from a snapshot, Django-backed persistence, an operator CLI, an HTTP snapshot endpoint, a staff-only debug evaluation endpoint, audit history, and safe behavior when definitions or runtime inputs are invalid.

The repo is explicitly split into two layers:

- `flags_core`: pure Python evaluation core with no Django imports.
- `flags_django`: Django adapter for ORM persistence, services, API, admin, audit log, snapshot versioning, and management command operations.

The central product requirement is that evaluation returns a structured `EvaluationResult`, not a raw boolean. That result captures value, reason, matched rule, bucket, default usage, and error information.

---

## Decisions

### Decision 1 — Keep evaluation in a pure core package

**Chosen:** Put all deterministic flag evaluation behavior in `flags_core`.

**Rejected:** Embedding evaluation directly in Django models or views.

**Reason:** The same evaluation semantics must serve the CLI, snapshot-based clients, debug API, and a future SDK. Keeping the core framework-free makes it reusable, testable, and safe to import without `DJANGO_SETTINGS_MODULE`.

---

### Decision 2 — Persist flags in Django, but ship snapshots as pure dataclasses

**Chosen:** Store environments, flags, rules, audit logs, and snapshot versions in Django models, then convert persisted rows into `FlagDefinition` and `Snapshot` dataclasses.

**Rejected:** Evaluating directly from ORM rows everywhere.

**Reason:** Django is appropriate as the source of truth. The pure snapshot model is appropriate for client polling and framework-free evaluation.

---

### Decision 3 — Return `EvaluationResult`, not `bool`

**Chosen:** Evaluation returns `EvaluationResult` with `flag_key`, `value`, `reason`, `matched_rule_id`, `bucket`, `default_used`, and `error`.

**Rejected:** Returning only true or false.

**Reason:** Feature-flag systems need explainability. Operators need to know whether a value came from a kill switch, disabled flag, targeting rule, rollout, default, missing context, missing snapshot, or failure.

---

### Decision 4 — Kill switch wins before schema validation

**Chosen:** If `kill_switch` is true, evaluation immediately returns false before validating the flag definition.

**Rejected:** Validating the definition before honoring kill switch.

**Reason:** Kill switch is a safety override. Operators must be able to disable a risky feature even when stored metadata is partially corrupt.

---

### Decision 5 — Fail safe on evaluation errors

**Chosen:** Unexpected evaluation errors are logged and converted into `EvaluationResult(reason="error")` using a safe default.

**Rejected:** Raising runtime exceptions into the host application.

**Reason:** Feature-flag evaluation should not crash the consuming application. Failure should be observable but safe.

---

### Decision 6 — Use ordered first-match targeting rules

**Chosen:** Rules are evaluated by ascending `order`; the first matching rule returns its configured result.

**Rejected:** Combining rules with implicit AND/OR logic.

**Reason:** First-match semantics are understandable for operators and easy to audit. More complex rule trees are deferred.

---

### Decision 7 — Use deterministic percentage rollout via SHA-256 bucketing

**Chosen:** Bucket users using `sha256(flag_key:user_id) % 100`.

**Rejected:** Random assignment at evaluation time.

**Reason:** Rollout assignment must be stable across requests, hosts, and client SDKs. Deterministic bucketing preserves consistency.

---

### Decision 8 — Snapshot API uses ETag polling

**Chosen:** Expose `GET /api/v1/environments/<env>/snapshot/` with ETag and `304 Not Modified` support.

**Rejected:** Shipping SSE/WebSocket push in MVP.

**Reason:** Polling is simpler for V1 of the server and aligns with a local-evaluation client design. An SSE seam exists for future push behavior.

---

### Decision 9 — Staff-only debug eval API

**Chosen:** Expose `POST /api/v1/environments/<env>/eval/` only to authenticated staff users, with a 64 KB body cap.

**Rejected:** Public unauthenticated evaluation endpoint.

**Reason:** Snapshot reads are safe for clients, but debug evaluation is an operator troubleshooting tool. It can expose reasoning and should be restricted.

---

### Decision 10 — Operator writes go through service layer

**Chosen:** CLI and future write surfaces call `FlagService` and `RuleService`, which validate definitions, write audit logs, bump versions, and mark snapshots changed.

**Rejected:** Allowing direct admin edits to live rows.

**Reason:** The audit trail and snapshot versioning must be trustworthy. The Django admin is read-only inspection in the MVP.

---

### Decision 11 — Soft archive flags instead of hard delete

**Chosen:** Delete operations set `archived_at`, disable the flag, increment version, audit the change, and remove the flag from active snapshots.

**Rejected:** Hard deletion.

**Reason:** Feature flag history matters. Archiving preserves audit and allows recreation semantics.

---

### Decision 12 — Validate strict schema boundaries

**Chosen:** Flag keys, environment slugs, booleans, rollout percentage, rule order, operator, value shape, and duplicate rule orders are validated explicitly.

**Rejected:** Accepting loosely typed JSON and relying only on database constraints.

**Reason:** Flags are runtime configuration. Bad configuration must be rejected at write time, and snapshot parsing must reject malformed payloads.

---

## Consequences

**Positive:**
- Evaluation semantics are shared across CLI, API, DB-backed service evaluation, and future SDKs.
- Core code remains framework-free and fully typed.
- Operators get explainable reasons for every result.
- Kill switch behavior is strong and immediate.
- Snapshot ETags make client polling efficient.
- Audit log and version bump behavior are centralized.
- Soft delete preserves operational history.
- Read-only admin prevents unvalidated writes.
- CI covers lint, format, mypy, migrations, audit, and coverage.

**Negative / Trade-offs:**
- MVP snapshot endpoint is unauthenticated.
- Debug eval depends on Django staff sessions.
- Rule language is flat and first-match only.
- No client SDK is installed yet.
- SSE is a no-op seam only.
- Django adapter is not mypy-scoped because django-stubs are out of scope.
- Audit actor is a free-form string, not an authenticated user FK.
- SQLite/local development settings are not production hardened.

---

## Alternatives Not Explored

- Multivariate flags.
- Rule groups and nested boolean expressions.
- Percentage rollout by segment or rule.
- Remote config SDK with local cache.
- SSE or WebSocket live updates.
- HTMX operator UI.
- Authentication tokens for snapshot reads.
- Rate limiting and tenant isolation.
- PostgreSQL-specific locking/hardening.

---

*Constitution reference: Article 1 (Python fundamentals and architecture), Article 3.3 (scope discipline), Article 4 (quality proportional to scope), Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — Feature Flag System
**Release Control Systems Group | Document 2 of 5**

---

## Overview

Feature Flag System is a Django-backed feature flag MVP with a pure Python evaluation core. It supports deterministic evaluation, rule targeting, percentage rollout, kill switches, snapshots, audit logs, a management command, and read/debug APIs.

**Package:** `feature-flag-system`  
**Version:** `0.1.3`  
**Python:** `>=3.12`  
**Runtime dependency:** Django 5.2  
**Core package:** `flags_core`  
**Django package:** `flags_django`  
**Django settings:** `feature_flags_project.settings`  
**Operator command:** `python manage.py flagctl`

---

## System Context

```text
Operator CLI                  HTTP clients                  Staff debug
   │                              │                            │
   ▼                              ▼                            ▼
flagctl                    /snapshot/ API                 /eval/ API
   │                              │                            │
   └──────────────┬───────────────┴───────────────┬────────────┘
                  ▼                               ▼
            flags_django services           flags_core evaluator
                  │                               ▲
                  ▼                               │
            Django ORM models ───── converters ───┘
                  │
                  ▼
        Environment / FeatureFlag / FlagRule
        AuditLog / SnapshotVersion
```

---

## Evaluation Flow

```text
flag + context
  │
  ▼
if kill_switch: return false / kill_switch
  │
  ▼
validate flag definition
  │
  ▼
normalize context
  │
  ▼
if disabled: return default / flag_disabled
  │
  ▼
for rules sorted by order:
    if rule matches: return rule.result / targeting_match
  │
  ▼
if rollout == 0: return default / rollout_zero
if rollout == 100: return true / percentage_rollout
if missing user_id: return default / missing_context
  │
  ▼
bucket = sha256(flag_key:user_id) % 100
  │
  ├── bucket < rollout: return true / percentage_rollout
  └── otherwise: return default / default
```

Unexpected errors return:

```text
reason = error
value = flag.default if valid bool else false
```

---

## Module-Level Structure

```text
Feature-Flag-System/
  flags_core/
    __init__.py
    bucketing.py
    errors.py
    evaluator.py
    models.py
    rules.py
    schema.py
    serialization.py
  flags_django/
    admin.py
    api_urls.py
    api_views.py
    converters.py
    models.py
    services.py
    sse.py
    management/commands/flagctl.py
    migrations/
  feature_flags_project/
    settings.py
    urls.py
    asgi.py
    wsgi.py
  flags_client/
    placeholder seam for V1 client SDK
  examples/minimal_consumer/
  tests/
  docs/
  scripts/
  pyproject.toml
  requirements.txt
  manage.py
```

---

## Core Data Structures

### `RuleDefinition`

```python
@dataclass(frozen=True)
class RuleDefinition:
    id: str
    order: int
    attribute: str
    operator: str
    value: Any
    result: bool
```

Represents one ordered targeting rule.

---

### `FlagDefinition`

```python
@dataclass(frozen=True)
class FlagDefinition:
    key: str
    name: str
    environment: str
    enabled: bool
    kill_switch: bool
    default: bool
    rollout_percentage: int
    rules: list[RuleDefinition]
    version: int
```

Evaluation-relevant flag shape that ships in snapshots.

---

### `EvaluationContext`

```python
@dataclass(frozen=True)
class EvaluationContext:
    user_id: str | None
    attributes: dict[str, Any]
```

`from_mapping()` accepts string/integer user IDs, rejects boolean user IDs, and stores all non-`user_id` keys as attributes.

---

### `EvaluationResult`

```python
@dataclass(frozen=True)
class EvaluationResult:
    flag_key: str
    value: bool
    reason: str
    matched_rule_id: str | None
    bucket: int | None
    default_used: bool
    error: str | None
```

Structured output from evaluation.

---

### `Snapshot`

```python
@dataclass(frozen=True)
class Snapshot:
    environment: str
    version: int
    generated_at: str
    flags: dict[str, FlagDefinition]
```

Payload model used by the snapshot API and future client SDK.

---

## Django Data Model

### `Environment`

- `name`
- `slug` unique
- timestamps

---

### `FeatureFlag`

- `key`
- `name`
- `description`
- `environment`
- `enabled`
- `kill_switch`
- `default_value` JSONField
- `rollout_percentage`
- `archived_at`
- timestamps
- `version`

Constraints:
- unique `(environment, key)`
- rollout percentage between 0 and 100

---

### `FlagRule`

- `flag`
- `order`
- `attribute`
- `operator`
- `value` JSONField
- `result`
- timestamps

Constraint:
- unique `(flag, order)`

---

### `AuditLog`

- `flag`
- `environment`
- `action`
- free-form `actor`
- `before`
- `after`
- `created_at`

Ordering is newest first.

---

### `SnapshotVersion`

- one-to-one `environment`
- `version`
- raw `etag`
- timestamps

`save()` stores raw token like `production-1`; `quoted_etag` wraps it for HTTP comparison.

---

## Service Layer

### `FlagService`

Responsibilities:
- list flags
- get flag
- create / recreate flag
- update flag
- enable / disable
- set kill switch
- set rollout
- soft delete
- return audit history

Important behavior:
- unknown env can return empty list or raise in strict mode
- create validates core definition first
- recreate can reuse archived rows
- every mutation audits and marks the snapshot changed
- update increments flag version

---

### `RuleService`

Responsibilities:
- add rule
- delete rule

Important behavior:
- default rule order is max existing order + 1
- proposed full flag definition is validated before rule save
- duplicate order becomes validation error
- mutations increment flag version, audit, and bump snapshot version

---

### `SnapshotService`

Responsibilities:
- build snapshot from active flags
- serialize snapshot
- return serialized snapshot with ETag
- mark snapshot changed

Important behavior:
- archived flags are excluded
- rules are prefetched in order
- snapshot version increments under `select_for_update`
- `transaction.on_commit()` notifies the SSE seam

---

### `EvaluationService`

Responsibilities:
- get persisted flag
- convert model to core definition
- call pure evaluator

---

## API Layer

### URL Routes

```text
/api/v1/environments/<env>/snapshot/
/api/v1/environments/<env>/eval/
```

### Snapshot endpoint

```text
GET /api/v1/environments/<env>/snapshot/
```

Behavior:
- returns JSON snapshot
- returns ETag header
- honors `If-None-Match: *`
- honors comma-separated ETag lists
- returns `304` when client cache is current
- returns `404` for unknown environment
- returns `500` for invalid stored flag data

Cache policy:

```text
Cache-Control: private, must-revalidate
```

---

### Debug eval endpoint

```text
POST /api/v1/environments/<env>/eval/
```

Behavior:
- staff session required
- body cap: 64 KB
- parses JSON body
- requires `flag_key`
- validates `context`
- evaluates DB-backed flag
- returns structured result fields

Status codes:
- `403` staff access required
- `413` body too large
- `400` invalid JSON, missing flag key, invalid context
- `404` unknown environment or flag
- `500` invalid stored flag data

---

## CLI Layer

Management command:

```text
python manage.py flagctl <subcommand> [options]
```

Subcommands:
- `list`
- `env-list`
- `get`
- `create`
- `update`
- `delete`
- `enable`
- `disable`
- `kill`
- `unkill`
- `rollout`
- `rule-add`
- `rule-delete`
- `eval`
- `history`

Shared options include `--env`, `--actor`, `--name`, `--description`, `--default`, `--rollout`, `--enabled`, `--kill-switch`, `--order`, `--attribute`, `--operator`, `--value`, `--result`, `--user`, `--attr`, `--strict`, and `--limit`.

---

## Rule Operators

Supported operators:
- `equals`
- `not_equals`
- `in`
- `not_in`
- `contains`
- `startswith`
- `endswith`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`

Numeric comparisons coerce both sides to floats and return false on invalid numeric input.

---

## Serialization

Snapshot serialization:
- converts dataclasses to dictionaries
- validates flag map keys match `flag.key`
- validates flag environment matches snapshot environment
- validates strict JSON booleans and integers
- rejects malformed JSON with `SnapshotError`
- emits sorted JSON for stable payloads

---

## Error Handling Strategy

Core error hierarchy:
- `FlagError`
- `FlagNotFoundError`
- `FlagAlreadyExistsError`
- `RuleNotFoundError`
- `EnvironmentNotFoundError`
- `SchemaError`
- `FlagValidationError`
- `SnapshotError`
- `StaleConfigError` reserved for V1 SDK

CLI converts `FlagError`, `ValueError`, and `KeyError` into `CommandError`.

HTTP endpoints convert domain exceptions into status-coded JSON responses.

Evaluation itself catches unexpected runtime errors and returns an `EvaluationResult` with `reason="error"`.

---

## Concurrency Model

- Flag/rule mutations use `transaction.atomic()`.
- Update/delete paths lock active flags via `select_for_update()`.
- Snapshot version increments use `select_for_update()`.
- SSE notification seam is called with `transaction.on_commit()`.
- No live streaming transport is implemented in MVP.

---

## Known Limits

- Snapshot reads are unauthenticated.
- Debug eval is staff-only but CSRF-exempt in MVP.
- No production-grade auth token model.
- No rate limiting.
- No multivariate values.
- No nested rule groups.
- No installed client SDK.
- SSE is a no-op seam.
- Django adapter excluded from mypy scope.

---

## Verification Summary

The repo configures:
- pytest-django
- coverage over `flags_core` and `flags_django`
- coverage fail-under 99
- Ruff lint
- Ruff format check
- mypy scoped to `flags_core`
- Django migration check
- pip-audit against pinned runtime dependencies
- CI matrix on Python 3.12, 3.13, and 3.14

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — Feature Flag System
**Release Control Systems Group | Document 3 of 5**

---

## Public Python Core Interface

```python
from flags_core import (
    EvaluationContext,
    EvaluationResult,
    FlagDefinition,
    RuleDefinition,
    Snapshot,
    evaluate,
    evaluate_snapshot,
)
```

---

## `evaluate()` Contract

```python
evaluate(flag: FlagDefinition, context: EvaluationContext | dict | None) -> EvaluationResult
```

Inputs:
- `flag`: one flag definition
- `context`: `EvaluationContext`, mapping, or `None`

Returns:
- `EvaluationResult`

Never intentionally raises for invalid flag definitions during normal evaluation; it fails safe into `reason="error"` unless kill switch already handled.

---

## `evaluate_snapshot()` Contract

```python
evaluate_snapshot(snapshot, flag_key, context, default=False) -> EvaluationResult
```

Behavior:
- `snapshot is None` returns caller default with `reason="no_snapshot"`
- missing flag returns caller default with `reason="flag_not_found"`
- existing flag delegates to `evaluate()`

---

## `EvaluationResult.reason` Values

| Reason | Meaning |
|---|---|
| `kill_switch` | Kill switch forced false |
| `flag_disabled` | Flag disabled, default returned |
| `targeting_match` | First matching rule returned result |
| `rollout_zero` | Rollout 0%, default returned |
| `percentage_rollout` | User included by rollout, or rollout is 100% |
| `missing_context` | Rollout requires user ID but none provided |
| `default` | No rule or rollout matched |
| `error` | Unexpected validation/runtime error |
| `no_snapshot` | Snapshot evaluation had no snapshot |
| `flag_not_found` | Snapshot did not include requested flag |

---

## Flag Schema Contract

### Flag key

Pattern:

```text
^[a-z][a-z0-9_]*$
```

### Environment

Pattern:

```text
^[a-z][a-z0-9_-]*$
```

### Rollout

Integer, not boolean, between 0 and 100.

### Rules

- rule id required
- order positive integer
- duplicate orders forbidden
- attribute required
- operator must be supported
- comparison value required
- result must be boolean

---

## Snapshot JSON Contract

Top-level shape:

```json
{
  "environment": "production",
  "version": 1,
  "generated_at": "2026-06-03T00:00:00+00:00",
  "flags": {
    "new_checkout": {
      "key": "new_checkout",
      "name": "New Checkout",
      "environment": "production",
      "enabled": true,
      "kill_switch": false,
      "default": false,
      "rollout_percentage": 25,
      "rules": [],
      "version": 1
    }
  }
}
```

Rules:
- flag map key must equal `flag.key`
- flag environment must equal snapshot environment
- booleans must be JSON booleans
- integers must be JSON integers, not booleans
- each flag is validated during load

---

## HTTP API

### Snapshot

```text
GET /api/v1/environments/<env>/snapshot/
```

Request headers:

```text
If-None-Match: "production-1"
```

Response headers:

```text
ETag: "production-1"
Cache-Control: private, must-revalidate
```

Status codes:

| Status | Meaning |
|---:|---|
| 200 | Snapshot returned |
| 304 | Client ETag already current |
| 404 | Unknown environment |
| 500 | Invalid stored flag data |

---

### Staff debug eval

```text
POST /api/v1/environments/<env>/eval/
```

Request body:

```json
{
  "flag_key": "new_checkout",
  "context": {
    "user_id": "user_123",
    "plan": "premium"
  }
}
```

Response body:

```json
{
  "flag_key": "new_checkout",
  "value": true,
  "reason": "targeting_match",
  "matched_rule_id": "12",
  "bucket": null,
  "default_used": false,
  "error": null
}
```

Status codes:

| Status | Meaning |
|---:|---|
| 200 | Evaluation returned |
| 400 | Bad JSON, missing `flag_key`, invalid context |
| 403 | Staff access required |
| 404 | Unknown environment or flag |
| 413 | Request body exceeds 64 KB |
| 500 | Invalid stored flag data |

---

## CLI Interface

### List flags

```powershell
python manage.py flagctl list --env production
python manage.py flagctl list --env production --strict
```

### Create flag

```powershell
python manage.py flagctl create new_checkout --env production --default false
```

### Update flag

```powershell
python manage.py flagctl update new_checkout --env production --name "New Checkout"
```

### Enable / disable

```powershell
python manage.py flagctl enable new_checkout --env production
python manage.py flagctl disable new_checkout --env production
```

### Kill switch

```powershell
python manage.py flagctl kill new_checkout --env production
python manage.py flagctl unkill new_checkout --env production
```

### Percentage rollout

```powershell
python manage.py flagctl rollout new_checkout 25 --env production
```

### Rule add / delete

```powershell
python manage.py flagctl rule-add new_checkout --env production `
  --attribute plan --operator equals --value premium --result true

python manage.py flagctl rule-delete new_checkout --env production 12
```

### Evaluate from CLI

```powershell
python manage.py flagctl eval new_checkout --env production --user user_123 --attr plan=premium
```

Output:

```text
new_checkout = true
reason: targeting_match
matched rule: 12
bucket: 17
```

### History

```powershell
python manage.py flagctl history new_checkout --env production --limit 10
```

### Environment list

```powershell
python manage.py flagctl env-list
```

---

## CLI Parsing Contracts

Boolean input accepts:

```text
true, 1, yes, y, on
false, 0, no, n, off
```

Rule `--value` is parsed as JSON when possible, otherwise treated as a string.

Context attributes use:

```text
--attr key=value
```

---

## Side Effects

| Operation | Side Effect |
|---|---|
| create | writes flag/rules, audit log, snapshot version bump |
| recreate | reuses archived row, clears/replaces rules, audit log, snapshot bump |
| update | validates merged definition, increments flag version, audit log, snapshot bump |
| delete | soft archives, disables flag, audit log, snapshot bump |
| rule-add | validates proposed definition, creates rule, increments version, audit log, snapshot bump |
| rule-delete | deletes rule, increments version, audit log, snapshot bump |
| snapshot API | reads environment, flags, rules, snapshot version |
| debug eval API | reads flag, converts to core, evaluates |

---

## Configuration

Runtime settings are supplied through Django settings. The MVP uses SQLite by default and installs `flags_django` into `INSTALLED_APPS`.

Important local environment variables:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`

Logging surfaces fail-safe warnings from `flags_core` and `flags_django` to console.

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — Feature Flag System
**Release Control Systems Group | Document 4 of 5**

---

## Requirements

### Runtime

- Python 3.12+
- Django 5.2+
- SQLite for local MVP use

### Development

- pytest
- pytest-django
- pytest-cov
- ruff
- mypy
- python-dotenv
- pip-audit
- pip-tools

---

## Installation

### Bootstrap scripts

PowerShell:

```powershell
.\scripts\bootstrap.ps1
python manage.py createsuperuser
.\scripts\verify.ps1
```

Bash:

```bash
chmod +x scripts/bootstrap.sh scripts/verify.sh scripts/capture-demo.sh
./scripts/bootstrap.sh
python manage.py createsuperuser
./scripts/verify.sh
```

### Manual setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev]"
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

---

## Running Locally

```powershell
python manage.py runserver
```

The API is served under:

```text
/api/v1/
```

---

## Quality Gate

```powershell
ruff check .
ruff format --check .
mypy
python manage.py makemigrations --check --dry-run
pip-audit -r requirements.txt
pytest --cov=flags_core --cov=flags_django --cov-fail-under=99 --cov-report=term-missing
```

or:

```powershell
.\scripts\verify.ps1
```

---

## Standard Operating Procedures

### Create a flag

```powershell
python manage.py flagctl create new_checkout --env production --default false
```

Expected:

```text
created production:new_checkout
```

If an archived row is reused:

```text
recreated production:new_checkout
```

---

### Enable the flag

```powershell
python manage.py flagctl enable new_checkout --env production
```

---

### Set rollout

```powershell
python manage.py flagctl rollout new_checkout 25 --env production
```

---

### Add targeting rule

```powershell
python manage.py flagctl rule-add new_checkout --env production `
  --attribute plan --operator equals --value premium --result true
```

---

### Evaluate from CLI

```powershell
python manage.py flagctl eval new_checkout --env production --user user_123 --attr plan=premium
```

---

### Check snapshot

```text
GET http://127.0.0.1:8000/api/v1/environments/production/snapshot/
```

Expected:
- 200 with JSON snapshot
- ETag header
- `Cache-Control: private, must-revalidate`

---

### Check ETag behavior

First request:

```text
GET /api/v1/environments/production/snapshot/
```

Record:

```text
ETag: "production-1"
```

Second request:

```text
GET /api/v1/environments/production/snapshot/
If-None-Match: "production-1"
```

Expected:

```text
304 Not Modified
```

---

### Debug evaluation from API

Log in as staff, then send:

```json
{
  "flag_key": "new_checkout",
  "context": {"user_id": "user_123", "plan": "premium"}
}
```

Expected:

```json
{
  "flag_key": "new_checkout",
  "value": true,
  "reason": "targeting_match",
  "matched_rule_id": "...",
  "bucket": null,
  "default_used": false,
  "error": null
}
```

---

### Review audit history

```powershell
python manage.py flagctl history new_checkout --env production --limit 10
```

---

### Soft delete / archive

```powershell
python manage.py flagctl delete new_checkout --env production
```

Expected behavior:
- sets `archived_at`
- disables flag
- increments version
- writes audit log
- bumps snapshot version
- removes flag from active snapshot

---

## Health Checks

### Core import without Django

```powershell
python -c "from flags_core import evaluate, FlagDefinition; print('ok')"
```

Expected:

```text
ok
```

---

### Migration check

```powershell
python manage.py makemigrations --check --dry-run
```

Expected:

```text
No changes detected
```

---

### CLI version

```powershell
python manage.py flagctl --version
```

Expected:

```text
0.1.3
```

---

### Snapshot unknown environment

```text
GET /api/v1/environments/does-not-exist/snapshot/
```

Expected:

```text
404
```

---

### Debug eval non-staff

```text
POST /api/v1/environments/production/eval/
```

Expected:

```text
403 staff access required
```

---

## Common Failure Modes

### Flag validates in DB but evaluation returns `reason: error`

Possible causes:
- corrupted JSON field
- bad rule value shape
- invalid rollout percentage from direct DB edit
- bypassed service layer

Resolution:
1. Inspect admin read-only view.
2. Check audit history.
3. Correct through service/CLI where possible.
4. Avoid direct DB writes.

---

### Snapshot does not update after write

Expected service path should call `SnapshotService.mark_snapshot_changed()`.

Check:
- write occurred through `FlagService` or `RuleService`
- transaction committed
- snapshot version row exists
- ETag changed

---

### Unknown environment during list

Default `list` behavior returns a warning and no flags. Use `--strict` when absence should fail the command.

---

### Debug API returns 413

Cause: request body exceeds 64 KB.

Resolution:
- reduce context size
- debug one user/flag scenario at a time

---

### Rule add fails with duplicate order

Cause: selected `--order` already exists on that flag.

Resolution:
- omit `--order` to append automatically
- delete/recreate rule order manually
- defer rule reordering until V1 commands exist

---

### Snapshot endpoint returns 500

Cause: invalid stored flag data caused conversion/validation failure.

Resolution:
- inspect rows through admin
- check audit history
- repair using service layer
- avoid direct writes

---

## Recovery Procedures

### Emergency disable

```powershell
python manage.py flagctl kill new_checkout --env production
```

Kill switch forces false even before schema validation during evaluation.

---

### Restore a killed flag

```powershell
python manage.py flagctl unkill new_checkout --env production
```

Then verify:

```powershell
python manage.py flagctl eval new_checkout --env production --user user_123
```

---

### Roll back rollout

```powershell
python manage.py flagctl rollout new_checkout 0 --env production
```

---

### Recreate archived flag

```powershell
python manage.py flagctl create new_checkout --env production --default false
```

When an archived row exists, service returns action `recreate`.

---

## Maintenance Notes

- Do not add Django imports to `flags_core`.
- Do not bypass `FlagService` or `RuleService` for writes.
- Keep admin read-only until write flows enforce validation/audit/versioning.
- Add tests before changing evaluation order.
- Add tests before changing rollout bucketing.
- Add tests before changing API status codes.
- Preserve ETag quoting behavior.
- Keep snapshot JSON strict about booleans and integers.
- Treat snapshot unauthenticated access as MVP/local-only.
- Move auth tokens/rate limits/PostgreSQL hardening to V1 work.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — Feature Flag System
**Release Control Systems Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because feature flag systems sit directly on the boundary between deployment safety and runtime behavior. The project needed a core evaluator that was small, deterministic, and reusable, plus an adapter layer that handled persistence, operators, audit history, snapshots, and HTTP access.

The cleanest separation was to keep `flags_core` pure and push all Django concerns into `flags_django`. That makes evaluation rules easy to test independently, while still giving the MVP a practical operator workflow through Django models and management commands.

Returning `EvaluationResult` instead of `bool` was the most important product decision. A boolean tells the application what to do. A result tells the operator why it happened.

---

## What Was Intentionally Omitted

**Client SDK:** A placeholder seam exists, but installed SDK behavior is deferred.

**SSE push:** A no-op function exists so services already call a future seam, but transport is deferred.

**Operator web UI:** CLI and admin inspection are sufficient for MVP.

**Multivariate flags:** Boolean flags only keep evaluation rules clear.

**Nested rule groups:** First-match ordered rules are easier to reason about.

**Production authentication:** Snapshot reads are unauthenticated in MVP because no secrets should be stored in flags.

**Rate limiting:** Deferred with production hardening.

**PostgreSQL hardening:** SQLite/local setup is acceptable for the academic MVP.

---

## Biggest Weakness

The biggest weakness is production security posture. Snapshot reads are unauthenticated, debug eval is staff-session based, and there is no rate limiting or token model. That is acceptable only because the README frames the project as a trusted local/development MVP.

The second weakness is that the rule language is intentionally simple. Ordered first-match rules are easy to audit, but they cannot express nested boolean logic or rich segmentation.

The third weakness is client behavior. Snapshot polling is designed, but there is no packaged client SDK yet.

---

## Scaling Considerations

**If used beyond local development:**
- add token auth for snapshot reads
- add rate limiting
- move to PostgreSQL
- add structured audit actors
- harden settings and deployment

**If rule complexity grows:**
- introduce rule groups
- define AND/OR semantics explicitly
- version rule schemas
- preserve first-match behavior as a compatibility layer

**If clients grow:**
- build `flags_client` package
- add snapshot polling cache
- add stale config behavior
- add SSE support behind existing seam

**If operations grow:**
- add HTMX operator UI
- add rule reorder/update commands
- add environment-level dashboards
- add metrics for evaluation errors and snapshot versions

---

## What the Next Refactor Would Be

1. **Install the client SDK** — package `flags_client`, support polling, ETag cache, local evaluation, and stale snapshot policy.

2. **Add authenticated snapshot access** — introduce read tokens or environment-scoped API keys.

3. **Add operator UI** — provide a web workflow for creating flags and managing rules without losing service-layer validation.

4. **Add rule update / rule move** — avoid delete/recreate workflows when editing rules.

5. **Add production deployment profile** — PostgreSQL, rate limits, structured logging, and secure Django settings.

---

## What This Project Taught

- **Evaluation must be explainable.** The reason code is as important as the boolean value.

- **Safety overrides need priority.** Kill switch must work even when metadata is questionable.

- **Framework boundaries matter.** A pure evaluator is easier to test and reuse than ORM-bound logic.

- **Snapshots are contracts.** Snapshot shape, strict JSON typing, ETag behavior, and versioning define the future SDK interface.

- **Audit is part of correctness.** Feature flag changes affect runtime behavior, so writes must be validated, versioned, and recorded.

- **MVP scope must be explicit.** It is honest to ship polling without SSE and CLI without a web UI when those omissions are documented.

- **Fail-safe behavior should still be observable.** Runtime evaluation should not crash host apps, but errors should be logged and exposed in structured results.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for Feature Flag System.*
