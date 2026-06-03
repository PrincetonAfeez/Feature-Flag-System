# Glossary

| Term | Meaning in this project |
|------|-------------------------|
| **Feature flag** | A named toggle with a default, optional targeting rules, and optional percentage rollout. |
| **Environment** | Slug-scoped namespace (e.g. `production`, `staging`) isolating flag sets. |
| **Snapshot** | Immutable JSON view of all active flags in an environment at a version. |
| **ETag** | HTTP entity tag (`"{env}-{version}"`) for conditional GET / `304 Not Modified`. |
| **Targeting rule** | Ordered predicate on context attributes; first match wins. |
| **Rollout percentage** | Share of users (by deterministic hash) receiving `true` when no rule matches. |
| **Kill switch** | Emergency off — returns `false` before other logic, even if metadata is corrupt. |
| **Fail-safe** | Runtime evaluation returns a boolean default with reason `error` instead of raising. |
| **Archive (soft delete)** | Flag row retained with `archived_at` set; can be recreated on same key. |
| **Audit log** | Append-only record of operator actions with before/after JSON snapshots. |

See also [architecture.md](architecture.md) and [api.md](api.md).
