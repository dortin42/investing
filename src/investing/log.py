"""Logging estructurado en JSON. Una línea por evento, con los datos en ``campos``."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_LOGGER_RAIZ = "investing"


class FormateadorJSON(logging.Formatter):
    """Serializa cada registro como un objeto JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        campos = getattr(record, "campos", None)
        if isinstance(campos, dict) and campos:
            payload["campos"] = campos
        if record.exc_info:
            payload["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Configura el logger ``investing`` para escribir JSON por stderr."""
    logger = logging.getLogger(_LOGGER_RAIZ)
    logger.setLevel(nivel)
    logger.handlers.clear()
    salida = logging.StreamHandler(sys.stderr)
    salida.setFormatter(FormateadorJSON())
    logger.addHandler(salida)
    logger.propagate = False


def evento(logger: logging.Logger, mensaje: str, **campos: Any) -> None:
    """Registra un evento con campos estructurados."""
    logger.info(mensaje, extra={"campos": campos})
