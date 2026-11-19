#!/bin/bash
# Cron del VPS: comprueba que la API del IB Gateway responde; si no, lo reinicia.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/deploy/telegram_env.sh"
cd "$ROOT"
exec .venv/bin/python deploy/gateway_watchdog.py --port 4002
