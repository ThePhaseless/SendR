#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
output_spec="$repo_root/openapi.json"
output_client_dir="$repo_root/frontend/src/app/api"
generator_package="@openapitools/openapi-generator-cli@2.30.2"
generator_version="7.20.0"
generator_args=(
  generate
  -i "$output_spec"
  -g typescript-angular
  -o "$output_client_dir"
  --additional-properties=ngVersion=21,providedInRoot=true,fileNaming=kebab-case
)

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to export the backend OpenAPI schema." >&2
  exit 1
fi

cd "$backend_dir"
export PYTHONPATH=src

uv run python - <<'PY'
import json
from pathlib import Path

from app import app

output_path = Path("../openapi.json")
schema = app.openapi()
output_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
PY

cd "$repo_root"

if command -v java >/dev/null 2>&1; then
  if [[ -x "$repo_root/frontend/node_modules/.bin/openapi-generator-cli" ]]; then
    "$repo_root/frontend/node_modules/.bin/openapi-generator-cli" "${generator_args[@]}"
  elif command -v npx >/dev/null 2>&1; then
    npx --yes "$generator_package" "${generator_args[@]}"
  else
    echo "OpenAPI Generator CLI is unavailable. Install frontend dependencies or ensure npx is available." >&2
    exit 1
  fi
elif command -v docker >/dev/null 2>&1; then
  docker run --rm \
    -v "$repo_root:/local" \
    "openapitools/openapi-generator-cli:v$generator_version" \
    generate \
    -i /local/openapi.json \
    -g typescript-angular \
    -o /local/frontend/src/app/api \
    --additional-properties=ngVersion=21,providedInRoot=true,fileNaming=kebab-case
else
  echo "Generating the Angular API client requires either Java or Docker." >&2
  exit 1
fi

git add openapi.json frontend/src/app/api