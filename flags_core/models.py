"""Dataclasses used by the pure evaluation core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleDefinition:
    id: str
    order: int
    attribute: str
    operator: str
    value: Any
    result: bool


@dataclass(frozen=True)
class FlagDefinition:
    key: str
    name: str
    environment: str
    enabled: bool
    kill_switch: bool
    default: bool
    rollout_percentage: int
    rules: list[RuleDefinition] = field(default_factory=list)
    version: int = 1


@dataclass(frozen=True)
class EvaluationContext:
    user_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> EvaluationContext:
        if data is None:
            return cls()
        user_id = _normalize_user_id(data.get("user_id"))
        attributes = {key: value for key, value in data.items() if key != "user_id"}
        return cls(user_id=user_id, attributes=attributes)


def _normalize_user_id(user_id: Any) -> str | None:
    """Accept string or integer user ids; reject booleans and other types."""
    if user_id is None:
        return None
    if isinstance(user_id, bool):
        raise ValueError("user_id must be a string or integer, not a boolean")
    if isinstance(user_id, int):
        return str(user_id)
    if isinstance(user_id, str):
        return user_id if user_id else None
    raise ValueError(f"user_id must be a string or integer, got {type(user_id).__name__}")


@dataclass(frozen=True)
class EvaluationResult:
    flag_key: str
    value: bool
    reason: str
    matched_rule_id: str | None = None
    bucket: int | None = None
    default_used: bool = False
    error: str | None = None


@dataclass(frozen=True)
class Snapshot:
    environment: str
    version: int
    generated_at: str
    flags: dict[str, FlagDefinition]
