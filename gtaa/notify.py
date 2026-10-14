"""Notificacion opcional por Telegram. Si no hay variables de entorno, no hace nada.

Setup (5 min): habla con @BotFather en Telegram -> /newbot -> copia el token.
Escribe algo a tu bot y saca tu chat_id de:
https://api.telegram.org/bot<TOKEN>/getUpdates
Luego define TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID como variables de entorno.
"""

import json
import os
import urllib.request


def send(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False
