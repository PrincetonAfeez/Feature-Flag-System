"""Deterministic percentage bucketing for rollouts."""

from __future__ import annotations

import hashlib


def bucket_user(flag_key: str, user_id: str, bucket_count: int = 100) -> int:
    """Return a stable bucket in the range 0..bucket_count-1."""
    if bucket_count <= 0:
        raise ValueError("bucket_count must be greater than zero")
    key = f"{flag_key}:{user_id}".encode()
    digest = hashlib.sha256(key).hexdigest()
    # Taking a 256-bit digest modulo bucket_count introduces a bias toward lower
    # buckets, but for bucket_count=100 it is on the order of 2**-249 — negligible.
    return int(digest, 16) % bucket_count
