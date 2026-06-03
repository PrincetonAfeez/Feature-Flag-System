"""Tests for the evaluation context module."""

import pytest

from flags_core.errors import FlagValidationError
from flags_core.models import EvaluationContext, RuleDefinition
from flags_core.schema import validate_flag_definition


def test_user_id_accepts_string_and_integer():
    assert EvaluationContext.from_mapping({"user_id": "u1"}).user_id == "u1"
    assert EvaluationContext.from_mapping({"user_id": 42}).user_id == "42"


def test_user_id_rejects_boolean():
    with pytest.raises(ValueError, match="not a boolean"):
        EvaluationContext.from_mapping({"user_id": True})


def test_user_id_rejects_other_types():
    with pytest.raises(ValueError, match="must be a string or integer"):
        EvaluationContext.from_mapping({"user_id": ["u1"]})


def test_empty_user_id_string_becomes_none():
    assert EvaluationContext.from_mapping({"user_id": ""}).user_id is None


def test_in_operator_requires_list_value(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "in", "premium", True)])

    with pytest.raises(FlagValidationError, match="requires a list value"):
        validate_flag_definition(flag)


def test_startswith_requires_string_value(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "startswith", 123, True)])

    with pytest.raises(FlagValidationError, match="requires a string value"):
        validate_flag_definition(flag)


def test_numeric_operator_requires_numeric_value(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "age", "greater_than", "old", True)])

    with pytest.raises(FlagValidationError, match="requires a numeric value"):
        validate_flag_definition(flag)


def test_in_operator_accepts_list(make_flag):
    flag = make_flag(
        rules=[RuleDefinition("a", 1, "country", "in", ["US", "CA"], True)],
    )
    validate_flag_definition(flag)


def test_in_operator_rejects_dict(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "in", {"US": "x"}, True)])

    with pytest.raises(FlagValidationError, match="requires a list value"):
        validate_flag_definition(flag)


def test_contains_requires_string_value(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "contains", 123, True)])

    with pytest.raises(FlagValidationError, match="requires a string value"):
        validate_flag_definition(flag)
