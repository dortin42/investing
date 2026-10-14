"""GTAA momentum sobre UCITS reales en Interactive Brokers.

Modos:
  python run_rebalance.py                  -> dry-run: calcula y muestra, NO opera
  python run_rebalance.py --check          -> verifica que IB resuelve cada ticker
  python run_rebalance.py --execute        -> envia las ordenes de verdad
  python run_rebalance.py --execute --scheduled
        -> para el Programador de tareas: solo opera si hoy es el primer
           dia habil del mes; el resto de dias sale sin hacer nada.

Ports: TWS paper 7497 | TWS real 7496 | Gateway paper 4002 | Gateway real 4001
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

# Los errores 162/354 (sin permisos de datos) los gestionamos con fallback a
# Yahoo; silenciar el logger evita que ensucien cada ejecucion.
logging.getLogger("ib_async.wrapper").setLevel(logging.CRITICAL)

import config
from gtaa import ledger, notify
from gtaa.broker import Broker
from gtaa.data import fetch_closes_chart
from gtaa.rebalance import build_plan
from gtaa.signals import compute_signals, select_targets

LOG_DIR = Path(__file__).parent / "logs"


def is_first_business_day(today: dt.date) -> bool:
    day = dt.date(today.year, today.month, 1)
    while day.weekday() >= 5:  # sabado/domingo
        day += dt.timedelta(days=1)
    return today == day


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="enviar ordenes (sin esto: dry-run)")
    parser.add_argument("--check", action="store_true",
                        help="solo verificar contratos en IB")
    parser.add_argument("--scheduled", action="store_true",
                        help="solo actuar el primer dia habil del mes")
    parser.add_argument("--host", default=config.IB_HOST)
    parser.add_argument("--port", type=int, default=config.IB_PORT)
    args = parser.parse_args()

    today = dt.date.today()
    if args.scheduled and not is_first_business_day(today):
        print(f"{today}: no es el primer dia habil del mes, nada que hacer.")
        return 0

    broker = Broker(args.host, args.port, config.IB_CLIENT_ID)
    try:
        # --- contratos ---
        contracts = {}
        for asset in config.UNIVERSE:
            contracts[asset.ib_symbol] = broker.qualify(asset)

        if args.check:
            print("Contratos resueltos por IB (revisa que sean los ETFs correctos):\n")
            for asset in config.UNIVERSE:
                desc = broker.describe(contracts[asset.ib_symbol])
                print(f"  {asset.ib_symbol:8s} -> {desc}")
            return 0

        # --- senales: IB si hay permisos de datos; si no, API de Yahoo ---
        series_by_asset = {}
        sources = set()
        for asset in config.UNIVERSE:
            try:
                series_by_asset[asset] = broker.daily_closes(
                    contracts[asset.ib_symbol])
                sources.add("IB")
            except Exception:
                series_by_asset[asset] = fetch_closes_chart(asset.yahoo)
                sources.add("Yahoo")
        signals = compute_signals(
            series_by_asset, config.MOM_DAYS, config.SMA_DAYS)
        targets = select_targets(
            config.UNIVERSE, signals, config.TOP_N, config.LEVERAGE)

        # --- estado de cuenta ---
        ib_net_liq = broker.net_liq_eur()
        # Paper ~1M: CAPITAL_EUR limita el sizing a la cuenta real (~3k).
        if config.CAPITAL_EUR is not None:
            net_liq = float(config.CAPITAL_EUR)
            sources.add(f"sizing={net_liq:,.0f} EUR")
        else:
            net_liq = ib_net_liq
        positions = broker.positions_by_conid()
        try:
            prices = broker.snapshot_prices(list(contracts.values()))
        except Exception:
            # Sin permisos de datos en vivo: usar el ultimo cierre conocido.
            # Las ordenes limite (+-0.2%) protegen contra un precio desfasado.
            prices = {
                contracts[a.ib_symbol].conId: float(series_by_asset[a].iloc[-1])
                for a in config.UNIVERSE
            }
            sources.add("precios=ultimo cierre")
        fx_eur = {cur: broker.eur_per_unit(cur)
                  for cur in {a.ib_currency for a in config.UNIVERSE}}

        plan = build_plan(
            config.UNIVERSE, targets, contracts, positions, prices, fx_eur,
            net_liq, config.REBALANCE_BAND, config.MIN_ORDER_EUR)

        # --- informe ---
        print(f"\nGTAA rebalanceo {today} | IB NetLiq: {ib_net_liq:,.0f} EUR "
              f"| sizing: {net_liq:,.0f} EUR "
              f"| leverage {config.LEVERAGE}x | top {config.TOP_N} "
              f"| datos: {', '.join(sorted(sources))}\n")
        print(f"{'Activo':22s} {'Senal':6s} {'Mom6m':>7s} {'Obj':>5s} {'Ahora':>6s} {'Px EUR':>9s}")
        for line in plan.lines:
            asset = line["asset"]
            sig = signals.get(asset)
            mom = f"{sig['mom']:+.1%}" if sig else "n/d"
            state = "ALZA" if (sig and sig["uptrend"]) else "-"
            print(f"{asset.name:22s} {state:6s} {mom:>7s} "
                  f"{line['weight_target']:>5.0%} {line['weight_now']:>6.1%} "
                  f"{line['price_eur']:>9,.2f}")

        for warning in plan.warnings:
            print(f"\n[AVISO] {warning}")

        if not plan.orders:
            msg = (f"GTAA {today}: sin ordenes, cartera dentro de la banda "
                   f"del {config.REBALANCE_BAND:.0%}.")
            print("\n" + msg)
            if args.execute:
                notify.send(msg)
            return 0

        print("\nOrdenes:")
        for o in plan.orders:
            print(f"  {o.side:4s} {o.qty:>4d} x {o.asset.ib_symbol:8s} "
                  f"~{o.value_eur:,.0f} EUR  ({o.reason})")

        if not args.execute:
            print("\nDRY-RUN: no se ha enviado nada. Usa --execute para operar.")
            return 0

        # --- ejecucion ---
        trades = [
            broker.place_limit(o.contract, o.side, o.qty, o.ref_price,
                               config.LIMIT_BUFFER)
            for o in plan.orders
        ]
        pending = broker.wait_for_fills(trades, config.FILL_TIMEOUT_S)

        summary = [f"GTAA {today}: {len(trades) - len(pending)}/{len(trades)} "
                   f"ordenes ejecutadas | sizing {net_liq:,.0f} EUR "
                   f"(IB {ib_net_liq:,.0f})"]
        for t in trades:
            status = t.orderStatus.status
            summary.append(f"{t.order.action} {t.order.totalQuantity} "
                           f"{t.contract.symbol}: {status}")

        # Apuntar las ejecuciones ahora: IB las olvida tras el reinicio nocturno.
        last_px = {s: prices[c.conId] for s, c in contracts.items()}
        try:
            _, ledger_warnings = ledger.sync(broker, contracts, last_px, net_liq,
                                             config.TRACK_START, today)
            summary += [f"Aviso libro: {w}" for w in ledger_warnings]
        except Exception as exc:
            summary.append(f"Aviso: no se pudo actualizar el libro de PnL: {exc}")
        report = "\n".join(summary)
        print("\n" + report)
        notify.send(report)

        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"rebalance_{today:%Y%m%d}.json"
        log_path.write_text(json.dumps({
            "date": str(today),
            "ib_net_liq_eur": ib_net_liq,
            "net_liq_eur": net_liq,
            "targets": {a.ib_symbol: w for a, w in targets.items()},
            "orders": [{"side": o.side, "qty": o.qty, "symbol": o.asset.ib_symbol,
                        "value_eur": round(o.value_eur, 2)} for o in plan.orders],
            "statuses": [t.orderStatus.status for t in trades],
        }, indent=2))
        print(f"\nLog guardado en {log_path}")

        if pending:
            print("\n[AVISO] Ordenes sin completar (revisa TWS):")
            for t in pending:
                print(f"  {t.order.action} {t.contract.symbol}: "
                      f"{t.orderStatus.status}")
            return 1
        return 0
    finally:
        broker.disconnect()


if __name__ == "__main__":
    sys.exit(main())
