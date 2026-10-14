# ESTADO del proyecto gtaa-bot — traspaso para futuros chats

Actualizado: 15-08-2026. Este documento contiene todo el contexto para
retomar el trabajo del bot en un chat nuevo sin releer conversaciones.

## Qué es esto

Bot en Python puro que ejecuta la estrategia **GTAA momentum** directamente
contra Interactive Brokers sobre **ETFs UCITS reales** (los que un residente
en España puede comprar; PRIIPs impide los ETFs US). Sustituye la ejecución
vía QuantConnect: QC queda **solo como laboratorio de backtests** (allí se
validó la estrategia con proxies US, IS/OOS, leverage 1.0x vs 1.4x).

Estrategia: filtro SMA200 + momentum absoluto 6m (126d) > 0 → top 4 por
momentum → pesos iguales × leverage 1.2 → rebalanceo mensual (primer día
hábil) con banda del 25% y mínimo 50 €/orden. Slots fijos: lo que no pasa
filtros queda en cash (defensa en bear markets).

Contexto del usuario: cuenta real IB con ~3.000 €, cuenta margen (mínimo
$2.000 cumplido), residente en Tarragona, España. Leverage 1.2x = ~600 €
prestados al tipo de margen EUR de IB.

## Estado actual: FUNCIONA en dry-run contra cuenta paper

Verificado el 15-08-2026 con TWS paper (puerto 7497, API activada):

- `--check`: los 10 contratos del universo resuelven en IB, todos en EUR
  (managed futures DBMFE incluido desde el 15-08 por la noche).
- Dry-run completo: señales + NetLiq + plan de órdenes correcto.
- Señales del día del test: ALZA en S&P (+17,2%), Nasdaq (+25,0%),
  ex-US (+9,8%), EM (+13,5%), tesoro 7-10 (+1,3%), commodities (+20,1%),
  REITs (+5,7%); fuera: tesoro 20+ (−1,9%) y oro (−9,0%).
  Top 4 elegido: Nasdaq, commodities, S&P, emergentes (30% cada uno).
- PENDIENTE: primer `--execute` en paper (el test fue en sábado, mercado
  cerrado; las órdenes límite DAY se habrían quedado colgadas hasta el lunes).

## Universo verificado contra IB (todo EUR, sin FX)

| Activo | IB symbol | Bolsa IB | Yahoo (señales) | Nombre en IB |
|---|---|---|---|---|
| S&P 500 | VUAA | IBIS2 | VUAA.DE | VANG S&P500 USDA (~130 €) |
| Nasdaq 100 | EQAC | IBIS2 | **EQAC.MI** | INVESCO NASDAQ 100 ACC (~446 €) |
| Desarrollados ex-US | EXUS | IBIS2 | EXUS.DE | X MSCI WORLD EX USA 1C (~41 €) |
| Emergentes | XMME | IBIS2 | XMME.DE | X MSCI EM 1C (~81 €) |
| Tesoro US 7-10a | BTMA | IBIS2 | BTMA.AS | ISHARES USD TREASURY 7-10Y (~147 €) |
| Tesoro US 20+a | IS04 | IBIS2 | IS04.DE | ISHARES USD TRES 20PLUS YR (~2,7 €) |
| Oro | 4GLD | IBIS | 4GLD.DE | XETRA-GOLD (~122 €) |
| Materias primas | EXXY | IBIS | EXXY.DE | ISH DIV COMDTY SWAP (~34 €) |
| REITs global | IWDP | IBIS2 | IWDP.AS | ISHARES DVL MKT PROPERTY YLD (~23 €) |
| Managed futures | DBMFE | SBF (París) | DBMFE.PA | IMGP DBI MNG FUT UCITS (~124 €) |

Nota managed futures: la clase de Xetra (MFEH) solo tenía 62 días de datos
(listada hace poco), insuficiente para SMA200; por eso se usa la de París
(DBMFE, 331 días). La clase LSE (DBMF) cotiza en USD: descartada por FX.

## Trampas descubiertas (no volver a tropezar)

1. **El segmento de ETFs de Xetra en IB es `IBIS2`, no `IBIS`** (IBIS solo
   para acciones y ETCs como 4GLD/EXXY). Con IBIS los ETFs dan error 200.
2. **La cuenta (paper) no tiene permisos de datos de mercado europeos**:
   `reqHistoricalData` y snapshots dan errores 162/354. El bot cae
   automáticamente a la API de gráficos de Yahoo y usa el último cierre como
   precio de referencia (las órdenes límite ±0,2% protegen). La cabecera del
   informe dice la fuente usada. Si algún día se paga la suscripción de
   datos (~2-3 €/mes por bolsa), IB pasa a ser la fuente primaria solo.
3. **yfinance NO funciona en esta máquina**: el firewall (Portmaster)
   bloquea `fc.yahoo.com` (host de cookies, está en listas de ad-block).
   Por eso `gtaa/data.py` es un cliente propio contra
   `query1.finance.yahoo.com/v8/finance/chart/` que sí responde. yfinance
   se eliminó de requirements.
4. **Tickers Yahoo**: EQAC no existe como EQAC.DE; usar `EQAC.MI` (Milán).
5. **Python del sistema no existe**; se usa el entorno conda `gtaa`
   (Anaconda en `C:\Users\Daniel\anaconda3`, sin conda en PATH):
   `C:\Users\Daniel\anaconda3\envs\gtaa\python.exe`.
6. Precio por participación vs slot (~900 € con 3k×1.2/4): EQAC a ~446 €
   solo permite 2 participaciones (granularidad gruesa); IS04 a 2,66 € va
   finísimo. El bot avisa si una participación no cabe en el slot.

## Comandos

```powershell
cd C:\Users\Daniel\Projects\gtaa-bot
$py = "C:\Users\Daniel\anaconda3\envs\gtaa\python.exe"
& $py run_rebalance.py --check      # verificar contratos en IB
& $py run_rebalance.py              # dry-run (no opera)
& $py run_rebalance.py --execute    # operar (paper si puerto 7497)
& $py test_signals.py               # señales sin TWS (solo Yahoo)
& $py find_contracts.py TICKER      # buscar contratos en IB
```

Programador de tareas (diario; solo actúa el primer día hábil del mes):

```powershell
schtasks /create /tn "GTAA rebalanceo" /sc daily /st 10:00 /tr "C:\Users\Daniel\anaconda3\envs\gtaa\python.exe C:\Users\Daniel\Projects\gtaa-bot\run_rebalance.py --execute --scheduled"
```

## PnL de la cuenta virtual (03-10-2026)

El NetLiq de paper (~1M) no sirve para medir el bot. `gtaa/ledger.py` lleva un
libro propio en `logs/ledger.json` (base `CAPITAL_EUR`, inicio `TRACK_START`):
- `run_rebalance.py --execute` apunta las ejecuciones de IB con precio y
  comisión reales justo tras los fills (IB las olvida al reiniciar).
- `daily_signals.py --port 4002` (cron 9:00) cuadra el libro con las
  posiciones de IB: compras que falten al avgCost de IB, ventas que falten al
  último cierre (marcadas "estimado"). Luego manda patrimonio, PnL, drawdown,
  realizado/no realizado, comisiones, cash virtual (negativo = margen por el
  1.2x), exposición, VUAA como referencia y detalle por posición.
- Las posiciones del 17-08 entraron con el avgCost de IB y fecha 17-08.
- `gtaa/data.py` rellena la última barra vacía de Yahoo con
  `meta.regularMarketPrice`; antes las señales iban un día atrasadas.

## Plan pendiente

1. Primer `--execute` en paper un día de mercado abierto (lun-vie,
   9:00-17:30) y revisar fills en TWS.
2. 2-3 meses en paper comparando cada rebalanceo con el algoritmo de QC
   (deben elegir activos parecidos; no idénticos por el efecto divisa EUR).
3. Paso a real: cambiar `IB_PORT` a 7496 en `config.py`, dry-run supervisado,
   primera ejecución real. NUNCA subir leverage por encima de 1.4.
4. Opcional: Telegram (`gtaa/notify.py`, variables TELEGRAM_BOT_TOKEN y
   TELEGRAM_CHAT_ID), VPS con docker gnzsnz/ib-gateway para desatenderlo,
   managed futures UCITS al universo.

## Contexto de decisiones (por qué es así)

- **Por qué no QC en live**: QC no puede comprar UCITS europeos; con IB
  directo no hacen falta proxies ni réplica manual.
- **Por qué todo en EUR**: comprar activos USD/GBP con cash EUR en cuenta
  margen crea préstamo en esa divisa (intereses ~5% en USD).
- **Por qué leverage 1.2 y no 2**: Kelly con error de estimación,
  volatility drag y el riesgo de liquidación forzosa; 1.2-1.4 es la zona
  práctica segura discutida y validada en backtests (1.4x OOS mejoró CAGR
  con MaxDD contenido).
- **Por qué banda 25% + mínimo 50 €**: con ~1 €/orden en IB y cuenta de 3k,
  sin banda las comisiones se comen decenas de puntos básicos al año.
- El backtest de referencia vive en QC (clase `GTAAMomentum3KIB` y
  anteriores); los JSON de backtests están en `C:\Users\Daniel\Downloads`
  (p. ej. `Determined Violet Shark.json` = OOS 1.0x,
  `Upgraded Magenta Gull.json` = OOS 1.4x).

## Sleeve crypto (nuevo, 24-08-2026)

No es parte del GTAA. Cuenta aparte mental de ~3.000 EUR en IB.

- Vehiculo: **spot IB** (BTC/ETH/SOL via Zero Hash EEA). No MBT: 0.10 BTC
  pide ~3.3-4.2k USD de margen, no cabe con 3k. MSL (25 SOL) igual.
  MET (0.10 ETH) si cabe pero solo cubre Ether.
- Estrategia: mismas reglas que el GTAA (SMA200 + mom 126d > 0, top 1,
  cash si nadie pasa, mensual, leverage **1.0**).
- Live recomendado con 3k: universo **solo BTC**. Los 3 coins en top-1
  concentran 100% en SOL tras un rebote; el CAGR 2021-26 esta inflado por
  SOL 2021. OOS 2024+ BTC-only ≈ BTC hold con menos drawdown.
- Lab: `crypto/qc_CryptoDualMom.py` (pegar en QC, Coinbase).
  Local: `python -m crypto.backtest`.
- Posicion a 24-08-2026: el ultimo rebalanceo (1-ago) dejo **cash**.
  El squeeze de mediados de agosto no se compra hasta el 1-sep.
- Long/short medido el 24-08: BTC always-in SMA200 gana +28% en 2022 y
  **-2.5% CAGR en 2024-26**. 3 coins L/S: +79% en 2022 y **-44% OOS**
  (3000 -> 647 EUR). Spot IB no shorta; haria falta BFF/MBT. No es el
  default. El lado corto del stack ya esta en DBMFE del GTAA.
