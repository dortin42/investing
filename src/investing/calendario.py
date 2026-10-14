"""Calendarios de sesión para el rebalanceo mensual.

La orden de los UCITS se programa con el calendario de Xetra: la señal usa el
cierre del último día hábil del mes y la ejecución es el día hábil siguiente.
``CalendarioEEUU`` reproduce la máscara del backtest (``USFederalHolidayCalendar``),
que servía para las series proxy americanas. No programa las órdenes de Xetra.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar


class Calendario(Protocol):
    nombre: str

    def es_habil(self, fecha: date) -> bool: ...

    def siguiente_habil(self, fecha: date) -> date: ...

    def es_ultimo_habil_del_mes(self, fecha: date) -> bool: ...


def domingo_de_pascua(anio: int) -> date:
    """Domingo de Pascua por el algoritmo gregoriano anónimo."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ele = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ele) // 451
    mes = (h + ele - 7 * m + 114) // 31
    dia = (h + ele - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def festivos_xetra(anio: int) -> set[date]:
    """Días sin negociación en Xetra y Börse Frankfurt.

    Regla publicada por Deutsche Börse: 1 de enero, Viernes Santo, Lunes de
    Pascua, 1 de mayo, 24, 25 y 26 de diciembre, y 31 de diciembre. No se
    trasladan al lunes si caen en fin de semana. Ascensión, Lunes de Pentecostés,
    Corpus Christi y el Día de la Unidad Alemana son sesión normal.
    """
    pascua = domingo_de_pascua(anio)
    return {
        date(anio, 1, 1),
        pascua - timedelta(days=2),
        pascua + timedelta(days=1),
        date(anio, 5, 1),
        date(anio, 12, 24),
        date(anio, 12, 25),
        date(anio, 12, 26),
        date(anio, 12, 31),
    }


def _siguiente(fecha: date, es_habil) -> date:
    candidato = fecha + timedelta(days=1)
    limite = fecha + timedelta(days=14)
    while not es_habil(candidato):
        candidato += timedelta(days=1)
        if candidato > limite:
            raise RuntimeError(f"no hay día hábil en los 14 días posteriores a {fecha.isoformat()}")
    return candidato


class CalendarioXetra:
    """Sesiones de Xetra. Es el calendario con el que se lanzan las órdenes de E1."""

    nombre = "xetra"

    def __init__(self) -> None:
        self._festivos: dict[int, set[date]] = {}

    def festivos(self, anio: int) -> set[date]:
        if anio not in self._festivos:
            self._festivos[anio] = festivos_xetra(anio)
        return self._festivos[anio]

    def es_habil(self, fecha: date) -> bool:
        if fecha.weekday() >= 5:
            return False
        return fecha not in self.festivos(fecha.year)

    def siguiente_habil(self, fecha: date) -> date:
        return _siguiente(fecha, self.es_habil)

    def es_ultimo_habil_del_mes(self, fecha: date) -> bool:
        if not self.es_habil(fecha):
            return False
        return self.siguiente_habil(fecha).month != fecha.month


class CalendarioEEUU:
    """Máscara de fin de mes del backtest, con el calendario federal de EE. UU.

    ``mascara_fin_de_mes`` es la misma cuenta que ``bt.strategies.month_end_mask``:
    un día del índice es fin de mes si el siguiente día hábil cae en otro mes.
    """

    nombre = "eeuu"

    def __init__(self) -> None:
        self._offset = pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())
        self._calendario = USFederalHolidayCalendar()

    def es_habil(self, fecha: date) -> bool:
        momento = pd.Timestamp(fecha)
        if momento.dayofweek >= 5:
            return False
        festivos = self._calendario.holidays(start=momento, end=momento)
        return len(festivos) == 0

    def siguiente_habil(self, fecha: date) -> date:
        return (pd.Timestamp(fecha) + self._offset).date()

    def es_ultimo_habil_del_mes(self, fecha: date) -> bool:
        if not self.es_habil(fecha):
            return False
        return self.siguiente_habil(fecha).month != fecha.month

    def mascara_fin_de_mes(self, indice: pd.DatetimeIndex) -> pd.Series:
        siguiente = pd.DatetimeIndex([dia + self._offset for dia in indice])
        return pd.Series(siguiente.month != indice.month, index=indice)


def proximo_cierre_de_senal(calendario: Calendario, desde: date) -> date:
    """Próximo último día hábil del mes, incluido ``desde`` si ya lo es."""
    candidato = desde
    for _ in range(40):
        if calendario.es_ultimo_habil_del_mes(candidato):
            return candidato
        candidato += timedelta(days=1)
    raise RuntimeError(f"no aparece un fin de mes hábil a partir de {desde.isoformat()}")
