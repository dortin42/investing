"""Informe diario por Telegram: senales y PnL de la cuenta del bot. No opera.

Senales: API de graficos de Yahoo (la misma que usa el rebalanceo como fallback).
PnL: posiciones de IB + libro propio (gtaa/ledger.py). Si el Gateway no
responde, el informe sale igual, sin el bloque de PnL.
Guarda el estado en logs/signals_state.json para marcar que cambio desde el
ultimo informe.

  python daily_signals.py [--port 4002]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

logging.getLogger("ib_async.wrapper").setLevel(logging.CRITICAL)

import config
from crypto import config as crypto_config
from crypto.data import fetch_daily
from gtaa import fmt, ledger, notify
from gtaa.broker import Broker
from gtaa.data import fetch_closes_chart
from gtaa.signals import compute_signals, select_targets

STATE_PATH = Path(__file__).parent / "logs" / "signals_state.json"
CLIENT_ID = 18  # distinto del rebalanceo (17) para no pisarse con el Gateway


def first_business_day(year: int, month: int) -> dt.date:
    day = dt.date(year, month, 1)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def next_rebalance(today: dt.date) -> dt.date:
    this_month = first_business_day(today.year, today.month)
    if this_month >= today:
        return this_month
    if today.month == 12:
        return first_business_day(today.year + 1, 1)
    return first_business_day(today.year, today.month + 1)


def _fetch(fetcher, assets) -> tuple[dict, list[str]]:
    series, missing = {}, []
    for asset in assets:
        try:
            series[asset] = fetcher(asset)
        except Exception:
            series[asset] = None
            missing.append(asset.name)
    return series, missing


def _by_momentum(assets, signals) -> list:
    return sorted(assets, key=lambda a: signals[a]["mom"] if signals.get(a) else -9.0,
                  reverse=True)


def gtaa_report() -> dict:
    series, missing = _fetch(lambda a: fetch_closes_chart(a.yahoo), config.UNIVERSE)
    signals = compute_signals(series, config.MOM_DAYS, config.SMA_DAYS)
    targets = select_targets(config.UNIVERSE, signals, config.TOP_N, config.LEVERAGE)
    lines = []
    for asset in _by_momentum(config.UNIVERSE, signals):
        sig = signals.get(asset)
        if sig is None:
            continue
        state = "ALZA" if sig["uptrend"] else "-"
        tag = "  TOP" if asset in targets else ""
        lines.append(f"{asset.name}: {fmt.pct(sig['mom'])} {state}{tag}")
    return {
        "top": [a.ib_symbol for a in config.UNIVERSE if a in targets],
        "top_names": [a.name for a in _by_momentum(list(targets), signals)],
        "lines": lines,
        "missing": missing,
        "series": {a.ib_symbol: series[a] for a in config.UNIVERSE},
    }


def pnl_report(port: int, series: dict, today: dt.date) -> list[str]:
    last_px = {s: float(v.dropna().iloc[-1]) for s, v in series.items()
               if v is not None and not v.dropna().empty}
    broker = Broker(config.IB_HOST, port, CLIENT_ID)
    try:
        contracts = {a.ib_symbol: broker.qualify(a) for a in config.UNIVERSE}
        capital = (config.CAPITAL_EUR if config.CAPITAL_EUR is not None
                   else broker.net_liq_eur())
        book, warnings = ledger.sync(broker, contracts, last_px, capital,
                                     config.TRACK_START, today)
    finally:
        broker.disconnect()
    return ledger.render(ledger.metrics(book, series)) + [f"Aviso: {w}" for w in warnings]


def crypto_report(today: dt.date) -> dict:
    start = today - dt.timedelta(days=500)
    series, missing = _fetch(lambda c: fetch_daily(c.yahoo, start), crypto_config.UNIVERSE)
    signals = compute_signals(series, crypto_config.MOM_DAYS, crypto_config.SMA_DAYS)
    top = select_targets(crypto_config.UNIVERSE, signals, crypto_config.TOP_N,
                         crypto_config.LEVERAGE)
    lines = []
    for coin in _by_momentum(crypto_config.UNIVERSE, signals):
        sig = signals.get(coin)
        if sig is None:
            continue
        state = "ALZA" if sig["uptrend"] else "-"
        lines.append(f"{coin.name}: {fmt.pct(sig['mom'])} {state} ({fmt.eur(sig['price'])})")
    btc = next(c for c in crypto_config.UNIVERSE if c.yahoo == "BTC-EUR")
    btc_sig = signals.get(btc)
    return {
        "btc": "LONG" if btc_sig and btc_sig["uptrend"] else "CASH",
        "top1": next((c.name for c in top), "CASH"),
        "lines": lines,
        "missing": missing,
    }


def diff_lines(prev: dict | None, state: dict) -> list[str]:
    if not prev:
        return ["Primer informe: sin estado anterior."]
    out = []
    before, after = set(prev.get("gtaa_top", [])), set(state["gtaa_top"])
    if after - before:
        out.append(f"GTAA entra en el top: {', '.join(sorted(after - before))}")
    if before - after:
        out.append(f"GTAA sale del top: {', '.join(sorted(before - after))}")
    if prev.get("btc") != state["btc"]:
        out.append(f"Regla BTC: {prev.get('btc')} -> {state['btc']}")
    if prev.get("crypto_top1") != state["crypto_top1"]:
        out.append(f"Top 1 crypto: {prev.get('crypto_top1')} -> {state['crypto_top1']}")
    if not out:
        return [f"Sin cambios desde {prev.get('date')}."]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=config.IB_HOST)
    parser.add_argument("--port", type=int, default=config.IB_PORT)
    args = parser.parse_args()

    today = dt.date.today()
    gtaa = gtaa_report()
    crypto = crypto_report(today)
    try:
        pnl = pnl_report(args.port, gtaa["series"], today)
    except Exception as exc:
        pnl = [f"PnL no disponible (sin conexion a IB en el puerto {args.port}): {exc}"]
    state = {
        "date": str(today),
        "gtaa_top": gtaa["top"],
        "btc": crypto["btc"],
        "crypto_top1": crypto["top1"],
    }
    prev = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else None

    parts = [f"Informe {today}", ""]
    parts += diff_lines(prev, state)
    parts += [""] + pnl
    parts += ["", f"GTAA top {config.TOP_N} (objetivo {fmt.pct(config.LEVERAGE / config.TOP_N, 0, False)} c/u): "
              f"{', '.join(gtaa['top_names']) or 'CASH'}",
              f"Proximo rebalanceo: {next_rebalance(today)}", ""]
    parts += gtaa["lines"]
    if gtaa["missing"]:
        parts.append(f"Sin datos: {', '.join(gtaa['missing'])}")
    parts += ["", "Crypto (solo senal, no se opera)",
              f"Regla BTC: {crypto['btc']} | Top 1 de 3: {crypto['top1']}"]
    parts += crypto["lines"]
    if crypto["missing"]:
        parts.append(f"Sin datos: {', '.join(crypto['missing'])}")
    text = "\n".join(parts)

    print(text)
    if not notify.send(text):
        print("\n[AVISO] Telegram no configurado o fallo el envio.", file=sys.stderr)

    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
