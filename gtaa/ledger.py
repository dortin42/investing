"""Libro de operaciones de la cuenta virtual del bot y su PnL.

La cuenta paper de IB tiene ~1M EUR, asi que su NetLiq no dice nada de los
CAPITAL_EUR del bot. El PnL sale de un libro propio en logs/ledger.json:
- Las ejecuciones que devuelve IB se apuntan con precio y comision reales.
- Si la posicion de IB no cuadra con el libro, se ajusta: las compras con el
  avgCost de IB (exacto, incluye comision) y las ventas al ultimo cierre,
  marcadas como estimadas.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd

from gtaa import fmt

LEDGER_PATH = Path(__file__).resolve().parent.parent / "logs" / "ledger.json"


def load(capital: float, start: str) -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {"capital_eur": capital, "start": start, "trades": [], "exec_ids": []}


def save(ledger: dict) -> None:
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    ledger["trades"].sort(key=lambda t: t["date"])
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2))


def book(trades: list, upto: str | None = None):
    """Recorre el libro (coste medio). Devuelve posiciones, cash, realizado, comisiones."""
    pos: dict[str, tuple[float, float]] = {}
    cash = realized = commissions = 0.0
    for t in sorted(trades, key=lambda t: t["date"]):
        if upto is not None and t["date"] > upto:
            break
        sym, qty, price = t["symbol"], t["qty"], t["price"]
        fee = t.get("commission", 0.0)
        q0, avg0 = pos.get(sym, (0.0, 0.0))
        commissions += fee
        if t["side"] == "BUY":
            cash -= qty * price + fee
            q1 = q0 + qty
            pos[sym] = (q1, (q0 * avg0 + qty * price + fee) / q1)
        else:
            cash += qty * price - fee
            realized += qty * (price - avg0) - fee
            q1 = q0 - qty
            pos[sym] = (q1, avg0 if q1 > 1e-9 else 0.0)
    return {s: v for s, v in pos.items() if abs(v[0]) > 1e-9}, cash, realized, commissions


def _ingest(ledger: dict, fills: list, symbol_by_conid: dict) -> None:
    seen = set(ledger["exec_ids"])
    for f in fills:
        sym = symbol_by_conid.get(f.contract.conId)
        ex = f.execution
        if sym is None or ex.execId in seen:
            continue
        fee = getattr(f.commissionReport, "commission", 0.0) or 0.0
        if math.isnan(fee) or fee > 1e6:  # IB manda DBL_MAX si aun no hay informe
            fee = 0.0
        ledger["trades"].append({
            "date": f.time.date().isoformat(),
            "symbol": sym,
            "side": "BUY" if ex.side == "BOT" else "SELL",
            "qty": float(ex.shares),
            "price": float(ex.price),
            "commission": float(fee),
            "source": "ejecucion IB",
        })
        ledger["exec_ids"].append(ex.execId)
        seen.add(ex.execId)


def _reconcile(ledger: dict, ib_pos: dict, last_px: dict, today: dt.date) -> list[str]:
    pos, *_ = book(ledger["trades"])
    when = ledger["start"] if not ledger["trades"] else today.isoformat()
    warnings = []
    for sym in sorted(set(pos) | set(ib_pos)):
        q_led, avg_led = pos.get(sym, (0.0, 0.0))
        q_ib, avg_ib = ib_pos.get(sym, (0.0, 0.0))
        diff = q_ib - q_led
        if abs(diff) < 1e-9:
            continue
        if diff > 0:
            price = (q_ib * avg_ib - q_led * avg_led) / diff
            source = "avgCost IB"
            if not price > 0:
                price, source = last_px.get(sym), "estimado: ultimo cierre"
            side = "BUY"
        else:
            price, source, side = last_px.get(sym), "estimado: ultimo cierre", "SELL"
            if price is not None:
                warnings.append(f"{sym}: venta de {-diff:g} sin ejecucion de IB, "
                                f"precio estimado {price:.2f}")
        if price is None:
            warnings.append(f"{sym}: posicion IB {q_ib:g} vs libro {q_led:g}, sin precio")
            continue
        ledger["trades"].append({
            "date": when, "symbol": sym, "side": side, "qty": abs(diff),
            "price": float(price), "commission": 0.0, "source": source,
        })
    return warnings


def sync(broker, contracts_by_symbol: dict, last_px: dict, capital: float,
         start: str, today: dt.date) -> tuple[dict, list[str]]:
    ledger = load(capital, start)
    by_conid = {c.conId: s for s, c in contracts_by_symbol.items()}
    _ingest(ledger, broker.executions(), by_conid)
    ib_pos = {by_conid[cid]: v for cid, v in broker.positions_detail().items()
              if cid in by_conid and abs(v[0]) > 1e-9}
    warnings = _reconcile(ledger, ib_pos, last_px, today)
    save(ledger)
    return ledger, warnings


def metrics(ledger: dict, series_by_symbol: dict) -> dict:
    """Curva de patrimonio diaria desde el inicio, con precios de cierre."""
    capital = ledger["capital_eur"]
    start = pd.Timestamp(ledger["start"])
    frames = {}
    for sym, s in series_by_symbol.items():
        if s is None or s.dropna().empty:
            continue
        s = s.dropna().copy()
        s.index = pd.to_datetime(s.index)
        frames[sym] = s
    prices = pd.DataFrame(frames).sort_index().ffill()
    prices = prices.loc[prices.index >= start]

    equity = {}
    for d, row in prices.iterrows():
        pos, cash, _, _ = book(ledger["trades"], upto=d.strftime("%Y-%m-%d"))
        mv = sum(q * row[s] for s, (q, _) in pos.items() if s in row and pd.notna(row[s]))
        equity[d] = capital + cash + mv
    eq = pd.Series(equity, dtype=float)

    pos, cash, realized, commissions = book(ledger["trades"])
    last = prices.iloc[-1] if len(prices) else pd.Series(dtype=float)
    positions = []
    for sym, (qty, avg) in sorted(pos.items()):
        px = float(last.get(sym, float("nan")))
        positions.append({"symbol": sym, "qty": qty, "avg": avg, "price": px,
                          "value": qty * px, "pnl": qty * (px - avg),
                          "pnl_pct": px / avg - 1 if avg else 0.0})
    value = sum(p["value"] for p in positions)
    cost = sum(p["qty"] * p["avg"] for p in positions)
    now = float(eq.iloc[-1]) if len(eq) else capital + cash + value

    def change_since(days: int) -> float | None:
        if len(eq) < 2:
            return None
        base = eq.loc[:eq.index[-1] - pd.Timedelta(days=days)]
        return now - float(base.iloc[-1]) if len(base) else None

    bench = None
    if "VUAA" in prices and prices["VUAA"].notna().sum() > 1:
        v = prices["VUAA"].dropna()
        bench = float(v.iloc[-1] / v.iloc[0] - 1)

    return {
        "capital": capital,
        "start": ledger["start"],
        "asof": eq.index[-1].date().isoformat() if len(eq) else None,
        "days": (eq.index[-1] - start).days if len(eq) else 0,
        "equity": now,
        "pnl": now - capital,
        "pnl_pct": now / capital - 1,
        "day": float(eq.iloc[-1] - eq.iloc[-2]) if len(eq) > 1 else None,
        "week": change_since(7),
        "max_dd": float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0,
        "unrealized": value - cost,
        "realized": realized,
        "commissions": commissions,
        "cost": cost,
        "value": value,
        "cash": capital + cash,
        "exposure": value / now if now else 0.0,
        "bench_vuaa": bench,
        "positions": positions,
        "estimated": sum(1 for t in ledger["trades"] if t["source"].startswith("estimado")),
    }


def render(m: dict) -> list[str]:
    cash = m["cash"]
    cash_line = (f"Margen usado: {fmt.eur(-cash)} (prestado por IB por el apalancamiento)"
                 if cash < 0 else f"Efectivo sin invertir: {fmt.eur(cash)}")
    lines = [
        f"PnL cuenta {fmt.eur(m['capital'])} (desde {m['start']}, {m['days']} días, "
        f"precios al cierre {m['asof']})",
        f"Patrimonio: {fmt.eur(m['equity'])} | PnL: {fmt.eur(m['pnl'], sign=True)} "
        f"({fmt.pct(m['pnl_pct'])})",
        f"Última sesión: {fmt.eur(m['day'], sign=True)} | 7 días: "
        f"{fmt.eur(m['week'], sign=True)} | Máx. drawdown: {fmt.pct(m['max_dd'], sign=False)}",
        f"No realizado: {fmt.eur(m['unrealized'], sign=True)} | Realizado: "
        f"{fmt.eur(m['realized'], sign=True)} | Comisiones: {fmt.eur(m['commissions'], 2)}",
        f"Invertido (coste): {fmt.eur(m['cost'])} | Valor actual: {fmt.eur(m['value'])}",
        cash_line,
        f"Exposición: {fmt.pct(m['exposure'], 0, False)}" + (
            f" | S&P (VUAA) mismo periodo: {fmt.pct(m['bench_vuaa'])}"
            if m["bench_vuaa"] is not None else ""),
    ]
    if m["positions"]:
        lines.append("Posiciones:")
        for p in m["positions"]:
            weight = p["value"] / m["equity"] if m["equity"] else 0.0
            lines.append(f"{p['symbol']} {fmt.num(p['qty'])} x {fmt.num(p['price'], 2)} = "
                         f"{fmt.eur(p['value'])} (coste {fmt.num(p['avg'], 2)}, "
                         f"{fmt.eur(p['pnl'], sign=True)} {fmt.pct(p['pnl_pct'])}, "
                         f"peso {fmt.pct(weight, 0, False)})")
    else:
        lines.append("Sin posiciones abiertas.")
    if m["estimated"]:
        lines.append(f"Ojo: {m['estimated']} operación(es) con precio estimado.")
    return lines
