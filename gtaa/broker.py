"""Capa de acceso a Interactive Brokers via ib_async (fork de ib_insync).

Requiere TWS o IB Gateway abiertos con la API activada:
File > Global Configuration > API > Settings > Enable ActiveX and Socket Clients.
"""

from __future__ import annotations

import math

import pandas as pd
from ib_async import IB, Forex, LimitOrder, Stock


class Broker:
    def __init__(self, host: str, port: int, client_id: int):
        self.ib = IB()
        self.ib.connect(host, port, clientId=client_id, timeout=20)
        # 3 = datos en diferido (15-20 min) si no hay suscripcion en tiempo real.
        # Para un rebalanceo mensual es mas que suficiente.
        self.ib.reqMarketDataType(3)

    def disconnect(self):
        self.ib.disconnect()

    # ---------- contratos ----------

    def qualify(self, asset):
        """Resuelve el contrato en IB. Lanza error si el ticker no existe."""
        contract = Stock(asset.ib_symbol, asset.ib_exchange, asset.ib_currency)
        result = self.ib.qualifyContracts(contract)
        if not result:
            raise ValueError(
                f"IB no reconoce {asset.ib_symbol} en {asset.ib_exchange} "
                f"({asset.ib_currency}). Corrige config.py"
            )
        return contract

    def describe(self, contract) -> str:
        details = self.ib.reqContractDetails(contract)
        if not details:
            return "sin detalles"
        d = details[0]
        return f"{d.longName} | {contract.primaryExchange or contract.exchange} | {contract.currency}"

    # ---------- historicos (fuente de las senales) ----------

    def daily_closes(self, contract, duration: str = "1 Y") -> pd.Series:
        """Cierres diarios ajustados por dividendos/splits, directos de IB."""
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting="1 day",
            whatToShow="ADJUSTED_LAST",
            useRTH=True,
            formatDate=1,
        )
        if not bars:
            raise RuntimeError(
                f"IB no devolvio historico para {contract.symbol}")
        return pd.Series(
            [b.close for b in bars], index=[b.date for b in bars], dtype=float)

    # ---------- cuenta ----------

    def net_liq_eur(self) -> float:
        for row in self.ib.accountSummary():
            if row.tag == "NetLiquidation":
                return float(row.value)  # divisa base de la cuenta (EUR)
        raise RuntimeError("No pude leer NetLiquidation de la cuenta")

    def positions_by_conid(self) -> dict[int, float]:
        return {p.contract.conId: p.position for p in self.ib.positions()}

    def positions_detail(self) -> dict[int, tuple[float, float]]:
        """{conId: (cantidad, coste medio por titulo con comisiones)}."""
        return {p.contract.conId: (float(p.position), float(p.avgCost))
                for p in self.ib.positions()}

    def executions(self) -> list:
        """Ejecuciones que IB conserva (normalmente las de la sesion actual)."""
        return self.ib.reqExecutions()

    # ---------- precios ----------

    def snapshot_prices(self, contracts: list) -> dict[int, float]:
        """Precio por conId, con cadena de fallbacks (last > close > mid)."""
        tickers = self.ib.reqTickers(*contracts)
        prices = {}
        for t in tickers:
            price = t.marketPrice()  # last/close con manejo de NaN
            if math.isnan(price) and not math.isnan(t.close):
                price = t.close
            if math.isnan(price):
                raise RuntimeError(f"Sin precio para {t.contract.symbol}")
            prices[t.contract.conId] = float(price)
        return prices

    def eur_per_unit(self, currency: str) -> float:
        """Cuantos EUR vale 1 unidad de `currency` (para valorar posiciones)."""
        if currency == "EUR":
            return 1.0
        pair = Forex(f"EUR{currency}")
        self.ib.qualifyContracts(pair)
        ticker = self.ib.reqTickers(pair)[0]
        rate = ticker.marketPrice()
        if math.isnan(rate) or rate <= 0:
            raise RuntimeError(f"Sin tipo de cambio EUR{currency}")
        return 1.0 / float(rate)

    # ---------- ordenes ----------

    def price_increment(self, contract, price: float) -> float:
        """Tick minimo de `contract` en su bolsa para ese nivel de precio.

        Xetra usa tablas por tramos: EQAC (regla 1874) cotiza de 0,05 en 0,05
        entre 200 y 500 EUR. Un limite como 423,37 se rechaza (error 110) y la
        orden sale como Cancelled.
        """
        if not hasattr(self, "_rules"):
            self._rules = {}
        key = (contract.conId, contract.exchange)
        if key not in self._rules:
            rule = []
            details = self.ib.reqContractDetails(contract)
            if details:
                d = details[0]
                by_exchange = dict(zip(d.validExchanges.split(","),
                                       d.marketRuleIds.split(",")))
                rule_id = by_exchange.get(contract.exchange)
                if rule_id:
                    rule = sorted((r.lowEdge, r.increment)
                                  for r in self.ib.reqMarketRule(int(rule_id)))
                if not rule and d.minTick:
                    rule = [(0.0, d.minTick)]
            self._rules[key] = rule or [(0.0, 0.01)]
        increment = self._rules[key][0][1]
        for low_edge, inc in self._rules[key]:
            if price >= low_edge:
                increment = inc
        return increment

    def limit_price(self, contract, side: str, ref_price: float,
                    buffer: float) -> float:
        """Limite marketable ajustado al tick de la bolsa.

        Se redondea hacia el lado marketable (compras arriba, ventas abajo):
        como mucho un tick mas alla del buffer.
        """
        factor = 1 + buffer if side == "BUY" else 1 - buffer
        raw = ref_price * factor
        tick = self.price_increment(contract, raw)
        steps = raw / tick
        steps = math.ceil(steps - 1e-9) if side == "BUY" else math.floor(steps + 1e-9)
        decimals = max(0, -math.floor(math.log10(tick)) + 1)
        return round(steps * tick, decimals)

    def place_limit(self, contract, side: str, qty: int, ref_price: float,
                    buffer: float):
        """Limite marketable: cruza el spread con proteccion de precio."""
        limit = self.limit_price(contract, side, ref_price, buffer)
        order = LimitOrder(side, qty, limit, tif="DAY")
        return self.ib.placeOrder(contract, order)

    def open_orders(self, conids: set[int]) -> list:
        """Ordenes vivas en la cuenta (de cualquier cliente) sobre esos contratos."""
        return [t for t in self.ib.reqAllOpenOrders()
                if t.contract.conId in conids and not t.isDone()]

    def wait_for_fills(self, trades: list, timeout_s: int) -> list:
        """Espera fills; devuelve los trades que quedaron sin completar."""
        waited = 0
        while waited < timeout_s:
            if all(t.isDone() for t in trades):
                return []
            self.ib.sleep(2)
            waited += 2
        return [t for t in trades if not t.isDone()]
