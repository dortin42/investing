"""Ciclo de rebalanceo: señal, banda, agregador, riesgo y, solo después, ejecutor.

En un día que no es el último hábil de Xetra el ciclo termina sin llamar al
riesgo ni al ejecutor, porque no hay orden que vetar. En un día de señal el
control de riesgo corre antes que el ejecutor. Si el stub de riesgo lanza
``NotImplementedError``, la orden no se llega a construir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Mapping, Sequence, assert_never

import pandas as pd

from investing.aggregator.agregador import Agregador, escalar_si_supera
from investing.calendario import Calendario, CalendarioXetra
from investing.configuracion import CuentaConfig
from investing.contratos import DecisionRiesgo, PesosCuenta, TargetWeights, VeredictoRiesgo
from investing.execution.ejecutor import Ejecutor
from investing.log import evento
from investing.risk.control import ControlRiesgo
from investing.strategies.banda import aplicar_banda
from investing.strategies.base import Estrategia

log = logging.getLogger("investing.flujo")


class EstadoCiclo(Enum):
    SIN_REBALANCEO = "sin_rebalanceo"
    VETADO = "vetado"
    EJECUTADO = "ejecutado"


@dataclass(frozen=True)
class ResultadoCiclo:
    estado: EstadoCiclo
    fecha_senal: date
    fecha_ejecucion: date | None
    propuesta: PesosCuenta | None
    veredicto: VeredictoRiesgo | None


def ejecutar_ciclo(
    *,
    cuenta: CuentaConfig,
    estrategias: Sequence[Estrategia],
    precios: pd.DataFrame,
    fecha: date,
    riesgo: ControlRiesgo,
    ejecutor: Ejecutor,
    pesos_actuales: Mapping[str, Mapping[str, float]] | None = None,
    calendario: Calendario | None = None,
    agregador: Agregador | None = None,
) -> ResultadoCiclo:
    """Prepara el rebalanceo mensual y solo entonces pide la ejecución."""
    calendario = calendario or CalendarioXetra()
    agregador = agregador or Agregador()
    actuales = pesos_actuales or {}
    _exigir_estrategias(cuenta, estrategias)

    if not calendario.es_ultimo_habil_del_mes(fecha):
        evento(
            log,
            "dia_sin_rebalanceo",
            cuenta=cuenta.id,
            fecha=fecha.isoformat(),
            calendario=calendario.nombre,
        )
        return ResultadoCiclo(
            estado=EstadoCiclo.SIN_REBALANCEO,
            fecha_senal=fecha,
            fecha_ejecucion=None,
            propuesta=None,
            veredicto=None,
        )

    if fecha not in {pd.Timestamp(marca).date() for marca in precios.index}:
        raise ValueError(f"no hay cierre el {fecha.isoformat()} para calcular la señal de {cuenta.id}")

    fecha_ejecucion = calendario.siguiente_habil(fecha)
    senales = _senales_tras_banda(estrategias, precios, fecha, actuales)
    propuesta = agregador.combinar(cuenta.id, senales, cuenta.presupuestos())
    evento(
        log,
        "pesos_netos",
        cuenta=cuenta.id,
        fecha_senal=fecha.isoformat(),
        fecha_ejecucion=fecha_ejecucion.isoformat(),
        pesos=dict(propuesta.pesos),
        factor_escala=propuesta.factor_escala,
    )

    veredicto = riesgo.evaluar(cuenta, propuesta, actuales)
    evento(
        log,
        "veredicto_riesgo",
        cuenta=cuenta.id,
        decision=veredicto.decision.value,
        motivos=list(veredicto.motivos),
    )

    match veredicto.decision:
        case DecisionRiesgo.VETAR:
            return ResultadoCiclo(
                estado=EstadoCiclo.VETADO,
                fecha_senal=fecha,
                fecha_ejecucion=fecha_ejecucion,
                propuesta=propuesta,
                veredicto=veredicto,
            )
        case DecisionRiesgo.PERMITIR | DecisionRiesgo.REDUCIR:
            ejecutor.ejecutar(cuenta, veredicto, fecha_ejecucion)
            return ResultadoCiclo(
                estado=EstadoCiclo.EJECUTADO,
                fecha_senal=fecha,
                fecha_ejecucion=fecha_ejecucion,
                propuesta=propuesta,
                veredicto=veredicto,
            )
        case otra:
            assert_never(otra)


def _exigir_estrategias(cuenta: CuentaConfig, estrategias: Sequence[Estrategia]) -> None:
    ids_cuenta = [estrategia.id for estrategia in cuenta.estrategias]
    ids_objetos = [estrategia.id for estrategia in estrategias]
    if ids_cuenta != ids_objetos:
        raise ValueError(
            f"las estrategias {ids_objetos} no coinciden con la configuración de {cuenta.id}: {ids_cuenta}"
        )


def _senales_tras_banda(
    estrategias: Sequence[Estrategia],
    precios: pd.DataFrame,
    fecha: date,
    actuales: Mapping[str, Mapping[str, float]],
) -> list[TargetWeights]:
    senales: list[TargetWeights] = []
    for estrategia in estrategias:
        cruda = estrategia.senal(precios, fecha)
        hibrido = aplicar_banda(cruda.pesos, actuales.get(estrategia.id, {}), estrategia.banda)
        # La banda puede conservar un peso ya desviado. Si la sleeve se pasa de 1×,
        # se escala antes de tratar esos pesos como objetivo. El backtest lo impide
        # al no gastar caja que no tiene; aquí el tope entra en el vector de pesos.
        ajustado, factor = escalar_si_supera(hibrido)
        evento(
            log,
            "senal_e1",
            estrategia=estrategia.id,
            fecha_senal=cruda.fecha_senal.isoformat(),
            pesos_crudos=dict(cruda.pesos),
            pesos_tras_banda=ajustado,
            factor_sleeve=factor,
        )
        senales.append(
            TargetWeights(estrategia=estrategia.id, fecha_senal=cruda.fecha_senal, pesos=ajustado)
        )
    return senales
