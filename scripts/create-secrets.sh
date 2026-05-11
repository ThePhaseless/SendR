#!/bin/bash
# Usage: ./scripts/create-secrets.sh <env> (dev|staging|prod)

set -e

ENV=${1:-dev}
NAMESPACE=sendr

echo "Creating secrets for environment: $ENV"

kubectl create secret generic sendr-secrets \
  --namespace=$NAMESPACE \
  --from-literal=database-url="${SENDR_DATABASE_URL}" \
  --from-literal=secret-key="${SENDR_SECRET_KEY}" \
  --from-literal=smtp-host="${SENDR_SMTP_HOST}" \
  --from-literal=smtp-port="${SENDR_SMTP_PORT}" \
  --from-literal=smtp-user="${SENDR_SMTP_USER}" \
  --from-literal=smtp-password="${SENDR_SMTP_PASSWORD}" \
  --from-literal=resend-api-key="${SENDR_RESEND_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret docker-registry ghcr-secret \
  --namespace=$NAMESPACE \
  --docker-server=ghcr.io \
  --docker-username=x-access-token \
  --docker-password="${GITHUB_APP_TOKEN}" \
  --docker-email="${SENDR_GITHUB_EMAIL}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created successfully for $ENV"