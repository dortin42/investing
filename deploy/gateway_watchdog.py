"""Watchdog del IB Gateway del VPS (cron). No opera.

El contenedor puede seguir "Up" con el puerto abierto y la API muerta: el
17-10-2026 el Gateway perdio el login, IBC se quedo parado en un dialogo y el
reinicio nocturno de las 23:45 nunca llego a ejecutarse. Estuvo un mes asi.

Comprueba el handshake real de la API (cuentas gestionadas). Si falla:
reinicia el contenedor, espera al login y avisa por Telegram del resultado.
Como mucho un reinicio cada MIN_GAP_S para no provocar un bloqueo de IB por
logins fallidos repetidos.

  python deploy/gateway_watchdog.py [--port 4002]
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.getLogger("ib_async").setLevel(logging.CRITICAL)

from ib_async import IB  # noqa: E402

from gtaa import notify  # noqa: E402

CONTAINER = "gtaa-ib-gateway-1"
CLIENT_ID = 99            # distinto del rebalanceo (17) y del informe (18)
LOGIN_WAIT_S = 180        # IBC tarda ~20-40 s en hacer login tras reiniciar
MIN_GAP_S = 2 * 3600
STAMP = ROOT / "logs" / "watchdog_last_restart"


def api_ok(port: int) -> str | None:
    """None si la API responde; si no, el motivo."""
    ib = IB()
    try:
        ib.connect("127.0.0.1", port, clientId=CLIENT_ID, timeout=15, readonly=True)
        if not ib.managedAccounts():
            return "conectado pero sin cuentas (Gateway sin login)"
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}".rstrip(": ")
    finally:
        ib.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4002)
    args = parser.parse_args()

    problem = api_ok(args.port)
    if problem is None:
        print(f"{time.strftime('%F %T')} Gateway OK")
        return 0

    last = float(STAMP.read_text()) if STAMP.exists() else 0.0
    if time.time() - last < MIN_GAP_S:
        print(f"{time.strftime('%F %T')} Gateway KO ({problem}); "
              f"reinicio reciente, no se repite")
        return 1

    print(f"{time.strftime('%F %T')} Gateway KO ({problem}); reiniciando {CONTAINER}")
    STAMP.parent.mkdir(exist_ok=True)
    STAMP.write_text(str(time.time()))
    subprocess.run(["docker", "restart", CONTAINER], check=False,
                   capture_output=True, timeout=120)

    deadline = time.time() + LOGIN_WAIT_S
    while time.time() < deadline:
        time.sleep(15)
        after = api_ok(args.port)
        if after is None:
            msg = (f"GTAA watchdog: el IB Gateway no respondia ({problem}). "
                   f"Reiniciado y conectado de nuevo.")
            print(msg)
            notify.send(msg)
            return 0

    msg = (f"GTAA watchdog: el IB Gateway no respondia ({problem}) y sigue sin "
           f"responder tras reiniciarlo ({after}). Revisa por VNC "
           f"(ssh -L 5900:127.0.0.1:5900) o si hay otra sesion de IB abierta "
           f"con el mismo usuario.")
    print(msg)
    notify.send(msg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
