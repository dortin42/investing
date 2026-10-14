from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from investing.data.csv_proveedor import ProveedorCSV

CSV_UCITS = Path(__file__).resolve().parents[1] / "data" / "ucits_eur.csv"


def test_el_csv_normaliza_los_tickers_de_yahoo_y_recorta_el_futuro():
    proveedor = ProveedorCSV(CSV_UCITS)
    marco = proveedor.cierres(["SPYL", "PPFB"], inicio=date(2024, 1, 1), fin=date(2024, 1, 31))
    assert list(marco.columns) == ["SPYL", "PPFB"]
    assert marco.index.min() >= pd.Timestamp("2024-01-01")
    assert marco.index.max() <= pd.Timestamp("2024-01-31")
    assert marco["SPYL"].notna().any()
    assert marco.index.is_monotonic_increasing


def test_fin_no_incluye_la_sesion_siguiente():
    marco = ProveedorCSV(CSV_UCITS).cierres(["SXRM"], fin=date(2024, 1, 31))
    assert marco.index.max() <= pd.Timestamp("2024-01-31")
    assert pd.Timestamp("2024-02-01") not in marco.index


def test_simbolo_ausente():
    with pytest.raises(KeyError, match="NO_EXISTE"):
        ProveedorCSV(CSV_UCITS).cierres(["NO_EXISTE"])
