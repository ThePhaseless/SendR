#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$repo_root/frontend"

if ! command -v bun >/dev/null 2>&1; then
  echo "bun is required to run frontend formatting hooks." >&2
  exit 1
fi

paths=()
for path in "$@"; do
  paths+=("${path#frontend/}")
done

cd "$frontend_dir"
bunx --no-install oxfmt "${paths[@]}"