from datetime import date

import pandas as pd
import pytest

from investing.configuracion import CuentaConfig, EstrategiaConfig
from investing.contratos import DecisionRiesgo, TargetWeights, VeredictoRiesgo
from investing.execution.ejecutor import EjecutorIBKR
from investing.flujo import EstadoCiclo, ejecutar_ciclo
from investing.risk.control import ControlRiesgoNoImplementado


class _EstrategiaFija:
    def __init__(self, estrategia_id: str, pesos: dict[str, float], banda: float = 0.05) -> None:
        self.id = estrategia_id
        self.banda = banda
        self.frecuencia = "mensual"
        self.universo = tuple(pesos)
        self._pesos = pesos

    def senal(self, precios, fecha=None):
        return TargetWeights(self.id, fecha, self._pesos)


class _Riesgo:
    def __init__(self, decision: DecisionRiesgo, orden: list[str], factor: float = 1.0) -> None:
        self.decision = decision
        self.orden = orden
        self.factor = factor
        self.llamadas = 0

    def evaluar(self, cuenta, propuesta, pesos_actuales):
        self.orden.append("riesgo")
        self.llamadas += 1
        if self.decision is DecisionRiesgo.VETAR:
            return VeredictoRiesgo(DecisionRiesgo.VETAR, {}, ("veto de prueba",))
        pesos = {simbolo: peso * self.factor for simbolo, peso in propuesta.pesos.items()}
        return VeredictoRiesgo(self.decision, pesos, ())


class _Ejecutor:
    def __init__(self, orden: list[str]) -> None:
        self.orden = orden
        self.veredictos = []
        self.fechas = []

    def ejecutar(self, cuenta, veredicto, fecha_ejecucion):
        self.orden.append("ejecutor")
        self.veredictos.append(veredicto)
        self.fechas.append(fecha_ejecucion)


def _cuenta() -> CuentaConfig:
    return CuentaConfig(
        id="cuenta_10k",
        capital_eur=10000,
        estrategias=(
            EstrategiaConfig(
                id="E1",
                tipo="e1_tsmom",
                universo=("SPYL", "PPFB", "SXRM", "SXRS"),
                presupuesto_riesgo=1.0,
            ),
        ),
    )


def _precios() -> pd.DataFrame:
    return pd.DataFrame(
        {"SPYL": [10.0, 10.0]},
        index=pd.to_datetime(["2024-12-30", "2024-12-31"]),
    )


def test_el_riesgo_corre_antes_que_el_ejecutor_y_puede_reducir():
    orden: list[str] = []
    riesgo = _Riesgo(DecisionRiesgo.REDUCIR, orden, factor=0.5)
    ejecutor = _Ejecutor(orden)
    resultado = ejecutar_ciclo(
        cuenta=_cuenta(),
        estrategias=[_EstrategiaFija("E1", {"SPYL": 0.4, "PPFB": 0.2, "SXRM": 0.0, "SXRS": 0.0})],
        precios=_precios(),
        fecha=date(2024, 12, 30),
        riesgo=riesgo,
        ejecutor=ejecutor,
    )
    assert orden == ["riesgo", "ejecutor"]
    assert resultado.estado is EstadoCiclo.EJECUTADO
    assert resultado.fecha_ejecucion == date(2025, 1, 2)
    assert ejecutor.veredictos[0].decision is DecisionRiesgo.REDUCIR
    assert ejecutor.veredictos[0].pesos["SPYL"] == 0.2
    assert resultado.veredicto is ejecutor.veredictos[0]


def test_un_veto_no_llama_al_ejecutor():
    orden: list[str] = []
    resultado = ejecutar_ciclo(
        cuenta=_cuenta(),
        estrategias=[_EstrategiaFija("E1", {"SPYL": 0.4})],
        precios=_precios(),
        fecha=date(2024, 12, 30),
        riesgo=_Riesgo(DecisionRiesgo.VETAR, orden),
        ejecutor=_Ejecutor(orden),
    )
    assert orden == ["riesgo"]
    assert resultado.estado is EstadoCiclo.VETADO
    assert resultado.veredicto is not None
    assert resultado.veredicto.motivos == ("veto de prueba",)


def test_el_stub_de_riesgo_corta_el_ciclo_antes_del_ejecutor():
    orden: list[str] = []
    ejecutor = _Ejecutor(orden)
    try:
        ejecutar_ciclo(
            cuenta=_cuenta(),
            estrategias=[_EstrategiaFija("E1", {"SPYL": 0.4})],
            precios=_precios(),
            fecha=date(2024, 12, 30),
            riesgo=ControlRiesgoNoImplementado(),
            ejecutor=ejecutor,
        )
    except NotImplementedError as exc:
        assert "TODO (Riesgo)" in str(exc)
    else:
        raise AssertionError("el stub de riesgo tenía que interrumpir el ciclo")
    assert orden == []


def test_el_31_de_diciembre_de_2024_no_es_sesion_de_rebalanceo_en_xetra():
    orden: list[str] = []
    riesgo = _Riesgo(DecisionRiesgo.PERMITIR, orden)
    resultado = ejecutar_ciclo(
        cuenta=_cuenta(),
        estrategias=[_EstrategiaFija("E1", {"SPYL": 0.4})],
        precios=_precios(),
        fecha=date(2024, 12, 31),
        riesgo=riesgo,
        ejecutor=_Ejecutor(orden),
    )
    assert resultado.estado is EstadoCiclo.SIN_REBALANCEO
    assert riesgo.llamadas == 0
    assert orden == []


def test_la_banda_conserva_el_peso_actual_dentro_de_cinco_puntos():
    orden: list[str] = []
    riesgo = _Riesgo(DecisionRiesgo.PERMITIR, orden)
    resultado = ejecutar_ciclo(
        cuenta=_cuenta(),
        estrategias=[_EstrategiaFija("E1", {"SPYL": 0.40, "PPFB": 0.20, "SXRM": 0.10, "SXRS": 0.10})],
        precios=_precios(),
        fecha=date(2024, 12, 30),
        riesgo=riesgo,
        ejecutor=_Ejecutor(orden),
        pesos_actuales={"E1": {"SPYL": 0.44, "PPFB": 0.23, "SXRM": 0.13, "SXRS": 0.12}},
    )
    assert resultado.propuesta is not None
    assert resultado.propuesta.pesos["SPYL"] == pytest.approx(0.44)
    assert resultado.propuesta.pesos["SXRS"] == pytest.approx(0.12)
    assert resultado.propuesta.factor_escala == 1.0


def test_una_sleeve_por_encima_de_uno_se_escala_antes_de_llegar_al_riesgo():
    # La banda conserva los pesos desviados (distancia de 4 puntos) y la suma pasa de 1.
    orden: list[str] = []
    riesgo = _Riesgo(DecisionRiesgo.PERMITIR, orden)
    actuales = {"SPYL": 0.44, "PPFB": 0.34, "SXRM": 0.24, "SXRS": 0.14}
    resultado = ejecutar_ciclo(
        cuenta=_cuenta(),
        estrategias=[_EstrategiaFija("E1", {"SPYL": 0.40, "PPFB": 0.30, "SXRM": 0.20, "SXRS": 0.10})],
        precios=_precios(),
        fecha=date(2024, 12, 30),
        riesgo=riesgo,
        ejecutor=_Ejecutor(orden),
        pesos_actuales={"E1": actuales},
    )
    assert resultado.propuesta is not None
    assert sum(resultado.propuesta.pesos.values()) == pytest.approx(1)
    assert resultado.propuesta.pesos["SPYL"] == pytest.approx(0.44 / 1.16)
    assert resultado.propuesta.pesos["SPYL"] != pytest.approx(0.40)


def test_el_ejecutor_stub_no_acepta_un_veto():
    from investing.execution.ejecutor import OrdenVetada

    cuenta = _cuenta()
    veredicto = VeredictoRiesgo(DecisionRiesgo.VETAR, {"SPYL": 0.4}, ("no",))
    try:
        EjecutorIBKR().ejecutar(cuenta, veredicto, date(2025, 1, 2))
    except OrdenVetada:
        return
    raise AssertionError("un veto no puede llegar a construirse como orden")
