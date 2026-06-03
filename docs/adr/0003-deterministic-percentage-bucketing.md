# ADR 0003: Deterministic Percentage Bucketing

- **Status:** Accepted
- **Date:** 2026-05-26
- **Deciders:** Project author

## Context

Percentage rollouts must assign users consistently: the same user should not
flip in/out on every request, and increasing rollout should only **add** users
(monotonicity).

## Decision

Use **SHA-256** over `flag_key:user_id`, take the first four bytes as an integer,
and map to buckets **`0..99`**. A user is in rollout when `bucket < rollout_percentage`.

## Consequences

**Positive**

- Deterministic and sticky per user per flag
- Independent rollout per flag key
- Monotonic when percentage increases (tested)

**Negative**

- Cannot hand-pick individual users for percentage rollout — use targeting rules
- Requires `user_id` in context for partial rollouts

**Follow-up**

- Documented in README evaluation order
- Implemented in `flags_core/bucketing.py`
