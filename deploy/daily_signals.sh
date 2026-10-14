#!/bin/bash
# Cron diario del VPS: informe de senales por Telegram. No opera.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/deploy/telegram_env.sh"
cd "$ROOT"
exec .venv/bin/python daily_signals.py --port 4002
