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

chmod +x "$repo_root/.githooks/pre-commit"
git -C "$repo_root" config core.hooksPath .githooks
pre-commit install-hooks --config "$repo_root/.pre-commit-config.yaml"

echo "Configured Git hooks for $repo_root"
