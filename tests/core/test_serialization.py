"""Tests for the serialization module."""

import pytest

from flags_core.errors import SnapshotError
from flags_core.models import FlagDefinition, RuleDefinition, Snapshot
from flags_core.serialization import (
    snapshot_from_dict,
    snapshot_from_json,
    snapshot_to_dict,
    snapshot_to_json,
)


def _snapshot() -> Snapshot:
    flag = FlagDefinition(
        key="new_checkout",
        name="New Checkout",
        environment="production",
        enabled=True,
        kill_switch=False,
        default=False,
        rollout_percentage=25,
        rules=[RuleDefinition("r1", 1, "plan", "equals", "premium", True)],
        version=3,
    )
    return Snapshot("production", 7, "2026-01-01T00:00:00+00:00", {"new_checkout": flag})


def test_dict_round_trip_is_lossless():
    snap = _snapshot()
    assert snapshot_from_dict(snapshot_to_dict(snap)) == snap


def test_json_round_trip_is_lossless():
    snap = _snapshot()
    assert snapshot_from_json(snapshot_to_json(snap)) == snap


def test_to_dict_includes_rules():
    data = snapshot_to_dict(_snapshot())
    assert data["flags"]["new_checkout"]["rules"][0]["operator"] == "equals"


def test_from_dict_rejects_malformed_payload():
    with pytest.raises(SnapshotError):
        snapshot_from_dict({"environment": "production"})  # missing version and flags


def test_from_json_rejects_invalid_json():
    with pytest.raises(SnapshotError):
        snapshot_from_json("{not valid json")


def test_from_dict_rejects_semantically_invalid_flag():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "Bad Key": {
                "key": "Bad Key",
                "name": "Bad",
                "environment": "production",
                "enabled": True,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="invalid flag 'Bad Key'"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_string_booleans():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "checkout": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "production",
                "enabled": "false",
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="enabled must be a JSON boolean"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_mismatched_map_key():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "wrong_key": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "production",
                "enabled": False,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="does not match flag.key"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_environment_mismatch():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "checkout": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "staging",
                "enabled": False,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="does not match snapshot environment"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_bool_rollout_percentage():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "checkout": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "production",
                "enabled": False,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": True,
                "rules": [],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="rollout_percentage must be an integer"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_bool_rule_order():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "checkout": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "production",
                "enabled": True,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [
                    {
                        "id": "1",
                        "order": True,
                        "attribute": "plan",
                        "operator": "equals",
                        "value": "premium",
                        "result": True,
                    }
                ],
                "version": 1,
            }
        },
    }
    with pytest.raises(SnapshotError, match="order must be an integer"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_bool_snapshot_version():
    payload = {
        "environment": "production",
        "version": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {},
    }
    with pytest.raises(SnapshotError, match="version must be an integer"):
        snapshot_from_dict(payload)


def test_from_dict_rejects_bool_flag_version():
    payload = {
        "environment": "production",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "flags": {
            "checkout": {
                "key": "checkout",
                "name": "Checkout",
                "environment": "production",
                "enabled": False,
                "kill_switch": False,
                "default": False,
                "rollout_percentage": 0,
                "rules": [],
                "version": True,
            }
        },
    }
    with pytest.raises(SnapshotError, match="version must be an integer"):
        snapshot_from_dict(payload)
