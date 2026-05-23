#!/usr/bin/env bash
# Usage: ./scripts/add-sops-recipient.sh <age-public-key>
#
# Adds a new Age recipient to .sops.yaml and re-encrypts all encrypted files.
# Run this from the repository root.
#
# Example:
#   ./scripts/add-sops-recipient.sh age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p

set -euo pipefail

NEW_KEY="${1:-}"

if [ -z "$NEW_KEY" ]; then
  echo "Usage: $0 <age-public-key>" >&2
  echo "Ask the new team member to run: age-keygen -o ~/.config/sops/age/keys.txt" >&2
  echo "They should send you their public key (the line starting with 'age1')." >&2
  exit 1
fi

if ! [[ "$NEW_KEY" =~ ^age1 ]]; then
  echo "Invalid Age public key. Must start with 'age1'." >&2
  exit 1
fi

SOPS_YAML=".sops.yaml"

if [ ! -f "$SOPS_YAML" ]; then
  echo "$SOPS_YAML not found. Run this from the repository root." >&2
  exit 1
fi

echo "Adding recipient: $NEW_KEY"

# Use Python to safely modify the YAML
python3 - "$SOPS_YAML" "$NEW_KEY" << 'PYEOF'
import re
import sys

sops_yaml = sys.argv[1]
new_key = sys.argv[2]

with open(sops_yaml, "r") as f:
    content = f.read()

# Find the age block and append the new key
# Match the age: >- followed by indented keys
pattern = r"(age:\s*>-\s*\n)(\s+)(age1[^,\s]+)"
match = re.search(pattern, content)
if not match:
    print("Could not find age block in .sops.yaml", file=sys.stderr)
    sys.exit(1)

indent = match.group(2)
last_key = match.group(3)

# Append new key after the last one
replacement = f"{match.group(1)}{indent}{last_key},\n{indent}{new_key}"
content = content.replace(match.group(0), replacement, 1)

with open(sops_yaml, "w") as f:
    f.write(content)

print("Updated .sops.yaml")
PYEOF

SOPS_CMD="${SOPS_CMD:-$(command -v sops || true)}"
if [ -z "$SOPS_CMD" ]; then
  echo "sops not found in PATH. Set SOPS_CMD or install sops (e.g. via mise)." >&2
  exit 1
fi

echo "Re-encrypting all encrypted files..."
find . -name "*.enc.*" -not -path "./.venv/*" -not -path "./node_modules/*" -not -path "./.git/*" -exec "$SOPS_CMD" rotate -i {} \;

echo "Done. Review the changes, then commit and push:"
echo "  git add .sops.yaml"
echo "  find . -name '*.enc.*' -not -path './.venv/*' -not -path './node_modules/*' -not -path './.git/*' | xargs git add"
echo "  git commit -m 'Add SOPS recipient ${NEW_KEY}'"
