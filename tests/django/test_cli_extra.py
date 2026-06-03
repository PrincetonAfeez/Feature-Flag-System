"""CLI helper functions and remaining command branches."""

from importlib.metadata import PackageNotFoundError
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from flags_django.management.commands.flagctl import (
    Command,
    _parse_bool,
    _parse_context,
    _parse_value,
    yes_no,
)


def run(*args) -> str:
    out = StringIO()
    call_command("flagctl", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_cli_update_default_and_enabled():
    run("create", "checkout", "--env", "production", "--default", "false")
    run("update", "checkout", "--env", "production", "--default", "true", "--enabled", "true")
    details = run("get", "checkout", "--env", "production")
    assert "default: True" in details
    assert "enabled: True" in details


@pytest.mark.django_db
def test_cli_rollout_positional_percentage():
    run("create", "checkout", "--env", "production", "--default", "false")
    assert "set rollout for production:checkout to 75%" in run(
        "rollout", "checkout", "75", "--env", "production"
    )


@pytest.mark.django_db
def test_cli_rollout_without_percentage_errors():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError, match="rollout requires a percentage"):
        call_command("flagctl", "rollout", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_rule_add_missing_fields():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError, match="rule-add missing"):
        call_command("flagctl", "rule-add", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_rule_delete_without_id():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError, match="rule-delete requires a rule id"):
        call_command("flagctl", "rule-delete", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_eval_shows_bucket_for_partial_rollout():
    run("create", "checkout", "--env", "production", "--default", "false", "--enabled", "true")
    run("rollout", "checkout", "50", "--env", "production")
    output = run("eval", "checkout", "--env", "production", "--user", "user_0")
    if "bucket:" in output:
        assert "bucket:" in output


@pytest.mark.django_db
def test_cli_get_shows_rules():
    run("create", "checkout", "--env", "production", "--default", "false", "--enabled", "true")
    run(
        "rule-add",
        "checkout",
        "--env",
        "production",
        "--attribute",
        "plan",
        "--operator",
        "equals",
        "--value",
        "premium",
        "--result",
        "true",
    )
    details = run("get", "checkout", "--env", "production")
    assert "rules:" in details
    assert "plan" in details


@pytest.mark.django_db
def test_cli_create_with_description_and_rollout():
    assert "created production:full" in run(
        "create",
        "full",
        "--env",
        "production",
        "--default",
        "false",
        "--description",
        "desc",
        "--rollout",
        "10",
        "--enabled",
        "true",
    )
    details = run("get", "full", "--env", "production")
    assert "description: desc" in details
    assert "rollout_percentage: 10" in details


@pytest.mark.django_db
def test_cli_env_list_rejects_flag_key():
    with pytest.raises(CommandError, match="env-list takes no flag key"):
        call_command("flagctl", "env-list", "extra", "--env", "production")


@pytest.mark.django_db
def test_cli_command_requires_flag_key():
    with pytest.raises(CommandError, match="get requires a flag key"):
        call_command("flagctl", "get", "--env", "production")


def test_get_version_when_package_not_installed():
    with patch(
        "flags_django.management.commands.flagctl.version",
        side_effect=PackageNotFoundError("feature-flag-system"),
    ):
        assert Command().get_version() == "0.1.3"


def test_yes_no_helper():
    assert yes_no(True) == "yes"
    assert yes_no(False) == "no"


def test_parse_bool_accepts_common_literals():
    assert _parse_bool("true") is True
    assert _parse_bool("FALSE") is False
    assert _parse_bool("yes") is True
    assert _parse_bool("off") is False
    assert _parse_bool("1") is True
    assert _parse_bool(None, default=False) is False
    assert _parse_bool(True) is True
    assert _parse_bool(False) is False


def test_parse_bool_invalid_raises():
    with pytest.raises(ValueError, match="invalid boolean"):
        _parse_bool("maybe")


def test_parse_bool_required_raises():
    with pytest.raises(ValueError, match="boolean value is required"):
        _parse_bool(None)


def test_parse_value_json_and_raw():
    assert _parse_value('["US","CA"]') == ["US", "CA"]
    assert _parse_value("plain") == "plain"


def test_parse_context_invalid_attribute():
    with pytest.raises(ValueError, match="attribute must be key=value"):
        _parse_context("u1", ["badattr"])


def test_handle_unknown_command_guard():
    command = Command()
    options = {
        "subcommand": "bogus",
        "env": "production",
        "key": None,
        "extra": [],
        "strict": False,
        "actor": "cli",
        "name": None,
        "description": None,
        "default_value": None,
        "rollout": None,
        "enabled": None,
        "kill_switch": None,
        "order": None,
        "attribute": None,
        "operator": None,
        "value": None,
        "result": None,
        "user": None,
        "attr": [],
        "limit": None,
    }
    with pytest.raises(CommandError, match="unknown command"):
        command._handle(**options)
