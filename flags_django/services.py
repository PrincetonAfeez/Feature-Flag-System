"""Application services for feature flag persistence and snapshots."""

from __future__ import annotations

from typing import Any, NamedTuple

from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from flags_core.errors import (
    EnvironmentNotFoundError,
    FlagAlreadyExistsError,
    FlagNotFoundError,
    FlagValidationError,
    RuleNotFoundError,
)
from flags_core.evaluator import evaluate
from flags_core.models import EvaluationContext, FlagDefinition, RuleDefinition, Snapshot
from flags_core.schema import coerce_strict_bool, coerce_strict_int, validate_flag_definition
from flags_core.serialization import snapshot_to_dict
from flags_django.converters import flag_model_to_core, flag_model_to_dict
from flags_django.models import AuditLog, Environment, FeatureFlag, FlagRule, SnapshotVersion
from flags_django.sse import notify_flags_changed


class FlagCreateResult(NamedTuple):
    flag: FeatureFlag
    action: str  # "create" or "recreate"


class FlagService:
    @staticmethod
    def list_flags(environment: str, include_archived: bool = False, strict: bool = False):
        """List flags in an environment.

        When ``strict`` is False (default), an unknown environment returns an empty
        queryset — convenient for CLI listing. When ``strict`` is True, the same
        case raises ``EnvironmentNotFoundError``, matching ``get_flag`` behavior.
        """
        try:
            env = _get_environment(environment)
        except EnvironmentNotFoundError:
            if strict:
                raise
            return FeatureFlag.objects.none()
        queryset = (
            FeatureFlag.objects.filter(environment=env)
            .select_related("environment")
            .prefetch_related(_ordered_rules())
        )
        if not include_archived:
            queryset = queryset.filter(archived_at__isnull=True)
        return queryset.order_by("key")

    @staticmethod
    def get_flag(environment: str, key: str) -> FeatureFlag:
        env = _get_environment(environment)
        try:
            return (
                FeatureFlag.objects.filter(environment=env, key=key, archived_at__isnull=True)
                .select_related("environment")
                .prefetch_related(_ordered_rules())
                .get()
            )
        except FeatureFlag.DoesNotExist as exc:
            raise FlagNotFoundError(f"flag '{key}' was not found in '{environment}'") from exc

    @staticmethod
    def create_flag(data: dict[str, Any], actor: str = "system") -> FlagCreateResult:
        try:
            flag_definition = _definition_from_data(data, environment=data["environment"])
        except KeyError as exc:
            field = exc.args[0] if exc.args else "field"
            raise FlagValidationError([f"missing required field: {field}"]) from exc
        validate_flag_definition(flag_definition)
        env = get_or_create_environment(flag_definition.environment)

        with transaction.atomic():
            if FeatureFlag.objects.filter(
                environment=env, key=flag_definition.key, archived_at__isnull=True
            ).exists():
                raise FlagAlreadyExistsError(
                    f"flag '{flag_definition.key}' already exists in '{env.slug}'"
                )

            archived = FeatureFlag.objects.filter(
                environment=env, key=flag_definition.key, archived_at__isnull=False
            ).first()

            if archived is not None:
                flag = _reuse_archived_flag(archived, flag_definition, data)
                audit_action = "recreate"
            else:
                try:
                    flag = FeatureFlag.objects.create(
                        environment=env,
                        key=flag_definition.key,
                        name=flag_definition.name,
                        description=data.get("description", ""),
                        enabled=flag_definition.enabled,
                        kill_switch=flag_definition.kill_switch,
                        default_value=flag_definition.default,
                        rollout_percentage=flag_definition.rollout_percentage,
                        version=1,
                    )
                except IntegrityError as exc:
                    raise FlagAlreadyExistsError(
                        f"flag '{flag_definition.key}' already exists in '{env.slug}'"
                    ) from exc
                _write_rules(flag, flag_definition.rules)
                audit_action = "create"

            flag = _reload_flag(flag.pk)
            _audit(flag, audit_action, actor, before=None, after=flag_model_to_dict(flag))
            SnapshotService.mark_snapshot_changed(env.slug)
            return FlagCreateResult(flag, audit_action)

    @staticmethod
    def update_flag(
        environment: str, key: str, data: dict[str, Any], actor: str = "system"
    ) -> FeatureFlag:
        env = _get_environment(environment)
        with transaction.atomic():
            flag = _locked_flag(env.slug, key)
            before = flag_model_to_dict(flag)
            merged = {
                "key": flag.key,
                "name": data.get("name", flag.name),
                "environment": env.slug,
                "enabled": data.get("enabled", flag.enabled),
                "kill_switch": data.get("kill_switch", flag.kill_switch),
                "default": data.get("default", flag.default_value),
                "rollout_percentage": data.get("rollout_percentage", flag.rollout_percentage),
                "rules": _rule_definitions_from_models(flag),
                "version": flag.version + 1,
            }
            try:
                validate_flag_definition(_definition_from_data(merged, environment=env.slug))
            except KeyError as exc:
                field = exc.args[0] if exc.args else "field"
                raise FlagValidationError([f"missing required field: {field}"]) from exc
            flag.name = merged["name"]
            flag.description = data.get("description", flag.description)
            flag.enabled = merged["enabled"]
            flag.kill_switch = merged["kill_switch"]
            flag.default_value = merged["default"]
            flag.rollout_percentage = merged["rollout_percentage"]
            flag.version += 1
            try:
                flag.save()
            except IntegrityError as exc:
                raise FlagValidationError(["conflicting flag update"]) from exc
            flag = _reload_flag(flag.pk)
            _audit(flag, "update", actor, before=before, after=flag_model_to_dict(flag))
            SnapshotService.mark_snapshot_changed(env.slug)
            return flag

    @staticmethod
    def enable_flag(environment: str, key: str, actor: str = "system") -> FeatureFlag:
        return FlagService.update_flag(environment, key, {"enabled": True}, actor=actor)

    @staticmethod
    def disable_flag(environment: str, key: str, actor: str = "system") -> FeatureFlag:
        return FlagService.update_flag(environment, key, {"enabled": False}, actor=actor)

    @staticmethod
    def set_kill_switch(
        environment: str, key: str, value: bool, actor: str = "system"
    ) -> FeatureFlag:
        return FlagService.update_flag(environment, key, {"kill_switch": value}, actor=actor)

    @staticmethod
    def set_rollout(environment: str, key: str, percent: int, actor: str = "system") -> FeatureFlag:
        rollout = coerce_strict_int(percent, "rollout_percentage")
        return FlagService.update_flag(
            environment, key, {"rollout_percentage": rollout}, actor=actor
        )

    @staticmethod
    def delete_flag(environment: str, key: str, actor: str = "system") -> FeatureFlag:
        env = _get_environment(environment)
        with transaction.atomic():
            flag = _locked_flag(env.slug, key)
            before = flag_model_to_dict(flag)
            flag.archived_at = timezone.now()
            flag.enabled = False
            flag.version += 1
            try:
                flag.save(update_fields=["archived_at", "enabled", "version", "updated_at"])
            except IntegrityError as exc:
                raise FlagValidationError(["conflicting flag delete"]) from exc
            flag = _reload_flag(flag.pk)
            _audit(flag, "delete", actor, before=before, after=flag_model_to_dict(flag))
            SnapshotService.mark_snapshot_changed(env.slug)
            return flag

    @staticmethod
    def get_history(environment: str, key: str, limit: int | None = None):
        env = _get_environment(environment)
        flags = FeatureFlag.objects.filter(environment=env, key=key)
        if not flags.exists():
            raise FlagNotFoundError(f"flag '{key}' was not found in '{environment}'")
        queryset = (
            AuditLog.objects.filter(environment=env, flag__in=flags)
            .select_related("environment", "flag")
            .order_by("-created_at", "-id")
        )
        if limit is not None:
            return queryset[:limit]
        return queryset


def _required_rule_field(data: dict[str, Any], field: str) -> Any:
    if field not in data:
        raise FlagValidationError([f"missing required field: {field}"])
    return data[field]


def _coerce_rule_order(order: Any, fallback: int) -> int:
    if order is None:
        return fallback
    return coerce_strict_int(order, "order")


class RuleService:
    @staticmethod
    def add_rule(
        environment: str, flag_key: str, data: dict[str, Any], actor: str = "system"
    ) -> FlagRule:
        env = _get_environment(environment)
        with transaction.atomic():
            flag = _locked_flag(env.slug, flag_key)
            before = flag_model_to_dict(flag)
            max_order = flag.rules.aggregate(max_order=Max("order"))["max_order"] or 0
            order = _coerce_rule_order(data.get("order"), max_order + 1)
            rule = FlagRule(
                flag=flag,
                order=order,
                attribute=_required_rule_field(data, "attribute"),
                operator=_required_rule_field(data, "operator"),
                value=_required_rule_field(data, "value"),
                result=coerce_strict_bool(_required_rule_field(data, "result"), "result"),
            )
            proposed_rules = _rule_definitions_from_models(flag) + [
                _rule_definition_from_unsaved(rule)
            ]
            proposed = flag_model_to_core(flag, validate=False)
            validate_flag_definition(
                FlagDefinition(
                    key=proposed.key,
                    name=proposed.name,
                    environment=proposed.environment,
                    enabled=proposed.enabled,
                    kill_switch=proposed.kill_switch,
                    default=proposed.default,
                    rollout_percentage=proposed.rollout_percentage,
                    rules=proposed_rules,
                    version=proposed.version,
                )
            )
            try:
                rule.save()
            except IntegrityError as exc:
                raise FlagValidationError([f"duplicate rule order: {order}"]) from exc
            flag.version += 1
            flag.save(update_fields=["version", "updated_at"])
            flag = _reload_flag(flag.pk)
            _audit(flag, "rule_added", actor, before=before, after=flag_model_to_dict(flag))
            SnapshotService.mark_snapshot_changed(env.slug)
            return rule

    @staticmethod
    def delete_rule(environment: str, flag_key: str, rule_id: int, actor: str = "system") -> None:
        env = _get_environment(environment)
        with transaction.atomic():
            flag = _locked_flag(env.slug, flag_key)
            before = flag_model_to_dict(flag)
            try:
                rule = flag.rules.get(id=rule_id)
            except FlagRule.DoesNotExist as exc:
                raise RuleNotFoundError(
                    f"rule '{rule_id}' was not found on flag '{flag_key}'"
                ) from exc
            rule.delete()
            flag.version += 1
            try:
                flag.save(update_fields=["version", "updated_at"])
            except IntegrityError as exc:
                raise FlagValidationError(["conflicting rule delete"]) from exc
            flag = _reload_flag(flag.pk)
            _audit(flag, "rule_removed", actor, before=before, after=flag_model_to_dict(flag))
            SnapshotService.mark_snapshot_changed(env.slug)


class SnapshotService:
    @staticmethod
    def build_snapshot(environment: str) -> Snapshot:
        env = _get_environment(environment)
        return SnapshotService._build(env, _snapshot_version(env))

    @staticmethod
    def _build(env: Environment, snapshot_version: SnapshotVersion) -> Snapshot:
        flags = {
            flag.key: flag_model_to_core(flag)
            for flag in FeatureFlag.objects.filter(environment=env, archived_at__isnull=True)
            .select_related("environment")
            .prefetch_related(_ordered_rules())
            .order_by("key")
        }
        return Snapshot(
            environment=env.slug,
            version=snapshot_version.version,
            generated_at=snapshot_version.updated_at.isoformat(),
            flags=flags,
        )

    @staticmethod
    def serialize_snapshot(environment: str) -> dict[str, Any]:
        return snapshot_to_dict(SnapshotService.build_snapshot(environment))

    @staticmethod
    def serialize_with_etag(environment: str) -> tuple[dict[str, Any], str]:
        env = _get_environment(environment)
        snapshot_version = _snapshot_version(env)
        snapshot = SnapshotService._build(env, snapshot_version)
        return snapshot_to_dict(snapshot), snapshot_version.quoted_etag

    @staticmethod
    def mark_snapshot_changed(environment: str) -> SnapshotVersion:
        env = _get_environment(environment)
        _snapshot_version(env)
        version = SnapshotVersion.objects.select_for_update().get(environment=env)
        version.version += 1
        version.save()
        transaction.on_commit(
            lambda: notify_flags_changed(env.slug, version.version, version.quoted_etag)
        )
        return version


class EvaluationService:
    @staticmethod
    def evaluate_from_db(environment: str, flag_key: str, context: EvaluationContext | dict):
        flag = FlagService.get_flag(environment, flag_key)
        return evaluate(flag_model_to_core(flag), context)

    @staticmethod
    def convert_model_to_core(flag: FeatureFlag):
        return flag_model_to_core(flag)


def get_or_create_environment(slug: str) -> Environment:
    return Environment.objects.get_or_create(slug=slug, defaults={"name": slug.title()})[0]


def _get_environment(slug: str) -> Environment:
    try:
        return Environment.objects.get(slug=slug)
    except Environment.DoesNotExist as exc:
        raise EnvironmentNotFoundError(f"environment '{slug}' was not found") from exc


def _ordered_rules() -> Prefetch:
    return Prefetch("rules", queryset=FlagRule.objects.order_by("order"))


def _snapshot_version(environment: Environment) -> SnapshotVersion:
    return SnapshotVersion.objects.get_or_create(environment=environment)[0]


def _reload_flag(flag_id: int) -> FeatureFlag:
    return (
        FeatureFlag.objects.filter(pk=flag_id)
        .select_related("environment")
        .prefetch_related(_ordered_rules())
        .get()
    )


def _locked_flag(environment: str, key: str) -> FeatureFlag:
    env = _get_environment(environment)
    try:
        flag_id = (
            FeatureFlag.objects.select_for_update()
            .filter(environment=env, key=key, archived_at__isnull=True)
            .values_list("id", flat=True)
            .get()
        )
    except FeatureFlag.DoesNotExist as exc:
        raise FlagNotFoundError(f"flag '{key}' was not found in '{environment}'") from exc
    return _reload_flag(flag_id)


def _reuse_archived_flag(
    archived: FeatureFlag, flag_definition: FlagDefinition, data: dict[str, Any]
) -> FeatureFlag:
    archived.archived_at = None
    archived.name = flag_definition.name
    archived.description = data.get("description", "")
    archived.enabled = flag_definition.enabled
    archived.kill_switch = flag_definition.kill_switch
    archived.default_value = flag_definition.default
    archived.rollout_percentage = flag_definition.rollout_percentage
    archived.version = archived.version + 1
    archived.save()
    archived.rules.all().delete()
    _write_rules(archived, flag_definition.rules)
    return archived


def _coerce_rule(raw: RuleDefinition | dict[str, Any]) -> RuleDefinition:
    if isinstance(raw, RuleDefinition):
        return raw
    order_raw = raw.get("order")
    return RuleDefinition(
        id=str(raw.get("id") or order_raw or ""),
        order=coerce_strict_int(order_raw, "order") if order_raw is not None else 0,
        attribute=raw.get("attribute", ""),
        operator=raw.get("operator", ""),
        value=raw.get("value"),
        result=coerce_strict_bool(raw.get("result"), "rule result"),
    )


def _optional_strict_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    if key not in data:
        return default
    return coerce_strict_bool(data[key], key)


def _definition_from_data(data: dict[str, Any], environment: str) -> FlagDefinition:
    missing = [field for field in ("key", "default") if field not in data]
    if missing:
        raise FlagValidationError([f"missing required field: {field}" for field in missing])
    rollout_raw = data.get("rollout_percentage", 0)
    version_raw = data.get("version", 1)
    return FlagDefinition(
        key=data["key"],
        name=data.get("name") or data["key"],
        environment=environment,
        enabled=_optional_strict_bool(data, "enabled", False),
        kill_switch=_optional_strict_bool(data, "kill_switch", False),
        default=coerce_strict_bool(data["default"], "default"),
        rollout_percentage=coerce_strict_int(rollout_raw, "rollout_percentage"),
        rules=[_coerce_rule(rule) for rule in data.get("rules", [])],
        version=coerce_strict_int(version_raw, "version"),
    )


def _write_rules(flag: FeatureFlag, rules: list[RuleDefinition]) -> None:
    try:
        for rule in rules:
            FlagRule.objects.create(
                flag=flag,
                order=rule.order,
                attribute=rule.attribute,
                operator=rule.operator,
                value=rule.value,
                result=rule.result,
            )
    except IntegrityError as exc:
        raise FlagValidationError(["duplicate rule order in flag definition"]) from exc


def _rule_definitions_from_models(flag: FeatureFlag) -> list[RuleDefinition]:
    return [
        RuleDefinition(
            id=str(rule.id),
            order=rule.order,
            attribute=rule.attribute,
            operator=rule.operator,
            value=rule.value,
            result=rule.result,
        )
        for rule in flag.rules.all()
    ]


def _rule_definition_from_unsaved(rule: FlagRule) -> RuleDefinition:
    return RuleDefinition(
        id=str(rule.id or f"new-{rule.order}"),
        order=rule.order,
        attribute=rule.attribute,
        operator=rule.operator,
        value=rule.value,
        result=rule.result,
    )


def _audit(
    flag: FeatureFlag, action: str, actor: str, before: dict | None, after: dict | None
) -> None:
    AuditLog.objects.create(
        flag=flag,
        environment=flag.environment,
        action=action,
        actor=actor,
        before=before,
        after=after,
    )
