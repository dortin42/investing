"""Numeros en formato espanol: punto para miles, coma para decimales."""

from __future__ import annotations


def num(x: float, dec: int = 0, sign: bool = False) -> str:
    s = f"{x:{'+' if sign else ''},.{dec}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float, dec: int = 1, sign: bool = True) -> str:
    return num(x * 100, dec, sign) + " %"


def eur(x: float | None, dec: int = 0, sign: bool = False) -> str:
    return "n/d" if x is None else num(x, dec, sign) + " €"
