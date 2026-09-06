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

- **Nunca commitear** `token_drive.json`, `service_account.json`, `envs/.env*`. Están gitignoreados.
- **`git push` no publica la landing GAS.** El deploy es manual: `clasp push -f` + `clasp deploy -i <id estable>` (o `/publicar`). Siempre verificar que el deploy corrió (`clasp deployments`).
- El **deployment estable** es `AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig`. `clasp push` solo actualiza HEAD; hay que `clasp deploy -i <ese id>` para que la webapp cambie.
- Los JSON en Drive se **sobreescriben** (no hay versiones).

## Gotchas (aprendidos)

- **Apps Script no lee blobs >50 MB.** Por eso `loyalty_sync.py` sube los JSON de acum/reden **agregados por mes** (no fila por fila). Si vuelven a crecer, la serie LY de los charts se cae a cero (`fyYears()` → NaN).
- **Pestaña TOTAL**: `dashboard.html` la trata como pseudo-país (`dataKey='total'`). `matchCountryRow` / `rowCountryKey` deciden si una fila entra y con qué país se hace el lookup de SSP. La suma es sobre `COUNTRY_DATAKEYS` (los 8 países), no "todo lo que haya" — así no se cuela un `Pais` agregado del P&L.
- **Miembros**: es un snapshot del padrón HOY. Las "altas" de meses viejos solo incluyen a los que siguen activos → sesgo de supervivencia (no es la serie histórica real de altas). El KPI de total sí es el padrón actual correcto. Mismo sesgo en Club Despegar (query filtra por estado actual + `rn=1`).
- **Club Despegar / iFood** usan catálogos nuevos del datalake (`data.raw.*`, `analytics.ifood_dim_users`) — no `data.lake.*`. Si el ODBC tira `errorCode member not found` al *conectar* (no al correr la query), es la VPN/driver, reintentar (`conectar()` ya reintenta 4×).
- **`membertrip_subscription.updated_at` está BULK-TOUCHED** (todos los ACTIVE actualizados ago-2026; cero bajas registradas dic25→may26, pico de 4k en jun26). NO usarlo para stock histórico ni timing real de bajas. Único timestamp confiable = `created_at`. Por eso el "stock por mes" del dashboard es la base activa acumulada (survivorship), no un snapshot real, y la tablita de bajas dice "fecha registrada (aprox.)".
- **iFood**: la query de Metabase (150076) arrancaba en 2026-01; el pipeline la bajó a 2025-01 para tener LY. `event_date` de `closed_loop_discount` es la fecha de alta de Club iFood (la query original solo tenía fecha para cross_cashback).
- **`points` vs `points_distribuidos`**: la query trae `SUM(puntosv2)` como `points`. El cierre de Loyalty usa `points_distribuidos` (~2-4% menos), que **falla vía ODBC** → el pipeline usa `points`. El SSP calculado difiere ~1% del cierre por esto. En el frontend, `getPts(row)` usa `points` directo (el fallback a `points_distribuidos` se eliminó porque nunca venía en los JSON).
- **Agregación con `abs()` por fila**: acum/reden se suman en valor absoluto por fila (preserva el criterio previo del dashboard). Cambiarlo mueve todos los totales.
- **SSP / valor de acumulación**: `getAcumUsd = acum_usd_base · SSP_Facturación[país][mes]`, con `SSP_Facturación = SSP_Calculado · (1 − breakage_esperado)`. `SSP_Calculado` sale de las redenciones Pasaporte D!. El Excel de cierre tenía un **swap MX↔CO** que el pipeline ya corrige.
- **ODBC + `data.analytics.*`**: un `SELECT` directo de una columna **`DECIMAL` cruda** de esas tablas tira `errorCode member not found`. El workaround —que ya usan `_ACUM_SQL` y `_REDEN_SQL`— es envolver en `SUM(CAST(col AS DECIMAL(18,2)))` o similar; así las queries centrales SÍ leen numéricos de `data.analytics.bi_transactional_fact_*` sin problema. NO es "cualquier número de analytics falla".
- El P&L Contable NO sale del datalake — es `baseline_actuals+projections.json` / `budget.json` / `forecast.json` del repo **B2B_Ecosystem/Inputs_Planning_PnL**.
- **Valor USD de acumulaciones — dos métodos excluyentes por fila.** `getAcumUsd` en el dashboard: **Cobrand y Partners** usan `acum_usd_precio` (columna nueva de `loyalty_acumulaciones_*.json`) = `puntos × precio_facturacion` de `Input_Precios.xlsx`, con FX BRL/MXN→USD del mes; el resto usa `acum_usd_base × SSP_Facturación`. Cobrand/Partners no tienen `acum_usd_base` (no hay comisión/GB de viaje detrás) — antes daban $0. El match es país+`point_type` (Cobrand) o país+`partner` (Partners) dentro de `[fecha_inicio, fecha_fin]`. Combinación sin precio → $0 + `[WARN]` en el log del sync (ej. `ICBCAR / Rewards & Benefits`). `PARTNER_COUNTRY_CODE` en `loyalty_sync.py` completa el `country_code` cuando el datalake lo trae `N/D` (BDBCO→CO, NOMADBR→BR, etc.).

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
