"""Tests for the rules module."""

from flags_core.models import EvaluationContext, RuleDefinition
from flags_core.rules import rule_matches

def ctx(**attrs) -> EvaluationContext:
    user_id = attrs.pop("user_id", None)
    return EvaluationContext(user_id=user_id, attributes=attrs)


def rule(operator, value, attribute="plan", result=True) -> RuleDefinition:
    return RuleDefinition("r1", 1, attribute, operator, value, result)


def test_equals_and_not_equals():
    assert rule_matches(rule("equals", "premium"), ctx(plan="premium"))
    assert not rule_matches(rule("equals", "premium"), ctx(plan="free"))
    assert rule_matches(rule("not_equals", "premium"), ctx(plan="free"))
    assert not rule_matches(rule("not_equals", "premium"), ctx(plan="premium"))


def test_missing_attribute_never_matches():
    assert not rule_matches(rule("equals", "premium"), ctx(country="US"))


def test_in_and_not_in():
    in_rule = rule("in", ["US", "CA"], attribute="country")
    assert rule_matches(in_rule, ctx(country="US"))
    assert not rule_matches(in_rule, ctx(country="GB"))

    not_in_rule = rule("not_in", ["US", "CA"], attribute="country")
    assert rule_matches(not_in_rule, ctx(country="GB"))
    assert not rule_matches(not_in_rule, ctx(country="US"))


def test_contains_for_strings_and_lists():
    assert rule_matches(rule("contains", "prem"), ctx(plan="premium"))
    assert rule_matches(rule("contains", "US", attribute="countries"), ctx(countries=["US", "CA"]))
    assert not rule_matches(rule("contains", "US", attribute="countries"), ctx(countries=["GB"]))


def test_startswith_and_endswith_require_strings():
    assert rule_matches(rule("startswith", "prem"), ctx(plan="premium"))
    assert rule_matches(rule("endswith", "ium"), ctx(plan="premium"))
    assert not rule_matches(rule("startswith", "prem"), ctx(plan=123))


def test_numeric_comparisons():
    assert rule_matches(rule("greater_than", 18, attribute="age"), ctx(age=21))
    assert not rule_matches(rule("greater_than", 18, attribute="age"), ctx(age=18))
    assert rule_matches(rule("greater_than_or_equal", 18, attribute="age"), ctx(age=18))
    assert rule_matches(rule("less_than", 18, attribute="age"), ctx(age=17))
    assert not rule_matches(rule("less_than", 18, attribute="age"), ctx(age=18))
    assert rule_matches(rule("less_than_or_equal", 18, attribute="age"), ctx(age=18))


def test_numeric_comparison_accepts_numeric_strings():
    assert rule_matches(rule("greater_than", "18", attribute="age"), ctx(age="21"))


def test_numeric_comparison_with_non_numeric_does_not_match():
    assert not rule_matches(rule("greater_than", 18, attribute="age"), ctx(age="old"))


def test_unknown_operator_does_not_match():
    assert not rule_matches(rule("regex", "x"), ctx(plan="premium"))
