#!/usr/bin/env bash
# One-command local setup for the Feature Flag System MVP.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

python manage.py migrate

cat <<'EOF'

Bootstrap complete.
Next steps:
  python manage.py createsuperuser   # admin UI + staff-only eval API
  python manage.py runserver
  python manage.py flagctl list --env production
  ./scripts/verify.sh                # lint, typecheck, tests
EOF
