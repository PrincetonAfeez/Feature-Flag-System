# Demo guide (portfolio)

Use this checklist to produce **screenshots** and a **short screen recording** for
submission. No hosted deployment is required for the academic MVP.

## 1. Bootstrap

```powershell
.\scripts\bootstrap.ps1
python manage.py createsuperuser
```

## 2. Capture CLI transcript (optional)

```powershell
.\scripts\capture-demo.ps1
```

```bash
chmod +x scripts/capture-demo.sh
./scripts/capture-demo.sh
```

Output: `docs/screenshots/cli-demo.txt`

## 3. Screenshots to capture (3 minimum)

Save PNG files in `docs/screenshots/`:

| File | What to show |
|------|----------------|
| `admin-flags.png` | Django admin → Feature flags list (`/admin/`) |
| `cli-list.png` | Terminal: `python manage.py flagctl list --env production` |
| `snapshot-json.png` | Browser or curl: `GET /api/v1/environments/production/snapshot/` with JSON + ETag header |

Optional fourth: `eval-debug.png` — staff POST to eval endpoint returning `reason`.

## 4. Screen recording script (~2 minutes)

1. `python manage.py runserver`
2. `flagctl create demo --env production --default false`
3. `flagctl enable demo --env production`
4. `flagctl rollout demo 100 --env production`
5. `flagctl eval demo --env production --user user_1`
6. Browser: snapshot URL → show ETag; refresh after change → version bump
7. `python examples/minimal_consumer/poll_and_eval.py` → local eval matches API

## 5. Minimal consumer (proves ADR 0001)

With server running:

```bash
python examples/minimal_consumer/poll_and_eval.py http://127.0.0.1:8000 production demo user_1
```

See [examples/minimal_consumer/README.md](../examples/minimal_consumer/README.md).
