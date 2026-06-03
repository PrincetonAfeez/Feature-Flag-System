# Contributing

Thank you for reviewing this academic MVP. This is primarily a portfolio artifact;
large feature PRs should align with [docs/roadmap.md](docs/roadmap.md).

## Development setup

```powershell
.\scripts\bootstrap.ps1
```

```bash
chmod +x scripts/bootstrap.sh scripts/verify.sh
./scripts/bootstrap.sh
```

## Quality gates (match CI)

```powershell
.\scripts\verify.ps1
```

```bash
./scripts/verify.sh
```

Or individually:

```bash
ruff check .
ruff format --check .
mypy
python manage.py makemigrations --check --dry-run
pytest --cov=flags_core --cov=flags_django --cov-fail-under=99
```

## Architecture rule

`flags_core` must **never** import Django. Add core logic under `flags_core/`;
persistence and HTTP under `flags_django/`. See [docs/architecture.md](docs/architecture.md).

## Documentation

- MVP scope: [docs/scope-mvp.md](docs/scope-mvp.md)
- Academic report: [docs/report.md](docs/report.md)
- ADRs: [docs/adr/](docs/adr/)

## Versioning

Follow [CHANGELOG.md](CHANGELOG.md). Tag releases as `v0.1.x` to trigger the
release workflow.
