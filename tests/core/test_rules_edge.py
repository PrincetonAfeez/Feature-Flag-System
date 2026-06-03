"""Edge-case coverage for rule matching helpers."""

from flags_core.models import EvaluationContext, RuleDefinition
from flags_core.rules import _contains, rule_matches


class _BadList(list):
    def __contains__(self, item: object) -> bool:
        raise TypeError("membership failed")


def test_contains_type_error_on_iterable_returns_false():
    assert _contains(_BadList([1, 2, 3]), 2) is False


def test_contains_non_string_non_iterable_returns_false():
    assert _contains(123, 1) is False


def test_contains_string_requires_string_item():
    assert _contains("hello", "ell") is True
    assert _contains("hello", 123) is False


def test_in_operator_with_unhashable_actual_does_not_match():
    rule = RuleDefinition("r", 1, "tags", "in", ["a", "b"], True)
    ctx = EvaluationContext(attributes={"tags": []})
    assert rule_matches(rule, ctx) is False


def test_not_in_operator():
    rule = RuleDefinition("r", 1, "country", "not_in", ["US"], True)
    assert rule_matches(rule, EvaluationContext(attributes={"country": "CA"}))
    assert not rule_matches(rule, EvaluationContext(attributes={"country": "US"}))


def test_endswith_no_match():
    rule = RuleDefinition("r", 1, "email", "endswith", ".com", True)
    assert not rule_matches(rule, EvaluationContext(attributes={"email": "user@org"}))


def test_unsupported_operator_returns_false():
    rule = RuleDefinition("r", 1, "plan", "regex", ".*", True)
    assert rule_matches(rule, EvaluationContext(attributes={"plan": "premium"})) is False
