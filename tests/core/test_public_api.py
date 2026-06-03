"""The shim modules are stable public import seams for the future client SDK."""

from flags_core.context import EvaluationContext
from flags_core.evaluator import evaluate_snapshot as core_evaluate_snapshot
from flags_core.models import EvaluationContext as ModelEvaluationContext
from flags_core.models import Snapshot as ModelSnapshot
from flags_core.snapshot import Snapshot, evaluate_snapshot


def test_context_shim_reexports_model_type():
    assert EvaluationContext is ModelEvaluationContext


def test_snapshot_shim_reexports_model_and_evaluator():
    assert Snapshot is ModelSnapshot
    assert evaluate_snapshot is core_evaluate_snapshot
