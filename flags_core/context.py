"""Stable import location for the evaluation context dataclass.

`EvaluationContext` is defined in :mod:`flags_core.models`. This module re-exports
it so adapters and the future client SDK can depend on a small, intention-revealing
import path (``from flags_core.context import EvaluationContext``) that stays stable
even if the internal module layout changes.
"""

from flags_core.models import EvaluationContext

__all__ = ["EvaluationContext"]
