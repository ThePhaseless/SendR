#!/bin/sh

if [ -z "${API_URL:-}" ]; then
  echo "API_URL must be set to the backend upstream URL." >&2
  exit 1
fi

if [ -z "${DNS_RESOLVER:-}" ]; then
  DNS_RESOLVER=$(awk '/^nameserver / { print $2; exit }' /etc/resolv.conf)
  export DNS_RESOLVER
fi

exec /docker-entrypoint.sh "$@"
