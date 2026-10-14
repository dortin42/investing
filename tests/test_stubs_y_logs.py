import json
import logging
import socket
import sys
from datetime import date
from pathlib import Path

import pytest

from investing.contratos import DecisionRiesgo, VeredictoRiesgo
from investing.data.ibkr_historico import ProveedorHistoricoIBKR
from investing.execution.ejecutor import EjecutorIBKR, OrdenVetada
from investing.log import configurar_logging, evento
from investing.risk.control import ControlRiesgoNoImplementado
from tests.test_flujo import _cuenta


def test_importar_el_paquete_no_carga_ib_async():
    sys.modules.pop("ib_async", None)
    import investing.cli
    import investing.data.ibkr_historico
    import investing.execution.ejecutor
    import investing.flujo

    assert investing.flujo and investing.cli
    assert "ib_async" not in sys.modules


def test_el_codigo_no_importa_el_cliente_de_ibkr():
    raiz = Path(__file__).resolve().parents[1] / "src"
    for path in raiz.rglob("*.py"):
        texto = path.read_text(encoding="utf-8")
        assert "import ib_async" not in texto
        assert "from ib_async" not in texto
        assert "ib_insync" not in texto


def test_los_stubs_no_abren_socket(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("esta PR no puede abrir un socket")

    monkeypatch.setattr(socket, "create_connection", prohibido)
    monkeypatch.setattr(socket.socket, "connect", prohibido)
    ProveedorHistoricoIBKR()
    EjecutorIBKR()
    ControlRiesgoNoImplementado()
    with pytest.raises(NotImplementedError, match="TODO \\(Ejecución\\)"):
        ProveedorHistoricoIBKR().cierres(["SPYL"], date(2024, 1, 1), date(2024, 6, 1))
    veredicto = VeredictoRiesgo(DecisionRiesgo.PERMITIR, {"SPYL": 0.1}, ())
    with pytest.raises(NotImplementedError, match="TODO \\(Ejecución\\)"):
        EjecutorIBKR().ejecutar(_cuenta(), veredicto, date(2025, 1, 2))
    with pytest.raises(OrdenVetada):
        EjecutorIBKR().ejecutar(
            _cuenta(),
            VeredictoRiesgo(DecisionRiesgo.VETAR, {}, ("veto",)),
            date(2025, 1, 2),
        )


def test_log_json(capsys):
    configurar_logging()
    evento(logging.getLogger("investing.prueba"), "senal_cruda", cuenta="cuenta_3k", peso=0.4)
    linea = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert linea["mensaje"] == "senal_cruda"
    assert linea["nivel"] == "INFO"
    assert linea["campos"]["cuenta"] == "cuenta_3k"
    assert linea["campos"]["peso"] == 0.4
