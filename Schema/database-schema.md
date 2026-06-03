# Database Schema

This document describes the persistence schema implemented by the Django adapter.

## `Environment`

Stores deployment/runtime environments.

| Field | Type | Notes |
|---|---|---|
| `name` | string, max 120 | Human-readable environment name. |
| `slug` | slug string, max 80 | Unique environment identifier. |
| `created_at` | datetime | Auto-created timestamp. |
| `updated_at` | datetime | Auto-updated timestamp. |

Ordering: `slug` ascending.

## `FeatureFlag`

Stores the source-of-truth flag configuration for one environment.

| Field | Type | Notes |
|---|---|---|
| `key` | string, max 120 | Flag identifier. Unique with environment. |
| `name` | string, max 200 | Human-readable name. |
| `description` | text | Optional description. |
| `environment` | FK to `Environment` | Protected delete; related name `flags`. |
| `enabled` | boolean | Whether normal evaluation is active. |
| `kill_switch` | boolean | Safety override that forces `false`. |
| `default_value` | JSON | MVP expects a boolean default. |
| `rollout_percentage` | positive small integer | Must be between 0 and 100. |
| `archived_at` | nullable datetime | Soft-archive marker. |
| `created_at` | datetime | Auto-created timestamp. |
| `updated_at` | datetime | Auto-updated timestamp. |
| `version` | positive integer | Incremented when flag config changes. |

Constraints:

- Unique: `(environment, key)`.
- Check: `0 <= rollout_percentage <= 100`.

Ordering: `environment.slug`, then `key`.

## `FlagRule`

Stores ordered targeting rules for a feature flag.

| Field | Type | Notes |
|---|---|---|
| `flag` | FK to `FeatureFlag` | Cascade delete; related name `rules`. |
| `order` | positive integer | Rule evaluation order. Unique within flag. |
| `attribute` | string, max 120 | Context attribute to inspect. |
| `operator` | string, max 40 | Must be a supported rule operator. |
| `value` | JSON | Comparison value. Shape depends on operator. |
| `result` | boolean | Value returned when the rule matches. |
| `created_at` | datetime | Auto-created timestamp. |
| `updated_at` | datetime | Auto-updated timestamp. |

Constraint: unique `(flag, order)`.

Ordering: `flag`, then `order`.

## `AuditLog`

Stores operator history for flag changes.

| Field | Type | Notes |
|---|---|---|
| `flag` | FK to `FeatureFlag` | Protected delete; related name `audit_logs`. |
| `environment` | FK to `Environment` | Protected delete; related name `audit_logs`. |
| `action` | string, max 80 | Operator action name. |
| `actor` | string, max 150 | Free-form actor label such as `cli` or `system`. |
| `before` | nullable JSON | Previous state snapshot. |
| `after` | nullable JSON | New state snapshot. |
| `created_at` | datetime | Auto-created timestamp. |

Ordering: newest first by `created_at`, then `id`.

## `SnapshotVersion`

Stores the current snapshot version and ETag for one environment.

| Field | Type | Notes |
|---|---|---|
| `environment` | one-to-one FK to `Environment` | Cascade delete; related name `snapshot_version`. |
| `version` | positive integer | Snapshot version counter. |
| `etag` | string, max 120 | Raw token such as `production-1`; quoted at HTTP boundary. |
| `created_at` | datetime | Auto-created timestamp. |
| `updated_at` | datetime | Auto-updated timestamp. |

Ordering: `environment.slug`.
