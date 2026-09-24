#!/bin/sh
# Certbot manual HTTP-01 hook for the short staging IP certificate.
set -eu

action=${1:-}
test -n "${RETRO_STAGING_PUBLIC_IP:-}" || { echo 'Missing staging public IP.' >&2; exit 2; }
case "${CERTBOT_TOKEN:-}" in
  ''|*[!A-Za-z0-9_-]*) echo 'Invalid ACME token.' >&2; exit 2 ;;
esac
case "${CERTBOT_IDENTIFIER:-}" in
  "${RETRO_STAGING_PUBLIC_IP:-}") ;;
  *) echo 'ACME challenge is for a different IP.' >&2; exit 2 ;;
esac

namespace=retro-coop-staging
deployment=retro-coop-staging
target="/var/www/acme/.well-known/acme-challenge/$CERTBOT_TOKEN"

case "$action" in
  auth)
    test -n "${CERTBOT_VALIDATION:-}" || { echo 'Missing ACME validation.' >&2; exit 2; }
    printf '%s' "$CERTBOT_VALIDATION" |
      kubectl -n "$namespace" exec -i "deployment/$deployment" -c edge -- sh -c \
        'umask 022; mkdir -p /var/www/acme/.well-known/acme-challenge; cat > "$1"' sh "$target"
    attempt=0
    while [ "$attempt" -lt 30 ]; do
      value=$(curl --silent --show-error --max-time 2 "http://$RETRO_STAGING_PUBLIC_IP/.well-known/acme-challenge/$CERTBOT_TOKEN" 2>/dev/null || true)
      if [ "$value" = "$CERTBOT_VALIDATION" ]; then exit 0; fi
      attempt=$((attempt + 1))
      sleep 1
    done
    echo 'ACME challenge was not reachable at the reserved IP.' >&2
    exit 1
    ;;
  cleanup)
    kubectl -n "$namespace" exec "deployment/$deployment" -c edge -- rm -f "$target"
    ;;
  *)
    echo 'Use auth or cleanup.' >&2
    exit 2
    ;;
esac
