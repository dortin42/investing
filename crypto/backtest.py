"""Backtest local del dual momentum crypto (precios Yahoo EUR).

Uso:
  python -m crypto.backtest
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd

from crypto import config
from crypto.data import fetch_daily
from crypto.signals import select_always_in, select_long_short
from gtaa.signals import compute_signals, select_targets

OUT = Path(__file__).parent / "last_backtest.json"


class _Asset:
    """Adapter minimo para reutilizar gtaa.signals (espera .name)."""

    def __init__(self, coin: config.Coin):
        self.name = coin.name
        self.yahoo = coin.yahoo
        self.coin = coin


def _load_prices() -> tuple[list[_Asset], pd.DataFrame]:
    assets = [_Asset(c) for c in config.UNIVERSE]
    series = {}
    for a in assets:
        s = fetch_daily(a.yahoo, start=dt.date(2019, 1, 1))
        s.index = pd.to_datetime(s.index)
        series[a.name] = s
    prices = pd.DataFrame(series).sort_index().ffill()
    start = pd.Timestamp(config.START)
    prices = prices.loc[prices.index >= start - pd.Timedelta(days=400)]
    if prices.isna().all().any():
        missing = [c for c in prices.columns if prices[c].isna().all()]
        raise RuntimeError(f"Sin precios para {missing}")
    return assets, prices


def _month_starts(index: pd.DatetimeIndex, start: pd.Timestamp) -> list[pd.Timestamp]:
    usable = index[index >= start]
    months = pd.Series(usable).groupby(usable.to_period("M")).first()
    return list(months)


def _metrics(equity: pd.Series) -> dict:
    eq = equity.dropna()
    if len(eq) < 3:
        return {}
    rets = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if years > 0 else 0.0
    vol = float(rets.std() * math.sqrt(365))
    sharpe = float((rets.mean() * 365) / (rets.std() * math.sqrt(365))) if rets.std() else 0.0
    dd = eq / eq.cummax() - 1
    maxdd = float(dd.min())
    calmar = float(cagr / abs(maxdd)) if maxdd < 0 else 0.0
    return {
        "cagr": round(cagr, 4),
        "vol": round(vol, 4),
        "sharpe": round(sharpe, 2),
        "maxdd": round(maxdd, 4),
        "calmar": round(calmar, 2),
        "final": round(float(eq.iloc[-1]), 2),
        "years": round(years, 2),
    }


def _run_variant(assets, prices, mom_days, sma_days, top_n, start,
                 mode: str = "long_only") -> dict:
    idx = prices.index
    rebal_dates = _month_starts(idx, start)
    min_len = max(sma_days, mom_days) + 5

    weights = pd.DataFrame(0.0, index=idx, columns=[a.name for a in assets])
    holdings_log = []

    for i, dt in enumerate(rebal_dates):
        hist = {a: prices[a.name].loc[:dt] for a in assets}
        signals = compute_signals(hist, mom_days, sma_days)
        if mode == "long_short":
            targets = select_long_short(assets, signals, config.LEVERAGE)
        elif mode == "always_in":
            targets = select_always_in(assets, signals, config.LEVERAGE)
        else:
            targets = select_targets(assets, signals, top_n, config.LEVERAGE)
        end = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else idx[-1]
        span = (idx >= dt) & (idx <= end)
        for a in assets:
            weights.loc[span, a.name] = targets.get(a, 0.0)
        labeled = []
        for a in assets:
            w = targets.get(a, 0.0)
            if w > 0:
                labeled.append(f"LONG {a.name}")
            elif w < 0:
                labeled.append(f"SHORT {a.name}")
        row = {
            "date": str(dt.date()),
            "hold": labeled or ["CASH"],
        }
        for a in assets:
            sig = signals.get(a)
            if sig:
                row[f"{a.name}_mom"] = round(sig["mom"], 4)
                row[f"{a.name}_up"] = bool(sig["uptrend"])
            else:
                row[f"{a.name}_mom"] = None
                row[f"{a.name}_up"] = False
        holdings_log.append(row)

    coin_ret = prices.pct_change().fillna(0.0)
    # Peso de hoy = decision de AYER (sin look-ahead). Coste = |dw| * comision.
    w = weights.shift(1).fillna(0.0)
    dw = w.diff().abs().sum(axis=1)
    port_ret = (w * coin_ret.reindex(w.index).fillna(0.0)).sum(axis=1)
    port_ret = port_ret - dw * config.COMMISSION

    equity = (1 + port_ret.loc[start:]).cumprod() * config.CAPITAL_EUR
    equity = equity.loc[equity.index >= start]
    w_live = w.loc[start:]
    net = w_live.sum(axis=1)
    time_long = float((net > 0).mean())
    time_short = float((net < 0).mean())
    time_cash = float((net == 0).mean())

    last = idx[-1]
    last_hist = {a: prices[a.name] for a in assets}
    last_sig = compute_signals(last_hist, mom_days, sma_days)
    if mode == "long_short":
        last_tgt = select_long_short(assets, last_sig, config.LEVERAGE)
    elif mode == "always_in":
        last_tgt = select_always_in(assets, last_sig, config.LEVERAGE)
    else:
        last_tgt = select_targets(assets, last_sig, top_n, config.LEVERAGE)

    today_hold = []
    for a in assets:
        tw = last_tgt.get(a, 0.0)
        if tw > 0:
            today_hold.append(f"LONG {a.name}")
        elif tw < 0:
            today_hold.append(f"SHORT {a.name}")

    bear = _metrics(equity.loc["2022-01-01":"2022-12-31"]) if len(equity) else {}

    return {
        "params": {"mom_days": mom_days, "sma_days": sma_days, "top_n": top_n,
                   "mode": mode},
        "metrics": _metrics(equity),
        "bear_2022": bear,
        "time_long": round(time_long, 3),
        "time_short": round(time_short, 3),
        "time_cash": round(time_cash, 3),
        "time_invested": round(time_long, 3),
        "trades_per_year": round(
            len(rebal_dates) / max(_metrics(equity).get("years") or 1, 0.1), 1),
        "equity": {str(t.date()): round(v, 2) for t, v in equity.items()},
        "holdings": holdings_log[-18:],
        "today": {
            "asof": str(last.date()),
            "hold": today_hold or ["CASH"],
            "signals": {
                a.name: None if last_sig.get(a) is None else {
                    "price": round(last_sig[a]["price"], 2),
                    "mom": round(last_sig[a]["mom"], 4),
                    "uptrend": last_sig[a]["uptrend"],
                }
                for a in assets
            },
        },
        "n_rebalances": len(rebal_dates),
        "min_history_ok": min_len,
    }


def _buy_hold(prices: pd.DataFrame, col: str, start: pd.Timestamp) -> dict:
    s = prices[col].loc[start:].dropna()
    equity = (s / s.iloc[0]) * config.CAPITAL_EUR
    return {"metrics": _metrics(equity), "equity": {str(t.date()): round(v, 2) for t, v in equity.items()}}


def _equal_weight(prices: pd.DataFrame, start: pd.Timestamp) -> dict:
    rets = prices.pct_change().fillna(0.0).loc[start:]
    port = rets.mean(axis=1)
    equity = (1 + port).cumprod() * config.CAPITAL_EUR
    return {"metrics": _metrics(equity), "equity": {str(t.date()): round(v, 2) for t, v in equity.items()}}


def main() -> None:
    assets, prices = _load_prices()
    start = pd.Timestamp(config.START)
    # Asegurar SMA warmup dentro de prices
    print(f"Precios: {prices.index[0].date()} -> {prices.index[-1].date()}  "
          f"filas={len(prices)}")

    variants = [
        ("top1 sma100/90d", 90, 100, 1),
        ("top1 sma200/126d (GTAA)", 126, 200, 1),
        ("top2 sma100/90d", 90, 100, 2),
        ("top1 sma100/60d", 60, 100, 1),
    ]
    results = {"start": config.START, "capital": config.CAPITAL_EUR,
               "commission": config.COMMISSION, "asof": str(prices.index[-1].date()),
               "variants": {}, "benchmarks": {}}

    for name, mom, sma, top in variants:
        print(f"\n=== {name} ===")
        r = _run_variant(assets, prices, mom, sma, top, start)
        m = r["metrics"]
        print(f"  CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  "
              f"MaxDD {m['maxdd']:.1%}  Calmar {m['calmar']:.2f}  "
              f"final {m['final']:,.0f} EUR  invested {r['time_invested']:.0%}")
        print(f"  Hoy {r['today']['asof']}: {', '.join(r['today']['hold'])}")
        for coin, sig in r["today"]["signals"].items():
            if not sig:
                print(f"    {coin}: sin datos")
            else:
                flag = "ALZA" if sig["uptrend"] else "-"
                print(f"    {coin:8s}  {sig['mom']:+.1%}  {flag}  {sig['price']:,.2f} EUR")
        results["variants"][name] = r

    results["benchmarks"]["BTC hold"] = _buy_hold(prices, "Bitcoin", start)
    results["benchmarks"]["ETH hold"] = _buy_hold(prices, "Ethereum", start)
    results["benchmarks"]["SOL hold"] = _buy_hold(prices, "Solana", start)
    results["benchmarks"]["EQW 3 coins"] = _equal_weight(prices, start)
    for k, v in results["benchmarks"].items():
        m = v["metrics"]
        print(f"\nBH {k}: CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  "
              f"MaxDD {m['maxdd']:.1%}  final {m['final']:,.0f} EUR")

    # BTC-only: misma SMA/mom, universo de 1. Es el control "sin loteria SOL".
    btc_only = [a for a in assets if a.name == "Bitcoin"]
    print("\n=== BTC-only SMA200/126d ===")
    r_btc = _run_variant(btc_only, prices[["Bitcoin"]], 126, 200, 1, start)
    m = r_btc["metrics"]
    print(f"  CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  MaxDD {m['maxdd']:.1%}  "
          f"final {m['final']:,.0f} EUR  invested {r_btc['time_invested']:.0%}")
    print(f"  Hoy: {', '.join(r_btc['today']['hold'])}")
    results["variants"]["BTC-only sma200/126d"] = r_btc
    oos = pd.Timestamp("2024-01-01")
    results["oos_2024"] = {}
    print("\n=== OOS 2024+ ===")
    for name, mom, sma, top in variants:
        r_oos = _run_variant(assets, prices, mom, sma, top, oos)
        results["oos_2024"][name] = r_oos["metrics"]
        m = r_oos["metrics"]
        print(f"  {name}: CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  "
              f"MaxDD {m['maxdd']:.1%}  final {m['final']:,.0f} EUR")
    r_btc_oos = _run_variant(btc_only, prices[["Bitcoin"]], 126, 200, 1, oos)
    results["oos_2024"]["BTC-only sma200/126d"] = r_btc_oos["metrics"]
    print(f"  BTC-only sma200/126d: CAGR {r_btc_oos['metrics']['cagr']:+.1%}  "
          f"Sharpe {r_btc_oos['metrics']['sharpe']:.2f}  "
          f"MaxDD {r_btc_oos['metrics']['maxdd']:.1%}  "
          f"final {r_btc_oos['metrics']['final']:,.0f} EUR")
    btc_oos = _buy_hold(prices, "Bitcoin", oos)["metrics"]
    eqw_oos = _equal_weight(prices, oos)["metrics"]
    results["oos_2024"]["BTC hold"] = btc_oos
    results["oos_2024"]["EQW 3 coins"] = eqw_oos
    print(f"  BTC hold: CAGR {btc_oos['cagr']:+.1%}  MaxDD {btc_oos['maxdd']:.1%}  "
          f"final {btc_oos['final']:,.0f} EUR")
    print(f"  EQW 3:    CAGR {eqw_oos['cagr']:+.1%}  MaxDD {eqw_oos['maxdd']:.1%}  "
          f"final {eqw_oos['final']:,.0f} EUR")

    def _print_ls(label, result, extra=""):
        m = result["metrics"]
        b = result.get("bear_2022") or {}
        print(f"\n=== {label} ===")
        print(f"  CAGR {m['cagr']:+.1%}  Sharpe {m['sharpe']:.2f}  "
              f"MaxDD {m['maxdd']:.1%}  final {m['final']:,.0f} EUR")
        print(f"  tiempo  long {result['time_long']:.0%}  "
              f"short {result['time_short']:.0%}  cash {result['time_cash']:.0%}")
        if b:
            print(f"  2022: {b['cagr']:+.1%}  MaxDD {b['maxdd']:.1%}  "
                  f"final {b['final']:,.0f} EUR (sobre el valor a 1-ene-2022)")
        print(f"  Hoy: {', '.join(result['today']['hold'])}{extra}")

    ls_specs = [
        ("BTC L/S filtro (cash en chop)", btc_only, prices[["Bitcoin"]],
         126, 200, "long_short"),
        ("BTC always-in SMA200", btc_only, prices[["Bitcoin"]],
         126, 200, "always_in"),
        ("3 coins L/S filtro", assets, prices, 126, 200, "long_short"),
    ]
    results["ls"] = {}
    for label, univ, px, mom, sma, mode in ls_specs:
        r = _run_variant(univ, px, mom, sma, 1, start, mode=mode)
        _print_ls(label, r)
        results["ls"][label] = r
        r_oos = _run_variant(univ, px, mom, sma, 1, oos, mode=mode)
        results["oos_2024"][label] = r_oos["metrics"]
        print(f"  OOS 2024+: CAGR {r_oos['metrics']['cagr']:+.1%}  "
              f"Sharpe {r_oos['metrics']['sharpe']:.2f}  "
              f"MaxDD {r_oos['metrics']['maxdd']:.1%}  "
              f"final {r_oos['metrics']['final']:,.0f} EUR  "
              f"short {r_oos['time_short']:.0%}")

    # 2022 del long-only BTC para comparar
    print("\n=== 2022 long-only BTC trend (cash, no short) ===")
    print(f"  2022: {r_btc['bear_2022']}")

    # Compactar equity a semanal para el JSON (el daily es enorme)
    def _weekly(eq_map: dict) -> dict:
        s = pd.Series({pd.Timestamp(k): v for k, v in eq_map.items()})
        w = s.resample("W-FRI").last().dropna()
        return {str(t.date()): float(v) for t, v in w.items()}

    for name, r in results["variants"].items():
        r["equity_weekly"] = _weekly(r["equity"])
        del r["equity"]
    for name, r in results.get("ls", {}).items():
        r["equity_weekly"] = _weekly(r["equity"])
        del r["equity"]
    for name, r in results["benchmarks"].items():
        r["equity_weekly"] = _weekly(r["equity"])
        del r["equity"]

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nJSON: {OUT}")


if __name__ == "__main__":
    main()
