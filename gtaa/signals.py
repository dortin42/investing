"""Senales GTAA: momentum 6m + filtro SMA200.

Las series de precios llegan de IB (fuente principal, misma que la ejecucion)
o de la API de graficos de Yahoo (gtaa/data.py) como fallback. En ambos casos
se calculan sobre las clases UCITS reales en EUR, asi que el momentum incluye
el efecto divisa: es lo que vive tu cuenta.
"""

from __future__ import annotations

import pandas as pd


def compute_signals(series_by_asset: dict, mom_days: int, sma_days: int) -> dict:
    """{Asset: {price, sma, mom, uptrend}} o {Asset: None} si falta historial."""
    out = {}
    min_len = max(sma_days, mom_days) + 5
    for asset, series in series_by_asset.items():
        s = series.dropna() if series is not None else pd.Series(dtype=float)
        if len(s) < min_len:
            out[asset] = None  # historial insuficiente -> excluido este mes
            continue
        price = float(s.iloc[-1])
        sma = float(s.tail(sma_days).mean())
        mom = float(price / s.iloc[-1 - mom_days] - 1)
        out[asset] = {
            "price": price,
            "sma": sma,
            "mom": mom,
            "uptrend": price > sma and mom > 0,
        }
    return out


def select_targets(universe, signals: dict, top_n: int, leverage: float) -> dict:
    """Top N por momentum entre los que pasan ambos filtros.

    Slots fijos: si solo pasan 2 activos, el resto del capital queda en cash.
    Devuelve {Asset: peso}.
    """
    candidates = []
    for asset in universe:
        sig = signals.get(asset)
        if sig and sig["uptrend"]:
            candidates.append((asset, sig["mom"]))
    candidates.sort(key=lambda pair: pair[1], reverse=True)

    slot = leverage / top_n
    return {asset: slot for asset, _ in candidates[:top_n]}
