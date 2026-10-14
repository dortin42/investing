"""Descubrimiento de contratos: pregunta a IB que hay para cada ticker/nombre.

Uso: python find_contracts.py VUAA "vanguard s&p 500" IS3N ...
Sin argumentos, busca los tickers problematicos del universo actual.
"""

import sys

from ib_async import IB, Stock

import config

DEFAULT_QUERIES = ["VUAA", "EQAC", "EQQQ", "IS3N", "SXRM", "IS04", "IQQ6",
                   "CSPX", "SXR8", "DTLA", "IBTM"]

EXCHANGES = [("SMART", "EUR"), ("IBIS", "EUR"), ("IBIS2", "EUR"),
             ("LSEETF", "USD"), ("LSEETF", "GBP"), ("AEB", "EUR"),
             ("BVME.ETF", "EUR")]


def main():
    queries = sys.argv[1:] or DEFAULT_QUERIES
    ib = IB()
    ib.connect(config.IB_HOST, config.IB_PORT, clientId=config.IB_CLIENT_ID + 1,
               timeout=20)
    try:
        for q in queries:
            print(f"\n=== {q} ===")
            # 1) busqueda difusa de IB (como la barra de busqueda de TWS)
            matches = ib.reqMatchingSymbols(q)
            for m in (matches or [])[:8]:
                c = m.contract
                if c.secType != "STK":
                    continue
                print(f"  [match] {c.symbol:8s} {c.primaryExchange or c.exchange:10s} "
                      f"{c.currency:4s} {m.contractDescription.longName if hasattr(m, 'contractDescription') else ''}")
            # 2) intentos directos por bolsa
            for exchange, currency in EXCHANGES:
                contract = Stock(q, exchange, currency)
                try:
                    if ib.qualifyContracts(contract) and contract.conId:
                        details = ib.reqContractDetails(contract)
                        name = details[0].longName if details else "?"
                        print(f"  [ok]    {q:8s} {exchange:10s} {currency:4s} {name}")
                except Exception:
                    pass
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
