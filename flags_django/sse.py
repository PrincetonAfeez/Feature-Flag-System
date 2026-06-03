"""SSE notification seam for the future V1 push layer.

MVP intentionally ships a no-op: there is no push transport yet. V1 will wire an
in-memory broadcaster behind this same function (see
docs/adr/0002-polling-and-sse-behind-refresh-interface.md) without touching the
service layer, which already calls it via ``transaction.on_commit()``. The debug
log keeps the seam observable during development.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_flags_changed(environment_slug: str, version: int, etag: str) -> None:
    logger.debug("flags_changed env=%s version=%s etag=%s", environment_slug, version, etag)
    return None
