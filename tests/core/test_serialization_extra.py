"""Serialization error paths and round-trip edge cases."""

import pytest

from flags_core.errors import SnapshotError
from flags_core.serialization import snapshot_from_dict


def test_from_dict_rejects_non_int_snapshot_version_string():
    payload = {
        "environment": "production",
        "version": "one",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {},
    }
    with pytest.raises(SnapshotError, match="version must be an integer"):
        snapshot_from_dict(payload)
