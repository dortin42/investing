"""Agregador por cuenta: presupuesto de riesgo por estrategia y pesos netos.

El peso neto de un símbolo es la suma, sobre las estrategias, de
``presupuesto × peso``. Con estrategias long-only eso es el neteo entre sleeves.
Si el bruto supera 1, se escala todo a la baja (apalancamiento máximo 1×).
El redondeo a participaciones, la orden mínima de 500 EUR y el neteo contra la
posición real del bróker los hace el ejecutor.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from investing.contratos import TOLERANCIA_PESO, PesosCuenta, TargetWeights, validar_pesos


def escalar_si_supera(
    pesos: Mapping[str, float],
    maximo: float = 1.0,
) -> tuple[dict[str, float], float]:
    """Devuelve los pesos y el factor aplicado. El factor es 1 si ya cabían en ``maximo``."""
    if not math.isfinite(maximo) or maximo <= 0:
        raise ValueError(f"tope de apalancamiento no válido: {maximo}")
    limpios: dict[str, float] = {}
    for simbolo, peso in pesos.items():
        valor = float(peso)
        if not math.isfinite(valor):
            raise ValueError(f"peso no finito para {simbolo}")
        if valor < -TOLERANCIA_PESO:
            raise ValueError(f"peso negativo en {simbolo}: no hay cortos")
        limpios[simbolo] = 0.0 if valor <= TOLERANCIA_PESO else valor
    total = math.fsum(limpios.values())
    if total > maximo + TOLERANCIA_PESO:
        factor = maximo / total
        return {simbolo: peso * factor for simbolo, peso in limpios.items()}, factor
    return limpios, 1.0


class Agregador:
    """Combina las sleeves de una cuenta. El apalancamiento de las cuentas propias es 1×."""

    def __init__(self, apalancamiento_max: float = 1.0) -> None:
        if apalancamiento_max != 1.0:
            raise ValueError("el apalancamiento máximo de las cuentas propias es 1")
        self.apalancamiento_max = apalancamiento_max

    def combinar(
        self,
        cuenta: str,
        senales: Sequence[TargetWeights],
        presupuestos: Mapping[str, float],
    ) -> PesosCuenta:
        if not senales:
            raise ValueError("el agregador necesita al menos una señal")
        ids = [senal.estrategia for senal in senales]
        if len(set(ids)) != len(ids):
            raise ValueError(f"hay estrategias repetidas en el ciclo: {ids}")
        if set(ids) != set(presupuestos):
            raise ValueError(
                f"los presupuestos {sorted(presupuestos)} no cubren las señales {sorted(ids)}"
            )
        fechas = {senal.fecha_senal for senal in senales}
        if len(fechas) != 1:
            raise ValueError(f"las señales del ciclo no comparten fecha: {sorted(fechas)}")
        self._validar_presupuestos(presupuestos)

        neto: dict[str, float] = {}
        detalle: dict[str, dict[str, float]] = {}
        for senal in senales:
            presupuesto = float(presupuestos[senal.estrategia])
            contribucion: dict[str, float] = {}
            for simbolo, peso in senal.pesos.items():
                aportacion = presupuesto * float(peso)
                contribucion[simbolo] = aportacion
                neto[simbolo] = neto.get(simbolo, 0.0) + aportacion
            detalle[senal.estrategia] = contribucion

        escalados, factor = escalar_si_supera(neto, self.apalancamiento_max)
        # validar_pesos deja el contrato cerrado antes de construir PesosCuenta
        return PesosCuenta(
            cuenta=cuenta,
            fecha_senal=senales[0].fecha_senal,
            pesos=validar_pesos(escalados),
            factor_escala=factor,
            por_estrategia=detalle,
        )

    @staticmethod
    def _validar_presupuestos(presupuestos: Mapping[str, float]) -> None:
        total = 0.0
        for estrategia, presupuesto in presupuestos.items():
            valor = float(presupuesto)
            if not math.isfinite(valor) or valor < 0 or valor > 1 + TOLERANCIA_PESO:
                raise ValueError(f"presupuesto de {estrategia} fuera de [0, 1]: {presupuesto}")
            total += valor
        if total > 1 + TOLERANCIA_PESO:
            raise ValueError(f"la suma de presupuestos es {total}; el máximo de la cuenta es 1")
