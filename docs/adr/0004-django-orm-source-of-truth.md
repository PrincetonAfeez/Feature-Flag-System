# ADR 0004: Django ORM As Source Of Truth

- **Status:** Accepted
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

The MVP needs durable storage, constraints, migrations, admin integration, and
transactional writes with audit history.

## Decision

Use **Django ORM models** as the source of truth. Convert ORM rows to pure
`FlagDefinition` dataclasses before evaluation.

## Consequences

**Positive**

- Transactions, unique constraints, and migrations out of the box
- Service layer centralizes validation and audit logging
- Read-only admin prevents unvalidated writes

**Negative**

- Persistence layer is Django-specific
- Adapter conversion code required (`converters.py`)

**Follow-up**

- PostgreSQL recommended post-MVP for locking semantics
- Optional `django-stubs` typing in roadmap
