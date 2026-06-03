#!/usr/bin/env bash
# Run the same quality gates as CI locally.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "==> ruff check"
ruff check .

echo "==> ruff format --check"
ruff format --check .

echo "==> mypy"
mypy

echo "==> makemigrations --check"
python manage.py makemigrations --check --dry-run

echo "==> pytest"
pytest --cov=flags_core --cov=flags_django --cov-fail-under=99

echo
echo "All checks passed."
