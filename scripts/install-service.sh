#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_dir="$PWD"
listen_host=127.0.0.1
listen_port=18767
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) listen_host="${2:?--host requires an IP address}"; shift 2 ;;
    --port) listen_port="${2:?--port requires a port}"; shift 2 ;;
    --help) echo 'Usage: bash scripts/install-service.sh [--host IP] [--port PORT]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
python3 - "$listen_host" "$listen_port" <<'PY'
import ipaddress, sys
if '%' in sys.argv[1] or any(c.isspace() or ord(c) < 32 for c in sys.argv[1]):
    raise SystemExit('Scoped addresses and whitespace are not supported')
ipaddress.ip_address(sys.argv[1])
if not sys.argv[2].isascii() or not sys.argv[2].isdigit() or not 1 <= int(sys.argv[2]) <= 65535:
    raise SystemExit('Invalid port')
PY
uv sync --frozen
mkdir -p data "$HOME/.config/systemd/user"
chmod 700 data
if [[ ! -f .env ]]; then
  (umask 077; python3 - <<'PY' > .env
import secrets
print('UPRI_API_TOKEN=' + secrets.token_urlsafe(36))
print('UPRI_DELIVERY_TYPE=UPRI_PREPAID')
PY
  )
fi
chmod 600 .env
cat > "$HOME/.config/systemd/user/upri-api.service" <<EOF
[Unit]
Description=Upri local CSV REST bridge
After=network.target

[Service]
WorkingDirectory=$project_dir
EnvironmentFile=$project_dir/.env
ExecStart=$project_dir/.venv/bin/uvicorn upri.api:create_app --factory --host $listen_host --port $listen_port --no-access-log
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now upri-api.service
systemctl --user restart upri-api.service
probe_host="$listen_host"
[[ "$probe_host" == 0.0.0.0 ]] && probe_host=127.0.0.1
[[ "$probe_host" == :: ]] && probe_host=::1
[[ "$probe_host" == *:* ]] && probe_host="[$probe_host]"
curl --noproxy '*' --retry 10 --retry-connrefused --retry-delay 1 --fail --silent "http://$probe_host:$listen_port/health"
