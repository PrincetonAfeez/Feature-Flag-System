# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The public, stability-bearing surface is the pure evaluation core,
`flags_core` (see `flags_core.__all__`). Breaking changes to it will be called out
explicitly here.

## [Unreleased]

### Added

- Comprehensive test expansion: **211 tests**, **100% line coverage** on
  `flags_core` + `flags_django` (CI floor raised to 99%).

## [0.1.3] — 2026-06-02

### Fixed

- Strict integer coercion for `version` in snapshot parsing and service-layer flag
  definitions (rejects bool inputs, consistent with rollout/order).
- Missing required fields (`key`, `default`) map to `FlagValidationError` instead
  of generic `KeyError`.

## [0.1.2] — 2026-06-02

### Fixed

- Snapshot parsing rejects JSON booleans coerced as ints for `rollout_percentage`
  and rule `order` (uses `coerce_strict_int`).
- Service layer strict-coerces `default`; `set_rollout` rejects bool inputs.
- Missing `default` on create maps to `FlagValidationError`.

### Added

- Academic portfolio package: `docs/report.md`, `docs/glossary.md`, `docs/demo.md`,
  expanded ADRs, `SECURITY.md`, `CONTRIBUTING.md`.
- Bootstrap and verify scripts (`scripts/bootstrap.*`, `scripts/verify.*`).
- `examples/minimal_consumer/` — poll snapshot and evaluate locally (ADR 0001).
- E2E test: CLI → snapshot → eval API → local core eval agree.
- CI: `pip-audit`, coverage HTML artifact; release workflow on version tags.

### Changed

- `flags_client` removed from setuptools packages until V1 SDK ships.
- Version 0.1.2.

## [0.1.1] — 2026-06-02

### Fixed

- Schema rejects Python `bool` values masquerading as `int` for `rollout_percentage`
  and rule `order`.
- Rule `result` coercion uses strict booleans (rejects `"false"` strings) in the
  service layer.
- `evaluate()` re-normalizes pre-built `EvaluationContext` instances (invalid
  `user_id` types fail safe instead of bypassing validation).
- `update_flag`, `delete_flag`, and `delete_rule` map `IntegrityError` to
  `FlagValidationError`.

### Added

- `flagctl history --limit N` and `FlagService.get_history(..., limit=)`.
- Documented `FlagCreateResult(flag, action)` and rollout-at-100 semantics in
  README / `docs/api.md`.

### Changed

- Portfolio hardening from audit rounds: strict snapshot parsing, read-path
  validation, archive recreate/history, CLI/API error handling, `docs/api.md`,
  CI coverage floor (90%), Python 3.12–3.14 matrix.

## [0.1.0] — 2026-05-26

### Added

- Pure deterministic evaluation core (`flags_core`): `evaluate`, `evaluate_snapshot`,
  `FlagDefinition`, `RuleDefinition`, `EvaluationContext`, `EvaluationResult`, `Snapshot`.
- Deterministic SHA-256 percentage bucketing.
- Schema validation with a typed error taxonomy (`flags_core.errors`).
- Django persistence (source of truth) with a validating, audited, transactional
  service layer and snapshot versioning.
- Admin CLI (`python manage.py flagctl`).
- Read-only JSON snapshot API with `ETag` / `304 Not Modified`, plus a staff-only
  debug `eval` endpoint.
- Inspection-only Django admin.
- ADRs for the major architecture decisions; CI; test suite.
