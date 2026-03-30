#!/bin/sh
# Extract an IPv4 DNS resolver for nginx (IPv6 addresses need brackets and cause issues)
export DNS_RESOLVER=$(awk '/^nameserver/ && $2 !~ /:/ {print $2; exit}' /etc/resolv.conf)
export DNS_RESOLVER="${DNS_RESOLVER:-8.8.8.8}"

exec /docker-entrypoint.sh "$@"
