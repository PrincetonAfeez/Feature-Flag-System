"""Read-only JSON API for feature flag snapshots."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from flags_core.errors import (
    EnvironmentNotFoundError,
    FlagNotFoundError,
    FlagValidationError,
)
from flags_core.models import EvaluationContext
from flags_django.services import EvaluationService, SnapshotService

MAX_EVAL_BODY_BYTES = 64 * 1024
SNAPSHOT_CACHE_CONTROL = "private, must-revalidate"


def _if_none_match(request: HttpRequest, etag: str) -> bool:
    """Return True when the client's If-None-Match header covers ``etag``.

    Honors RFC 7232 ``*`` and comma-separated tag lists, not just an exact match.
    """
    header = request.headers.get("If-None-Match")
    if not header:
        return False
    candidates = {tag.strip() for tag in header.split(",")}
    return "*" in candidates or etag in candidates


def _snapshot_response(payload: dict | None, etag: str, *, status: int = 200) -> HttpResponse:
    if status == 304:
        response = HttpResponse(status=304)
    else:
        response = JsonResponse(payload)
    response["ETag"] = etag
    response["Cache-Control"] = SNAPSHOT_CACHE_CONTROL
    return response


@require_GET
def snapshot(request: HttpRequest, env: str) -> HttpResponse:
    try:
        payload, etag = SnapshotService.serialize_with_etag(env)
    except EnvironmentNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except FlagValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    if _if_none_match(request, etag):
        return _snapshot_response(None, etag, status=304)

    return _snapshot_response(payload, etag)


@csrf_exempt  # MVP: staff session POST without CSRF token; see docs/api.md
@require_POST
def eval_debug(request: HttpRequest, env: str) -> JsonResponse:
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "staff access required"}, status=403)

    if len(request.body) > MAX_EVAL_BODY_BYTES:
        return JsonResponse({"error": "request body too large"}, status=413)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "flag_key must be a non-empty string"}, status=400)

    flag_key = payload.get("flag_key")
    if not isinstance(flag_key, str) or not flag_key.strip():
        return JsonResponse({"error": "flag_key must be a non-empty string"}, status=400)

    context_payload = payload.get("context", {})
    if context_payload is None:
        context_payload = {}
    if not isinstance(context_payload, dict):
        return JsonResponse({"error": "context must be a JSON object"}, status=400)

    try:
        context = EvaluationContext.from_mapping(context_payload)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        result = EvaluationService.evaluate_from_db(env, flag_key, context)
    except (FlagNotFoundError, EnvironmentNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except FlagValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "flag_key": result.flag_key,
            "value": result.value,
            "reason": result.reason,
            "matched_rule_id": result.matched_rule_id,
            "bucket": result.bucket,
            "default_used": result.default_used,
            "error": result.error,
        }
    )
