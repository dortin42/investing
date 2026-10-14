"""Interfaz de una estrategia: devuelve pesos, nunca órdenes."""

from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd

from investing.contratos import TargetWeights


class Estrategia(Protocol):
    id: str
    frecuencia: str
    universo: tuple[str, ...]
    banda: float

    def senal(self, precios: pd.DataFrame, fecha: date | None = None) -> TargetWeights:
        """Pesos calculados solo con cierres hasta ``fecha`` (inclusive)."""
