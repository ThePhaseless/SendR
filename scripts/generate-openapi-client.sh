#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
output_spec="$repo_root/openapi.json"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to export the backend OpenAPI schema." >&2
  exit 1
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "bun is required to generate the Angular API client." >&2
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

cd "$repo_root/frontend"
bunx --bun orval

cd "$repo_root"
git add openapi.json frontend/src/app/api
