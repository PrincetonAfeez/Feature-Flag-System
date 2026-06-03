# ADR 0005: Fail Safe To Default

- **Status:** Accepted
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

Feature flag libraries run inside application request paths. Uncaught exceptions
can take down production traffic. Operators still need loud failures when
**writing** invalid configuration.

## Decision

**Runtime evaluation fails safe:** return a boolean default with reason `error`
(and log the exception). **Admin writes fail loud** via `FlagValidationError`.

Kill switch is checked **before** schema validation so operators can disable a
flag even when stored metadata is corrupt.

## Consequences

**Positive**

- Host applications stay up during unexpected evaluation errors
- Operators get validation errors on create/update/delete

**Negative**

- Some runtime misconfiguration surfaces as silent default (logged, not raised)
- Kill switch bypasses validation by design

**Follow-up**

- Debug eval API and CLI expose `reason` for troubleshooting
- Corrupt read paths return HTTP 500 on snapshot/eval (configuration error)
