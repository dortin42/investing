"""Cierres leídos de un CSV. Sirve para los tests y para calcular la señal sin IBKR.

El fichero de investigación trae tickers de Yahoo (``SPYL.DE``). Aquí se
normalizan a los símbolos del universo (``SPYL``). No se rellenan huecos:
E1 hace ``dropna`` al alinear el universo, igual que el backtest.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

import pandas as pd

from investing.universo import UNIVERSO


class ProveedorCSV:
    def __init__(self, ruta: Path | str) -> None:
        self.ruta = Path(ruta)
        if not self.ruta.is_file():
            raise FileNotFoundError(f"no está el CSV de precios: {self.ruta}")

    def cierres(
        self,
        simbolos: Sequence[str],
        inicio: date | None = None,
        fin: date | None = None,
    ) -> pd.DataFrame:
        if not simbolos:
            raise ValueError("hay que pedir al menos un símbolo")
        crudo = pd.read_csv(self.ruta, index_col=0, parse_dates=True)
        if crudo.index.has_duplicates:
            crudo = crudo[~crudo.index.duplicated(keep="last")]
        crudo = crudo.sort_index()
        if getattr(crudo.index, "tz", None) is not None:
            crudo.index = crudo.index.tz_localize(None)

        columnas: dict[str, str] = {}
        for simbolo in simbolos:
            instrumento = UNIVERSO.get(simbolo)
            candidatos = [simbolo]
            if instrumento is not None:
                candidatos.append(instrumento.yahoo)
            origen = next((columna for columna in candidatos if columna in crudo.columns), None)
            if origen is None:
                raise KeyError(f"{simbolo} no está en {self.ruta.name} (columnas: {list(crudo.columns)})")
            columnas[origen] = simbolo

        marco = crudo.loc[:, list(columnas)].rename(columns=columnas)
        marco = marco.loc[:, list(simbolos)].astype(float)
        if inicio is not None:
            marco = marco.loc[pd.Timestamp(inicio) :]
        if fin is not None:
            marco = marco.loc[: pd.Timestamp(fin)]
        return marco
