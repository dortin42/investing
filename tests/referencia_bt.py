"""Copia congelada de la fórmula de E1 del backtest del equipo.

Sirve de oráculo en los tests. No es código de producción. Procede de
``bt/strategies.py``: ``ewma_vol``, ``e1_tsmom`` y ``month_end_mask``.
"""

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

_NEXT_BDAY = pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())


def month_end_mask(idx):
    """Ultimo dia habil del mes segun calendario (conocido de antemano, no depende de datos futuros)."""
    nxt = pd.DatetimeIndex([d + _NEXT_BDAY for d in idx])
    return pd.Series(nxt.month != idx.month, index=idx)


def ewma_vol(prices, span=60, ppy=252):
    return prices.pct_change().ewm(span=span, min_periods=span).std() * np.sqrt(ppy)


def e1_tsmom(prices, lookback=252, sigma_target=0.10, cap=0.40, band=0.05):
    """E1: momentum serie temporal long/flat + vol targeting (Oxford M4U3)."""
    n_activos = prices.shape[1]
    sig = (prices / prices.shift(lookback) - 1 > 0).astype(float)
    vol = ewma_vol(prices)
    w = sig * (sigma_target / n_activos) / vol
    w = w.clip(upper=cap)
    tot = w.sum(axis=1)
    w = w.div(np.maximum(tot, 1.0), axis=0)
    w[vol.isna() | prices.shift(lookback).isna()] = 0.0
    return w.fillna(0.0), month_end_mask(prices.index), band, 1
