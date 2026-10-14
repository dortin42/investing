"""Configuracion del bot GTAA momentum para IB (UCITS, residente en Espana).

IMPORTANTE: los tickers UCITS marcados con VERIFICAR hay que confirmarlos con
`python run_rebalance.py --check`, que le pregunta a IB que contrato resuelve
para cada uno. Ajusta symbol/exchange/currency hasta que --check muestre
exactamente el ETF que quieres.

Criterio al elegir clase de ETF: acumulacion (Acc), denominada en EUR si es
posible (evita conversiones de divisa), y con precio por participacion bajo
(< ~200 EUR) para que quepa en slots de ~900 EUR con una cuenta de 3.000 EUR.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    name: str          # descripcion humana
    yahoo: str         # ticker en Yahoo Finance (datos para senales)
    ib_symbol: str     # ticker en IB
    ib_exchange: str   # IBIS = Xetra, LSEETF = Londres ETFs
    ib_currency: str


# Universo verificado contra IB el 15-08-2026 con find_contracts.py.
# Todo en EUR (Xetra: IBIS = acciones/ETCs, IBIS2 = segmento ETFs): sin FX.
UNIVERSE = [
    # nombre                     yahoo        IB        bolsa     divisa
    Asset("S&P 500",             "VUAA.DE",   "VUAA",   "IBIS2",  "EUR"),  # Vanguard S&P 500 Acc
    Asset("Nasdaq 100",          "EQAC.MI",   "EQAC",   "IBIS2",  "EUR"),  # Invesco Nasdaq-100 Acc
    Asset("Desarrollados ex-US", "EXUS.DE",   "EXUS",   "IBIS2",  "EUR"),  # Xtrackers World ex USA 1C
    Asset("Emergentes",          "XMME.DE",   "XMME",   "IBIS2",  "EUR"),  # Xtrackers MSCI EM 1C
    Asset("Tesoro US 7-10a",     "BTMA.AS",   "BTMA",   "IBIS2",  "EUR"),  # iShares $ Treasury 7-10y
    Asset("Tesoro US 20+a",      "IS04.DE",   "IS04",   "IBIS2",  "EUR"),  # iShares $ Treasury 20+y
    Asset("Oro (ETC)",           "4GLD.DE",   "4GLD",   "IBIS",   "EUR"),  # Xetra-Gold
    Asset("Materias primas",     "EXXY.DE",   "EXXY",   "IBIS",   "EUR"),  # iShares Div Commodity Swap
    Asset("REITs global",        "IWDP.AS",   "IWDP",   "IBIS2",  "EUR"),  # iShares Dev Mkt Property Yield
    Asset("Managed futures",     "DBMFE.PA",  "DBMFE",  "SBF",    "EUR"),  # iMGP DBi Managed Futures UCITS
]

# --- Parametros de la estrategia (identicos al backtest validado en QC) ---
LEVERAGE = 1.2          # zona practica 1.0 - 1.4; con margen IB (interes en EUR)
TOP_N = 4               # numero de slots
MOM_DAYS = 126          # momentum ~6 meses (dias de mercado)
SMA_DAYS = 200          # filtro de tendencia
REBALANCE_BAND = 0.25   # relativo al peso objetivo: solo opera si se desvia >25%

# --- Ejecucion ---
MIN_ORDER_EUR = 50      # ignora ajustes menores a esto (no regalar comisiones)
LIMIT_BUFFER = 0.002    # limite marketable: +0.2% compras / -0.2% ventas
FILL_TIMEOUT_S = 120    # espera de fills antes de reportar pendientes

# Patrimonio usado para calcular tamaños de orden.
# Paper de IB suele venir con ~1M: fija 3000 para imitar la cuenta real.
# En cuenta real pon None para usar el NetLiquidation de IB.
CAPITAL_EUR = 3000
# Inicio del libro de operaciones (logs/ledger.json): base del PnL y del benchmark.
TRACK_START = "2026-08-17"

# --- Conexion IB ---
# TWS paper: 7497 | TWS real: 7496 | Gateway paper: 4002 | Gateway real: 4001
IB_HOST = "127.0.0.1"
IB_PORT = 7497
IB_CLIENT_ID = 17
