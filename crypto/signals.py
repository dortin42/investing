"""Seleccion long/short para el sleeve crypto.

Spot IB es solo largo. Para el lado corto hace falta un futuro (BFF/MBT/MET).
"""

from gtaa.signals import select_targets  # noqa: F401  (reexport)


def select_long_short(universe, signals: dict, leverage: float) -> dict:
    """Una posicion: long el mejor alcista, short el peor bajista, o cash.

    Bajista = precio < SMA y momentum < 0 (simetrico al filtro GTAA).
    Si hay candidato long y short, gana el de mayor |momentum|.
    """
    longs, shorts = [], []
    for asset in universe:
        sig = signals.get(asset)
        if not sig:
            continue
        if sig["uptrend"]:
            longs.append((asset, sig["mom"]))
        elif sig["price"] < sig["sma"] and sig["mom"] < 0:
            shorts.append((asset, sig["mom"]))

    best_long = max(longs, key=lambda x: x[1]) if longs else None
    best_short = min(shorts, key=lambda x: x[1]) if shorts else None

    if best_long and best_short:
        if best_long[1] >= abs(best_short[1]):
            return {best_long[0]: leverage}
        return {best_short[0]: -leverage}
    if best_long:
        return {best_long[0]: leverage}
    if best_short:
        return {best_short[0]: -leverage}
    return {}


def select_always_in(universe, signals: dict, leverage: float) -> dict:
    """Siempre en mercado: long si precio > SMA, short si no. Un solo activo."""
    out = {}
    for asset in universe:
        sig = signals.get(asset)
        if not sig:
            continue
        out[asset] = leverage if sig["price"] > sig["sma"] else -leverage
    return out
