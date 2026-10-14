"""Contrato entre estrategia, agregador, riesgo y ejecutor.

La estrategia entrega ``TargetWeights``. El agregador los combina por cuenta.
El control de riesgo puede vetar o reducir. El ejecutor solo recibe un veredicto
que ya pasó por riesgo. Los stubs de riesgo, ejecución y datos históricos de IBKR
están en sus paquetes y lanzan ``NotImplementedError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Mapping

TOLERANCIA_PESO = 1e-9


class DecisionRiesgo(Enum):
    """Qué puede hacer el control de riesgo con una propuesta de pesos."""

    PERMITIR = "permitir"
    REDUCIR = "reducir"
    VETAR = "vetar"


def validar_pesos(pesos: Mapping[str, float]) -> dict[str, float]:
    """Comprueba el contrato de una estrategia: cada peso en [0, 1] y la suma <= 1.

    El resto hasta 1 es caja. Un peso negativo sería un corto y se rechaza.
    """
    if isinstance(pesos, (str, bytes)) or not isinstance(pesos, Mapping):
        raise TypeError("los pesos deben ser un diccionario símbolo -> peso")
    limpios: dict[str, float] = {}
    for simbolo, peso in pesos.items():
        if not isinstance(simbolo, str) or simbolo == "" or simbolo != simbolo.strip():
            raise ValueError(f"símbolo no válido: {simbolo!r}")
        try:
            valor = float(peso)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"peso no numérico para {simbolo}") from exc
        if not math.isfinite(valor):
            raise ValueError(f"peso no finito para {simbolo}: {valor}")
        if valor < -TOLERANCIA_PESO or valor > 1 + TOLERANCIA_PESO:
            raise ValueError(f"el peso de {simbolo} está fuera de [0, 1]: {valor}")
        if valor < 0:
            valor = 0.0
        elif valor > 1:
            valor = 1.0
        limpios[simbolo] = valor
    total = math.fsum(limpios.values())
    if total > 1 + TOLERANCIA_PESO:
        raise ValueError(f"la suma de pesos es {total}; el máximo es 1 (el resto queda en caja)")
    return limpios


def _congelar(pesos: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType(dict(pesos))


@dataclass(frozen=True)
class TargetWeights:
    """Pesos objetivo de una estrategia en la fecha del cierre que los genera.

    ``pesos`` mapea símbolo a fracción del capital de la sleeve. Cada valor está
    en [0, 1] y la suma es <= 1. Lo que no está invertido se queda en caja.
    """

    estrategia: str
    fecha_senal: date
    pesos: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.estrategia, str) or self.estrategia.strip() == "":
            raise ValueError("la estrategia necesita un id")
        if not isinstance(self.fecha_senal, date):
            raise TypeError("fecha_senal tiene que ser datetime.date")
        object.__setattr__(self, "pesos", _congelar(validar_pesos(self.pesos)))

    @property
    def suma(self) -> float:
        return math.fsum(self.pesos.values())

    @property
    def caja(self) -> float:
        return 1.0 - self.suma


@dataclass(frozen=True)
class PesosCuenta:
    """Pesos netos de una cuenta después del agregador, listos para el control de riesgo.

    ``por_estrategia`` son los pesos de cada sleeve ya multiplicados por su
    presupuesto y todavía sin el factor de escala de la cuenta. ``factor_escala``
    es 1 cuando el bruto ya cabía en 1×, y menor que 1 cuando hubo que escalar.
    """

    cuenta: str
    fecha_senal: date
    pesos: Mapping[str, float]
    factor_escala: float
    por_estrategia: Mapping[str, Mapping[str, float]]

    def __post_init__(self) -> None:
        if not isinstance(self.cuenta, str) or self.cuenta.strip() == "":
            raise ValueError("la cuenta necesita un id")
        if not isinstance(self.fecha_senal, date):
            raise TypeError("fecha_senal tiene que ser datetime.date")
        if not math.isfinite(self.factor_escala) or self.factor_escala <= 0 or self.factor_escala > 1 + TOLERANCIA_PESO:
            raise ValueError(f"factor de escala fuera de (0, 1]: {self.factor_escala}")
        object.__setattr__(self, "pesos", _congelar(validar_pesos(self.pesos)))
        detalle: dict[str, Mapping[str, float]] = {}
        for estrategia, pesos in self.por_estrategia.items():
            if not isinstance(estrategia, str) or estrategia.strip() == "":
                raise ValueError("id de estrategia vacío en el desglose")
            detalle[estrategia] = _congelar({simbolo: float(peso) for simbolo, peso in pesos.items()})
        object.__setattr__(self, "por_estrategia", MappingProxyType(detalle))


@dataclass(frozen=True)
class VeredictoRiesgo:
    """Resultado del control de riesgo. El ejecutor solo actúa si la decisión lo permite.

    En ``REDUCIR``, ``pesos`` ya son los pesos recortados. En ``VETAR`` no se envía
    ninguna orden. En ``PERMITIR``, ``pesos`` son los de la propuesta.
    """

    decision: DecisionRiesgo
    pesos: Mapping[str, float]
    motivos: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.decision, DecisionRiesgo):
            raise TypeError("decision tiene que ser DecisionRiesgo")
        if self.decision is DecisionRiesgo.VETAR:
            object.__setattr__(self, "pesos", _congelar({}))
        else:
            object.__setattr__(self, "pesos", _congelar(validar_pesos(self.pesos)))
        if isinstance(self.motivos, str) or not isinstance(self.motivos, tuple):
            raise TypeError("motivos tiene que ser una tupla de textos")
        object.__setattr__(self, "motivos", tuple(str(motivo) for motivo in self.motivos))
