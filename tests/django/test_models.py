"""Tests for the models module."""

import pytest

from flags_django.models import AuditLog, SnapshotVersion
from flags_django.services import FlagService, RuleService
from flags_django.sse import notify_flags_changed


@pytest.mark.django_db
def test_model_str_representations():
    flag = FlagService.create_flag(
        {
            "environment": "production",
            "key": "checkout",
            "name": "Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    ).flag
    rule = RuleService.add_rule(
        "production",
        "checkout",
        {"attribute": "plan", "operator": "equals", "value": "premium", "result": True},
    )
    env = flag.environment

    assert str(env) == "production"
    assert str(flag) == "production:checkout"
    assert str(rule) == "checkout rule 1"
    # create bumps the snapshot version to 1, add_rule to 2.
    assert str(SnapshotVersion.objects.get(environment=env)) == '"production-2"'

    audit = AuditLog.objects.filter(flag=flag, action="create").first()
    assert "create" in str(audit)
    assert "checkout" in str(audit)


def test_sse_notify_is_noop():
    # The MVP push seam is intentionally a no-op (see ADR 0002).
    assert notify_flags_changed("production", 1, '"production-1"') is None
