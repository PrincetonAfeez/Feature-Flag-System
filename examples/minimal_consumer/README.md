# Minimal snapshot consumer

Demonstrates [ADR 0001](../../docs/adr/0001-local-snapshot-local-evaluation.md):
fetch a snapshot from the read API and evaluate flags locally with `flags_core`.

## Prerequisites

1. Bootstrap the project: `../../scripts/bootstrap.ps1` or `../../scripts/bootstrap.sh`
2. Create flags: `python manage.py flagctl create new_checkout --env production --default false`
3. Start the server: `python manage.py runserver`

## Run

```bash
python examples/minimal_consumer/poll_and_eval.py http://127.0.0.1:8000 production new_checkout user_123
```

Expected output (when the flag is enabled at 100% rollout):

```text
ETag: "production-1"
new_checkout = true (percentage_rollout)
```

This script uses only `flags_core` — no Django imports — matching the future
`flags_client` SDK direction described in the roadmap.
