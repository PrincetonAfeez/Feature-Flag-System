# Run the same quality gates as CI locally.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "==> ruff check"
ruff check .

Write-Host "==> ruff format --check"
ruff format --check .

Write-Host "==> mypy"
mypy

Write-Host "==> makemigrations --check"
python manage.py makemigrations --check --dry-run

Write-Host "==> pip-audit"
pip-audit -r requirements.txt

Write-Host "==> pytest"
pytest --cov=flags_core --cov=flags_django --cov-fail-under=99

Write-Host ""
Write-Host "All checks passed."
