#!/usr/bin/env bash
# Usage: ./scripts/create-secrets.sh <deployment-name>
#
# Applies the encrypted SOPS manifest for the given deployment and patches
# dynamic values (database-url, spaces-bucket-name) from Terraform outputs.
#
# Requires:
#   - sops (with SOPS_AGE_KEY or SOPS_AGE_KEY_FILE configured)
#   - kubectl (configured with cluster access)

set -euo pipefail

DEPLOYMENT=${1:-live}
NAMESPACE=sendr

MANIFEST="k8s/overlays/${DEPLOYMENT}/secrets.enc.yaml"

if [ ! -f "$MANIFEST" ]; then
  echo "Encrypted manifest not found: $MANIFEST" >&2
  exit 1
fi

echo "Applying static secrets from $MANIFEST"
sops -d "$MANIFEST" | kubectl apply -f -

# Patch dynamic values that come from Terraform outputs.
# These are not known at encryption time, so they are injected after apply.
if [ -n "${SENDR_DATABASE_URL:-}" ]; then
  echo "Patching database-url from Terraform output"
  kubectl patch secret sendr-secrets \
    -n "$NAMESPACE" \
    --type=merge \
    -p="{\"stringData\":{\"database-url\":\"${SENDR_DATABASE_URL}\"}}"
fi

if [ -n "${SENDR_SPACES_BUCKET_NAME:-}" ]; then
  echo "Patching spaces-bucket-name from Terraform output"
  kubectl patch secret sendr-secrets \
    -n "$NAMESPACE" \
    --type=merge \
    -p="{\"stringData\":{\"spaces-bucket-name\":\"${SENDR_SPACES_BUCKET_NAME}\"}}"
fi

echo "Secrets applied successfully for $DEPLOYMENT"
