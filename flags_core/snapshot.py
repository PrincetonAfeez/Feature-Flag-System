"""Stable import location for local snapshot evaluation.

`Snapshot` and `evaluate_snapshot` are defined in :mod:`flags_core.models` and
:mod:`flags_core.evaluator`. This module re-exports them as the public seam the
future client SDK will use to evaluate flags against a locally cached snapshot
(see docs/adr/0001-local-snapshot-local-evaluation.md).
"""

from flags_core.evaluator import evaluate_snapshot
from flags_core.models import Snapshot

__all__ = ["Snapshot", "evaluate_snapshot"]
