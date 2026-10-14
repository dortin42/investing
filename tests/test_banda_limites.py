import math

import pytest

from investing.strategies.banda import aplicar_banda, debe_operar
from investing.strategies.e1_tsmom import BANDA_NO_OPERAR


def test_dentro_de_la_banda_se_mantiene_el_peso_actual():
    pesos = aplicar_banda({"SPYL": 0.30, "PPFB": 0.10}, {"SPYL": 0.26, "PPFB": 0.10}, BANDA_NO_OPERAR)
    assert pesos["SPYL"] == 0.26
    assert pesos["PPFB"] == 0.10


def test_por_encima_de_cinco_puntos_se_adopta_el_objetivo():
    pesos = aplicar_banda({"SPYL": 0.30}, {"SPYL": 0.36}, BANDA_NO_OPERAR)
    assert pesos["SPYL"] == 0.30


def test_la_distancia_exacta_de_cinco_puntos_no_opera():
    assert not debe_operar(0.30, 0.35, BANDA_NO_OPERAR)
    assert debe_operar(0.30, 0.35 + 1e-9, BANDA_NO_OPERAR)


def test_salir_a_caja_opera_aunque_la_distancia_quepa_en_la_banda():
    # El motor compara el signo. De largo a cero el signo cambia y se cierra.
    pesos = aplicar_banda({"SPYL": 0.0}, {"SPYL": 0.04}, BANDA_NO_OPERAR)
    assert pesos["SPYL"] == 0.0


def test_entrar_desde_caja_opera_aunque_el_objetivo_sea_pequeno():
    pesos = aplicar_banda({"SPYL": 0.02}, {"SPYL": 0.0}, BANDA_NO_OPERAR)
    assert pesos["SPYL"] == 0.02


def test_un_corto_se_rechaza():
    with pytest.raises(ValueError, match="cortos"):
        aplicar_banda({"SPYL": 0.1}, {"SPYL": -0.1}, BANDA_NO_OPERAR)


def test_la_banda_de_e1_es_cinco_puntos():
    assert BANDA_NO_OPERAR == 0.05
    assert math.isclose(BANDA_NO_OPERAR, 5 / 100)
