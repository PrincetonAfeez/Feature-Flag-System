# HTTP API

Read-only snapshot polling and a staff-only debug evaluation endpoint. Full URL
prefix: `/api/v1/`.

## Snapshot

```http
GET /api/v1/environments/{env}/snapshot/
If-None-Match: "production-3"
```

### Success — `200 OK`

```json
{
  "environment": "production",
  "version": 3,
  "generated_at": "2026-05-26T18:53:00.123456+00:00",
  "flags": {
    "new_checkout": {
      "key": "new_checkout",
      "name": "New Checkout",
      "environment": "production",
      "enabled": true,
      "kill_switch": false,
      "default": false,
      "rollout_percentage": 25,
      "rules": [
        {
          "id": "1",
          "order": 1,
          "attribute": "plan",
          "operator": "equals",
          "value": "premium",
          "result": true
        }
      ],
      "version": 2
    }
  }
}
```

Response headers include `ETag`, e.g. `"production-3"` (quoted per RFC 7232), and
`Cache-Control: private, must-revalidate` on both `200` and `304` responses.

### Not modified — `304 Not Modified`

When `If-None-Match` matches the current ETag (including `*` or a comma-separated
list of tags). Body is empty; `ETag` header is still returned.

### Errors

| Status | Condition |
|--------|-----------|
| `404` | Unknown environment (environments are never auto-created on read) |
| `500` | Corrupt flag data in the database (validation failed at read time) |

### Notes

- **Unauthenticated** by design for the MVP — clients only read public config.
- Environments with all flags archived remain addressable and return `"flags": {}`.
  Environment rows are not deleted automatically (see [scope-mvp.md](scope-mvp.md)).

## Debug evaluation

Staff session required (Django admin user with `is_staff=True`).

```http
POST /api/v1/environments/{env}/eval/
Content-Type: application/json

{
  "flag_key": "new_checkout",
  "context": {
    "user_id": "u1",
    "plan": "premium"
  }
}
```

### Success — `200 OK`

```json
{
  "flag_key": "new_checkout",
  "value": true,
  "reason": "targeting_match",
  "matched_rule_id": "1",
  "bucket": null,
  "default_used": false,
  "error": null
}
```

### Errors

| Status | Condition |
|--------|-----------|
| `403` | Not authenticated or not staff |
| `400` | Invalid JSON, missing `flag_key`, or invalid `context` (e.g. boolean `user_id`) |
| `404` | Unknown environment or flag |
| `413` | Request body larger than 64 KB |
| `500` | Corrupt flag definition in the database |

`context.user_id` must be a **string or integer** (integers are stringified). Booleans
and other types return **`400`**.

### Rule validation at write time

Targeting rules are validated when flags are created or updated. Operator/value
shapes are checked (e.g. `in` requires a list, `contains` requires a string).
Misconfigured rules that pass write validation but fail to match at runtime (e.g.
`equals` with a type mismatch) **silently no-match** — they do not raise at eval
time. Use the debug eval endpoint to troubleshoot.

### MVP CSRF note

The debug eval view uses `@csrf_exempt` so staff can POST JSON without a CSRF
token during local development. This is an **MVP trade-off** — not recommended
for production without token auth or session CSRF protection. V1 will address
auth tokens and CSRF policy in the roadmap.

## Evaluation reasons

See the README evaluation-order section. Common `reason` values: `kill_switch`,
`flag_disabled`, `targeting_match`, `rollout_zero`, `percentage_rollout`,
`missing_context`, `default`, `error`.

When `rollout_percentage` is **100**, `percentage_rollout` always yields
`value: true` regardless of the flag `default` (full rollout semantics).
