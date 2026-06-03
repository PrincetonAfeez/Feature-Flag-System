"""Admin CLI for feature flags."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from flags_core.errors import FlagError
from flags_django.models import Environment
from flags_django.services import EvaluationService, FlagService, RuleService


class Command(BaseCommand):
    help = "Manage feature flags"

    def get_version(self) -> str:
        # Report the project's version for `flagctl --version` instead of Django's.
        try:
            return version("feature-flag-system")
        except PackageNotFoundError:
            return "0.1.3"  # running from source without an install; mirrors pyproject

    def add_arguments(self, parser):
        parser.add_argument(
            "subcommand",
            choices=[
                "list",
                "env-list",
                "get",
                "create",
                "update",
                "delete",
                "enable",
                "disable",
                "kill",
                "unkill",
                "rollout",
                "rule-add",
                "rule-delete",
                "eval",
                "history",
            ],
        )
        parser.add_argument("key", nargs="?")
        parser.add_argument("extra", nargs="*")
        parser.add_argument("--env", default="development")
        parser.add_argument("--actor", default="cli")
        parser.add_argument("--name")
        parser.add_argument("--description")
        parser.add_argument(
            "--default",
            dest="default_value",
            help="boolean default value: true/false (also accepts yes/no/on/off/1/0)",
        )
        parser.add_argument("--rollout", type=int)
        parser.add_argument("--enabled", choices=["true", "false"])
        parser.add_argument(
            "--kill-switch",
            dest="kill_switch",
            choices=["true", "false"],
            help="set the kill switch at create time (default false)",
        )
        parser.add_argument("--order", type=int)
        parser.add_argument("--attribute")
        parser.add_argument("--operator")
        parser.add_argument(
            "--value",
            help=(
                "rule comparison value, parsed as JSON when possible, otherwise "
                "treated as a raw string (quote to force a string, e.g. --value '\"100\"')"
            ),
        )
        parser.add_argument("--result", choices=["true", "false"])
        parser.add_argument("--user")
        parser.add_argument("--attr", action="append", default=[])
        parser.add_argument(
            "--strict",
            action="store_true",
            help="for list: raise an error when the environment does not exist",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="for history: maximum number of audit entries to show (newest first)",
        )

    def handle(self, *args, **options):
        try:
            return self._handle(*args, **options)
        except (FlagError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc

    def _handle(self, *args, **options):
        command = options["subcommand"]
        env = options["env"]
        key = options.get("key")
        actor = options["actor"]

        keyless = {"list", "env-list"}
        accepts_extra = {"rollout", "rule-delete"}
        if command in keyless and key:
            raise CommandError(f"{command} takes no flag key")
        if command not in accepts_extra and options["extra"]:
            raise CommandError(f"{command} got unexpected arguments: {' '.join(options['extra'])}")
        if command in accepts_extra and len(options["extra"]) > 1:
            raise CommandError(f"{command} takes at most one positional argument")

        if command == "list":
            return self._list(env, strict=options["strict"])
        if command == "env-list":
            return self._env_list()
        if command == "create":
            self._require_key(key, command)
            result = FlagService.create_flag(
                {
                    "environment": env,
                    "key": key,
                    "name": options.get("name") or key,
                    "description": options.get("description") or "",
                    "enabled": _parse_bool(options.get("enabled"), default=False),
                    "kill_switch": _parse_bool(options.get("kill_switch"), default=False),
                    "default": _parse_bool(options.get("default_value"), default=False),
                    "rollout_percentage": options.get("rollout") or 0,
                    "rules": [],
                },
                actor=actor,
            )
            verb = result.action
            self.stdout.write(
                self.style.SUCCESS(f"{verb}d {result.flag.environment.slug}:{result.flag.key}")
            )
            return None
        if command == "get":
            self._require_key(key, command)
            return self._get(env, key)
        if command == "update":
            self._require_key(key, command)
            data: dict[str, Any] = {}
            for field in ("name", "description"):
                if options.get(field) is not None:
                    data[field] = options[field]
            if options.get("default_value") is not None:
                data["default"] = _parse_bool(options["default_value"])
            if options.get("rollout") is not None:
                data["rollout_percentage"] = options["rollout"]
            if options.get("enabled") is not None:
                data["enabled"] = _parse_bool(options["enabled"])
            if not data:
                raise CommandError("update requires at least one field to change")
            flag = FlagService.update_flag(env, key, data, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"updated {flag.environment.slug}:{flag.key}"))
            return None
        if command == "delete":
            self._require_key(key, command)
            FlagService.delete_flag(env, key, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"deleted {env}:{key}"))
            return None
        if command == "enable":
            self._require_key(key, command)
            FlagService.enable_flag(env, key, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"enabled {env}:{key}"))
            return None
        if command == "disable":
            self._require_key(key, command)
            FlagService.disable_flag(env, key, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"disabled {env}:{key}"))
            return None
        if command == "kill":
            self._require_key(key, command)
            FlagService.set_kill_switch(env, key, True, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"kill switch enabled for {env}:{key}"))
            return None
        if command == "unkill":
            self._require_key(key, command)
            FlagService.set_kill_switch(env, key, False, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"kill switch disabled for {env}:{key}"))
            return None
        if command == "rollout":
            self._require_key(key, command)
            percent = options.get("rollout")
            if percent is None:
                if not options["extra"]:
                    raise CommandError("rollout requires a percentage")
                percent = int(options["extra"][0])
            FlagService.set_rollout(env, key, percent, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"set rollout for {env}:{key} to {percent}%"))
            return None
        if command == "rule-add":
            self._require_key(key, command)
            missing = [
                name
                for name in ("attribute", "operator", "value", "result")
                if options.get(name) is None
            ]
            if missing:
                raise CommandError(f"rule-add missing: {', '.join(missing)}")
            rule = RuleService.add_rule(
                env,
                key,
                {
                    "order": options.get("order"),
                    "attribute": options["attribute"],
                    "operator": options["operator"],
                    "value": _parse_value(options["value"]),
                    "result": _parse_bool(options["result"]),
                },
                actor=actor,
            )
            self.stdout.write(self.style.SUCCESS(f"added rule {rule.id} to {env}:{key}"))
            return None
        if command == "rule-delete":
            self._require_key(key, command)
            if not options["extra"]:
                raise CommandError("rule-delete requires a rule id")
            RuleService.delete_rule(env, key, int(options["extra"][0]), actor=actor)
            self.stdout.write(
                self.style.SUCCESS(f"deleted rule {options['extra'][0]} from {env}:{key}")
            )
            return None
        if command == "eval":
            self._require_key(key, command)
            context = _parse_context(options.get("user"), options.get("attr") or [])
            result = EvaluationService.evaluate_from_db(env, key, context)
            self.stdout.write(f"{result.flag_key} = {str(result.value).lower()}")
            self.stdout.write(f"reason: {result.reason}")
            if result.matched_rule_id:
                self.stdout.write(f"matched rule: {result.matched_rule_id}")
            if result.bucket is not None:
                self.stdout.write(f"bucket: {result.bucket}")
            return None
        if command == "history":
            self._require_key(key, command)
            limit = options.get("limit")
            for entry in FlagService.get_history(env, key, limit=limit):
                self.stdout.write(f"{entry.created_at.isoformat()} {entry.actor} {entry.action}")
            return None

        raise CommandError(f"unknown command: {command}")

    def _env_list(self):
        from django.db.models import Count, Q

        self.stdout.write("SLUG                 ACTIVE FLAGS")
        for env in (
            Environment.objects.annotate(
                active_flags=Count("flags", filter=Q(flags__archived_at__isnull=True))
            )
            .order_by("slug")
            .iterator()
        ):
            self.stdout.write(f"{env.slug:<20} {env.active_flags:>5}")
        return None

    def _list(self, env: str, *, strict: bool = False):
        if not strict and not Environment.objects.filter(slug=env).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"warning: environment '{env}' does not exist (no flags to show)"
                )
            )
        self.stdout.write("KEY                 ENABLED  KILL  ROLLOUT  DEFAULT")
        for flag in FlagService.list_flags(env, strict=strict):
            self.stdout.write(
                f"{flag.key:<19} {yes_no(flag.enabled):<7} {yes_no(flag.kill_switch):<5} "
                f"{flag.rollout_percentage:>3}%     {str(flag.default_value).lower()}"
            )
        return None

    def _get(self, env: str, key: str):
        flag = FlagService.get_flag(env, key)
        self.stdout.write(f"key: {flag.key}")
        self.stdout.write(f"name: {flag.name}")
        self.stdout.write(f"description: {flag.description}")
        self.stdout.write(f"environment: {flag.environment.slug}")
        self.stdout.write(f"enabled: {flag.enabled}")
        self.stdout.write(f"kill_switch: {flag.kill_switch}")
        self.stdout.write(f"default: {flag.default_value}")
        self.stdout.write(f"rollout_percentage: {flag.rollout_percentage}")
        self.stdout.write(f"version: {flag.version}")
        self.stdout.write("rules:")
        for rule in flag.rules.all().order_by("order"):
            self.stdout.write(
                f"  {rule.id}: order={rule.order} {rule.attribute} "
                f"{rule.operator} {rule.value!r} -> {rule.result}"
            )
        return None

    def _require_key(self, key: str | None, command: str) -> None:
        if not key:
            raise CommandError(f"{command} requires a flag key")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _parse_bool(value: str | bool | None, default: bool | None = None) -> bool:
    if value is None:
        if default is None:
            raise ValueError("boolean value is required")
        return default
    if isinstance(value, bool):
        return value
    normalized = value.lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _parse_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_context(user_id: str | None, attrs: list[str]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if user_id:
        context["user_id"] = user_id
    for attr in attrs:
        if "=" not in attr:
            raise ValueError(f"attribute must be key=value: {attr}")
        key, value = attr.split("=", 1)
        context[key] = _parse_value(value)
    return context
