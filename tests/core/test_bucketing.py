"""Tests for the bucketing module."""

import pytest

from flags_core.bucketing import bucket_user


def test_bucket_is_deterministic_and_in_range():
    first = bucket_user("new_checkout", "user_123")
    second = bucket_user("new_checkout", "user_123")

    assert first == second
    assert 0 <= first <= 99


def test_rollout_increase_only_adds_users():
    users = [f"user_{i}" for i in range(1000)]
    ten_percent = {user for user in users if bucket_user("new_checkout", user) < 10}
    twenty_five_percent = {user for user in users if bucket_user("new_checkout", user) < 25}

    assert ten_percent <= twenty_five_percent
    assert len(ten_percent) > 0
    assert len(twenty_five_percent) > len(ten_percent)


def test_flag_key_changes_bucket_distribution():
    users = [f"user_{i}" for i in range(100)]
    first = [bucket_user("flag_a", user) for user in users]
    second = [bucket_user("flag_b", user) for user in users]

    assert first != second


def test_bucket_count_must_be_positive():
    with pytest.raises(ValueError):
        bucket_user("flag_a", "user_1", bucket_count=0)
