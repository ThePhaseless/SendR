#!/usr/bin/env bash
# Usage: ./scripts/create-secrets.sh <deployment-name>

set -euo pipefail

DEPLOYMENT=${1:-live}
NAMESPACE=sendr
RUNTIME_ENVIRONMENT=${SENDR_ENVIRONMENT:-production}

: "${SENDR_DATABASE_URL:?Set SENDR_DATABASE_URL}"
: "${SENDR_SECRET_KEY:?Set SENDR_SECRET_KEY}"
: "${SENDR_ALTCHA_HMAC_KEY:?Set SENDR_ALTCHA_HMAC_KEY}"
: "${SENDR_SPACES_ACCESS_KEY:?Set SENDR_SPACES_ACCESS_KEY}"
: "${SENDR_SPACES_SECRET_KEY:?Set SENDR_SPACES_SECRET_KEY}"
: "${SENDR_SPACES_BUCKET_NAME:?Set SENDR_SPACES_BUCKET_NAME}"

if [ -z "${SENDR_SMTP_HOST:-}" ] && [ -z "${SENDR_RESEND_API_KEY:-}" ]; then
  echo "Set either SENDR_SMTP_HOST or SENDR_RESEND_API_KEY" >&2
  exit 1
fi

echo "Creating secrets for deployment: $DEPLOYMENT"

kubectl create secret generic sendr-secrets \
  --namespace="$NAMESPACE" \
  --from-literal=environment="${RUNTIME_ENVIRONMENT}" \
  --from-literal=database-url="${SENDR_DATABASE_URL}" \
  --from-literal=secret-key="${SENDR_SECRET_KEY}" \
  --from-literal=altcha-hmac-key="${SENDR_ALTCHA_HMAC_KEY}" \
  --from-literal=smtp-host="${SENDR_SMTP_HOST:-}" \
  --from-literal=smtp-port="${SENDR_SMTP_PORT:-587}" \
  --from-literal=smtp-user="${SENDR_SMTP_USER:-}" \
  --from-literal=smtp-password="${SENDR_SMTP_PASSWORD:-}" \
  --from-literal=resend-api-key="${SENDR_RESEND_API_KEY:-}" \
  --from-literal=spaces-access-key="${SENDR_SPACES_ACCESS_KEY}" \
  --from-literal=spaces-secret-key="${SENDR_SPACES_SECRET_KEY}" \
  --from-literal=spaces-bucket-name="${SENDR_SPACES_BUCKET_NAME}" \
  --from-literal=spaces-region="${SENDR_SPACES_REGION:-fra1}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created successfully for $DEPLOYMENT"