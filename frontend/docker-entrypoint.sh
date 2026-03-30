#!/bin/sh
# Extract system DNS resolver for nginx variable-based proxy_pass
export DNS_RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
export DNS_RESOLVER="${DNS_RESOLVER:-8.8.8.8}"

exec /docker-entrypoint.sh "$@"
