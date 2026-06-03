"""Tests for the domain error taxonomy."""

import pytest

from flags_core.errors import (
    EnvironmentNotFoundError,
    FlagAlreadyExistsError,
    FlagError,
    FlagNotFoundError,
    FlagValidationError,
    RuleNotFoundError,
    SchemaError,
    SnapshotError,
    StaleConfigError,
)


def test_flag_validation_error_joins_messages():
    exc = FlagValidationError(["first problem", "second problem"])
    assert exc.errors == ["first problem", "second problem"]
    assert str(exc) == "first problem; second problem"


def test_exception_hierarchy():
    assert issubclass(FlagNotFoundError, FlagError)
    assert issubclass(FlagAlreadyExistsError, FlagError)
    assert issubclass(RuleNotFoundError, FlagError)
    assert issubclass(EnvironmentNotFoundError, FlagError)
    assert issubclass(FlagValidationError, SchemaError)
    assert issubclass(SchemaError, FlagError)
    assert issubclass(SnapshotError, FlagError)
    assert issubclass(StaleConfigError, FlagError)


def test_errors_are_catchable_as_flag_error():
    with pytest.raises(FlagError):
        raise FlagNotFoundError("missing")
    with pytest.raises(FlagError):
        raise FlagValidationError(["bad"])
    with pytest.raises(FlagError):
        raise SnapshotError("bad snapshot")
    with pytest.raises(FlagError):
        raise StaleConfigError("stale")
