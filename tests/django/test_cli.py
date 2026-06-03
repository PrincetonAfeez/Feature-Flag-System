"""Tests for the CLI module."""

from io import StringIO

import django
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from flags_django.management.commands.flagctl import Command
from flags_django.models import FlagRule


def run(*args) -> str:
    out = StringIO()
    call_command("flagctl", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_cli_create_enable_eval_and_history():
    assert "created production:new_checkout" in run(
        "create", "new_checkout", "--env", "production", "--default", "false"
    )
    assert "enabled production:new_checkout" in run("enable", "new_checkout", "--env", "production")
    assert "100%" in run("rollout", "new_checkout", "100", "--env", "production")

    eval_output = run("eval", "new_checkout", "--env", "production", "--user", "u1")
    assert "new_checkout = true" in eval_output
    assert "reason: percentage_rollout" in eval_output

    history = run("history", "new_checkout", "--env", "production")
    assert "create" in history
    assert "update" in history


@pytest.mark.django_db
def test_cli_create_with_kill_switch():
    assert "created production:checkout" in run(
        "create", "checkout", "--env", "production", "--default", "false", "--kill-switch", "true"
    )
    assert "kill_switch: True" in run("get", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_list_and_get_show_flag():
    run("create", "checkout", "--env", "production", "--default", "false", "--rollout", "25")

    listing = run("list", "--env", "production")
    assert "KEY" in listing
    assert "checkout" in listing

    details = run("get", "checkout", "--env", "production")
    assert "key: checkout" in details
    assert "enabled: False" in details
    assert "rollout_percentage: 25" in details


@pytest.mark.django_db
def test_cli_disable_toggles_state():
    run("create", "checkout", "--env", "production", "--default", "false", "--enabled", "true")
    assert "disabled production:checkout" in run("disable", "checkout", "--env", "production")
    assert "enabled: False" in run("get", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_kill_and_unkill():
    run("create", "checkout", "--env", "production", "--default", "false")

    assert "kill switch enabled for production:checkout" in run(
        "kill", "checkout", "--env", "production"
    )
    assert "kill_switch: True" in run("get", "checkout", "--env", "production")

    assert "kill switch disabled for production:checkout" in run(
        "unkill", "checkout", "--env", "production"
    )
    assert "kill_switch: False" in run("get", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_update_fields():
    run("create", "checkout", "--env", "production", "--default", "false")
    assert "updated production:checkout" in run(
        "update", "checkout", "--env", "production", "--name", "Renamed", "--rollout", "30"
    )
    details = run("get", "checkout", "--env", "production")
    assert "name: Renamed" in details
    assert "rollout_percentage: 30" in details


@pytest.mark.django_db
def test_cli_delete_archives_flag():
    run("create", "checkout", "--env", "production", "--default", "false")
    assert "deleted production:checkout" in run("delete", "checkout", "--env", "production")
    # Archived flags are no longer retrievable.
    with pytest.raises(CommandError):
        call_command("flagctl", "get", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_create_duplicate_key_errors():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError, match="already exists"):
        call_command("flagctl", "create", "checkout", "--env", "production", "--default", "false")


@pytest.mark.django_db
def test_cli_history_works_after_delete():
    run("create", "checkout", "--env", "production", "--default", "false")
    run("delete", "checkout", "--env", "production")
    history = run("history", "checkout", "--env", "production")
    assert "create" in history
    assert "delete" in history


@pytest.mark.django_db
def test_cli_recreate_after_delete():
    run("create", "checkout", "--env", "production", "--default", "false")
    run("delete", "checkout", "--env", "production")
    assert "recreated production:checkout" in run(
        "create", "checkout", "--env", "production", "--default", "true"
    )
    history = run("history", "checkout", "--env", "production")
    assert "recreate" in history
    assert "default: True" in run("get", "checkout", "--env", "production")


@pytest.mark.django_db
def test_cli_list_warns_for_unknown_environment():
    output = run("list", "--env", "ghost")
    assert "warning: environment 'ghost' does not exist" in output


@pytest.mark.django_db
def test_cli_list_strict_errors_for_unknown_environment():
    with pytest.raises(CommandError, match="environment 'ghost' was not found"):
        call_command("flagctl", "list", "--env", "ghost", "--strict")


@pytest.mark.django_db
def test_cli_env_list():
    run("create", "checkout", "--env", "production", "--default", "false")
    run("create", "other", "--env", "staging", "--default", "true")
    output = run("env-list")
    assert "SLUG" in output
    assert "production" in output
    assert "staging" in output
    assert " 1" in output or "1\n" in output


@pytest.mark.django_db
def test_cli_history_limit():
    run("create", "checkout", "--env", "production", "--default", "false")
    run("enable", "checkout", "--env", "production")
    run("disable", "checkout", "--env", "production")
    output = run("history", "checkout", "--env", "production", "--limit", "2")
    assert len([line for line in output.strip().splitlines() if line.strip()]) == 2


@pytest.mark.django_db
def test_cli_rule_add_eval_and_delete():
    run("create", "checkout", "--env", "production", "--default", "false", "--enabled", "true")

    assert "added rule" in run(
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

    eval_output = run(
        "eval", "checkout", "--env", "production", "--user", "u1", "--attr", "plan=premium"
    )
    assert "checkout = true" in eval_output
    assert "reason: targeting_match" in eval_output

    rule_id = FlagRule.objects.get(flag__key="checkout").id
    assert f"deleted rule {rule_id}" in run(
        "rule-delete", "checkout", str(rule_id), "--env", "production"
    )


@pytest.mark.django_db
def test_cli_update_without_fields_errors():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError):
        call_command("flagctl", "update", "checkout", "--env", "production")


def test_cli_invalid_subcommand_errors():
    with pytest.raises(CommandError):
        call_command("flagctl", "frobnicate")


def test_cli_list_rejects_flag_key():
    with pytest.raises(CommandError):
        call_command("flagctl", "list", "unexpected_key")


@pytest.mark.django_db
def test_cli_enable_rejects_extra_arguments():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError):
        call_command("flagctl", "enable", "checkout", "garbage", "--env", "production")


@pytest.mark.django_db
def test_cli_rollout_rejects_surplus_positionals():
    run("create", "checkout", "--env", "production", "--default", "false")
    with pytest.raises(CommandError):
        call_command("flagctl", "rollout", "checkout", "25", "99", "--env", "production")


def test_cli_version_reports_project_not_framework():
    # --version must report the tool's version, not Django's.
    assert Command().get_version() != django.get_version()
