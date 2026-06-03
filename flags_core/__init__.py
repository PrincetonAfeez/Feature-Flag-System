"""Pure feature flag evaluation core."""

from flags_core.evaluator import evaluate, evaluate_snapshot
from flags_core.models import (
    EvaluationContext,
    EvaluationResult,
    FlagDefinition,
    RuleDefinition,
    Snapshot,
)

__all__ = [
    "EvaluationContext",
    "EvaluationResult",
    "FlagDefinition",
    "RuleDefinition",
    "Snapshot",
    "evaluate",
    "evaluate_snapshot",
]
