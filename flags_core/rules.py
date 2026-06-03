"""Rule matching for the pure feature flag evaluator."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from flags_core.models import EvaluationContext, RuleDefinition

SUPPORTED_OPERATORS = {
    "equals",
    "not_equals",
    "in",
    "not_in",
    "contains",
    "startswith",
    "endswith",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
}


def rule_matches(rule: RuleDefinition, context: EvaluationContext) -> bool:
    if rule.attribute not in context.attributes:
        return False

    actual = context.attributes[rule.attribute]
    expected = rule.value

    if rule.operator == "equals":
        return actual == expected
    if rule.operator == "not_equals":
        return actual != expected
    if rule.operator == "in":
        return _contains(expected, actual)
    if rule.operator == "not_in":
        return not _contains(expected, actual)
    if rule.operator == "contains":
        return _contains(actual, expected)
    if rule.operator == "startswith":
        return isinstance(actual, str) and isinstance(expected, str) and actual.startswith(expected)
    if rule.operator == "endswith":
        return isinstance(actual, str) and isinstance(expected, str) and actual.endswith(expected)
    if rule.operator == "greater_than":
        return _numeric_compare(actual, expected, lambda a, b: a > b)
    if rule.operator == "greater_than_or_equal":
        return _numeric_compare(actual, expected, lambda a, b: a >= b)
    if rule.operator == "less_than":
        return _numeric_compare(actual, expected, lambda a, b: a < b)
    if rule.operator == "less_than_or_equal":
        return _numeric_compare(actual, expected, lambda a, b: a <= b)

    return False


def _contains(container: Any, item: Any) -> bool:
    if isinstance(container, str):
        return isinstance(item, str) and item in container
    if isinstance(container, Iterable):
        try:
            return item in container
        except TypeError:
            return False
    return False


def _numeric_compare(actual: Any, expected: Any, op: Callable[[float, float], bool]) -> bool:
    try:
        actual_number = float(actual)
        expected_number = float(expected)
    except (TypeError, ValueError):
        return False
    return op(actual_number, expected_number)
