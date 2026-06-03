# Schema

This folder contains lightweight, repository-level schema documentation for the Feature Flag System.

The files are intentionally simple and portable:

- `flag-definition.schema.json` documents the canonical feature flag object used by the pure evaluation core.
- `snapshot-response.schema.json` documents the public snapshot API response.
- `debug-eval-request.schema.json` documents the staff-only debug evaluation request body.
- `evaluation-result.schema.json` documents the debug evaluation response / core evaluation result.
- `database-schema.md` documents the Django persistence model in plain English.
- `example-snapshot.json` provides a small valid sample snapshot payload.

## Scope

These schemas are meant to help reviewers, future SDK work, documentation, and API contract checks. They do not replace the runtime validators already implemented in `flags_core.schema` or the Django model constraints in `flags_django.models`.

## Conventions

- Feature flag keys must use lowercase letters, numbers, and underscores, beginning with a lowercase letter.
- Environment slugs must start with a lowercase letter and may contain lowercase letters, numbers, underscores, and hyphens.
- Boolean fields are strict JSON booleans.
- `rollout_percentage` must be an integer from 0 through 100.
- Rule order values must be positive integers and should be unique per flag.
- Supported rule operators are enumerated in the schema files.
