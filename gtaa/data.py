"""Cliente minimo de la API de graficos de Yahoo (sin yfinance).

Motivo: yfinance necesita fc.yahoo.com (bloqueado por firewalls/ad-block),
pero query1.finance.yahoo.com responde sin cookies para datos de graficos.
Se usa como fallback cuando IB no da historicos (sin suscripcion de datos
para bolsas europeas, error 162).
"""

from __future__ import annotations

import json
import urllib.request

import pandas as pd

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_closes_chart(ticker: str, range_: str = "2y") -> pd.Series:
    """Cierres diarios ajustados (adjclose) para un ticker de Yahoo."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?range={range_}&interval=1d&events=div%2Csplit"
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.load(response)

    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result or not result.get("timestamp"):
        raise RuntimeError(f"Yahoo sin datos para {ticker}")

    indicators = result["indicators"]
    adj = indicators.get("adjclose")
    closes = list(adj[0]["adjclose"] if adj else indicators["quote"][0]["close"])
    index = pd.to_datetime(result["timestamp"], unit="s").date

    # Yahoo suele dejar vacia la ultima barra aunque la sesion ya cerro;
    # el precio esta en meta.regularMarketPrice.
    meta = result.get("meta", {})
    last_px, last_time = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if closes and closes[-1] is None and last_px and last_time:
        if pd.to_datetime(last_time, unit="s").date() == index[-1]:
            closes[-1] = last_px
    return pd.Series(closes, index=index, dtype=float).dropna()
