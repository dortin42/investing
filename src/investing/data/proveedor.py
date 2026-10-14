"""Proveedor de cierres. La estrategia solo ve precios, no el origen."""

from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence

import pandas as pd


class ProveedorPrecios(Protocol):
    def cierres(
        self,
        simbolos: Sequence[str],
        inicio: date | None = None,
        fin: date | None = None,
    ) -> pd.DataFrame:
        """Cierres en EUR, índice ascendente de sesiones, columnas = símbolos.

        ``fin`` es inclusive. El marco no incluye sesiones posteriores a ``fin``.
        """
