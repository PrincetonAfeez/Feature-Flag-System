"""Shared pytest fixtures for the feature flag test suite."""

import pytest

from flags_core.models import FlagDefinition


@pytest.fixture
def make_flag():
    """Factory for a valid FlagDefinition with overridable fields.

    Centralizes the definition that core tests previously duplicated, so the
    canonical "valid flag" lives in exactly one place.
    """

    def _make_flag(**overrides) -> FlagDefinition:
        data = {
            "key": "new_checkout",
            "name": "New Checkout",
            "environment": "production",
            "enabled": True,
            "kill_switch": False,
            "default": False,
            "rollout_percentage": 0,
            "rules": [],
            "version": 1,
        }
        data.update(overrides)
        return FlagDefinition(**data)

    return _make_flag
