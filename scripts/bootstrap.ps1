# One-command local setup for the Feature Flag System MVP.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item .env.example .env
}

python manage.py migrate

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Next steps:"
Write-Host "  python manage.py createsuperuser   # admin UI + staff-only eval API"
Write-Host "  python manage.py runserver"
Write-Host "  python manage.py flagctl list --env production"
Write-Host "  .\scripts\verify.ps1               # lint, typecheck, tests"
