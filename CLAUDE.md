# Loyalty Ecosystem — guía para Claude y para el equipo

Dashboard de reporting de Loyalty (Despegar): **P&L Contable** (Baseline vs Goal) +
**Métricas de Negocio por programa** (acumulación / redención / breakage) por país.

```
Datalake (ODBC) ─┐
Config Sheet    ─┼─► loyalty_sync.py ─► JSON en Drive ─► landing GAS (webapp) ─► navegador
                 │      (agendado)      folder 1yCPp6…
Inputs_Planning_PnL (otro repo) ─► baseline/budget/forecast.json ─► folder 1XqQPL…
```

## Al iniciar una sesión — identificar el perfil

Si la persona no se presentó y va a tocar algo, preguntá **qué va a hacer**:

| Perfil | Hace | Setup |
|---|---|---|
| **Analista** | Editar inputs de negocio (planilla) · cambios de dashboard/queries por PR | Acceso a repo + planilla. Nada instalado. |
| **Analista + query** | Además valida cambios de query con `--dry-run` | + datalake creds + DSN ODBC + libs Python (sin Drive) |
| **Operador** | Corre la sync real (sube a Drive). En la práctica: **la máquina del Task Scheduler + Diego de backup.** | Setup completo (+ Drive) — `SETUP.md` |

La mayoría es Analista. Para setup: skill **`/configurar-entorno`**.

## Los dos tipos de cambio

| Si el cambio es en… | Flujo |
|---|---|
| **Inputs de negocio** (breakage esperado, mapeo de programas) | Editar la planilla **"Loyalty Ecosystem - Config"** en Drive. El sync la lee en la próxima corrida. NO tocar `breakage_esperado.csv` / `Diccionario.xlsx` (son solo fallback). |
| **Precios de facturación Cobrand/Partners + FX** | Editar **`Input_Precios.xlsx`** en OneDrive (Control de Gestión). El sync lo lee en la próxima corrida y recalcula `acum_usd_precio`. Después actualizar la copia del repo (`cp` + commit) para mantener el fallback al día. |
| **Dashboard / GAS** (`dashboard.html`, `Código.js`) | branch → editar → commit → push → PR. **El deploy es manual** (igual que B2B_Ecosystem): `clasp push -f` + `clasp deploy -i AKfycbzyHV8nz…` o el comando `/publicar`. La GitHub Action `deploy-gas.yml` quedó **solo `workflow_dispatch`** (no corre en cada push) porque el secret `CLASP_CREDENTIALS` nunca se cargó. |
| **Pipeline** (`loyalty_sync.py`, queries SQL) | branch → editar → validar con **`python loyalty_sync.py --dry-run`** (corre las queries, arma los JSON en `_out/`, NO sube a Drive ni lee la planilla — solo hace falta datalake + DSN, **no** credenciales de Drive) → PR. El operador / scheduler hace la corrida real. |
| **Manual** (`Manual_Loyalty_Ecosystem/manual.html`) | Editar → `clasp push -f` + `clasp deploy -i <id>` **desde `Manual_Loyalty_Ecosystem/`** (subcarpeta con su propio `.clasp.json`, scriptId `1SrytXvn5f44…`). Al cambiar el proceso/IDs/queries de arriba, actualizar también el manual. |

## Archivos

| Archivo | Qué es |
|---|---|
| `loyalty_sync.py` | Pipeline: datalake → agrega por mes+país+partner+point_type → sube 10 JSON a Drive |
| `Código.js` | Backend GAS: sirve los JSON crudos + filtra loyalty del P&L (`_loyPnl`) |
| `dashboard.html` | SPA: pestaña **TOTAL** (suma de países) + una por país; P&L Contable (Baseline/Goal/Δ, selector Mes/Q/Half), Métricas por programa, Miembros del programa por tier, Club Despegar (AR) e iFood (BR) |
| `loyalty_miembros.json` | Snapshot del padrón activo (`clm_customers` status='A') por mes de `enrolment_date` × país × tier. Sin ventana de fecha (foto actual). Tier: mismo criterio que la query de breakage. |
| `loyalty_club_despegar.json` | Club Despegar (suscripción AR): 3 series por mes × plan (`serie`): **stock** (base activa acumulada — subs que HOY siguen `ACTIVE`, por mes de alta; monótona, survivorship), **alta** (created_at, confiable), **baja** (USER_CANCELLED+PENDING por updated_at — timing APROX, ver gotcha). Desde `data.raw.membertrip_subscription`. Se muestra **dentro** de la sección de programa "Club Despegar" (solapa Argentina + TOTAL). |
| `loyalty_ifood_enroll.json` | iFood enrolados (BR): altas por mes de `iFood enrol` (cross_cashback) y `Club iFood` (closed_loop_discount), desde `analytics.ifood_dim_users`. Se muestra **dentro** de la sección de programa "IFOOD" (solapa Brasil + TOTAL). |
| `breakage_esperado.csv` · `Diccionario.xlsx` | **Fallback** de la planilla de config. La fuente real es el Sheet. |
| `Input_Precios.xlsx` | Precios de facturación de **Cobrand / Partners** + FX mensual por moneda. Lo mantiene Control de Gestión en OneDrive; la copia del repo es fallback. `loyalty_sync.py` lo usa para `acum_usd_precio` (ver gotcha). Solapas: `Cobrand`, `Partners`, `FX_Currency`. |
| `auth_drive.py` | OAuth de Drive (necesita `credentials_drive.json`, que no está en el repo) |
| `setup_check.py` · `configurar_datalake.py` | Diagnóstico y carga de credenciales para operadores |
| `.github/workflows/deploy-gas.yml` | Deploy a Apps Script — **solo manual** (`workflow_dispatch`). Trigger `push` desactivado hasta que exista el secret `CLASP_CREDENTIALS`. |
| `SETUP.md` | Runbook operativo completo |

## Reglas que no romper

- **Nunca commitear** `token_drive.json`, `credentials_drive.json`, `envs/.env*`. Están gitignoreados.
- **`git push` no publica la landing GAS.** El deploy es manual: `clasp push -f` + `clasp deploy -i <id estable>` (o `/publicar`). Siempre verificar que el deploy corrió (`clasp deployments`).
- El **deployment estable** es `AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig`. `clasp push` solo actualiza HEAD; hay que `clasp deploy -i <ese id>` para que la webapp cambie.
- Los JSON en Drive se **sobreescriben** (no hay versiones).

## Gotchas (aprendidos)

- **`_out/` (carpeta de `--dry-run`) queda STALE y confunde análisis — no usarla como fuente de verdad.** Solo se escribe con `--dry-run`/`--no-upload` (nunca en una corrida real, que sube directo a Drive sin tocar `_out/`). El 08-sep esto causó 2 análisis erróneos en la misma sesión (un "hueco" de diccionario que en realidad ya estaba resuelto en el Sheet real, y un "gap" de clasificación que un subagente de auditoría reportó por la misma razón). Para analizar el estado REAL de producción, bajar los JSON directo de Drive (folder `1yCPp6…`, vía Drive API con `token_drive.json`) o correr el sync real, nunca confiar en archivos viejos de `_out/` sin chequear su fecha primero. Se borró la carpeta el 08-sep para evitar reincidencia; si reaparece por un `--dry-run` futuro, tratarla como descartable después de usarla.
- **Apps Script no lee blobs >50 MB.** Por eso `loyalty_sync.py` sube los JSON de acum/reden **agregados por mes** (no fila por fila). Si vuelven a crecer, la serie LY de los charts se cae a cero (`fyYears()` → NaN).
- **Auth de Drive = OAuth de usuario, sin service account (decisión 07-sep).** Mismo patrón que B2B (`Daily_Dashboard`, `Inputs_Planning_PnL`): `credentials_drive.json` (client compartido, no versionado) + `token_drive.json` personal vía `auth_drive.py`. `_build_drive_service()` NO tiene rama de service account. El refresh token no expira mientras la consent screen del proyecto GCP esté en modo "Internal" — verificar eso una vez (`docs/PENDIENTE-DIEGO.md` item 1). Si el sync agendado queda con datos viejos: `python auth_drive.py` de nuevo.
- **Pestaña TOTAL**: `dashboard.html` la trata como pseudo-país (`dataKey='total'`). Para acum/reden, `matchCountryCode`/`rowCountryKey` deciden si una fila entra (por `country_code` ISO, no por nombre — ver gotcha de abajo); para P&L/Club Despegar/Miembros (sin `country_code`) sigue siendo `matchCountryRow` por nombre. La suma es sobre `COUNTRY_DATAKEYS` (los 8 países), no "todo lo que haya" — así no se cuela un `Pais` agregado del P&L.
- **`matchCountryRow` (por nombre) vs `matchCountryCode` (por `country_code` ISO) — fix 07-sep.** Varios gráficos de Acumulación/Redención quedaban en blanco porque `row.country` (nombre completo) viene `'N/D'` para partners sin transacción de viaje asociada (welcome bonuses/subs), aun cuando `row.country_code` sí estaba resuelto. Los 4 call-sites sobre `acum_cy/ly`/`reden_cy/ly` (`filterCY`/`filterLY`, `monthlyMap`, `pasivoFlowMap`) migraron a `matchCountryCode`. Sigue habiendo casos sin arreglo posible por este medio: **Acciones Marketing (`FORTUNE`/`Mkt_App`)** no tiene país en el origen ni por nombre ni por código — dejado en blanco a propósito (decisión de Rosario), salvo que se agregue un fallback de país en `loyalty_sync.py` (ver `_ACUM_ER_COUNTRY_SQL` más abajo, que sí lo resuelve para acum, pendiente de aplicar el mismo criterio si hiciera falta en otro lado).
- **Diccionario (Sheet Config, pestaña `diccionario`) — 5 columnas, no 4** (`partner, point_type, concatenado, point_agrupado, seccion` — `SETUP.md` decía 4, desactualizado). `point_agrupado` es informal, no lo usa el código. `acum[concatenado]=seccion` se arma con **todas** las filas (con o sin partner); `reden[point_type]=seccion` solo con las filas **sin partner**. Regla de negocio confirmada (07-sep): cualquier partner con `point_type` exactamente `"Rewards & Benefits"` es **Puntos Manuales**, sin importar el partner — se implementa como una fila **sin partner** (bare fallback), no una por partner.
- **Miembros**: es un snapshot del padrón HOY. Las "altas" de meses viejos solo incluyen a los que siguen activos → sesgo de supervivencia (no es la serie histórica real de altas). El KPI de total sí es el padrón actual correcto. Mismo sesgo en Club Despegar (query filtra por estado actual + `rn=1`).
- **Club Despegar / iFood** usan catálogos nuevos del datalake (`data.raw.*`, `analytics.ifood_dim_users`) — no `data.lake.*`. Si el ODBC tira `errorCode member not found` al *conectar* (no al correr la query), es la VPN/driver, reintentar (`conectar()` ya reintenta 4×).
- **`membertrip_subscription.updated_at` está BULK-TOUCHED** (todos los ACTIVE actualizados ago-2026; cero bajas registradas dic25→may26, pico de 4k en jun26). NO usarlo para stock histórico ni timing real de bajas. Único timestamp confiable = `created_at`. Por eso el "stock por mes" del dashboard es la base activa acumulada (survivorship), no un snapshot real, y la tablita de bajas dice "fecha registrada (aprox.)".
- **iFood**: la query de Metabase (150076) arrancaba en 2026-01; el pipeline la bajó a 2025-01 para tener LY. `event_date` de `closed_loop_discount` es la fecha de alta de Club iFood (la query original solo tenía fecha para cross_cashback).
- **`points` vs `points_distribuidos`**: la query trae `SUM(puntosv2)` como `points`. El cierre de Loyalty usa `points_distribuidos` (~2-4% menos), que **falla vía ODBC** → el pipeline usa `points`. El SSP calculado difiere ~1% del cierre por esto. En el frontend, `getPts(row)` usa `points` directo (el fallback a `points_distribuidos` se eliminó porque nunca venía en los JSON).
- **Agregación con `abs()` por fila — solo redenciones.** `aggregate_reden` sigue sumando en valor absoluto por fila (preserva el criterio previo del dashboard). **`aggregate_acum` ya NO** (fix 07-sep): `_ACUM_SQL` tiene una rama de Cancelación que resta puntos (`cr.points * -1`) para netear contra el accrual; el `abs()` post-query anulaba esa resta y sobreestimaba cualquier partner/point_type con cancelaciones (`accrual + |cancel|` en vez de `accrual − cancel`) — confirmado contra el bajada real de cierre y su tabla dinámica (suma simple con signo, sin abs()). Afectaba sobre todo `DP`/`general` (Pasaporte D!, +157% en 2026) y `FORTUNE`/`FORTUNE`. `points` puede salir negativo a nivel de fila agregada (mes×país×partner×point_type) cuando la cancelación de ese grupo supera al accrual — es esperado, no es un bug. Ojo: `getPts()` en `dashboard.html` sigue haciendo `Math.abs()` (deliberado, es función compartida con redenciones) — un grupo con neto negativo se sigue viendo como un pequeño positivo en el navegador, en vez de negativo.
- **SSP / valor de acumulación**: `getAcumUsd = acum_usd_base · SSP_Facturación[país][mes]`, con `SSP_Facturación = SSP_Calculado · (1 − breakage_esperado)`. `SSP_Calculado` sale de las redenciones Pasaporte D!. El Excel de cierre tenía un **swap MX↔CO** que el pipeline ya corrige.
- **ODBC + `data.analytics.*`**: un `SELECT` directo de una columna **`DECIMAL` cruda** de esas tablas tira `errorCode member not found`. El workaround —que ya usan `_ACUM_SQL` y `_REDEN_SQL`— es envolver en `SUM(CAST(col AS DECIMAL(18,2)))` o similar; así las queries centrales SÍ leen numéricos de `data.analytics.bi_transactional_fact_*` sin problema. NO es "cualquier número de analytics falla".
- El P&L Contable NO sale del datalake — es `baseline_actuals+projections.json` / `budget.json` / `forecast.json` del repo **B2B_Ecosystem/Inputs_Planning_PnL**.
- **`_ACUM_ER_COUNTRY_SQL` / `apply_acum_er_country()` (fix 07-sep) — fallback de país para accruals `'ER'` sin reserva de viaje** (`FORTUNE`/`MISSIONS`: `comarch_accumulation_report.country`/`dsp_transaction_id` vienen `NULL`, así que el JOIN de `_ACUM_SQL` contra la reserva nunca les resuelve país). Resuelve vía `clm_transaction_id -> clm_transactions.account_id -> clm_customers.ext_country_program` (mismo campo que Breakage/Miembros), **en una query aparte** — meterlo dentro de `_ACUM_SQL` tira en Presto `"Number of stages (61) exceeds the allowed maximum (60)"` (esa query ya está en el límite de stages). Incluye también la cancelación (UNION ALL negado) para no reintroducir el bug del `abs()` de arriba solo para estos dos point_type. Guard de integridad: compara puntos sacados (`country='N/D'`) vs puntos resueltos y avisa `[WARN]` si no coinciden (hoy da 0 — verificado que el 100% de FORTUNE/MISSIONS sale con `country=NULL` en ambas tablas fuente, accrual y cancelación).
- **`Input_Precios.xlsx` → `FX_Currency`**: completado 07-sep dic-25→ago-26 para Colombia/Chile/Perú/Uruguay (estaban 100% vacíos desde 2019 — nunca se habían cargado). Argentina/Brasil/México ya tenían esos meses. El resto de la historia (2019-2025) y sep-2026 en adelante siguen vacíos — hace falta cargarlos mes a mes, no hay proceso automático que traiga el TC. **Ojo al editar con `openpyxl`/similar**: las columnas `Pais`/`Moneda` son fórmulas de arrastre (`=A(fila-1)`); guardar con una librería que no evalúa fórmulas invalida el caché para `pandas.read_excel` en **toda la hoja**, no solo las filas tocadas — hay que "hornear" esas fórmulas a valor literal antes de guardar.
- **Valor USD de acumulaciones — tres métodos excluyentes por fila (`getAcumUsd`, actualizado 08-sep).** (1) **Cobrand y Partners** usan `acum_usd_precio` (columna de `loyalty_acumulaciones_*.json`) = `puntos × precio_facturacion` de `Input_Precios.xlsx`, con FX BRL/MXN→USD del mes; no tienen `acum_usd_base` (no hay comisión/GB de viaje detrás) — antes daban $0. El match es país+`point_type` (Cobrand) o país+`partner` (Partners) dentro de `[fecha_inicio, fecha_fin]`. Combinación sin precio → $0 + `[WARN]` en el log del sync (ej. `ICBCAR / Rewards & Benefits`). `PARTNER_COUNTRY_CODE` en `loyalty_sync.py` completa el `country_code` cuando el datalake lo trae `N/D` (BDBCO→CO, NOMADBR→BR, etc.). (2) **IFOOD, Acciones Marketing y Club Despegar** (fix 08-sep): `acum_usd_base` es 0 en el 100% de sus filas (welcome bonuses/campañas/subscripción, sin comisión de reserva de viaje ni precio de `Input_Precios.xlsx`) → se valúan directo como `puntos × factor SSP` (variable `PV` en el código), sin pasar por el reparto DRO de abajo (que con `R=0` siempre daría `$0`). (3) **Resto (Pasaporte D! genuino)**: DRO/relative fair value — `R=acum_usd_base`, `PV=-(points×factor SSP)`, `DRO=(PV/(|PV|+R))×R` (fix 08-sep, reemplazó una fórmula vieja dimensionalmente inválida que mezclaba USD × USD/punto).

## Comandos

- `/configurar-entorno` — setup de analista u operador
- `/publicar` — deploy manual de la landing GAS a producción

## Agentes de auditoría (`.claude/agents/`)

4 agentes de auditoría, cada uno con su skill en `.agents/skills/`. **Revisan y reportan — no corrigen código** salvo que se les pida explícitamente después del reporte.

| Agente | Skill | Para qué |
|---|---|---|
| `auditor-de-codigo` | `code-audit` | Calidad de código, integridad de datos del pipeline, credenciales, consistencia pipeline↔landing |
| `calidad-de-procesos` | `process-quality-audit` | Orden / claridad / escalabilidad / integridad / eficiencia de CÓMO se trabaja (no del código) |
| `ux-designer` | `ux-consistency-review` | Estética, paleta oficial Despegar, consistencia visual, accesibilidad del `dashboard.html` |
| `data-engineer` | `data-source-consistency-review` | Mapeo de fuentes (queries → JSON → sección), duplicidad, formato homogéneo, fechas, staleness de doc |

**Cuándo:** correr `auditor-de-codigo` antes de un merge a `main` / `/publicar` y después de cambios grandes en `loyalty_sync.py` o las queries. Los demás a pedido ("revisar UX", "revisar procesos", "cómo se conectan los datos"). Si hay hallazgos bloqueantes, avisar al usuario y esperar confirmación antes de mergear/deployar.

**Cómo invocarlos en este entorno:** los agentes custom de `.claude/agents/` **NO son invocables por `subagent_type`** — lanzarlos como `general-purpose` con un prompt que diga: "leé completo `.claude/agents/<nombre>.md` (tu rol) y `.agents/skills/<skill>/SKILL.md` (la skill que corrés), y seguí eso al pie de la letra; alcance = <lo que sea>; no edites nada, solo reportá".

**Si la sesión está cerca del límite de uso:** correr los agentes de a 1-2, no los 4 juntos (cada uno son ~100-140k tokens).
