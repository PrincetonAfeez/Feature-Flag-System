"""Service-layer edge cases, integrity errors, and helper coverage."""

from unittest.mock import patch

import pytest
from django.db import IntegrityError

from flags_core.errors import (
    EnvironmentNotFoundError,
    FlagAlreadyExistsError,
    FlagNotFoundError,
    FlagValidationError,
)
from flags_core.models import RuleDefinition
from flags_django.models import FeatureFlag, FlagRule, FlagRule
from flags_django.services import (
    FlagService,
    RuleService,
    SnapshotService,
    get_or_create_environment,
)


def _create(key="new_checkout", **extra):
    data = {
        "environment": "production",
        "key": key,
        "name": key.replace("_", " ").title(),
        "default": False,
        "rollout_percentage": 0,
    }
    data.update(extra)
    return FlagService.create_flag(data).flag


@pytest.mark.django_db
def test_create_flag_missing_environment_raises():
    with pytest.raises(FlagValidationError, match="missing required field: environment"):
        FlagService.create_flag({"key": "k", "default": False})


@pytest.mark.django_db
def test_create_flag_integrity_error_maps_to_already_exists():
    with patch.object(
        FeatureFlag.objects,
        "create",
        side_effect=IntegrityError("duplicate"),
    ):
        with pytest.raises(FlagAlreadyExistsError):
            FlagService.create_flag(
                {
                    "environment": "production",
                    "key": "dup",
                    "default": False,
                }
            )


@pytest.mark.django_db
def test_create_flag_with_rules_persists():
    result = FlagService.create_flag(
        {
            "environment": "production",
            "key": "with_rules",
            "default": False,
            "rules": [
                {
                    "id": "1",
                    "order": 1,
                    "attribute": "plan",
                    "operator": "equals",
                    "value": "premium",
                    "result": True,
                }
            ],
        }
    )
    assert result.flag.rules.count() == 1


@pytest.mark.django_db
def test_write_rules_integrity_error():
    with patch.object(FlagRule.objects, "create", side_effect=IntegrityError("dup order")):
        with pytest.raises(FlagValidationError, match="duplicate rule order in flag definition"):
            FlagService.create_flag(
                {
                    "environment": "production",
                    "key": "bad_rules",
                    "default": False,
                    "rules": [
                        {
                            "id": "1",
                            "order": 1,
                            "attribute": "plan",
                            "operator": "equals",
                            "value": "a",
                            "result": True,
                        }
                    ],
                }
            )


@pytest.mark.django_db
def test_update_flag_integrity_error():
    _create()
    flag = FlagService.get_flag("production", "new_checkout")
    with patch.object(FeatureFlag, "save", side_effect=IntegrityError("conflict")):
        with patch("flags_django.services._locked_flag", return_value=flag):
            with pytest.raises(FlagValidationError, match="conflicting flag update"):
                FlagService.update_flag("production", "new_checkout", {"name": "Renamed"})


@pytest.mark.django_db
def test_delete_flag_integrity_error():
    _create()
    flag = FlagService.get_flag("production", "new_checkout")
    with patch.object(FeatureFlag, "save", side_effect=IntegrityError("conflict")):
        with patch("flags_django.services._locked_flag", return_value=flag):
            with pytest.raises(FlagValidationError, match="conflicting flag delete"):
                FlagService.delete_flag("production", "new_checkout")


@pytest.mark.django_db
def test_delete_rule_integrity_error():
    _create()
    rule = RuleService.add_rule(
        "production",
        "new_checkout",
        {"attribute": "plan", "operator": "equals", "value": "x", "result": True},
    )
    flag = FlagService.get_flag("production", "new_checkout")
    with patch.object(FeatureFlag, "save", side_effect=IntegrityError("conflict")):
        with patch("flags_django.services._locked_flag", return_value=flag):
            with pytest.raises(FlagValidationError, match="conflicting rule delete"):
                RuleService.delete_rule("production", "new_checkout", rule.id)


@pytest.mark.django_db
def test_get_history_raises_when_flag_never_existed():
    _create(key="exists")
    with pytest.raises(FlagNotFoundError):
        list(FlagService.get_history("production", "missing"))


@pytest.mark.django_db
def test_list_flags_include_archived():
    _create(key="active")
    _create(key="archived")
    FlagService.delete_flag("production", "archived")
    assert FlagService.list_flags("production").count() == 1
    assert FlagService.list_flags("production", include_archived=True).count() == 2


@pytest.mark.django_db
def test_set_kill_switch():
    _create()
    flag = FlagService.set_kill_switch("production", "new_checkout", True, actor="ops")
    assert flag.kill_switch is True
    flag = FlagService.set_kill_switch("production", "new_checkout", False, actor="ops")
    assert flag.kill_switch is False


@pytest.mark.django_db
def test_add_rule_auto_assigns_order():
    _create()
    first = RuleService.add_rule(
        "production",
        "new_checkout",
        {"attribute": "a", "operator": "equals", "value": "1", "result": True},
    )
    second = RuleService.add_rule(
        "production",
        "new_checkout",
        {"attribute": "b", "operator": "equals", "value": "2", "result": False},
    )
    assert first.order == 1
    assert second.order == 2


@pytest.mark.django_db
def test_add_rule_integrity_error_maps_to_validation():
    _create()
    with patch.object(FlagRule, "save", side_effect=IntegrityError("dup")):
        with pytest.raises(FlagValidationError, match="duplicate rule order"):
            RuleService.add_rule(
                "production",
                "new_checkout",
                {
                    "order": 99,
                    "attribute": "plan",
                    "operator": "equals",
                    "value": "x",
                    "result": True,
                },
            )


@pytest.mark.django_db
def test_update_flag_key_error_maps_to_validation():
    _create()
    flag = FlagService.get_flag("production", "new_checkout")
    with patch("flags_django.services._definition_from_data", side_effect=KeyError("key")):
        with patch("flags_django.services._locked_flag", return_value=flag):
            with pytest.raises(FlagValidationError, match="missing required field: key"):
                FlagService.update_flag("production", "new_checkout", {"name": "X"})


@pytest.mark.django_db
def test_mark_snapshot_changed_increments_version():
    _create()
    before_version = SnapshotService.serialize_with_etag("production")[0]["version"]
    SnapshotService.mark_snapshot_changed("production")
    after_version = SnapshotService.serialize_with_etag("production")[0]["version"]
    assert after_version > before_version


@pytest.mark.django_db
def test_get_or_create_environment_reuses_existing():
    _create()
    env = get_or_create_environment("production")
    assert env.slug == "production"
    assert env.name == "Production"


@pytest.mark.django_db
def test_create_with_rule_definition_instance():
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "rule_obj",
            "default": False,
            "rules": [RuleDefinition("1", 1, "plan", "equals", "x", True)],
        }
    )
    assert FlagService.get_flag("production", "rule_obj").rules.count() == 1
