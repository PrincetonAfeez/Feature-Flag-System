"""Tests for the schema module."""

import pytest

from flags_core.errors import FlagValidationError
from flags_core.models import RuleDefinition
from flags_core.schema import coerce_strict_int, validate_flag_definition


def test_valid_flag_passes_validation(make_flag):
    validate_flag_definition(make_flag())


def test_invalid_percentage_is_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(make_flag(rollout_percentage=101))

    assert "rollout_percentage" in str(exc.value)


def test_invalid_flag_key_is_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(make_flag(key="New Checkout"))

    assert "flag key" in str(exc.value)


def test_duplicate_rule_order_is_rejected(make_flag):
    flag = make_flag(
        rules=[
            RuleDefinition("a", 1, "plan", "equals", "premium", True),
            RuleDefinition("b", 1, "country", "equals", "US", True),
        ]
    )

    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(flag)

    assert "duplicate rule order" in str(exc.value)


def test_non_boolean_values_are_rejected(make_flag):
    with pytest.raises(FlagValidationError):
        validate_flag_definition(make_flag(default="false"))


def test_unsupported_operator_is_rejected(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "regexx", "premium", True)])

    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(flag)

    assert "unsupported operator" in str(exc.value)


def test_rule_missing_value_is_rejected(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "plan", "equals", None, True)])

    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(flag)

    assert "comparison value is required" in str(exc.value)


def test_missing_key_is_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(make_flag(key=""))

    assert "flag key is required" in str(exc.value)


def test_missing_environment_is_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(make_flag(environment=""))

    assert "environment is required" in str(exc.value)


def test_invalid_environment_is_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(make_flag(environment="Bad Env"))

    assert "environment must be slug-like" in str(exc.value)


def test_non_boolean_flags_and_non_int_rollout_are_rejected(make_flag):
    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(
            make_flag(enabled="yes", kill_switch="no", rollout_percentage="50")
        )

    message = str(exc.value)
    assert "enabled must be a boolean value" in message
    assert "kill_switch must be a boolean value" in message
    assert "rollout_percentage must be an integer" in message


def test_bool_rollout_percentage_is_rejected(make_flag):
    with pytest.raises(FlagValidationError, match="rollout_percentage must be an integer"):
        validate_flag_definition(make_flag(rollout_percentage=True))


def test_bool_rule_order_is_rejected(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", True, "plan", "equals", "x", True)])

    with pytest.raises(FlagValidationError, match="order must be a positive integer"):
        validate_flag_definition(flag)


def test_coerce_strict_int_rejects_bool():
    with pytest.raises(FlagValidationError, match="rollout_percentage must be an integer"):
        coerce_strict_int(True, "rollout_percentage")


def test_coerce_strict_int_accepts_int():
    assert coerce_strict_int(42, "rollout_percentage") == 42


def test_malformed_rule_reports_each_problem(make_flag):
    flag = make_flag(
        rules=[
            RuleDefinition(
                id="", order=0, attribute="", operator="equals", value="x", result="nope"
            )
        ]
    )

    with pytest.raises(FlagValidationError) as exc:
        validate_flag_definition(flag)

    message = str(exc.value)
    assert "id is required" in message
    assert "order must be a positive integer" in message
    assert "attribute is required" in message
    assert "result must be a boolean value" in message
