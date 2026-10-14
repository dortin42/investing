"""Universo UCITS en Xetra que usa E1. Los símbolos son los del marco de riesgo, sin sufijo de Yahoo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrumento:
    simbolo: str
    nombre: str
    clase_activo: str
    yahoo: str
    proxy_backtest: str
    moneda: str = "EUR"
    mercado: str = "XETRA"


UNIVERSO: dict[str, Instrumento] = {
    "SPYL": Instrumento(
        simbolo="SPYL",
        nombre="State Street SPDR S&P 500 UCITS ETF (Acc)",
        clase_activo="renta_variable",
        yahoo="SPYL.DE",
        proxy_backtest="SPY",
    ),
    "PPFB": Instrumento(
        simbolo="PPFB",
        nombre="iShares Physical Gold ETC",
        clase_activo="oro",
        yahoo="PPFB.DE",
        proxy_backtest="GLD",
    ),
    "SXRM": Instrumento(
        simbolo="SXRM",
        nombre="ETF UCITS de bonos del Tesoro USD 7-10 años",
        clase_activo="bonos",
        yahoo="SXRM.DE",
        proxy_backtest="IEF",
    ),
    "SXRS": Instrumento(
        simbolo="SXRS",
        nombre="iShares Diversified Commodity Swap UCITS ETF",
        clase_activo="materias_primas",
        yahoo="SXRS.DE",
        proxy_backtest="DJP",
    ),
}

UNIVERSO_3K: tuple[str, ...] = ("SPYL", "PPFB")
UNIVERSO_10K: tuple[str, ...] = ("SPYL", "PPFB", "SXRM", "SXRS")


def exigir_simbolos(simbolos: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Devuelve los símbolos si todos pertenecen al universo conocido."""
    if not simbolos:
        raise ValueError("el universo de la estrategia está vacío")
    limpios = tuple(simbolos)
    if len(set(limpios)) != len(limpios):
        raise ValueError(f"universo con símbolos repetidos: {limpios}")
    desconocidos = [simbolo for simbolo in limpios if simbolo not in UNIVERSO]
    if desconocidos:
        raise ValueError(f"símbolos fuera del universo UCITS de E1: {desconocidos}")
    return limpios
