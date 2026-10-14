"""Control de riesgo. Stub: lo implementa la PR de Riesgo (kill switch y riesgo.yaml).

Toda propuesta de órdenes pasa por ``evaluar`` antes de llegar al ejecutor.
La implementación futura puede vetar el ciclo o devolver pesos más bajos.
Los límites del marco (drawdown −12/−18/−25 %, concentración, orden mínima,
desconexión por sleeve) viven ahí, no en esta PR.
"""

from __future__ import annotations

from typing import Mapping, Protocol

from investing.configuracion import CuentaConfig
from investing.contratos import PesosCuenta, VeredictoRiesgo

_TODO_RIESGO = (
    "TODO (Riesgo): implementar el kill switch y la lectura de riesgo.yaml "
    "(marco v1.2: drawdown de cuenta −12/−18/−25 %, concentración de oro y de "
    "renta variable, orden mínima de 500 EUR, desconexión por sleeve). "
    "evaluar() puede vetar o devolver pesos reducidos. Ninguna orden puede saltarse esta interfaz."
)


class ControlRiesgo(Protocol):
    def evaluar(
        self,
        cuenta: CuentaConfig,
        propuesta: PesosCuenta,
        pesos_actuales: Mapping[str, Mapping[str, float]],
    ) -> VeredictoRiesgo:
        """Veta, reduce o deja pasar la propuesta. Se llama antes de cualquier orden."""


class ControlRiesgoNoImplementado:
    """Stub. No deja pasar una propuesta por silencio: falla de forma explícita."""

    def evaluar(
        self,
        cuenta: CuentaConfig,
        propuesta: PesosCuenta,
        pesos_actuales: Mapping[str, Mapping[str, float]],
    ) -> VeredictoRiesgo:
        raise NotImplementedError(_TODO_RIESGO)
