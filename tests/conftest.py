from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSV_UCITS = ROOT / "data" / "ucits_eur.csv"
CONFIG_EJEMPLO = ROOT / "config" / "cuentas.ejemplo.yaml"


@pytest.fixture(scope="session")
def precios_ucits():
    from investing.data.csv_proveedor import ProveedorCSV

    return ProveedorCSV(CSV_UCITS).cierres(("SPYL", "PPFB", "SXRM", "SXRS"))
