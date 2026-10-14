from datetime import date

import pandas as pd

from investing.calendario import CalendarioEEUU, CalendarioXetra, domingo_de_pascua
from tests.referencia_bt import month_end_mask


def test_pascua_conocida():
    assert domingo_de_pascua(2024) == date(2024, 3, 31)
    assert domingo_de_pascua(2025) == date(2025, 4, 20)
    assert domingo_de_pascua(2026) == date(2026, 4, 5)


def test_xetra_2026_coincide_con_el_calendario_de_deutsche_borse():
    calendario = CalendarioXetra()
    cerrados = [
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 12, 24),
        date(2026, 12, 25),
        date(2026, 12, 31),
    ]
    for festivo in cerrados:
        assert not calendario.es_habil(festivo)
    # Ascensión y Lunes de Pentecostés de 2026 son sesión en Xetra.
    assert calendario.es_habil(date(2026, 5, 14))
    assert calendario.es_habil(date(2026, 5, 25))
    # 26 de diciembre de 2026 cae en sábado; en 2025 cae en viernes y no hay sesión.
    assert not calendario.es_habil(date(2025, 12, 26))


def test_fin_de_mes_xetra_en_diciembre_y_la_orden_al_dia_siguiente():
    calendario = CalendarioXetra()
    assert calendario.es_ultimo_habil_del_mes(date(2024, 12, 30))
    assert not calendario.es_ultimo_habil_del_mes(date(2024, 12, 31))
    assert calendario.siguiente_habil(date(2024, 12, 30)) == date(2025, 1, 2)
    assert calendario.es_ultimo_habil_del_mes(date(2026, 12, 30))
    assert calendario.siguiente_habil(date(2026, 12, 23)) == date(2026, 12, 28)


def test_mayo_2021_xetra_senala_el_31_y_el_backtest_usa_el_calendario_de_eeuu():
    xetra = CalendarioXetra()
    eeuu = CalendarioEEUU()
    assert not xetra.es_ultimo_habil_del_mes(date(2021, 5, 28))
    assert xetra.es_ultimo_habil_del_mes(date(2021, 5, 31))
    # Memorial Day: el calendario federal salta del viernes 28 al martes 1 de junio.
    assert eeuu.siguiente_habil(date(2021, 5, 28)) == date(2021, 6, 1)
    assert eeuu.es_ultimo_habil_del_mes(date(2021, 5, 28))
    assert not eeuu.es_habil(date(2021, 5, 31))


def test_mascara_eeuu_repite_la_del_backtest(precios_ucits):
    indice = pd.DatetimeIndex(precios_ucits.dropna(how="any").index)
    nuestra = CalendarioEEUU().mascara_fin_de_mes(indice)
    pd.testing.assert_series_equal(nuestra, month_end_mask(indice), check_names=False)
