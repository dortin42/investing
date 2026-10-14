from pathlib import Path

from investing.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_muestra_la_senal_del_cierre_de_diciembre_y_no_conecta(capsys):
    codigo = main(
        [
            "--config",
            str(ROOT / "config" / "cuentas.ejemplo.yaml"),
            "--csv",
            str(ROOT / "data" / "ucits_eur.csv"),
            "--cuenta",
            "cuenta_10k",
            "--fecha",
            "2025-12-30",
        ]
    )
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "Cuenta: cuenta_10k (10000 EUR)" in salida
    assert "2026-01-02" in salida
    assert "SPYL     21.68 %" in salida
    assert "PPFB     13.68 %" in salida
    assert "SXRM     40.00 %" in salida
    assert "SXRS     20.42 %" in salida
    assert "caja      4.21 %" in salida
    assert "No se ha conectado a IBKR" in salida


def test_cli_de_la_cuenta_3k_topa_spyl_en_el_mismo_cierre(capsys):
    codigo = main(
        [
            "--config",
            str(ROOT / "config" / "cuentas.ejemplo.yaml"),
            "--csv",
            str(ROOT / "data" / "ucits_eur.csv"),
            "--cuenta",
            "cuenta_3k",
            "--fecha",
            "2025-12-30",
        ]
    )
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "SPYL     40.00 %" in salida
    assert "PPFB     27.37 %" in salida
    assert "SXRM" not in salida


def test_cli_ciclo_se_detiene_en_el_stub_de_riesgo(capsys):
    codigo = main(
        [
            "--config",
            str(ROOT / "config" / "cuentas.ejemplo.yaml"),
            "--csv",
            str(ROOT / "data" / "ucits_eur.csv"),
            "--cuenta",
            "cuenta_3k",
            "--fecha",
            "2025-12-30",
            "--ciclo",
        ]
    )
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "TODO (Riesgo)" in salida
    assert "Ciclo detenido antes de enviar órdenes." in salida
