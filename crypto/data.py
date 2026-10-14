"""Precios diarios Yahoo para crypto.

`range=max` comprime a velas semanales. Aqui se piden ventanas de ~2 anos
con period1/period2 e interval=1d y se concatenan.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request

import pandas as pd

from gtaa.data import _HEADERS


def fetch_daily(ticker: str, start: dt.date) -> pd.Series:
    chunks = []
    cursor = dt.datetime.combine(start, dt.time())
    end = dt.datetime.now()
    step = dt.timedelta(days=700)
    while cursor < end:
        p1 = int(cursor.timestamp())
        p2 = int(min(cursor + step, end).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.load(response)
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if result and result.get("timestamp"):
            indicators = result["indicators"]
            adj = indicators.get("adjclose")
            closes = (adj[0]["adjclose"] if adj else indicators["quote"][0]["close"])
            index = pd.to_datetime(result["timestamp"], unit="s")
            chunks.append(pd.Series(closes, index=index, dtype=float))
        cursor = cursor + step

    if not chunks:
        raise RuntimeError(f"Yahoo sin datos diarios para {ticker}")
    s = pd.concat(chunks)
    return s[~s.index.duplicated(keep="last")].sort_index().dropna()
