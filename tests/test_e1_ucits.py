"""La señal sobre ucits_eur.csv tiene que coincidir con e1_tsmom del backtest."""

from datetime import date

import pandas as pd
import pytest

from investing.calendario import CalendarioXetra
from investing.strategies.e1_tsmom import LOOKBACK_SESIONES, TOPE_POR_ACTIVO, E1TSMOM, serie_pesos_e1
from tests.referencia_bt import e1_tsmom

# Cierres de fin de mes en Xetra con las dos variantes ya calientes (lookback cubierto).
FECHAS_MUESTRA = (
    date(2025, 1, 31),
    date(2025, 6, 30),
    date(2025, 12, 30),
)


def _alinear(precios: pd.DataFrame, simbolos: tuple[str, ...]) -> pd.DataFrame:
    return precios.loc[:, list(simbolos)].dropna(how="any").sort_index()


def _comparar_con_el_backtest(precios: pd.DataFrame, simbolos: tuple[str, ...]) -> pd.DataFrame:
    alineados = _alinear(precios, simbolos)
    nuestra = serie_pesos_e1(alineados)
    referencia, _, banda, retraso = e1_tsmom(alineados)
    pd.testing.assert_frame_equal(nuestra, referencia, check_freq=False)
    assert banda == 0.05
    assert retraso == 1
    por_clase = E1TSMOM(simbolos).serie_pesos(precios)
    pd.testing.assert_frame_equal(por_clase, referencia, check_freq=False)
    return nuestra


def test_variante_3k_coincide_con_el_backtest(precios_ucits):
    pesos = _comparar_con_el_backtest(precios_ucits, ("SPYL", "PPFB"))
    _assert_limites(pesos)
    _assert_fechas_de_muestra(pesos)


def test_variante_10k_coincide_con_el_backtest(precios_ucits):
    pesos = _comparar_con_el_backtest(precios_ucits, ("SPYL", "PPFB", "SXRM", "SXRS"))
    _assert_limites(pesos)
    _assert_fechas_de_muestra(pesos)


def test_el_reparto_de_sigma_cambia_entre_la_variante_de_2_y_la_de_4(precios_ucits):
    dos = _alinear(precios_ucits, ("SPYL", "PPFB"))
    cuatro = _alinear(precios_ucits, ("SPYL", "PPFB", "SXRM", "SXRS"))
    pesos_2 = serie_pesos_e1(dos)
    pesos_4 = serie_pesos_e1(cuatro)
    # 2025-01-31 ningún peso de SPYL está en el tope: al pasar de N=4 a N=2 el peso se duplica.
    momento = pd.Timestamp(date(2025, 1, 31))
    assert pesos_2.loc[momento, "SPYL"] == pytest.approx(2 * pesos_4.loc[momento, "SPYL"])
    assert pesos_2.loc[momento, "PPFB"] == pytest.approx(2 * pesos_4.loc[momento, "PPFB"])


def test_topes_sobre_el_csv(precios_ucits):
    dos = serie_pesos_e1(_alinear(precios_ucits, ("SPYL", "PPFB")))
    cuatro = serie_pesos_e1(_alinear(precios_ucits, ("SPYL", "PPFB", "SXRM", "SXRS")))
    diciembre = pd.Timestamp(date(2025, 12, 30))
    assert dos.at[diciembre, "SPYL"] == pytest.approx(TOPE_POR_ACTIVO)
    assert cuatro.at[diciembre, "SXRM"] == pytest.approx(TOPE_POR_ACTIVO)
    # El tope por ETF no rellena el resto: por debajo de 1× el sobrante se queda en caja.
    assert cuatro.loc[diciembre].sum() < 1
    assert dos.loc[diciembre].sum() < 1
    junio = pd.Timestamp(date(2025, 6, 30))
    assert cuatro.at[junio, "SXRS"] == 0.0


def test_muestra_congelada_de_la_variante_de_4(precios_ucits):
    """Ancla numérica por si la copia del oráculo y el código se editan a la vez."""
    pesos = serie_pesos_e1(_alinear(precios_ucits, ("SPYL", "PPFB", "SXRM", "SXRS")))
    muestra = {
        date(2025, 1, 31): {
            "SPYL": 0.17897463855145548,
            "PPFB": 0.16020273345500052,
            "SXRM": 0.4,
            "SXRS": 0.1698948722082087,
        },
        date(2025, 6, 30): {
            "SPYL": 0.12991377412592892,
            "PPFB": 0.1425376013924928,
            "SXRM": 0.39868848668764173,
            "SXRS": 0.0,
        },
        date(2025, 12, 30): {
            "SPYL": 0.21684324920248801,
            "PPFB": 0.13682511146800833,
            "SXRM": 0.4,
            "SXRS": 0.20419089363473464,
        },
    }
    for fecha, esperado in muestra.items():
        fila = pesos.loc[pd.Timestamp(fecha)]
        for simbolo, peso in esperado.items():
            assert fila[simbolo] == pytest.approx(peso, rel=0, abs=1e-12)
        assert fila.sum() == pytest.approx(sum(esperado.values()), abs=1e-12)
        assert fila.sum() <= 1


def test_la_ventana_es_de_252_sesiones_cuando_el_cierre_mensual_discrepa(precios_ucits):
    simbolos = ("SPYL", "PPFB", "SXRM", "SXRS")
    alineados = _alinear(precios_ucits, simbolos)
    pesos = serie_pesos_e1(alineados)
    retorno_sesiones = alineados / alineados.shift(LOOKBACK_SESIONES) - 1
    retorno_mensual = alineados.resample("ME").last()
    retorno_mensual = retorno_mensual / retorno_mensual.shift(12) - 1
    # El 30-04-2025 SXRS lleva doce meses de cierres mensuales en negativo y,
    # a la vez, las 252 sesiones en positivo. Manda la cuenta del backtest.
    momento = pd.Timestamp(date(2025, 4, 30))
    assert float(retorno_sesiones.at[momento, "SXRS"]) > 0
    assert float(retorno_mensual.at[momento, "SXRS"]) < 0
    assert float(pesos.at[momento, "SXRS"]) > 0


def _assert_limites(pesos: pd.DataFrame) -> None:
    assert (pesos >= -1e-12).all().all()
    assert (pesos <= TOPE_POR_ACTIVO + 1e-12).all().all()
    assert (pesos.sum(axis=1) <= 1 + 1e-9).all()
    calendario = CalendarioXetra()
    fines = [marca for marca in pesos.index if calendario.es_ultimo_habil_del_mes(marca.date())]
    assert fines, "el CSV debería cubrir algún fin de mes con señal"
    assert (pesos.loc[fines] <= TOPE_POR_ACTIVO + 1e-12).all().all()


def _assert_fechas_de_muestra(pesos: pd.DataFrame) -> None:
    for fecha in FECHAS_MUESTRA:
        momento = pd.Timestamp(fecha)
        assert momento in pesos.index
        fila = pesos.loc[momento]
        assert (fila >= -1e-12).all()
        assert (fila <= TOPE_POR_ACTIVO + 1e-12).all()
        assert fila.sum() <= 1 + 1e-9
        assert fila.sum() > 0
