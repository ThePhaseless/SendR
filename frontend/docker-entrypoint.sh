#!/bin/sh

if [ -z "${DNS_RESOLVER:-}" ]; then
  DNS_RESOLVER=$(awk '/^nameserver / { print $2; exit }' /etc/resolv.conf)
  export DNS_RESOLVER
fi

exec /docker-entrypoint.sh "$@"
