"""Converter and model coverage beyond happy paths."""

import pytest

from flags_django.converters import flag_model_to_core, flag_model_to_dict
from flags_django.models import FeatureFlag, default_false
from flags_django.services import FlagService, RuleService


@pytest.mark.django_db
def test_flag_model_to_dict_includes_rules():
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "checkout",
            "name": "Checkout",
            "description": "Main flow",
            "default": False,
        }
    )
    RuleService.add_rule(
        "production",
        "checkout",
        {"attribute": "plan", "operator": "equals", "value": "premium", "result": True},
    )
    flag = FlagService.get_flag("production", "checkout")
    data = flag_model_to_dict(flag)
    assert data["description"] == "Main flow"
    assert data["archived_at"] is None
    assert len(data["rules"]) == 1
    assert data["rules"][0]["operator"] == "equals"


@pytest.mark.django_db
def test_flag_model_to_dict_archived_timestamp():
    created = FlagService.create_flag(
        {"environment": "production", "key": "gone", "default": False}
    ).flag
    FlagService.delete_flag("production", "gone")
    archived = FeatureFlag.objects.get(pk=created.pk)
    data = flag_model_to_dict(archived)
    assert data["archived_at"] is not None


@pytest.mark.django_db
def test_flag_model_to_core_skips_validation():
    flag = FlagService.create_flag(
        {"environment": "production", "key": "checkout", "default": False}
    ).flag
    core = flag_model_to_core(flag, validate=False)
    assert core.key == "checkout"


def test_default_false_callable():
    assert default_false() is False
