"""JSON serialization for pure snapshot dataclasses."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from flags_core.errors import FlagValidationError, SnapshotError
from flags_core.models import FlagDefinition, RuleDefinition, Snapshot
from flags_core.schema import coerce_strict_int, validate_flag_definition


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "environment": snapshot.environment,
        "version": snapshot.version,
        "generated_at": snapshot.generated_at,
        "flags": {key: _flag_to_dict(flag) for key, flag in snapshot.flags.items()},
    }


def snapshot_from_dict(data: dict[str, Any]) -> Snapshot:
    try:
        snapshot_environment = data["environment"]
        flags: dict[str, FlagDefinition] = {}
        for key, flag_data in data.get("flags", {}).items():
            flag = _flag_from_dict(flag_data)
            if key != flag.key:
                raise SnapshotError(f"flag map key '{key}' does not match flag.key '{flag.key}'")
            if flag.environment != snapshot_environment:
                raise SnapshotError(
                    f"flag '{key}' environment '{flag.environment}' does not match "
                    f"snapshot environment '{snapshot_environment}'"
                )
            try:
                validate_flag_definition(flag)
            except FlagValidationError as exc:
                raise SnapshotError(f"invalid flag '{key}': {exc}") from exc
            flags[key] = flag
        return Snapshot(
            environment=snapshot_environment,
            version=_parse_json_int(data["version"], "version"),
            generated_at=data["generated_at"],
            flags=flags,
        )
    except SnapshotError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError(f"invalid snapshot payload: {exc}") from exc


def snapshot_to_json(snapshot: Snapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), sort_keys=True)


def snapshot_from_json(json_text: str) -> Snapshot:
    try:
        return snapshot_from_dict(json.loads(json_text))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"invalid snapshot JSON: {exc}") from exc


def _flag_to_dict(flag: FlagDefinition) -> dict[str, Any]:
    return asdict(flag)


def _flag_from_dict(data: dict[str, Any]) -> FlagDefinition:
    rules = [_rule_from_dict(rule_data) for rule_data in data.get("rules", [])]
    return FlagDefinition(
        key=data["key"],
        name=data.get("name", data["key"]),
        environment=data["environment"],
        enabled=_parse_json_bool(data["enabled"], "enabled"),
        kill_switch=_parse_json_bool(data["kill_switch"], "kill_switch"),
        default=_parse_json_bool(data["default"], "default"),
        rollout_percentage=_parse_json_int(data["rollout_percentage"], "rollout_percentage"),
        rules=rules,
        version=_parse_json_int(data.get("version", 1), "version"),
    )


def _rule_from_dict(data: dict[str, Any]) -> RuleDefinition:
    return RuleDefinition(
        id=str(data["id"]),
        order=_parse_json_int(data["order"], "order"),
        attribute=data["attribute"],
        operator=data["operator"],
        value=data["value"],
        result=_parse_json_bool(data["result"], "result"),
    )


def _parse_json_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise SnapshotError(f"{field_name} must be a JSON boolean true or false")


def _parse_json_int(value: Any, field_name: str) -> int:
    try:
        return coerce_strict_int(value, field_name)
    except FlagValidationError as exc:
        raise SnapshotError(str(exc)) from exc
