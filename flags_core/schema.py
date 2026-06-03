"""Validation for feature flag definitions."""

from __future__ import annotations

import re

from flags_core.errors import FlagValidationError
from flags_core.models import FlagDefinition, RuleDefinition
from flags_core.rules import SUPPORTED_OPERATORS

FLAG_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ENVIRONMENT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _is_int_not_bool(value: object) -> bool:
    """True when ``value`` is a genuine int (Python bool subclasses int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def coerce_strict_bool(value: object, field_name: str) -> bool:
    """Return a bool or raise ``FlagValidationError`` — rejects bool-like strings."""
    if isinstance(value, bool):
        return value
    raise FlagValidationError([f"{field_name} must be a boolean value"])


def coerce_strict_int(value: object, field_name: str) -> int:
    """Return an int or raise ``FlagValidationError`` — rejects bool (subclass of int)."""
    if not _is_int_not_bool(value):
        raise FlagValidationError([f"{field_name} must be an integer"])
    assert isinstance(value, int)
    return value


def validate_flag_definition(flag: FlagDefinition) -> None:
    errors: list[str] = []

    if not flag.key:
        errors.append("flag key is required")
    elif not FLAG_KEY_RE.match(flag.key):
        errors.append("flag key must use lowercase letters, numbers, and underscores")

    if not flag.environment:
        errors.append("environment is required")
    elif not ENVIRONMENT_RE.match(flag.environment):
        errors.append("environment must be slug-like")

    if not isinstance(flag.default, bool):
        errors.append("default must be a boolean value")

    if not isinstance(flag.enabled, bool):
        errors.append("enabled must be a boolean value")

    if not isinstance(flag.kill_switch, bool):
        errors.append("kill_switch must be a boolean value")

    if not _is_int_not_bool(flag.rollout_percentage):
        errors.append("rollout_percentage must be an integer")
    elif not 0 <= flag.rollout_percentage <= 100:
        errors.append("rollout_percentage must be between 0 and 100")

    seen_orders: set[int] = set()
    for rule in flag.rules:
        _validate_rule(rule, errors)
        if rule.order in seen_orders:
            errors.append(f"duplicate rule order: {rule.order}")
        seen_orders.add(rule.order)

    if errors:
        raise FlagValidationError(errors)


def _validate_rule(rule: RuleDefinition, errors: list[str]) -> None:
    label = f"rule {rule.id or rule.order}"

    if not rule.id:
        errors.append(f"{label}: id is required")
    if not _is_int_not_bool(rule.order) or rule.order < 1:
        errors.append(f"{label}: order must be a positive integer")
    if not rule.attribute:
        errors.append(f"{label}: attribute is required")
    if rule.operator not in SUPPORTED_OPERATORS:
        errors.append(f"{label}: unsupported operator '{rule.operator}'")
    if rule.value is None:
        errors.append(f"{label}: comparison value is required")
    if not isinstance(rule.result, bool):
        errors.append(f"{label}: result must be a boolean value")
    else:
        _validate_rule_value(rule.operator, rule.value, label, errors)


def _validate_rule_value(operator: str, value: object, label: str, errors: list[str]) -> None:
    if operator in {"in", "not_in"}:
        if not isinstance(value, (list, tuple)):
            errors.append(f"{label}: '{operator}' requires a list value")
    elif operator == "contains":
        if not isinstance(value, str):
            errors.append(f"{label}: 'contains' requires a string value")
    elif operator in {"startswith", "endswith"}:
        if not isinstance(value, str):
            errors.append(f"{label}: '{operator}' requires a string value")
    elif operator in {
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
    }:
        if not _is_numeric(value):
            errors.append(f"{label}: '{operator}' requires a numeric value")


def _is_numeric(value: object) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            float(value)
        except ValueError:
            return False
        return True
    return False
