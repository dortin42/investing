"""Traduce pesos objetivo a ordenes concretas, con banda y tamano minimo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PlannedOrder:
    asset: object
    contract: object
    side: str          # BUY / SELL
    qty: int
    ref_price: float   # en divisa del activo
    value_eur: float
    reason: str


@dataclass
class Plan:
    orders: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    lines: list = field(default_factory=list)  # resumen por activo para el informe


def build_plan(universe, targets, contracts, positions, prices, fx_eur,
               net_liq, band, min_order_eur) -> Plan:
    """positions/prices indexados por conId; fx_eur por divisa."""
    plan = Plan()

    for asset in universe:
        contract = contracts[asset.ib_symbol]
        conid = contract.conId
        px = prices[conid]
        px_eur = px * fx_eur[asset.ib_currency]
        qty_now = positions.get(conid, 0)
        value_now = qty_now * px_eur
        weight_now = value_now / net_liq if net_liq else 0.0

        weight_target = targets.get(asset, 0.0)
        value_target = weight_target * net_liq

        plan.lines.append({
            "asset": asset, "price_eur": px_eur, "qty_now": qty_now,
            "weight_now": weight_now, "weight_target": weight_target,
        })

        if weight_target == 0.0:
            if qty_now > 0:
                plan.orders.append(PlannedOrder(
                    asset, contract, "SELL", int(qty_now), px,
                    value_now, "fuera del top / filtro"))
            continue

        # Banda: solo tocar si nos desviamos >25% del peso objetivo
        if value_now > 0 and abs(value_now - value_target) <= band * value_target:
            continue

        qty_target = math.floor(value_target / px_eur)
        if qty_target == 0:
            plan.warnings.append(
                f"{asset.name} ({asset.ib_symbol}): 1 participacion cuesta "
                f"{px_eur:,.0f} EUR y el slot es {value_target:,.0f} EUR. "
                f"Elige una clase mas barata del mismo indice en config.py")
            continue

        delta = qty_target - int(qty_now)
        if delta == 0:
            continue
        side = "BUY" if delta > 0 else "SELL"
        value = abs(delta) * px_eur
        if value < min_order_eur:
            continue
        plan.orders.append(PlannedOrder(
            asset, contract, side, abs(delta), px, value, "rebalanceo"))

    # Vender primero libera cash para las compras
    plan.orders.sort(key=lambda o: 0 if o.side == "SELL" else 1)
    return plan
