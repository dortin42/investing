"""BTC filtrado por macro USA (tipos, dolar, Nasdaq), no por SMA del propio BTC.

Tesis: Bitcoin se mueve con liquidez y sentimiento de riesgo USA.
Regla mensual, long 100% o cash, 3000 EUR, comision 0.18%.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from crypto import config
from crypto.backtest import _metrics, _month_starts
from crypto.data import fetch_daily

OUT = Path(__file__).parent / "last_macro.json"


def _series(ticker: str) -> pd.Series:
    s = fetch_daily(ticker, start=dt.date(2018, 1, 1))
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s.sort_index()


def _run(btc: pd.Series, long_mask: pd.Series, start: pd.Timestamp, label: str) -> dict:
    idx = btc.index
    rebal = _month_starts(idx, start)
    w = pd.Series(0.0, index=idx)
    log = []
    for i, d in enumerate(rebal):
        on = bool(long_mask.reindex(idx).ffill().loc[:d].iloc[-1])
        end = rebal[i + 1] if i + 1 < len(rebal) else idx[-1]
        w.loc[(idx >= d) & (idx <= end)] = 1.0 if on else 0.0
        log.append({"date": str(d.date()), "hold": "LONG BTC" if on else "CASH"})

    w = w.shift(1).fillna(0.0)
    ret = btc.pct_change().fillna(0.0)
    dw = w.diff().abs()
    port = w * ret.reindex(w.index).fillna(0.0) - dw * config.COMMISSION
    equity = (1 + port.loc[start:]).cumprod() * config.CAPITAL_EUR
    equity = equity.loc[equity.index >= start]
    m = _metrics(equity)
    bear = _metrics(equity.loc["2022-01-01":"2022-12-31"])
    oos = _metrics(equity.loc["2024-01-01":])
    print(f"\n=== {label} ===")
    print(f"  full  CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  "
          f"MaxDD {m['maxdd']:.1%}  final {m['final']:,.0f}  "
          f"long {float(w.loc[start:].mean()):.0%}")
    if bear:
        print(f"  2022  {bear['cagr']:+.1%}  MaxDD {bear['maxdd']:.1%}")
    if oos:
        print(f"  OOS   CAGR {oos['cagr']:+.1%}  Sharpe {oos['sharpe']:.2f}  "
              f"MaxDD {oos['maxdd']:.1%}  final {oos['final']:,.0f}")
    print(f"  ultimo rebalanceo: {log[-1]['hold']} ({log[-1]['date']})")
    return {
        "metrics": m, "bear_2022": bear, "oos_2024": oos,
        "time_long": round(float(w.loc[start:].mean()), 3),
        "holdings": log[-12:],
        "today": log[-1],
    }


def main() -> None:
    start = pd.Timestamp(config.START)
    print("Descargando BTC, TNX, DXY, QQQ...")
    btc = _series("BTC-EUR")
    tnx = _series("^TNX")          # yield 10y USA
    dxy = _series("DX-Y.NYB")      # dolar
    qqq = _series("QQQ")           # Nasdaq-100 ETF

    # Alinear a calendario BTC (crypto 7d); macro se propaga el ultimo valor
    panel = pd.DataFrame({"btc": btc, "tnx": tnx, "dxy": dxy, "qqq": qqq})
    panel = panel.sort_index().ffill()
    panel = panel.loc[panel.index >= start - pd.Timedelta(days=400)].dropna()
    btc = panel["btc"]

    tnx_chg = panel["tnx"].pct_change(60)          # ~3 meses de sesion
    dxy_chg = panel["dxy"].pct_change(60)
    qqq_sma = panel["qqq"].rolling(200).mean()
    btc_sma = panel["btc"].rolling(200).mean()
    btc_mom = panel["btc"] / panel["btc"].shift(126) - 1

    rules = {
        "BTC SMA200 + mom126 (tecnico)":
            (panel["btc"] > btc_sma) & (btc_mom > 0),
        "Tipos 10y bajando 60d":
            tnx_chg < 0,
        "Dolar bajando 60d":
            dxy_chg < 0,
        "Nasdaq QQQ > SMA200":
            panel["qqq"] > qqq_sma,
        "Tipos bajando Y Nasdaq alcista":
            (tnx_chg < 0) & (panel["qqq"] > qqq_sma),
        "Liquidez: tipos O dolar bajando":
            (tnx_chg < 0) | (dxy_chg < 0),
        "Macro+tecnico (tipos↓ y BTC SMA200)":
            (tnx_chg < 0) & (panel["btc"] > btc_sma) & (btc_mom > 0),
    }

    # Buy-hold
    bh = btc.loc[start:]
    bh_eq = bh / bh.iloc[0] * config.CAPITAL_EUR
    print("\n=== BTC hold ===")
    print(f"  full  {_metrics(bh_eq)}")
    print(f"  2022  {_metrics(bh_eq.loc['2022-01-01':'2022-12-31'])}")
    print(f"  OOS   {_metrics(bh_eq.loc['2024-01-01':])}")

    out = {"asof": str(btc.index[-1].date()), "rules": {}}
    for name, mask in rules.items():
        out["rules"][name] = _run(btc, mask, start, name)

    # Senales de hoy
    last = panel.iloc[-1]
    print("\n=== Macro hoy ===")
    print(f"  TNX 10y {last['tnx']:.2f}  chg60d {tnx_chg.iloc[-1]:+.1%}")
    print(f"  DXY     {last['dxy']:.2f}  chg60d {dxy_chg.iloc[-1]:+.1%}")
    print(f"  QQQ     {last['qqq']:.2f}  vs SMA200 {qqq_sma.iloc[-1]:.2f}")
    out["today_macro"] = {
        "tnx": round(float(last["tnx"]), 3),
        "tnx_chg60": round(float(tnx_chg.iloc[-1]), 4),
        "dxy": round(float(last["dxy"]), 2),
        "dxy_chg60": round(float(dxy_chg.iloc[-1]), 4),
        "qqq": round(float(last["qqq"]), 2),
        "qqq_above_sma": bool(last["qqq"] > qqq_sma.iloc[-1]),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nJSON {OUT}")


if __name__ == "__main__":
    main()
