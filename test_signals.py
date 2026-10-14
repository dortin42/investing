"""Prueba sin IB: senales de hoy con la API de graficos de Yahoo.

No requiere TWS abierto ni yfinance (usa gtaa/data.py, que funciona aunque
fc.yahoo.com este bloqueado por el firewall).
"""

import config
from gtaa.data import fetch_closes_chart
from gtaa.signals import compute_signals, select_targets


def main():
    series_by_asset = {}
    for asset in config.UNIVERSE:
        try:
            series_by_asset[asset] = fetch_closes_chart(asset.yahoo)
        except Exception as exc:
            print(f"[AVISO] {asset.yahoo}: {exc}")
            series_by_asset[asset] = None

    signals = compute_signals(series_by_asset, config.MOM_DAYS, config.SMA_DAYS)
    targets = select_targets(config.UNIVERSE, signals, config.TOP_N, config.LEVERAGE)

    print(f"\n{'Activo':22s} {'Yahoo':10s} {'Datos':>6s} {'Precio':>9s} "
          f"{'Mom6m':>8s} {'Senal':6s} {'Peso':>5s}")
    for asset in config.UNIVERSE:
        series = series_by_asset[asset]
        n = int(series.dropna().shape[0]) if series is not None else 0
        sig = signals.get(asset)
        if sig is None:
            print(f"{asset.name:22s} {asset.yahoo:10s} {n:>6d} {'n/d':>9s} "
                  f"{'n/d':>8s} SIN DATOS SUFICIENTES")
            continue
        weight = targets.get(asset, 0.0)
        state = "ALZA" if sig["uptrend"] else "-"
        print(f"{asset.name:22s} {asset.yahoo:10s} {n:>6d} {sig['price']:>9,.2f} "
              f"{sig['mom']:>+8.1%} {state:6s} {weight:>5.0%}")

    if targets:
        print("\nCartera objetivo del mes:")
        for asset, weight in targets.items():
            print(f"  {weight:.0%}  {asset.name} ({asset.ib_symbol})")
    else:
        print("\nCartera objetivo: 100% cash (nada pasa filtros)")


if __name__ == "__main__":
    main()
