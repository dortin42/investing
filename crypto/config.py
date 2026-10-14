"""Dual momentum BTC/ETH/SOL en spot IB (cuenta ~3.000 EUR).

Por que spot y no microfuturos:
- MBT (0.10 BTC) pide ~3.300-4.200 USD de margen: no cabe con colchon en 3k.
- MSL (25 SOL) igual de apretado.
- MET (0.10 ETH) si cabe, pero solo cubre Ether.
- IB EEA spot (Zero Hash) cotiza BTC, ETH y SOL en fracciones, 24/7,
  comision 0.12-0.18%. Encaja con 3.000 EUR y con las 3 monedas.

Misma filosofia que el GTAA: filtro de tendencia + momentum absoluto,
slots fijos (lo que no pasa queda en cash). Leverage 1.0: crypto ya es
volatil; no apalancar 3k.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Coin:
    name: str
    yahoo: str          # pares EUR: el P&L es el de una cuenta en euros
    qc_ticker: str      # ticker QuantConnect / Coinbase (USD)


UNIVERSE = [
    Coin("Bitcoin",  "BTC-EUR", "BTCUSD"),
    Coin("Ethereum", "ETH-EUR", "ETHUSD"),
    Coin("Solana",   "SOL-EUR", "SOLUSD"),
]

CAPITAL_EUR = 3000
LEVERAGE = 1.0
TOP_N = 1               # con 3k: 100% en el ganador (o cash)
MOM_DAYS = 126          # mismos parametros que el GTAA; los lookbacks rapidos empeoran el OOS
SMA_DAYS = 200
REBALANCE = "M"         # mensual (mismo ritmo que el GTAA)
COMMISSION = 0.0018     # 0.18% lado IB (techo de su rango)
START = "2021-01-01"    # SOL ya tiene historial; SMA200 necesita 2020
# Live con 3k: usa solo Bitcoin. THREE es el experimento de rotacion.
