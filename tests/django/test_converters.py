"""Tests for the converters module."""

import pytest

from flags_core.errors import FlagValidationError
from flags_django.converters import flag_model_to_core
from flags_django.models import FlagRule
from flags_django.services import FlagService


@pytest.mark.django_db
def test_flag_model_to_core_rejects_non_boolean_default():
    flag = FlagService.create_flag(
        {
            "environment": "production",
            "key": "checkout",
            "name": "Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    ).flag
    flag.default_value = "not_bool"
    flag.save(update_fields=["default_value"])

    with pytest.raises(FlagValidationError, match="default must be a boolean"):
        flag_model_to_core(flag)


@pytest.mark.django_db
def test_flag_model_to_core_rejects_unsupported_operator():
    flag = FlagService.create_flag(
        {
            "environment": "production",
            "key": "checkout",
            "name": "Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    ).flag
    rule = FlagRule.objects.create(
        flag=flag,
        order=1,
        attribute="plan",
        operator="regex",
        value="premium",
        result=True,
    )
    flag.refresh_from_db()

    with pytest.raises(FlagValidationError, match="unsupported operator"):
        flag_model_to_core(flag)

    rule.delete()
