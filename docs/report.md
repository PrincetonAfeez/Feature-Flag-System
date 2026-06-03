# Feature Flag System — Project Report

Academic portfolio report for the **0.1.3 MVP**. The public scope is defined in
[scope-mvp.md](scope-mvp.md). Private planning notes (gitignored) are **not** part
of the deliverable; this document and `scope-mvp.md` are canonical.

---

## Abstract

This project implements a **Django-backed feature flag system** with a **pure
Python evaluation core** (`flags_core`). Operators manage flags via CLI and
read-only admin; applications poll a versioned JSON snapshot and evaluate flags
locally. The design prioritizes **deterministic evaluation**, **fail-safe runtime
behavior**, and **architectural decoupling** between persistence and evaluation.

---

## 1. Problem statement

Feature flags let teams enable functionality for subsets of users without
redeploying application code. Production-grade systems must provide:

- Consistent evaluation across surfaces (CLI, API, future SDK)
- Safe behavior when configuration is missing or corrupt
- Auditable changes and versioned configuration distribution

**Objective:** Build an academic MVP that demonstrates these properties with
testable, documented boundaries — not a commercial LaunchDarkly replacement.

---

## 2. Related work

| System | Pattern | This MVP |
|--------|---------|----------|
| LaunchDarkly | Hosted SDK + streaming | Local snapshot + poll (ADR 0001) |
| Unleash | Server + client SDK | Core ready; client V1 |
| Flagsmith | Remote config API | Snapshot API + ETag/304 |
| Split.io | Targeting + experiments | Targeting rules + percentage rollout |

**References (concepts, not code):**

1. Fowler, M. — *Feature Toggles* (release / ops / permission toggles)
2. RFC 7232 — HTTP conditional requests (`ETag`, `304 Not Modified`)
3. Nygard, M. — *Documenting Architecture Decisions* (ADR format)
4. Industry practice — deterministic sticky bucketing for percentage rollouts

---

## 3. Design and methodology

### 3.1 Architecture

See [architecture.md](architecture.md). Dependency rule: **surfaces → adapters →
core**. `flags_core` has zero Django imports (enforced by
`tests/core/test_decoupling.py`).

### 3.2 Key decisions (ADRs)

| ADR | Decision | Module(s) |
|-----|----------|-----------|
| [0001](adr/0001-local-snapshot-local-evaluation.md) | Local snapshot + local evaluation | `serialization`, `evaluator` |
| [0002](adr/0002-polling-and-sse-behind-refresh-interface.md) | Polling baseline; SSE V1 | `api_views`, `sse` |
| [0003](adr/0003-deterministic-percentage-bucketing.md) | SHA-256 bucketing | `bucketing` |
| [0004](adr/0004-django-orm-source-of-truth.md) | ORM source of truth | `models`, `services` |
| [0005](adr/0005-fail-safe-to-default.md) | Fail-safe evaluation | `evaluator` |
| [0006](adr/0006-core-has-zero-framework-imports.md) | Core isolation | `flags_core/*` |

### 3.3 Requirements traceability

| Requirement | ADR | Implementation | Tests |
|-------------|-----|----------------|-------|
| Deterministic flag evaluation | 0003, 0005 | `flags_core/evaluator.py` | `tests/core/test_evaluator.py` |
| Percentage rollout stickiness | 0003 | `flags_core/bucketing.py` | `tests/core/test_bucketing.py` |
| Schema validation on writes | 0004 | `flags_core/schema.py`, `services.py` | `tests/core/test_schema.py`, `tests/django/test_services.py` |
| Snapshot versioning + ETag | 0001, 0002 | `SnapshotService`, `api_views` | `tests/django/test_api.py` |
| Audit trail | 0004 | `AuditLog`, `FlagService` | `tests/django/test_services.py` |
| Core decoupled from Django | 0006 | package layout | `tests/core/test_decoupling.py` |
| Fail-safe on runtime errors | 0005 | `evaluate()`, `evaluate_snapshot()` | `tests/core/test_evaluator.py` |
| Operator CLI | scope | `flagctl` | `tests/django/test_cli.py` |
| End-to-end consistency | 0001 | CLI → API → core | `tests/django/test_e2e.py` |

### 3.4 Verification methodology

1. **Unit tests** — pure core (evaluator, schema, rules, serialization)
2. **Service tests** — transactions, audit, archive/recreate, query-count guard
3. **Integration tests** — HTTP API, CLI, E2E CLI→snapshot→eval
4. **Static analysis** — ruff, mypy on `flags_core`
5. **CI matrix** — Python 3.12, 3.13, 3.14 on Ubuntu
6. **Dependency audit** — `pip-audit` on pinned `requirements.txt`

---

## 4. Results

| Metric | Value | Evidence |
|--------|-------|----------|
| Automated tests | 211 | `pytest` (see CI) |
| Line coverage | 100% | `flags_core` + `flags_django` |
| Line coverage | ≥ 90% (CI floor), ~96% typical | `pytest --cov`, CI artifact `htmlcov/` |
| Python versions | 3.12 – 3.14 | `.github/workflows/ci.yml` |
| Runtime lock | Django 5.2.14 | `requirements.txt` |
| ADRs | 6 | `docs/adr/` |
| Public API stability | `flags_core.__all__` | `CHANGELOG.md` |

**Functional evidence:** `tests/django/test_e2e.py` proves CLI writes, snapshot
reads, staff eval API, and local `evaluate_snapshot` agree on value and reason.

**Example consumer:** `examples/minimal_consumer/poll_and_eval.py` demonstrates
ADR 0001 without Django imports.

---

## 5. Learning outcomes mapping

| Typical LO | Evidence in this repo |
|------------|----------------------|
| Software architecture | Layered core/adapter design, ADRs, decoupling test |
| Database design | ORM models, constraints, migrations, audit log |
| API design | Snapshot ETag/304, documented status codes (`docs/api.md`) |
| Testing & QA | Multi-layer suite, coverage floor, E2E test |
| Security awareness | Threat model (README), `SECURITY.md`, staff-only eval |
| DevOps / CI | GitHub Actions: lint, mypy, audit, matrix test |
| Technical communication | README, report, CHANGELOG, scope/roadmap docs |

---

## 6. Limitations

- **Unauthenticated snapshot reads** — by design for MVP polling; not for secret config.
- **SQLite default** — row locking is best-effort; PostgreSQL recommended post-MVP.
- **No client SDK yet** — `flags_client/` is a V1 placeholder; not installed as a package.
- **Kill switch before validation** — intentional safety override (documented).
- **Debug eval CSRF exempt** — MVP trade-off for staff session POST; see `docs/api.md`.
- **Environment cleanup** — orphan environments persist after all flags archived.

---

## 7. Future work

See [roadmap.md](roadmap.md): client SDK, SSE refresh, HTMX admin, auth tokens,
PostgreSQL deployment guide, optional `django-stubs` for the adapter layer.

---

## 8. Reflection / lessons learned

1. **Separate the evaluator early** — keeping `flags_core` pure made CLI, API, and
   future SDK share one correctness surface.
2. **Fail loud on writes, fail safe on reads** — operators need validation errors;
   applications need uptime.
3. **Audit rounds pay off** — strict bool/int coercion caught real JSON and Python
   edge cases (`bool("false")`, `int(True)`).
4. **Document deferred scope explicitly** — portfolio reviewers trust honest
   boundaries more than unfinished features.

---

## 9. Reproducibility

**Tested with:** Python 3.12–3.14, Django 5.2.14 (pinned).

**Quick start:**

```powershell
.\scripts\bootstrap.ps1
.\scripts\verify.ps1
```

```bash
./scripts/bootstrap.sh
./scripts/verify.sh
```

**Demo assets:** run `scripts/capture-demo.ps1` or `scripts/capture-demo.sh` and follow
[demo.md](demo.md) for screenshots and screen recording steps.

---

## 10. References

1. Fowler, M. (2017). *Feature Toggles* (Feature Flags). martinfowler.com — release,
   ops, and permission toggle taxonomy.
2. Fielding, R., & Reschke, J. (2014). RFC 7232: *Hypertext Transfer Protocol
   (HTTP/1.1): Conditional Requests* — `ETag` and `304 Not Modified`.
3. Nygard, M. (2011). *Documenting Architecture Decisions* — ADR practice used in
   `docs/adr/`.
4. LaunchDarkly. *Feature flag platform documentation* — industry reference for
   local evaluation vs remote evaluation trade-offs.
5. Unleash. *Open-source feature management* — comparison baseline for snapshot +
   client SDK patterns.

---

## 11. Evaluation evidence index

| Claim | Test file(s) |
|-------|----------------|
| Kill switch overrides all | `tests/core/test_evaluator.py` |
| Bucketing deterministic / monotonic | `tests/core/test_bucketing.py` |
| Strict schema | `tests/core/test_schema.py` |
| Snapshot parse validation | `tests/core/test_serialization.py` |
| Service CRUD + audit | `tests/django/test_services.py` |
| CLI operator UX | `tests/django/test_cli.py` |
| HTTP API contracts | `tests/django/test_api.py` |
| E2E consistency | `tests/django/test_e2e.py` |
| No Django in core | `tests/core/test_decoupling.py` |
