"""Numeric validation paths in schema._is_numeric."""

import pytest

from flags_core.errors import FlagValidationError
from flags_core.models import RuleDefinition
from flags_core.schema import coerce_strict_bool, validate_flag_definition


def test_numeric_string_value_passes_validation(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "age", "greater_than", "18.5", True)])
    validate_flag_definition(flag)


def test_non_numeric_string_rejected_for_numeric_operator(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "age", "less_than", "not-a-number", True)])
    with pytest.raises(FlagValidationError, match="requires a numeric value"):
        validate_flag_definition(flag)


def test_float_threshold_accepted(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "score", "greater_than_or_equal", 3.14, True)])
    validate_flag_definition(flag)


def test_is_numeric_rejects_non_scalar_types(make_flag):
    flag = make_flag(rules=[RuleDefinition("a", 1, "age", "greater_than", [], True)])
    with pytest.raises(FlagValidationError, match="requires a numeric value"):
        validate_flag_definition(flag)


def test_coerce_strict_bool_rejects_strings():
    with pytest.raises(FlagValidationError, match="enabled must be a boolean"):
        coerce_strict_bool("true", "enabled")
