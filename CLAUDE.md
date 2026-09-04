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
| **Dashboard / GAS** (`dashboard.html`, `Código.js`) | branch → editar → commit → push → PR. Al mergear a `main` la GitHub Action hace `clasp push` + `clasp deploy` sola. Deploy manual: `/publicar`. |
| **Pipeline** (`loyalty_sync.py`, queries SQL) | branch → editar → validar con **`python loyalty_sync.py --dry-run`** (corre las queries, arma los JSON en `_out/`, NO sube a Drive ni lee la planilla — solo hace falta datalake + DSN, **no** credenciales de Drive) → PR. El operador / scheduler hace la corrida real. |

## Archivos

| Archivo | Qué es |
|---|---|
| `loyalty_sync.py` | Pipeline: datalake → agrega por mes+país+partner+point_type → sube 8 JSON a Drive |
| `Código.js` | Backend GAS: sirve los JSON crudos + filtra loyalty del P&L (`_loyPnl`) |
| `dashboard.html` | SPA: pestaña **TOTAL** (suma de países) + una por país; P&L Contable (Baseline/Goal/Δ, selector Mes/Q/Half), Métricas por programa, Miembros del programa por tier |
| `loyalty_miembros.json` | Snapshot del padrón activo (`clm_customers` status='A') por mes de `enrolment_date` × país × tier. Sin ventana de fecha (foto actual). Tier: mismo criterio que la query de breakage. |
| `breakage_esperado.csv` · `Diccionario.xlsx` | **Fallback** de la planilla de config. La fuente real es el Sheet. |
| `auth_drive.py` | OAuth de Drive (necesita `credentials_drive.json`, que no está en el repo) |
| `setup_check.py` · `configurar_datalake.py` | Diagnóstico y carga de credenciales para operadores |
| `reaggregate_legacy_jsons.py` · `build_ssp_legacy.py` | One-shots: regeneran JSON/SSP desde data vieja sin re-sync |
| `.github/workflows/deploy-gas.yml` | CI: deploy a Apps Script al mergear a `main` |
| `SETUP.md` | Runbook operativo completo |

## Reglas que no romper

- **Nunca commitear** `token_drive.json`, `service_account.json`, `envs/.env*`. Están gitignoreados.
- **`git push` no publica la landing GAS.** La publica la GitHub Action al mergear (o `/publicar` manual). Siempre verificar que el deploy corrió.
- El **deployment estable** es `AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig`. `clasp push` solo actualiza HEAD; hay que `clasp deploy -i <ese id>` para que la webapp cambie.
- Los JSON en Drive se **sobreescriben** (no hay versiones).

## Gotchas (aprendidos)

- **Apps Script no lee blobs >50 MB.** Por eso `loyalty_sync.py` sube los JSON de acum/reden **agregados por mes** (no fila por fila). Si vuelven a crecer, la serie LY de los charts se cae a cero (`fyYears()` → NaN).
- **Pestaña TOTAL**: `dashboard.html` la trata como pseudo-país (`dataKey='total'`). `matchCountryRow` / `rowCountryKey` deciden si una fila entra y con qué país se hace el lookup de SSP. La suma es sobre `COUNTRY_DATAKEYS` (los 8 países), no "todo lo que haya" — así no se cuela un `Pais` agregado del P&L.
- **Miembros**: es un snapshot del padrón HOY. Las "altas" de meses viejos solo incluyen a los que siguen activos → sesgo de supervivencia (no es la serie histórica real de altas). El KPI de total sí es el padrón actual correcto.
- **`points` vs `points_distribuidos`**: la query trae `SUM(puntosv2)` como `points`. El cierre de Loyalty usa `points_distribuidos` (~2-4% menos). El SSP calculado difiere ~1% del cierre por esto.
- **Agregación con `abs()` por fila**: acum/reden se suman en valor absoluto por fila (preserva el criterio previo del dashboard). Cambiarlo mueve todos los totales.
- **SSP / valor de acumulación**: `getAcumUsd = acum_usd_base · SSP_Facturación[país][mes]`, con `SSP_Facturación = SSP_Calculado · (1 − breakage_esperado)`. `SSP_Calculado` sale de las redenciones Pasaporte D!. El Excel de cierre tenía un **swap MX↔CO** que el pipeline ya corrige.
- **ODBC + columnas numéricas de `data.analytics.*`**: fallan (`errorCode member not found`). Usar solo VARCHAR/DATE de esas tablas; números solo de `data.lake.*`.
- El P&L Contable NO sale del datalake — es `baseline_actuals+projections.json` / `budget.json` / `forecast.json` del repo **B2B_Ecosystem/Inputs_Planning_PnL**.

## Comandos

- `/configurar-entorno` — setup de analista u operador
- `/publicar` — deploy manual de la landing GAS a producción
