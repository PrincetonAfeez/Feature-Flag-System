#!/usr/bin/env bash
# Generate text output for portfolio screenshots and demo scripts.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

out_dir="docs/screenshots"
mkdir -p "$out_dir"
transcript="$out_dir/cli-demo.txt"
: > "$transcript"

commands=(
  "create demo_flag --env production --default false"
  "enable demo_flag --env production"
  "rollout demo_flag 100 --env production"
  "list --env production"
  "eval demo_flag --env production --user user_123"
  "env-list"
)

for cmd in "${commands[@]}"; do
  {
    echo "\$ python manage.py flagctl $cmd"
    python manage.py flagctl $cmd
    echo
  } >> "$transcript"
done

echo "Wrote $transcript"
echo "Capture PNG screenshots from: Django admin, this CLI output, and snapshot JSON."
