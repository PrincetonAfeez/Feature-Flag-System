"""Additional evaluator paths: EvaluationContext input, logging, exports."""

import logging

import pytest

import flags_core
from flags_core.evaluator import evaluate
from flags_core.models import EvaluationContext, RuleDefinition


def test_evaluate_accepts_evaluation_context_instance(make_flag):
    flag = make_flag(
        rules=[RuleDefinition("1", 1, "plan", "equals", "premium", True)],
    )
    context = EvaluationContext(user_id="u1", attributes={"plan": "premium"})
    result = evaluate(flag, context)
    assert result.value is True
    assert result.reason == "targeting_match"


def test_evaluate_accepts_none_context_with_rollout_zero(make_flag):
    result = evaluate(make_flag(rollout_percentage=0), None)
    assert result.reason == "rollout_zero"


def test_evaluate_logs_warning_on_failure(make_flag, caplog):
    flag = make_flag(
        default=True,
        rules=[
            RuleDefinition("a", 1, "plan", "equals", "x", True),
            RuleDefinition("b", None, "plan", "equals", "y", True),  # type: ignore[arg-type]
        ],
    )
    with caplog.at_level(logging.WARNING):
        result = evaluate(flag, {"user_id": "u1"})
    assert result.reason == "error"
    assert any("failed; returning default" in record.message for record in caplog.records)


def test_flags_core_public_exports():
    assert set(flags_core.__all__) == {
        "EvaluationContext",
        "EvaluationResult",
        "FlagDefinition",
        "RuleDefinition",
        "Snapshot",
        "evaluate",
        "evaluate_snapshot",
    }
    assert flags_core.evaluate is evaluate
