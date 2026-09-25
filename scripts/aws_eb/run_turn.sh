#!/bin/sh
# Render coturn's secret and current EB Elastic IP without logging either value.
set -eu
umask 077
runtime=/run/retro-coop-turn
mkdir -p "$runtime"
token=${TURN_IMDS_TOKEN:-}
if [ -z "$token" ] && { [ -z "${TURN_PUBLIC_IP:-}" ] || [ -z "${TURN_PRIVATE_IP:-}" ]; }; then
  token=$(curl --silent --show-error --fail --retry 12 --retry-delay 2 -X PUT \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' http://169.254.169.254/latest/api/token)
fi
public_ip=${TURN_PUBLIC_IP:-}
private_ip=${TURN_PRIVATE_IP:-}
if [ -z "$public_ip" ]; then
  public_ip=$(curl --silent --show-error --fail --retry 12 --retry-delay 2 \
    -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/public-ipv4)
fi
if [ -z "$private_ip" ]; then
  private_ip=$(curl --silent --show-error --fail --retry 12 --retry-delay 2 \
    -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/local-ipv4)
fi
: "${TURN_SECRET:?managed TURN secret required}"
printf %s "$TURN_SECRET" > "$runtime/secret"
python3 /opt/retro-coop/render_turn.py --public-ip "$public_ip" --private-ip "$private_ip" \
  --secret-file "$runtime/secret" --output "$runtime/turn.conf" --runtime-dir "$runtime"
rm -f "$runtime/secret"
unset TURN_SECRET token
exec /usr/bin/turnserver -c "$runtime/turn.conf"
