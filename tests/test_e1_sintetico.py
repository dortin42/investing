import numpy as np
import pandas as pd
import pytest

from investing.strategies.e1_tsmom import (
    APALANCAMIENTO_MAX,
    BANDA_NO_OPERAR,
    LOOKBACK_SESIONES,
    SESIONES_ANIO,
    SIGMA_OBJETIVO,
    SPAN_VOL_EWMA,
    TOPE_POR_ACTIVO,
    E1TSMOM,
    serie_pesos_e1,
)


def _precios(retornos: dict[str, float], n: int = 400) -> pd.DataFrame:
    indice = pd.bdate_range("2015-01-01", periods=n)
    columnas = {}
    for simbolo, retorno in retornos.items():
        pasos = np.full(n, 1.0 + retorno)
        columnas[simbolo] = 100.0 * np.cumprod(pasos)
    return pd.DataFrame(columnas, index=indice)


def test_parametros_fijados_al_backtest():
    assert LOOKBACK_SESIONES == 252
    assert SPAN_VOL_EWMA == 60
    assert SESIONES_ANIO == 252
    assert SIGMA_OBJETIVO == 0.10
    assert TOPE_POR_ACTIVO == 0.40
    assert BANDA_NO_OPERAR == 0.05
    assert APALANCAMIENTO_MAX == 1.0


def test_tendencia_negativa_se_queda_en_caja():
    precios = _precios({"SPYL": -1e-3, "PPFB": -1e-3})
    ultima = E1TSMOM(("SPYL", "PPFB")).serie_pesos(precios).iloc[-1]
    assert ultima["SPYL"] == 0.0
    assert ultima["PPFB"] == 0.0


def test_volatilidad_nula_choca_con_el_tope_del_40_por_ciento_sin_apalancar():
    precios = _precios({"SPYL": 1e-4, "PPFB": 1e-4})
    ultima = E1TSMOM(("SPYL", "PPFB")).serie_pesos(precios).iloc[-1]
    assert ultima["SPYL"] == pytest.approx(0.40)
    assert ultima["PPFB"] == pytest.approx(0.40)
    assert ultima.sum() == pytest.approx(0.80)


def test_tres_activos_en_el_tope_se_escalan_a_una_vez():
    precios = _precios({"SPYL": 1e-4, "PPFB": 1e-4, "SXRM": 1e-4})
    ultima = E1TSMOM(("SPYL", "PPFB", "SXRM")).serie_pesos(precios).iloc[-1]
    assert ultima.sum() == pytest.approx(1.0)
    assert ultima["SPYL"] == pytest.approx(1 / 3)
    assert (ultima <= 0.40 + 1e-12).all()


def test_el_sigma_no_se_reasigna_al_activo_que_sigue_largo():
    rng = np.random.default_rng(7)
    indice = pd.bdate_range("2015-01-01", periods=500)
    # SPYL sube con ruido; PPFB baja, así que su señal se va a caja.
    shock_spyl = rng.normal(0.0015, 0.008, size=len(indice))
    shock_ppfb = rng.normal(-0.0015, 0.008, size=len(indice))
    precios = pd.DataFrame(
        {
            "SPYL": 100.0 * np.cumprod(1.0 + shock_spyl),
            "PPFB": 100.0 * np.cumprod(1.0 + shock_ppfb),
        },
        index=indice,
    )
    pesos = serie_pesos_e1(precios)
    retorno = precios / precios.shift(LOOKBACK_SESIONES) - 1
    volatilidad = (
        precios.pct_change()
        .ewm(span=SPAN_VOL_EWMA, min_periods=SPAN_VOL_EWMA, adjust=True, ignore_na=False)
        .std(bias=False)
        * np.sqrt(SESIONES_ANIO)
    )
    largo_sin_tope = (retorno["SPYL"] > 0) & (retorno["PPFB"] <= 0)
    largo_sin_tope &= volatilidad["SPYL"].notna()
    largo_sin_tope &= (SIGMA_OBJETIVO / 2) / volatilidad["SPYL"] < TOPE_POR_ACTIVO
    candidatos = pesos.index[largo_sin_tope.fillna(False)]
    assert len(candidatos) > 0
    momento = candidatos[-1]
    assert pesos.at[momento, "PPFB"] == 0.0
    vol = float(volatilidad.at[momento, "SPYL"])
    esperado = (SIGMA_OBJETIVO / 2) / vol
    sin_reparto = min(TOPE_POR_ACTIVO, SIGMA_OBJETIVO / vol)
    assert pesos.at[momento, "SPYL"] == pytest.approx(esperado)
    assert esperado != pytest.approx(sin_reparto)
