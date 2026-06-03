"""Import shims and Django app wiring."""

from flags_core.context import EvaluationContext as ContextShim
from flags_core.models import EvaluationContext
from flags_core.snapshot import Snapshot as SnapshotShim, evaluate_snapshot as eval_shim
from flags_django.apps import FlagsDjangoConfig


def test_context_module_all():
    import flags_core.context as ctx

    assert ctx.__all__ == ["EvaluationContext"]
    assert ContextShim is EvaluationContext


def test_snapshot_module_all():
    import flags_core.snapshot as snap

    assert set(snap.__all__) == {"Snapshot", "evaluate_snapshot"}
    assert SnapshotShim is snap.Snapshot
    assert eval_shim is snap.evaluate_snapshot


def test_flags_django_app_config():
    assert FlagsDjangoConfig.name == "flags_django"
