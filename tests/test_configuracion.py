from pathlib import Path

import pytest

from investing.configuracion import cargar_configuracion, construir_estrategias
from investing.universo import UNIVERSO_10K, UNIVERSO_3K

CONFIG_EJEMPLO = Path(__file__).resolve().parents[1] / "config" / "cuentas.ejemplo.yaml"


def test_ejemplo_de_cuentas_3k_y_10k():
    config = cargar_configuracion(CONFIG_EJEMPLO)
    cuenta_3k = config.cuenta("cuenta_3k")
    cuenta_10k = config.cuenta("cuenta_10k")
    assert cuenta_3k.capital_eur == 3000
    assert cuenta_10k.capital_eur == 10000
    assert cuenta_3k.estrategias[0].universo == UNIVERSO_3K
    assert cuenta_10k.estrategias[0].universo == UNIVERSO_10K
    assert cuenta_3k.estrategias[0].presupuesto_riesgo == 1.0
    assert cuenta_10k.estrategias[0].presupuesto_riesgo == 1.0
    estrategias_3k = construir_estrategias(cuenta_3k)
    estrategias_10k = construir_estrategias(cuenta_10k)
    assert estrategias_3k[0].universo == UNIVERSO_3K
    assert estrategias_10k[0].universo == UNIVERSO_10K


def test_no_se_pueden_cambiar_los_parametros_desde_el_yaml(tmp_path: Path):
    ruta = tmp_path / "cuentas.yaml"
    ruta.write_text(
        """
divisa: EUR
cuentas:
  cuenta_3k:
    capital_eur: 3000
    estrategias:
      - id: E1
        tipo: e1_tsmom
        universo: [SPYL, PPFB]
        presupuesto_riesgo: 1.0
        parametros:
          sigma_objetivo: 0.15
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="parámetros"):
        cargar_configuracion(ruta)


def test_rechaza_un_simbolo_que_no_esta_en_el_universo(tmp_path: Path):
    ruta = tmp_path / "cuentas.yaml"
    ruta.write_text(
        """
divisa: EUR
cuentas:
  cuenta_3k:
    capital_eur: 3000
    estrategias:
      - id: E1
        tipo: e1_tsmom
        universo: [SPYL, BTC]
        presupuesto_riesgo: 1.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="universo"):
        cargar_configuracion(ruta)
