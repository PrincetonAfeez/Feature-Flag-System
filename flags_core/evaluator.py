"""Pure deterministic feature flag evaluation."""

from __future__ import annotations

import logging
from typing import Any

from flags_core.bucketing import bucket_user
from flags_core.models import EvaluationContext, EvaluationResult, FlagDefinition, Snapshot
from flags_core.rules import rule_matches
from flags_core.schema import validate_flag_definition

logger = logging.getLogger(__name__)


def evaluate(flag: FlagDefinition, context: EvaluationContext | dict | None) -> EvaluationResult:
    """Evaluate one flag against a context with no framework or database access.

    When ``kill_switch`` is set, evaluation returns ``false`` immediately — before
    :func:`flags_core.schema.validate_flag_definition` runs. That is intentional:
    operators must be able to disable a flag even when stored metadata is corrupt.

    Otherwise ``flag`` must satisfy ``validate_flag_definition``; invalid definitions
    fail safe to a boolean default (reason ``error``).
    """
    if flag.kill_switch:
        return EvaluationResult(flag_key=flag.key, value=False, reason="kill_switch")

    try:
        validate_flag_definition(flag)
        evaluation_context = _normalize_context(context)

        if not flag.enabled:
            return EvaluationResult(
                flag_key=flag.key,
                value=flag.default,
                reason="flag_disabled",
                default_used=True,
            )

        for rule in sorted(flag.rules, key=lambda item: item.order):
            if rule_matches(rule, evaluation_context):
                return EvaluationResult(
                    flag_key=flag.key,
                    value=rule.result,
                    reason="targeting_match",
                    matched_rule_id=rule.id,
                )

        if flag.rollout_percentage == 0:
            return EvaluationResult(
                flag_key=flag.key,
                value=flag.default,
                reason="rollout_zero",
                default_used=True,
            )

        if flag.rollout_percentage == 100:
            return EvaluationResult(flag_key=flag.key, value=True, reason="percentage_rollout")

        if not evaluation_context.user_id:
            return EvaluationResult(
                flag_key=flag.key,
                value=flag.default,
                reason="missing_context",
                default_used=True,
            )

        bucket = bucket_user(flag.key, evaluation_context.user_id)
        if bucket < flag.rollout_percentage:
            return EvaluationResult(
                flag_key=flag.key,
                value=True,
                reason="percentage_rollout",
                bucket=bucket,
            )

        return _default_result(flag, bucket=bucket)
    except Exception as exc:  # fail safe to default (ADR 0005); never crash the host app
        # Logged (not swallowed silently) so a masked bug stays observable.
        logger.warning("evaluation of flag '%s' failed; returning default", flag.key, exc_info=exc)
        return EvaluationResult(
            flag_key=flag.key,
            value=_safe_default(flag),
            reason="error",
            default_used=True,
            error=str(exc),
        )


def evaluate_snapshot(
    snapshot: Snapshot | None,
    flag_key: str,
    context: EvaluationContext | dict | None,
    default: bool = False,
) -> EvaluationResult:
    """Evaluate a flag from a local snapshot, failing safely to caller default."""
    if snapshot is None:
        return EvaluationResult(
            flag_key=flag_key,
            value=default,
            reason="no_snapshot",
            default_used=True,
        )

    flag = snapshot.flags.get(flag_key)
    if flag is None:
        return EvaluationResult(
            flag_key=flag_key,
            value=default,
            reason="flag_not_found",
            default_used=True,
        )

    return evaluate(flag, context)


def _default_result(flag: FlagDefinition, bucket: int | None = None) -> EvaluationResult:
    return EvaluationResult(
        flag_key=flag.key,
        value=flag.default,
        reason="default",
        bucket=bucket,
        default_used=True,
    )


def _normalize_context(context: EvaluationContext | dict | None) -> EvaluationContext:
    if context is None:
        return EvaluationContext.from_mapping(None)
    if isinstance(context, EvaluationContext):
        data: dict[str, Any] = dict(context.attributes)
        if context.user_id is not None:
            data = {"user_id": context.user_id, **data}
        return EvaluationContext.from_mapping(data)
    return EvaluationContext.from_mapping(context)


def _safe_default(flag: FlagDefinition) -> bool:
    """Return the flag default when it is a bool; otherwise False."""
    return flag.default if isinstance(flag.default, bool) else False
