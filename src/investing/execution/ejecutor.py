"""Ejecutor de IBKR. Stub: lo implementa la PR de Ejecución.

Responsabilidad prevista, que esta PR no cubre:

- convertir los pesos netos en órdenes límite sobre Xetra el día hábil siguiente
- ``whatIfOrder`` antes de enviar, para ver margen y comisión
- netear contra las posiciones reales de la cuenta y mandar solo la diferencia
- participaciones enteras y orden mínima de 500 EUR, salvo cierre completo
- TWS en modo paper, ``127.0.0.1:7497``

El candado que rechaza el puerto live 7496, y ``paper_vs_backtest.py``, van en
otra PR (Paper). Aquí no hay socket ni envío de órdenes.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from investing.configuracion import CuentaConfig
from investing.contratos import DecisionRiesgo, VeredictoRiesgo

_TODO_EJECUCION = (
    "TODO (Ejecución): convertir los pesos netos en órdenes límite en Xetra "
    "el día hábil siguiente a la señal (exec_lag=1 del backtest). Antes de enviar, "
    "whatIfOrder para margen y comisión; netear contra las posiciones reales de IBKR; "
    "participaciones enteras; no enviar un nominal por debajo de 500 EUR salvo el cierre "
    "completo de la posición. TWS paper en 127.0.0.1:7497. "
    "TODO (Paper): el candado que impide el puerto live 7496 y paper_vs_backtest.py "
    "van en su PR. Esta clase no abre conexión y no envía órdenes."
)


class OrdenVetada(RuntimeError):
    """El control de riesgo ha vetado el ciclo. No se construye ninguna orden."""


class Ejecutor(Protocol):
    def ejecutar(
        self,
        cuenta: CuentaConfig,
        veredicto: VeredictoRiesgo,
        fecha_ejecucion: date,
    ) -> None:
        """Envía las órdenes del veredicto. No se llama si la decisión es vetar."""


class EjecutorIBKR:
    """Stub del ejecutor. Instanciarlo no conecta; ``ejecutar`` no está implementado."""

    def ejecutar(
        self,
        cuenta: CuentaConfig,
        veredicto: VeredictoRiesgo,
        fecha_ejecucion: date,
    ) -> None:
        if veredicto.decision is DecisionRiesgo.VETAR:
            raise OrdenVetada(
                "el control de riesgo ha vetado el rebalanceo; no se envía ninguna orden"
            )
        if veredicto.decision not in (DecisionRiesgo.PERMITIR, DecisionRiesgo.REDUCIR):
            raise RuntimeError(f"decisión de riesgo no contemplada: {veredicto.decision}")
        raise NotImplementedError(_TODO_EJECUCION)
