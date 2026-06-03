"""Tests for flags_core.models dataclasses and helpers."""

from flags_core.models import EvaluationContext, EvaluationResult, FlagDefinition, RuleDefinition, Snapshot


def test_evaluation_context_from_none():
    ctx = EvaluationContext.from_mapping(None)
    assert ctx.user_id is None
    assert ctx.attributes == {}


def test_evaluation_context_preserves_attributes_without_user_id():
    ctx = EvaluationContext.from_mapping({"plan": "premium", "country": "US"})
    assert ctx.user_id is None
    assert ctx.attributes == {"plan": "premium", "country": "US"}


def test_evaluation_context_dataclass_fields():
    ctx = EvaluationContext(user_id="u1", attributes={"tier": "gold"})
    assert ctx.user_id == "u1"
    assert ctx.attributes["tier"] == "gold"


def test_evaluation_result_optional_fields():
    result = EvaluationResult(
        flag_key="f",
        value=True,
        reason="targeting_match",
        matched_rule_id="1",
        bucket=42,
        default_used=False,
        error=None,
    )
    assert result.matched_rule_id == "1"
    assert result.bucket == 42


def test_snapshot_and_flag_definition_defaults():
    flag = FlagDefinition(
        key="k",
        name="K",
        environment="production",
        enabled=False,
        kill_switch=False,
        default=False,
        rollout_percentage=0,
    )
    assert flag.rules == []
    assert flag.version == 1

    snap = Snapshot("production", 1, "now", {"k": flag})
    assert snap.flags["k"] is flag


def test_rule_definition_fields():
    rule = RuleDefinition("r1", 1, "plan", "equals", "premium", True)
    assert rule.id == "r1"
    assert rule.result is True
