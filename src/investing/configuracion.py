"""Carga de la configuración de cuentas. Los parámetros de E1 no se leen de aquí."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

from investing.contratos import TOLERANCIA_PESO
from investing.strategies.e1_tsmom import E1TSMOM
from investing.universo import exigir_simbolos

_CLAVES_RAIZ = {"divisa", "cuentas"}
_CLAVES_CUENTA = {"capital_eur", "descripcion", "estrategias"}
_CLAVES_ESTRATEGIA = {"id", "tipo", "universo", "presupuesto_riesgo"}
_TIPO_E1 = "e1_tsmom"


@dataclass(frozen=True)
class EstrategiaConfig:
    id: str
    tipo: str
    universo: tuple[str, ...]
    presupuesto_riesgo: float


@dataclass(frozen=True)
class CuentaConfig:
    id: str
    capital_eur: float
    estrategias: tuple[EstrategiaConfig, ...]
    descripcion: str = ""

    def presupuestos(self) -> dict[str, float]:
        return {estrategia.id: estrategia.presupuesto_riesgo for estrategia in self.estrategias}

    def simbolos(self) -> tuple[str, ...]:
        vistos: list[str] = []
        for estrategia in self.estrategias:
            for simbolo in estrategia.universo:
                if simbolo not in vistos:
                    vistos.append(simbolo)
        return tuple(vistos)


@dataclass(frozen=True)
class Configuracion:
    divisa: str
    cuentas: Mapping[str, CuentaConfig]

    def cuenta(self, cuenta_id: str) -> CuentaConfig:
        try:
            return self.cuentas[cuenta_id]
        except KeyError as exc:
            disponibles = ", ".join(sorted(self.cuentas))
            raise KeyError(f"no existe la cuenta {cuenta_id!r}. Cuentas: {disponibles}") from exc


def construir_estrategias(cuenta: CuentaConfig) -> tuple[E1TSMOM, ...]:
    """Instancia las estrategias de la cuenta. En esta PR solo existe E1."""
    construidas: list[E1TSMOM] = []
    for estrategia in cuenta.estrategias:
        if estrategia.tipo != _TIPO_E1:
            raise NotImplementedError(
                f"TODO: la estrategia {estrategia.tipo!r} no entra en esta PR; "
                "la única implementada es e1_tsmom."
            )
        construidas.append(E1TSMOM(estrategia.universo, estrategia_id=estrategia.id))
    return tuple(construidas)


def cargar_configuracion(ruta: Path | str) -> Configuracion:
    path = Path(ruta)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} no contiene un mapa YAML")
    desconocidas = set(raw) - _CLAVES_RAIZ
    if desconocidas:
        raise ValueError(f"claves no reconocidas en la configuración: {sorted(desconocidas)}")
    if raw.get("divisa") != "EUR":
        raise ValueError("las cuentas de esta fase están en EUR")
    cuentas_raw = raw.get("cuentas")
    if not isinstance(cuentas_raw, dict) or not cuentas_raw:
        raise ValueError("la configuración necesita al menos una cuenta")
    cuentas = {
        str(cuenta_id): _cuenta(str(cuenta_id), cuerpo)
        for cuenta_id, cuerpo in cuentas_raw.items()
    }
    return Configuracion(divisa="EUR", cuentas=cuentas)


def _cuenta(cuenta_id: str, cuerpo: object) -> CuentaConfig:
    if not isinstance(cuerpo, dict):
        raise ValueError(f"la cuenta {cuenta_id} tiene que ser un mapa")
    desconocidas = set(cuerpo) - _CLAVES_CUENTA
    if desconocidas:
        raise ValueError(f"claves no reconocidas en {cuenta_id}: {sorted(desconocidas)}")
    capital = cuerpo.get("capital_eur")
    if isinstance(capital, bool) or not isinstance(capital, (int, float)) or not math.isfinite(capital):
        raise ValueError(f"capital_eur de {cuenta_id} tiene que ser un número")
    if float(capital) <= 0:
        raise ValueError(f"capital_eur de {cuenta_id} tiene que ser positivo")
    estrategias_raw = cuerpo.get("estrategias")
    if not isinstance(estrategias_raw, list) or not estrategias_raw:
        raise ValueError(f"{cuenta_id} necesita una lista de estrategias")
    estrategias = tuple(_estrategia(cuenta_id, item) for item in estrategias_raw)
    ids = [estrategia.id for estrategia in estrategias]
    if len(set(ids)) != len(ids):
        raise ValueError(f"ids de estrategia repetidos en {cuenta_id}: {ids}")
    suma = math.fsum(estrategia.presupuesto_riesgo for estrategia in estrategias)
    if suma > 1 + TOLERANCIA_PESO:
        raise ValueError(f"la suma de presupuestos de {cuenta_id} es {suma}; el máximo es 1")
    descripcion = cuerpo.get("descripcion", "")
    if not isinstance(descripcion, str):
        raise ValueError(f"la descripción de {cuenta_id} tiene que ser texto")
    return CuentaConfig(
        id=cuenta_id,
        capital_eur=float(capital),
        estrategias=estrategias,
        descripcion=descripcion,
    )


def _estrategia(cuenta_id: str, cuerpo: object) -> EstrategiaConfig:
    if not isinstance(cuerpo, dict):
        raise ValueError(f"estrategia mal formada en {cuenta_id}")
    if "parametros" in cuerpo:
        raise ValueError(
            "los parámetros de E1 están fijados en el código "
            "(L252, σ 10 %, tope 40 %, banda 5 puntos, apalancamiento 1×) "
            "y no se sobreescriben desde la configuración"
        )
    desconocidas = set(cuerpo) - _CLAVES_ESTRATEGIA
    if desconocidas:
        raise ValueError(f"claves no reconocidas en una estrategia de {cuenta_id}: {sorted(desconocidas)}")
    estrategia_id = cuerpo.get("id")
    tipo = cuerpo.get("tipo")
    if not isinstance(estrategia_id, str) or estrategia_id.strip() == "":
        raise ValueError(f"estrategia sin id en {cuenta_id}")
    if not isinstance(tipo, str) or tipo.strip() == "":
        raise ValueError(f"la estrategia {estrategia_id} no tiene tipo")
    universo_raw = cuerpo.get("universo")
    if not isinstance(universo_raw, list) or not all(isinstance(item, str) for item in universo_raw):
        raise ValueError(f"el universo de {estrategia_id} tiene que ser una lista de símbolos")
    presupuesto = cuerpo.get("presupuesto_riesgo")
    if isinstance(presupuesto, bool) or not isinstance(presupuesto, (int, float)) or not math.isfinite(presupuesto):
        raise ValueError(f"presupuesto_riesgo de {estrategia_id} tiene que ser un número")
    valor = float(presupuesto)
    if valor < 0 or valor > 1 + TOLERANCIA_PESO:
        raise ValueError(f"presupuesto_riesgo de {estrategia_id} está fuera de [0, 1]")
    return EstrategiaConfig(
        id=estrategia_id,
        tipo=tipo,
        universo=exigir_simbolos(universo_raw),
        presupuesto_riesgo=valor,
    )
