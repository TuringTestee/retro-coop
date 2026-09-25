#!/bin/sh
# Run on the dedicated Ubuntu EC2 relay after fetching the managed secret.
set -eu

test "$(id -u)" -eq 0 || { echo 'Run as root on the staging VM.' >&2; exit 2; }
test "$#" -eq 3 || { echo 'Use: configure_turn.sh PUBLIC_IP PRIVATE_IP SECRET_FILE' >&2; exit 2; }
public_ip=$1
private_ip=$2
secret_file=$3
script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
test -f "$secret_file" || { echo 'TURN secret file is missing.' >&2; exit 2; }

interface=$(ip -o route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++)if($i=="dev"){print $(i+1);exit}}')
case "$interface" in
  ''|*[!a-zA-Z0-9_.-]*) echo 'Could not identify the outbound network interface.' >&2; exit 1 ;;
esac

install -d -m 0750 -o root -g turnserver /etc/retro-coop-turn
chmod 0600 "$secret_file"
python3 "$script_dir/render_turn.py" --public-ip "$public_ip" --private-ip "$private_ip" \
  --secret-file "$secret_file" --output /etc/retro-coop-turn/turn.conf
chown turnserver:turnserver /etc/retro-coop-turn/turn.conf
rm -f "$secret_file"

cat > /etc/systemd/system/retro-coop-turn-limit.service <<EOF
[Unit]
Description=Limit Retro Coop staging relay egress
Before=retro-coop-turn.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/tc qdisc replace dev $interface root tbf rate 3mbit burst 32kb latency 400ms
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/retro-coop-turn.service <<'EOF'
[Unit]
Description=Retro Coop website TURN relay
Requires=retro-coop-turn-limit.service
After=network-online.target retro-coop-turn-limit.service
Wants=network-online.target

[Service]
Type=simple
User=turnserver
Group=turnserver
ExecStart=/usr/bin/turnserver -c /etc/retro-coop-turn/turn.conf
Restart=on-failure
RestartSec=2
RuntimeDirectory=retro-coop-turn
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/run/retro-coop-turn

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl disable --now coturn.service >/dev/null 2>&1 || true
systemctl enable --now retro-coop-turn-limit.service retro-coop-turn.service
systemctl is-active --quiet retro-coop-turn-limit.service
systemctl is-active --quiet retro-coop-turn.service
echo 'Bounded TURN relay is active. Verify UDP allocation from both tester networks.'
