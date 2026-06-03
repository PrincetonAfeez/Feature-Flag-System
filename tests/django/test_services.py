"""Tests for the services module."""

import pytest

from flags_core.errors import (
    EnvironmentNotFoundError,
    FlagAlreadyExistsError,
    FlagNotFoundError,
    FlagValidationError,
    RuleNotFoundError,
)
from flags_core.models import RuleDefinition
from flags_django.models import AuditLog, Environment, FeatureFlag, SnapshotVersion
from flags_django.services import (
    EvaluationService,
    FlagService,
    RuleService,
    SnapshotService,
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
def test_create_flag_writes_audit_and_snapshot_version():
    result = FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
        },
        actor="tester",
    )
    flag = result.flag

    assert flag.key == "new_checkout"
    assert AuditLog.objects.filter(flag=flag, action="create", actor="tester").exists()
    assert SnapshotVersion.objects.get(environment=flag.environment).version == 1


@pytest.mark.django_db
def test_create_duplicate_key_raises():
    _create()
    with pytest.raises(FlagAlreadyExistsError):
        _create()


@pytest.mark.django_db
def test_get_unknown_flag_in_existing_env_raises_not_found():
    _create(key="exists")  # materialize the environment so we test a missing flag
    with pytest.raises(FlagNotFoundError):
        FlagService.get_flag("production", "missing")


@pytest.mark.django_db
def test_update_unknown_flag_in_existing_env_raises_not_found():
    _create(key="exists")
    with pytest.raises(FlagNotFoundError):
        FlagService.set_rollout("production", "missing", 10)


@pytest.mark.django_db
def test_reads_do_not_create_environments():
    # get_flag on an unknown environment errors and creates nothing.
    with pytest.raises(EnvironmentNotFoundError):
        FlagService.get_flag("ghost", "anything")
    assert not Environment.objects.filter(slug="ghost").exists()

    # list_flags on an unknown environment is empty and creates nothing.
    assert list(FlagService.list_flags("ghost")) == []
    assert not Environment.objects.filter(slug="ghost").exists()


@pytest.mark.django_db
def test_create_flag_creates_environment():
    assert not Environment.objects.filter(slug="production").exists()
    _create()
    assert Environment.objects.filter(slug="production").exists()


@pytest.mark.django_db
def test_convert_model_to_core_maps_fields():
    flag = _create(key="checkout", rollout_percentage=25)
    core = EvaluationService.convert_model_to_core(flag)
    assert core.key == "checkout"
    assert core.environment == "production"
    assert core.rollout_percentage == 25


@pytest.mark.django_db
def test_build_snapshot_query_count_does_not_scale(django_assert_max_num_queries):
    for i in range(5):
        _create(key=f"flag_{i}")
        RuleService.add_rule(
            "production",
            f"flag_{i}",
            {"attribute": "plan", "operator": "equals", "value": "premium", "result": True},
        )

    # select_related("environment") + an ordered Prefetch keep this constant
    # (~4 queries) regardless of flag/rule count; the old N+1 was ~2N+1.
    with django_assert_max_num_queries(6):
        snapshot = SnapshotService.build_snapshot("production")

    assert len(snapshot.flags) == 5


@pytest.mark.django_db
def test_enable_disable_and_eval_use_core():
    _create()

    FlagService.enable_flag("production", "new_checkout")
    RuleService.add_rule(
        "production",
        "new_checkout",
        {"attribute": "plan", "operator": "equals", "value": "premium", "result": True},
    )

    result = EvaluationService.evaluate_from_db(
        "production", "new_checkout", {"user_id": "u1", "plan": "premium"}
    )
    assert result.value is True
    assert result.reason == "targeting_match"

    FlagService.disable_flag("production", "new_checkout")
    disabled = EvaluationService.evaluate_from_db(
        "production", "new_checkout", {"user_id": "u1", "plan": "premium"}
    )
    assert disabled.value is False
    assert disabled.reason == "flag_disabled"


@pytest.mark.django_db
def test_delete_unknown_rule_raises():
    _create()
    with pytest.raises(RuleNotFoundError):
        RuleService.delete_rule("production", "new_checkout", 999999)


@pytest.mark.django_db
def test_invalid_update_rolls_back_without_audit():
    flag = _create(rollout_percentage=10)
    audit_count = AuditLog.objects.count()

    with pytest.raises(FlagValidationError):
        FlagService.set_rollout("production", "new_checkout", 101)

    flag.refresh_from_db()
    assert flag.rollout_percentage == 10
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_snapshot_contains_active_flags_only():
    _create(key="active_flag")
    _create(key="old_flag")
    FlagService.delete_flag("production", "old_flag")

    payload = SnapshotService.serialize_snapshot("production")

    assert "active_flag" in payload["flags"]
    assert "old_flag" not in payload["flags"]
    assert FeatureFlag.objects.get(key="old_flag").archived_at is not None


@pytest.mark.django_db
def test_archived_flag_excluded_from_list_and_get():
    _create(key="temp_flag")
    FlagService.delete_flag("production", "temp_flag")

    assert not FlagService.list_flags("production").filter(key="temp_flag").exists()
    with pytest.raises(FlagNotFoundError):
        FlagService.get_flag("production", "temp_flag")


@pytest.mark.django_db
def test_serialize_with_etag_is_consistent():
    _create()
    payload, etag = SnapshotService.serialize_with_etag("production")
    assert etag == f'"production-{payload["version"]}"'


@pytest.mark.django_db
def test_snapshot_body_is_stable_between_reads():
    _create()
    first = SnapshotService.serialize_snapshot("production")
    second = SnapshotService.serialize_snapshot("production")
    # generated_at tracks the last change, not "now", so repeated reads match.
    assert first == second


@pytest.mark.django_db
def test_create_flag_returns_action():
    result = FlagService.create_flag(
        {
            "environment": "production",
            "key": "fresh",
            "name": "Fresh",
            "default": False,
        }
    )
    assert result.action == "create"
    assert result.flag.key == "fresh"


@pytest.mark.django_db
def test_create_flag_reuses_archived_row():
    _create(key="checkout")
    FlagService.delete_flag("production", "checkout")

    recreated = FlagService.create_flag(
        {
            "environment": "production",
            "key": "checkout",
            "name": "Checkout v2",
            "default": True,
            "rollout_percentage": 10,
        }
    ).flag

    assert recreated.key == "checkout"
    assert recreated.archived_at is None
    assert recreated.default_value is True
    assert FeatureFlag.objects.filter(environment__slug="production", key="checkout").count() == 1
    assert AuditLog.objects.filter(flag=recreated, action="recreate").exists()


@pytest.mark.django_db
def test_create_flag_with_string_rule_result_raises():
    with pytest.raises(FlagValidationError, match="rule result must be a boolean"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "rules_flag",
                "name": "Rules",
                "default": False,
                "rules": [
                    {
                        "id": "1",
                        "order": 1,
                        "attribute": "plan",
                        "operator": "equals",
                        "value": "premium",
                        "result": "false",
                    }
                ],
            }
        )


@pytest.mark.django_db
def test_create_flag_rejects_string_enabled():
    with pytest.raises(FlagValidationError, match="enabled must be a boolean"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "bad_enabled",
                "name": "Bad",
                "default": False,
                "enabled": "false",
            }
        )


@pytest.mark.django_db
def test_create_flag_rejects_bool_rollout():
    with pytest.raises(FlagValidationError, match="rollout_percentage must be an integer"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "bad_rollout",
                "name": "Bad",
                "default": False,
                "rollout_percentage": True,
            }
        )


@pytest.mark.django_db
def test_create_flag_rejects_string_default():
    with pytest.raises(FlagValidationError, match="default must be a boolean"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "bad_default",
                "name": "Bad",
                "default": "false",
            }
        )


@pytest.mark.django_db
def test_create_flag_missing_default_raises_validation_error():
    with pytest.raises(FlagValidationError, match="missing required field: default"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "no_default",
                "name": "Bad",
            }
        )


@pytest.mark.django_db
def test_create_flag_missing_key_raises_validation_error():
    with pytest.raises(FlagValidationError, match="missing required field: key"):
        FlagService.create_flag(
            {
                "environment": "production",
                "name": "Bad",
                "default": False,
            }
        )


@pytest.mark.django_db
def test_create_flag_rejects_bool_version():
    with pytest.raises(FlagValidationError, match="version must be an integer"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "bad_version",
                "name": "Bad",
                "default": False,
                "version": True,
            }
        )


@pytest.mark.django_db
def test_set_rollout_rejects_bool():
    _create(key="rollout_flag")
    with pytest.raises(FlagValidationError, match="rollout_percentage must be an integer"):
        FlagService.set_rollout("production", "rollout_flag", True)  # type: ignore[arg-type]


@pytest.mark.django_db
def test_get_history_limit():
    _create(key="limited")
    for _ in range(5):
        FlagService.update_flag("production", "limited", {"name": "Limited"}, actor="tester")

    assert len(list(FlagService.get_history("production", "limited", limit=2))) == 2


@pytest.mark.django_db
def test_create_flag_with_duplicate_rule_orders_raises():
    with pytest.raises(FlagValidationError, match="duplicate rule order"):
        FlagService.create_flag(
            {
                "environment": "production",
                "key": "rules_flag",
                "name": "Rules",
                "default": False,
                "rules": [
                    RuleDefinition("1", 1, "plan", "equals", "a", True),
                    RuleDefinition("2", 1, "plan", "equals", "b", False),
                ],
            }
        )


@pytest.mark.django_db
def test_get_history_includes_archived_flag():
    _create(key="checkout")
    FlagService.delete_flag("production", "checkout", actor="tester")

    history = list(FlagService.get_history("production", "checkout"))

    assert history
    assert any(entry.action == "delete" for entry in history)


@pytest.mark.django_db
def test_list_flags_strict_raises_for_unknown_environment():
    with pytest.raises(EnvironmentNotFoundError):
        FlagService.list_flags("ghost", strict=True)


@pytest.mark.django_db
def test_add_rule_duplicate_order_raises_validation_error():
    _create()
    RuleService.add_rule(
        "production",
        "new_checkout",
        {"order": 1, "attribute": "plan", "operator": "equals", "value": "free", "result": False},
    )
    with pytest.raises(FlagValidationError):
        RuleService.add_rule(
            "production",
            "new_checkout",
            {
                "order": 1,
                "attribute": "plan",
                "operator": "equals",
                "value": "premium",
                "result": True,
            },
        )
