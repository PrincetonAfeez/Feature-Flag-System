# ADR 0006: Core Has Zero Framework Imports

- **Status:** Accepted
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

Business logic duplicated across CLI, HTTP API, and a future client SDK leads
to inconsistent evaluation. Framework coupling makes unit testing harder.

## Decision

**`flags_core` must not import Django** (or any web framework). All surfaces
use the same pure evaluator, schema, and serialization modules.

## Consequences

**Positive**

- Single correctness surface for evaluation
- Core testable without Django settings
- Enforced by `tests/core/test_decoupling.py` (AST import scan)

**Negative**

- Adapter layer must map ORM ↔ dataclasses
- Two packages to maintain (`flags_core`, `flags_django`)

**Follow-up**

- `flags_core` is mypy-checked and listed as the stability-bearing API in CHANGELOG
- `flags_django` intentionally excluded from mypy in MVP
