"""Cálculo de la señal E1 desde un CSV. No conecta con IBKR."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from investing.calendario import CalendarioXetra, proximo_cierre_de_senal
from investing.configuracion import cargar_configuracion, construir_estrategias
from investing.data.csv_proveedor import ProveedorCSV
from investing.execution.ejecutor import EjecutorIBKR
from investing.flujo import EstadoCiclo, ejecutar_ciclo
from investing.log import configurar_logging
from investing.risk.control import ControlRiesgoNoImplementado
from investing.strategies.e1_tsmom import E1TSMOM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m investing",
        description=(
            "Calcula la señal E1 (TSMOM) de una cuenta a partir de un CSV de cierres. "
            "No abre TWS y no envía órdenes."
        ),
    )
    parser.add_argument(
        "--config",
        default="config/cuentas.ejemplo.yaml",
        help="YAML de cuentas (por defecto config/cuentas.ejemplo.yaml)",
    )
    parser.add_argument("--csv", required=True, help="CSV de cierres en EUR, con columnas Yahoo o símbolos")
    parser.add_argument("--cuenta", required=True, help="Id de cuenta dentro del YAML, por ejemplo cuenta_3k")
    parser.add_argument("--fecha", help="Cierre de la señal, YYYY-MM-DD. Por defecto el último del CSV")
    parser.add_argument(
        "--ciclo",
        action="store_true",
        help="Si la fecha es fin de mes en Xetra, recorre riesgo y ejecutor (ambos stubs en esta PR)",
    )
    args = parser.parse_args(argv)
    configurar_logging()

    try:
        configuracion = cargar_configuracion(args.config)
        cuenta = configuracion.cuenta(args.cuenta)
        precios = ProveedorCSV(args.csv).cierres(cuenta.simbolos())
    except (OSError, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    try:
        estrategias = construir_estrategias(cuenta)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return 1
    if precios.empty:
        print("El CSV no tiene cierres para el universo de la cuenta.", file=sys.stderr)
        return 1
    fecha = _parsear_fecha(args.fecha) if args.fecha else precios.index[-1].date()

    calendario = CalendarioXetra()
    es_rebalanceo = calendario.es_ultimo_habil_del_mes(fecha)
    print(f"Cuenta: {cuenta.id} ({cuenta.capital_eur:.0f} EUR)")
    print(f"Cierre: {fecha.isoformat()}")
    if es_rebalanceo:
        ejecucion = calendario.siguiente_habil(fecha)
        print(f"Día de rebalanceo mensual en Xetra. La orden límite iría el {ejecucion.isoformat()}.")
    else:
        proxima = proximo_cierre_de_senal(calendario, fecha)
        print(
            "Este cierre no es el último día hábil del mes en Xetra. "
            f"Próxima señal mensual: {proxima.isoformat()}."
        )

    try:
        for estrategia in estrategias:
            if not isinstance(estrategia, E1TSMOM):
                continue
            senal = estrategia.senal(precios, fecha)
            print(f"\n{estrategia.id} ({', '.join(estrategia.universo)}) señal cruda")
            print(_formatear_pesos(senal.pesos))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print("\nNo se ha conectado a IBKR y no se ha enviado ninguna orden.")
    if not args.ciclo:
        return 0
    if not es_rebalanceo:
        print("Sin ciclo de órdenes: no es día de rebalanceo.")
        return 0

    try:
        resultado = ejecutar_ciclo(
            cuenta=cuenta,
            estrategias=estrategias,
            precios=precios,
            fecha=fecha,
            riesgo=ControlRiesgoNoImplementado(),
            ejecutor=EjecutorIBKR(),
        )
    except NotImplementedError as exc:
        print(f"\n{exc}")
        print("Ciclo detenido antes de enviar órdenes.")
        return 0

    if resultado.estado is EstadoCiclo.VETADO:
        print("El control de riesgo ha vetado el rebalanceo.")
        return 0
    print(f"Ciclo en estado {resultado.estado.value}.")
    return 0


def _parsear_fecha(texto: str) -> date:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"fecha no válida ({texto!r}); usa YYYY-MM-DD") from exc


def _formatear_pesos(pesos) -> str:
    lineas = [f"  {simbolo:<6} {peso * 100:7.2f} %" for simbolo, peso in pesos.items()]
    caja = (1.0 - sum(pesos.values())) * 100
    lineas.append(f"  {'caja':<6} {caja:7.2f} %")
    return "\n".join(lineas)
