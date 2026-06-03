"""Conversions between Django persistence models and pure core dataclasses.

Rule lists use ``flag.rules.all()`` (no explicit ``.order_by``) so that when the
caller has loaded the flag with ``prefetch_related``/``Prefetch`` the cached,
pre-ordered rows are reused instead of triggering a per-flag re-query. Ordering is
guaranteed by ``FlagRule.Meta.ordering``.
"""

from __future__ import annotations

from flags_core.errors import FlagValidationError
from flags_core.models import FlagDefinition, RuleDefinition
from flags_core.schema import validate_flag_definition
from flags_django.models import FeatureFlag


def flag_model_to_core(flag: FeatureFlag, *, validate: bool = True) -> FlagDefinition:
    rules = [
        RuleDefinition(
            id=str(rule.id),
            order=rule.order,
            attribute=rule.attribute,
            operator=rule.operator,
            value=rule.value,
            result=rule.result,
        )
        for rule in flag.rules.all()
    ]
    definition = FlagDefinition(
        key=flag.key,
        name=flag.name,
        environment=flag.environment.slug,
        enabled=flag.enabled,
        kill_switch=flag.kill_switch,
        default=flag.default_value,
        rollout_percentage=flag.rollout_percentage,
        rules=rules,
        version=flag.version,
    )
    if validate:
        try:
            validate_flag_definition(definition)
        except FlagValidationError as exc:
            raise FlagValidationError(
                [f"flag '{flag.key}' in '{flag.environment.slug}': {error}" for error in exc.errors]
            ) from exc
    return definition


def flag_model_to_dict(flag: FeatureFlag) -> dict:
    # Audit/admin shape: the full mutable row, including description and
    # archived_at. This intentionally differs from flag_model_to_core(), which
    # exposes only the evaluation-relevant fields that ship in a snapshot.
    return {
        "key": flag.key,
        "name": flag.name,
        "description": flag.description,
        "environment": flag.environment.slug,
        "enabled": flag.enabled,
        "kill_switch": flag.kill_switch,
        "default": flag.default_value,
        "rollout_percentage": flag.rollout_percentage,
        "version": flag.version,
        "archived_at": flag.archived_at.isoformat() if flag.archived_at else None,
        "rules": [
            {
                "id": str(rule.id),
                "order": rule.order,
                "attribute": rule.attribute,
                "operator": rule.operator,
                "value": rule.value,
                "result": rule.result,
            }
            for rule in flag.rules.all()
        ],
    }
