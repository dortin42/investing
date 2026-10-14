# gtaa-bot — GTAA momentum sobre UCITS reales en Interactive Brokers

Bot en Python puro (sin QuantConnect) que ejecuta la estrategia GTAA momentum
validada en backtest, directamente sobre los ETFs UCITS que un residente en
España sí puede comprar. QC queda solo como laboratorio de backtesting.

Estrategia: filtro SMA200 + momentum absoluto 6m > 0, top 4 por momentum,
pesos iguales × leverage 1.2, rebalanceo mensual con banda del 25%.

## Setup (una vez)

1. **IB**: abre TWS (o IB Gateway) con tu cuenta **paper** y activa la API:
   File → Global Configuration → API → Settings → *Enable ActiveX and Socket
   Clients* (y desmarca *Read-Only API*). Puerto paper de TWS: 7497.
2. **Python**:

```powershell
cd C:\Users\Daniel\Projects\gtaa-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. **Verificar tickers** (imprescindible — varios en `config.py` están
   marcados VERIFICAR):

```powershell
python run_rebalance.py --check
```

Revisa que cada línea sea el ETF que quieres (nombre largo, bolsa, divisa).
Si alguno no resuelve o es otra cosa, corrige `config.py` y repite. Criterio:
clase de acumulación, en EUR si existe, y precio por participación < ~200 €
(con 3.000 € y 4 slots, cada slot son ~900 €; una participación de 600 € no
cabe bien). El propio bot avisa si una clase es demasiado cara para tu slot.

## Uso

```powershell
python run_rebalance.py             # dry-run: muestra señales y órdenes, no opera
python run_rebalance.py --execute   # opera de verdad (en paper si el puerto es 7497)
```

El dry-run imprime la tabla de señales (momentum, filtro, peso objetivo vs
actual) y las órdenes que enviaría. Ejecuta siempre un dry-run antes del
primer `--execute` del mes si quieres supervisar.

## Automatización 100%

**Programador de tareas de Windows** (corre a diario a las 10:00; el flag
`--scheduled` hace que solo actúe el primer día hábil del mes, con Xetra ya
abierto):

```powershell
schtasks /create /tn "GTAA rebalanceo" /sc daily /st 10:00 /tr "C:\Users\Daniel\Projects\gtaa-bot\.venv\Scripts\python.exe C:\Users\Daniel\Projects\gtaa-bot\run_rebalance.py --execute --scheduled"
```

Niveles reales de automatización, de menos a más:

| Nivel | Qué hace falta | Intervención tuya |
|---|---|---|
| PC propio + TWS abierto | Lo de arriba | Tener el PC encendido y TWS logueado el día 1 |
| VPS + IB Gateway + IBC | VPS Windows/Linux (~5 €/mes, Hetzner) con [gnzsnz/ib-gateway](https://github.com/gnzsnz/ib-gateway-docker) en Docker: login y reinicios automáticos | ~0 en paper; en real, algún toque de 2FA |
| Cuenta real | Lo mismo + 2FA de IBKR Mobile | IB fuerza reautenticación periódica; con IBC queda en un toque de móvil cada 1-2 semanas |

El "100%" honesto: en **paper es 100% desatendido** con el VPS. En **real es
~99%**: IB exige 2FA y el gateway reinicia semanalmente; IBC lo gestiona casi
todo pero de vez en cuando tendrás que aprobar un login en el móvil. Con
rebalanceo mensual, incluso el nivel 1 (tu PC) es perfectamente viable.

Notificaciones por Telegram opcionales: ver `gtaa/notify.py` (5 min de setup,
te llega el resumen de cada rebalanceo al móvil).

## Detalles que importan

- **Datos con fallback automático**: primero intenta los históricos del
  propio IB (`ADJUSTED_LAST`); si la cuenta no tiene permisos de datos para
  bolsas europeas (error 162, es lo normal sin suscripciones), cae a la API
  de gráficos de Yahoo (`gtaa/data.py`, cliente propio sin yfinance — que en
  esta máquina no funciona porque el firewall bloquea `fc.yahoo.com`). Los
  precios de referencia para las órdenes límite usan el último cierre si no
  hay snapshot en vivo. La cabecera del informe siempre dice qué fuente usó.
- Las señales se calculan sobre las clases UCITS reales en EUR: el momentum
  incluye el efecto divisa — que es lo que de verdad vive tu cuenta. Por eso
  los números diferirán ligeramente del backtest con proxies US.
- `test_signals.py` muestra las señales del día sin abrir TWS (solo Yahoo).
- **Leverage 1.2x** = pedir prestados ~600 € a IB al tipo de margen en EUR
  (~BM+1,5%). Es un coste de ~15-20 €/año a este tamaño: asumible, pero existe.
- **Órdenes límite marketables** (±0,2%): cruzan el spread pero con protección;
  en LSE/Xetra los spreads de ETFs pueden ser más anchos que en NYSE.
- **Banda del 25% + mínimo de 50 €/orden**: un mes normal genera 0-2 órdenes.
- **Datos en diferido de IB** (15-20 min): suficiente para esto, no pagues
  suscripciones de tiempo real.
- El bot **no decide nada intradía**: es un ejecutor mensual. Si un mes no se
  ejecuta (festivo, PC apagado), lo corres a mano al día siguiente y ya.

## Plan de puesta en marcha

1. `--check` hasta que los 9 contratos resuelvan bien.
2. 2-3 meses en **paper** (puerto 7497) comparando cada rebalanceo con el log
   del algoritmo de QC (deben elegir activos parecidos; no idénticos por la divisa).
3. Si cuadra: cambiar el puerto a 7496 (TWS real) y primera ejecución real
   supervisada con dry-run previo.
