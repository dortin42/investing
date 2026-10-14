# Exporta solo las variables de Telegram de deploy/.env.
# No se hace `source .env`: la contrasena de IB puede llevar caracteres que bash no acepta.
while IFS='=' read -r key value; do
  value="${value%$'\r'}"
  value="${value#[\"\']}"
  value="${value%[\"\']}"
  case "$key" in
    TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID) export "$key=$value" ;;
  esac
done < "$ROOT/deploy/.env"
