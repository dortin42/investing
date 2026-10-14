"""Estrategias. Cada una devuelve ``TargetWeights`` y no conoce las órdenes."""

from investing.strategies.banda import aplicar_banda, debe_operar
from investing.strategies.e1_tsmom import (
    APALANCAMIENTO_MAX,
    BANDA_NO_OPERAR,
    LOOKBACK_SESIONES,
    SESIONES_ANIO,
    SIGMA_OBJETIVO,
    SPAN_VOL_EWMA,
    TOPE_POR_ACTIVO,
    E1TSMOM,
    serie_pesos_e1,
)

__all__ = [
    "APALANCAMIENTO_MAX",
    "BANDA_NO_OPERAR",
    "E1TSMOM",
    "LOOKBACK_SESIONES",
    "SESIONES_ANIO",
    "SIGMA_OBJETIVO",
    "SPAN_VOL_EWMA",
    "TOPE_POR_ACTIVO",
    "aplicar_banda",
    "debe_operar",
    "serie_pesos_e1",
]
