# -*- coding: utf-8 -*-
"""QuantConnect — Dual momentum crypto (BTC / ETH / SOL).

Laboratorio: pegar en QC. Datos Coinbase, 3.000 USD (~3k EUR).
Live: no uses QC+IB (QC no ejecuta crypto spot de IB). El bot live ira
en Python contra TWS, como el GTAA.

Reglas (mismas que el GTAA, leverage 1.0):
  - Precio > SMA200 y momentum 126d > 0
  - Top 1 por momentum; si nadie pasa, 100% cash
  - Rebalanceo el primer dia de cada mes

Parametro UNIVERSE:
  "BTC"   -> solo Bitcoin (recomendado para live con 3k)
  "THREE" -> BTC + ETH + SOL

Parametro MODE:
  "LONG_ONLY"  -> long o cash (spot IB). Recomendado.
  "LONG_SHORT" -> long / short / cash. Live requiere futuros, no spot.
  "ALWAYS_IN"  -> siempre largo o corto segun SMA200 (BTC).
"""

from AlgorithmImports import *

UNIVERSE = "BTC"       # "BTC" o "THREE"
MODE = "LONG_ONLY"     # "LONG_ONLY" | "LONG_SHORT" | "ALWAYS_IN"
MOM_DAYS = 126
SMA_DAYS = 200
TOP_N = 1
FEE_RATE = 0.0018      # techo comision IB EEA spot


class IbSpotFeeModel(FeeModel):
    def GetOrderFee(self, parameters):
        value = abs(parameters.Security.Price * parameters.Order.AbsoluteQuantity)
        fee = max(value * FEE_RATE, 1.75)
        quote = parameters.Security.QuoteCurrency.Symbol
        return OrderFee(CashAmount(fee, quote))


class CryptoDualMomentum(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetCash(3000)
        self.SetBrokerageModel(BrokerageName.Coinbase, AccountType.Cash)
        self.SetWarmUp(SMA_DAYS + MOM_DAYS, Resolution.Daily)

        tickers = ["BTCUSD"] if UNIVERSE == "BTC" else ["BTCUSD", "ETHUSD", "SOLUSD"]
        self._windows = {}
        self._symbols = []
        for t in tickers:
            c = self.AddCrypto(t, Resolution.Daily, Market.Coinbase)
            c.SetFeeModel(IbSpotFeeModel())
            self._symbols.append(c.Symbol)
            self._windows[c.Symbol] = RollingWindow[float](SMA_DAYS + 5)

        self.Schedule.On(
            self.DateRules.MonthStart(self._symbols[0]),
            self.TimeRules.At(12, 0),
            self.Rebalance,
        )

    def OnData(self, data):
        for symbol in self._symbols:
            if data.Bars.ContainsKey(symbol):
                close = float(data.Bars[symbol].Close)
            elif data.QuoteBars.ContainsKey(symbol):
                close = float(data.QuoteBars[symbol].Close)
            else:
                continue
            if close > 0:
                self._windows[symbol].Add(close)

    def Rebalance(self):
        if self.IsWarmingUp:
            return

        longs, shorts = [], []
        for symbol in self._symbols:
            window = self._windows[symbol]
            if not window.IsReady:
                continue
            closes = [window[i] for i in range(window.Count)]
            price = closes[0]
            sma = sum(closes[:SMA_DAYS]) / SMA_DAYS
            if window.Count <= MOM_DAYS:
                continue
            mom = price / closes[MOM_DAYS] - 1.0
            if MODE == "ALWAYS_IN":
                w = 1.0 if price > sma else -1.0
                self.SetHoldings(symbol, w)
                side = "LONG" if w > 0 else "SHORT"
                self.Log(f"{self.Time.date()} -> {side} {symbol.Value}")
                return
            if price > sma and mom > 0:
                longs.append((symbol, mom))
            elif price < sma and mom < 0:
                shorts.append((symbol, mom))

        targets = {s: 0.0 for s in self._symbols}
        if MODE == "LONG_ONLY":
            longs.sort(key=lambda x: x[1], reverse=True)
            for s, _ in longs[:TOP_N]:
                targets[s] = 1.0 / TOP_N
        else:
            best_long = max(longs, key=lambda x: x[1]) if longs else None
            best_short = min(shorts, key=lambda x: x[1]) if shorts else None
            if best_long and best_short:
                if best_long[1] >= abs(best_short[1]):
                    targets[best_long[0]] = 1.0
                else:
                    targets[best_short[0]] = -1.0
            elif best_long:
                targets[best_long[0]] = 1.0
            elif best_short:
                targets[best_short[0]] = -1.0

        for symbol, w in targets.items():
            self.SetHoldings(symbol, w)
        names = []
        for s, w in targets.items():
            if w > 0:
                names.append(f"LONG {s.Value}")
            elif w < 0:
                names.append(f"SHORT {s.Value}")
        self.Log(f"{self.Time.date()} -> {', '.join(names) or 'CASH'}")
