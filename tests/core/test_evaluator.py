"""Tests for the evaluator module."""

from flags_core.bucketing import bucket_user
from flags_core.evaluator import evaluate, evaluate_snapshot
from flags_core.models import EvaluationContext, FlagDefinition, RuleDefinition, Snapshot


def test_kill_switch_overrides_rules_and_rollout(make_flag):
    flag = make_flag(
        kill_switch=True,
        rollout_percentage=100,
        rules=[
            RuleDefinition("1", 1, "plan", "equals", "premium", True),
        ],
    )

    result = evaluate(flag, {"user_id": "u1", "plan": "premium"})

    assert result.value is False
    assert result.reason == "kill_switch"
    assert result.matched_rule_id is None


def test_disabled_flag_returns_default(make_flag):
    result = evaluate(make_flag(enabled=False, default=True), {"user_id": "u1"})

    assert result.value is True
    assert result.reason == "flag_disabled"
    assert result.default_used is True


def test_ordered_rules_first_match_wins(make_flag):
    flag = make_flag(
        default=False,
        rules=[
            RuleDefinition("first", 1, "plan", "equals", "premium", True),
            RuleDefinition("second", 2, "country", "equals", "US", False),
        ],
    )

    result = evaluate(flag, {"user_id": "u1", "plan": "premium", "country": "US"})

    assert result.value is True
    assert result.reason == "targeting_match"
    assert result.matched_rule_id == "first"


def test_missing_attribute_does_not_crash(make_flag):
    flag = make_flag(rules=[RuleDefinition("1", 1, "plan", "equals", "premium", True)])

    result = evaluate(flag, {"user_id": "u1", "country": "US"})

    # No rule matches and rollout is 0, so the flag returns its default.
    assert result.value is False
    assert result.reason == "rollout_zero"
    assert result.default_used is True


def test_rollout_zero_returns_default(make_flag):
    result = evaluate(make_flag(rollout_percentage=0, default=False), {"user_id": "u1"})

    assert result.value is False
    assert result.reason == "rollout_zero"
    assert result.default_used is True


def test_rollout_100_enables_everyone(make_flag):
    result = evaluate(make_flag(rollout_percentage=100), {"user_id": "anyone"})

    assert result.value is True
    assert result.reason == "percentage_rollout"


def test_user_inside_rollout_is_enabled(make_flag):
    # Find a user whose bucket is low so a generous rollout includes them.
    user = next(
        u for u in (f"user_{i}" for i in range(1000)) if bucket_user("new_checkout", u) < 50
    )
    result = evaluate(make_flag(rollout_percentage=50), {"user_id": user})

    assert result.value is True
    assert result.reason == "percentage_rollout"
    assert result.bucket is not None


def test_user_outside_rollout_uses_default(make_flag):
    # Pick a user with a mid-range bucket so a rollout == bucket excludes them
    # (bucket < rollout is False), exercising the post-bucket "default" branch.
    user = next(
        u for u in (f"user_{i}" for i in range(1000)) if 1 <= bucket_user("new_checkout", u) <= 98
    )
    bucket = bucket_user("new_checkout", user)

    result = evaluate(make_flag(rollout_percentage=bucket, default=False), {"user_id": user})

    assert result.value is False
    assert result.reason == "default"
    assert result.bucket == bucket
    assert result.default_used is True


def test_missing_user_id_for_percentage_rollout_returns_default(make_flag):
    result = evaluate(make_flag(rollout_percentage=50, default=False), {"country": "US"})

    assert result.value is False
    assert result.reason == "missing_context"
    assert result.default_used is True


def test_unexpected_error_fails_safe_to_default(make_flag):
    # Mixing a None order with an int order makes sorted() raise a TypeError,
    # which must fail safe to the flag default rather than crash the caller.
    flag = make_flag(
        default=True,
        rules=[
            RuleDefinition("a", 1, "plan", "equals", "x", True),
            RuleDefinition("b", None, "plan", "equals", "y", True),
        ],
    )

    result = evaluate(flag, {"user_id": "u1", "plan": "z"})

    assert result.value is True
    assert result.reason == "error"
    assert result.default_used is True
    assert result.error is not None


def test_malformed_context_fails_safe_to_default(make_flag):
    # A non-mapping context (type-contract violation) must fail safe, not crash:
    # context normalization is inside the protected region.
    result = evaluate(make_flag(default=True), ["not", "a", "mapping"])

    assert result.value is True
    assert result.reason == "error"
    assert result.default_used is True
    assert result.error is not None


def test_kill_switch_honored_even_with_bad_context(make_flag):
    # kill_switch is the safety override and must win regardless of context shape.
    result = evaluate(make_flag(kill_switch=True), ["bad", "context"])

    assert result.value is False
    assert result.reason == "kill_switch"


def test_kill_switch_honored_before_invalid_definition(make_flag):
    # kill_switch is checked before schema validation so operators can disable
    # a flag even when stored metadata would fail validation.
    result = evaluate(make_flag(kill_switch=True, rollout_percentage=101), EvaluationContext())

    assert result.value is False
    assert result.reason == "kill_switch"


def test_snapshot_missing_flag_returns_caller_default():
    snapshot = Snapshot("production", 1, "now", {})

    result = evaluate_snapshot(snapshot, "missing", EvaluationContext(), default=True)

    assert result.value is True
    assert result.reason == "flag_not_found"


def test_no_snapshot_returns_caller_default():
    result = evaluate_snapshot(None, "anything", EvaluationContext(), default=True)

    assert result.value is True
    assert result.reason == "no_snapshot"
    assert result.default_used is True


def test_invalid_default_type_fails_safe_to_false():
    flag = FlagDefinition(
        key="bad",
        name="Bad",
        environment="production",
        enabled=True,
        kill_switch=False,
        default="not_bool",
        rollout_percentage=50,
    )

    result = evaluate(flag, {"user_id": "u1"})

    assert result.value is False
    assert result.reason == "error"
    assert isinstance(result.value, bool)


def test_evaluation_context_with_invalid_user_id_fails_safe(make_flag):
    result = evaluate(make_flag(rollout_percentage=50), EvaluationContext(user_id=True))  # type: ignore[arg-type]

    assert result.reason == "error"
    assert isinstance(result.value, bool)
    assert "user_id" in (result.error or "")
