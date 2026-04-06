#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v pre-commit >/dev/null 2>&1; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "pre-commit is not installed and 'uv' is unavailable." 1>&2
    echo "Install pre-commit manually or install uv first." 1>&2
    exit 1
  fi

  uv tool install pre-commit
  export PATH="$HOME/.local/bin:$PATH"
fi

git -C "$repo_root" config --unset core.hooksPath 2>/dev/null || true
pre-commit install --config "$repo_root/.pre-commit-config.yaml"
pre-commit install-hooks --config "$repo_root/.pre-commit-config.yaml"

echo "Configured Git hooks for $repo_root"
