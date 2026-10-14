"""Banda de no-operar, con la misma regla que el motor de backtest.

Se opera un símbolo si cambia el signo del peso o si la distancia al peso actual
supera la banda. El signo del peso actual se redondea a 10 decimales antes de
compararlo, igual que ``bt.engine.simulate``. Una distancia exactamente igual a
la banda no opera. Ir a cero (o salir de cero) cambia el signo y sí opera,
aunque la distancia sea menor que la banda: es la salida a caja de E1.
"""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from investing.contratos import TOLERANCIA_PESO


def debe_operar(objetivo: float, actual: float, banda: float) -> bool:
    signo_objetivo = int(np.sign(objetivo))
    signo_actual = int(np.sign(np.round(actual, 10)))
    return signo_objetivo != signo_actual or abs(objetivo - actual) > banda


def aplicar_banda(
    pesos_objetivo: Mapping[str, float],
    pesos_actuales: Mapping[str, float],
    banda: float,
) -> dict[str, float]:
    """Peso a mantener por símbolo: el objetivo si toca operar, el actual si no."""
    if not math.isfinite(banda) or banda < 0:
        raise ValueError(f"banda no válida: {banda}")
    simbolos = list(pesos_objetivo)
    for simbolo in pesos_actuales:
        if simbolo not in simbolos:
            simbolos.append(simbolo)
    resultado: dict[str, float] = {}
    for simbolo in simbolos:
        objetivo = float(pesos_objetivo.get(simbolo, 0.0))
        actual = float(pesos_actuales.get(simbolo, 0.0))
        if not math.isfinite(objetivo) or not math.isfinite(actual):
            raise ValueError(f"peso no finito en {simbolo}")
        if objetivo < -TOLERANCIA_PESO or actual < -TOLERANCIA_PESO:
            raise ValueError(f"E1 no admite cortos; {simbolo} tiene un peso negativo")
        resultado[simbolo] = objetivo if debe_operar(objetivo, actual, banda) else actual
    return resultado
