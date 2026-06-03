#!/usr/bin/env python3
"""Minimal snapshot consumer — fetch config once and evaluate locally (ADR 0001).

Usage (server must be running):

    python examples/minimal_consumer/poll_and_eval.py \\
        http://127.0.0.1:8000 production new_checkout user_123

Requires only the installed ``flags_core`` package (no Django import).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from flags_core.evaluator import evaluate_snapshot
from flags_core.serialization import snapshot_from_dict


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else "http://127.0.0.1:8000"
    environment = argv[2] if len(argv) > 2 else "production"
    flag_key = argv[3] if len(argv) > 3 else "new_checkout"
    user_id = argv[4] if len(argv) > 4 else "user_123"

    url = f"{base.rstrip('/')}/api/v1/environments/{environment}/snapshot/"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode())
            etag = response.headers.get("ETag", "")
    except urllib.error.HTTPError as exc:
        print(f"snapshot request failed: HTTP {exc.code}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"snapshot request failed: {exc.reason}", file=sys.stderr)
        return 1

    snapshot = snapshot_from_dict(payload)
    result = evaluate_snapshot(snapshot, flag_key, {"user_id": user_id})
    print(f"ETag: {etag}")
    print(f"{result.flag_key} = {str(result.value).lower()} ({result.reason})")
    if result.bucket is not None:
        print(f"bucket: {result.bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
