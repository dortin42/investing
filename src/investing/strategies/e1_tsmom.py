"""E1: momentum de serie temporal, largo o caja, con volatilidad objetivo.

La fórmula es la de ``bt.strategies.e1_tsmom`` con los parámetros de la fase 1
(L252, σ 10 %). El retorno de 12 meses es el cierre de hace 252 sesiones de la
serie diaria alineada, que es lo que calcula el backtest. El reparto del riesgo
es ``(σ_objetivo / N) / σ_i``: N es el número de columnas del universo y la
parte de un ETF que está en caja no se reasigna a los demás. El tope del 40 %
se aplica antes de escalar, y solo se escala a la baja cuando la suma supera 1.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from investing.contratos import TargetWeights
from investing.universo import exigir_simbolos

LOOKBACK_SESIONES = 252
SPAN_VOL_EWMA = 60
SESIONES_ANIO = 252
SIGMA_OBJETIVO = 0.10
TOPE_POR_ACTIVO = 0.40
BANDA_NO_OPERAR = 0.05
APALANCAMIENTO_MAX = 1.0


def serie_pesos_e1(precios: pd.DataFrame) -> pd.DataFrame:
    """Pesos diarios de E1. Misma secuencia de operaciones que el backtest."""
    if precios.index.has_duplicates:
        raise ValueError("el índice de precios tiene fechas duplicadas")
    if not precios.index.is_monotonic_increasing:
        raise ValueError("el índice de precios debe estar ordenado de forma ascendente")
    px = precios.astype(float)
    if px.empty:
        return px.copy()
    n_activos = px.shape[1]
    if n_activos == 0:
        raise ValueError("E1 necesita al menos un ETF")

    senal_larga = (px / px.shift(LOOKBACK_SESIONES) - 1 > 0).astype(float)
    # adjust=True, ignore_na=False y std(bias=False) son los valores con los que
    # pandas ejecuta la llamada del backtest: ewm(span=60, min_periods=60).std().
    volatilidad = (
        px.pct_change()
        .ewm(span=SPAN_VOL_EWMA, min_periods=SPAN_VOL_EWMA, adjust=True, ignore_na=False)
        .std(bias=False)
        * np.sqrt(SESIONES_ANIO)
    )
    pesos = senal_larga * (SIGMA_OBJETIVO / n_activos) / volatilidad
    pesos = pesos.clip(upper=TOPE_POR_ACTIVO)
    total = pesos.sum(axis=1)
    pesos = pesos.div(np.maximum(total, APALANCAMIENTO_MAX), axis=0)
    sin_historia = volatilidad.isna() | px.shift(LOOKBACK_SESIONES).isna()
    pesos = pesos.copy()
    pesos[sin_historia] = 0.0
    return pesos.fillna(0.0)


def _a_fecha(valor: date | datetime | pd.Timestamp) -> date:
    if isinstance(valor, pd.Timestamp):
        return valor.date()
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    raise TypeError(f"fecha no reconocida: {valor!r}")


class E1TSMOM:
    """Variante de E1 sobre un universo concreto (2 ETF en 3k, 4 ETF en 10k)."""

    frecuencia = "mensual"
    banda = BANDA_NO_OPERAR
    retraso_ejecucion_sesiones = 1

    def __init__(self, universo: tuple[str, ...] | list[str], estrategia_id: str = "E1") -> None:
        if not isinstance(estrategia_id, str) or estrategia_id.strip() == "":
            raise ValueError("E1 necesita un id de estrategia")
        self.id = estrategia_id
        self.universo = exigir_simbolos(universo)

    def serie_pesos(self, precios: pd.DataFrame) -> pd.DataFrame:
        """Alinea el universo (quita sesiones con algún cierre ausente) y calcula la serie."""
        faltan = [simbolo for simbolo in self.universo if simbolo not in precios.columns]
        if faltan:
            raise ValueError(f"faltan precios de {faltan}")
        alineados = precios.loc[:, list(self.universo)].sort_index()
        if alineados.index.has_duplicates:
            raise ValueError("el índice de precios tiene fechas duplicadas")
        # Igual que run_ibkr.py: dropna() antes de llamar a e1_tsmom, para que
        # las 252 sesiones sean filas en las que cotizan todos los ETF del universo.
        return serie_pesos_e1(alineados.dropna(how="any"))

    def senal(self, precios: pd.DataFrame, fecha: date | None = None) -> TargetWeights:
        """Pesos del cierre ``fecha``. Sin ``fecha``, usa el último cierre de la serie alineada."""
        serie = self.serie_pesos(precios)
        if serie.empty:
            raise ValueError(f"{self.id} no tiene historia común para {self.universo}")
        if fecha is None:
            momento = pd.Timestamp(serie.index[-1])
        else:
            momento = pd.Timestamp(fecha)
            if momento not in serie.index:
                raise ValueError(
                    f"{_a_fecha(momento).isoformat()} no está en la serie alineada de {self.id}: "
                    "hace falta el cierre de ese día y que todos los ETF del universo coticen"
                )
        fila = serie.loc[momento]
        pesos = {simbolo: float(fila[simbolo]) for simbolo in self.universo}
        return TargetWeights(estrategia=self.id, fecha_senal=_a_fecha(momento), pesos=pesos)
