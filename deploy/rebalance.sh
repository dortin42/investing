#!/bin/bash
# Cron del VPS. --scheduled solo opera el primer dia habil del mes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/deploy/telegram_env.sh"
cd "$ROOT"
exec .venv/bin/python run_rebalance.py --execute --scheduled --port 4002
