"""Histórico diario de IBKR. Stub: lo implementa la PR de Ejecución.

La llamada prevista, cuando exista conexión a TWS paper (``127.0.0.1:7497``), es
``IB.reqHistoricalData`` de ib_async con barras diarias de la sesión regular,
``keepUpToDate=False`` y ``formatDate=1``. ``whatToShow`` queda por acordar
(ajustado, para que el retorno sea comparable al CSV de investigación).

Esta clase no importa ib_async y no abre socket.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd

_TODO_DATOS = (
    "TODO (Ejecución): implementar los cierres diarios con ib_async "
    "reqHistoricalData(contract, endDateTime, durationStr, barSizeSetting='1 day', "
    "whatToShow por acordar, useRTH=True, formatDate=1, keepUpToDate=False) "
    "para los UCITS de Xetra en EUR. TWS paper en 127.0.0.1:7497. "
    "No conectar desde la PR de la señal; los tests leen el CSV."
)


class ProveedorHistoricoIBKR:
    """Stub del histórico de IBKR. Construirlo no conecta."""

    def cierres(
        self,
        simbolos: Sequence[str],
        inicio: date | None = None,
        fin: date | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError(_TODO_DATOS)
