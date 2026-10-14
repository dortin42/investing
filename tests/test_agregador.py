from datetime import date

import pytest

from investing.aggregator.agregador import Agregador, escalar_si_supera
from investing.contratos import TargetWeights


def _senal(estrategia, pesos):
    return TargetWeights(estrategia=estrategia, fecha_senal=date(2025, 1, 31), pesos=pesos)


def test_suma_los_solapes_y_aplica_el_presupuesto():
    agregador = Agregador()
    netos = agregador.combinar(
        "cuenta_10k",
        [
            _senal("E1_4act", {"SPYL": 0.40, "PPFB": 0.20, "SXRM": 0.10, "SXRS": 0.0}),
            _senal("E1_2act", {"SPYL": 0.30, "PPFB": 0.30}),
        ],
        {"E1_4act": 0.5, "E1_2act": 0.5},
    )
    assert netos.factor_escala == 1.0
    assert netos.pesos["SPYL"] == pytest.approx(0.5 * 0.40 + 0.5 * 0.30)
    assert netos.pesos["PPFB"] == pytest.approx(0.5 * 0.20 + 0.5 * 0.30)
    assert netos.pesos["SXRM"] == pytest.approx(0.05)
    assert netos.pesos["SXRS"] == pytest.approx(0.0)
    assert sum(netos.pesos.values()) <= 1


def test_el_presupuesto_parcial_deja_el_resto_en_caja():
    netos = Agregador().combinar(
        "cuenta_3k",
        [_senal("E1", {"SPYL": 0.40, "PPFB": 0.40})],
        {"E1": 0.5},
    )
    assert sum(netos.pesos.values()) == pytest.approx(0.40)
    assert netos.pesos["SPYL"] == pytest.approx(0.20)


def test_escalar_a_la_baja_cuando_el_bruto_supera_uno():
    escalados, factor = escalar_si_supera({"SPYL": 0.50, "PPFB": 0.50, "SXRM": 0.25})
    assert factor == pytest.approx(1 / 1.25)
    assert sum(escalados.values()) == pytest.approx(1.0)
    assert escalados["SPYL"] == pytest.approx(0.40)
    assert escalados["SXRM"] == pytest.approx(0.20)


def test_rechaza_presupuestos_que_suman_mas_de_uno():
    with pytest.raises(ValueError, match="presupuestos"):
        Agregador().combinar(
            "cuenta_10k",
            [
                _senal("E1_4act", {"SPYL": 0.2}),
                _senal("E1_2act", {"PPFB": 0.2}),
            ],
            {"E1_4act": 0.6, "E1_2act": 0.6},
        )


def test_target_weights_rechaza_cortos_y_suma_mayor_que_uno():
    with pytest.raises(ValueError, match="fuera de"):
        _senal("E1", {"SPYL": -0.2, "PPFB": 0.2})
    with pytest.raises(ValueError, match="suma"):
        _senal("E1", {"SPYL": 0.6, "PPFB": 0.6})
