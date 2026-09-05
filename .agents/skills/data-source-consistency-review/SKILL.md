---
name: data-source-consistency-review
description: Revisión de fuentes de datos, duplicidad y homogeneidad de formato del pipeline de Loyalty (`loyalty_sync.py`). Usar antes de sumar una query SQL nueva o un JSON de salida nuevo, o cuando el usuario pida revisar duplicidad de datos, formato homogéneo, parseo de fechas, o cómo se conectan las fuentes.
---

# Data Source Consistency Review — Loyalty Ecosystem

Revisión del pipeline entero o de una query/JSON puntual, en cinco ejes. A diferencia del Eje 2 de `code-audit` (integridad interna: nulls, totales que cierran, idempotencia), esta skill mira la **relación entre fuentes y salidas**: qué tabla del datalake alimenta qué JSON, si hay solapamiento no intencional, y si el formato de salida es homogéneo.

## 0. Definir alcance

Si el usuario no lo dijo: todo el pipeline (`loyalty_sync.py`), o una query/JSON puntual.

Leer `CLAUDE.md` (arquitectura + la lista larga de **"Gotchas"** — ya documenta la mitad de lo que buscás) y `SETUP.md` antes de revisar.

**Chequeo transversal de staleness de documentación** (cualquier alcance): los "Gotchas" de `CLAUDE.md` y los comentarios de `loyalty_sync.py`, ¿siguen siendo ciertos? Buscar: bugs marcados como abiertos que ya se cerraron, tablas del datalake renombradas, IDs de Drive cambiados, "pendientes" ya hechos. Un dato que induce a error operativo es tan grave como un bug de datos.

## Eje 1 — Mapeo de fuentes

Para cada query de `loyalty_sync.py` (`_ACUM_SQL`, `_REDEN_SQL`, `_MIEMBROS_SQL`, `_CLUB_DESPEGAR_SQL`, `_IFOOD_ENROLL_SQL`, `_WCLUBE_CA_SQL`, …), documentar leyendo el código:
- **Fuente cruda**: tabla(s) del Datalake y de qué familia (`data.lake.*`, `data.analytics.*`, `data.raw.*`, `analytics.ifood_dim_users`). Gotcha: **columnas numéricas de `data.analytics.*` fallan por ODBC** — solo VARCHAR/DATE de esas; números solo de `data.lake.*`.
- **Salida**: nombre del JSON, esquema, y a qué sección del dashboard alimenta.
- **Transformación clave**: la función `clean_*` correspondiente, agregación (`abs()` por fila en acum/reden — documentado, no cambiar), `to_compact`.

**Fuente externa**: el **P&L Contable NO sale del datalake**. Viene de `baseline_actuals+projections.json` / `budget.json` / `forecast.json` que genera `Inputs_Planning_PnL` en el repo **B2B_Ecosystem** (folder Drive `1XqQPL…`), y lo lee `Código.js` (`_loyPnl`). Es una dependencia cross-repo — mapearla explícitamente.

## Eje 2 — Duplicidad de datos

- ¿Hay dos queries que traen el MISMO concepto (ej. miembros activos) de tablas o criterios distintos, en vez de una sola? El criterio de tier aparece en `_MIEMBROS_SQL` y en la query de breakage — verificar que sea idéntico (el `CLAUDE.md` dice que lo es; confirmar).
- ¿Dos queries leen la misma tabla con SQL casi idéntico que podría ser una función/CTE compartida (riesgo: si hay que cambiar un filtro, se actualiza una copia y se olvida la otra)?
- JSON de salida con nombres muy parecidos o versiones viejas no borradas en el folder de Drive.

## Eje 3 — Formato homogéneo

- ¿Todos los JSON respetan el mismo esquema `{meta, data}`? Señalar cualquiera que se desvíe (`to_compact` vs `to_dict(orient="records")` — el de breakage usa records, verificar que el frontend lo espera así).
- Nombres de dimensión consistentes entre queries: país, partner, point_type, mes (`YYYY-MM`). Señalar variantes (`Pais` vs `country`, `mes` vs `month`, país en español vs código ISO).
- Tipos consistentes por columna (montos siempre float, mes siempre string `YYYY-MM`).
- Nombres de país: la pestaña TOTAL suma sobre `COUNTRY_DATAKEYS` (8 países) — ¿todas las queries emiten esos mismos 8 nombres exactos? Un país con otro nombre queda fuera del TOTAL sin aviso.

## Eje 4 — Fechas

- Grepear `pd.to_datetime(..., format="mixed", dayfirst=True)` (y cualquier parseo ambiguo) en `loyalty_sync.py` y helpers. Ese combo invierte día/mes en fechas ISO con día ≤12 — corrompió datos dos veces en el repo B2B. Hoy Loyalty parece limpio (`pd.to_datetime(val).strftime("%Y-%m-%d")` sin `dayfirst`); si aparece el patrón, es hallazgo.
- Verificar que las fechas que vienen del datalake (`enrolment_date`, `created_at`, `event_date`, `updated_at`) se parseen sabiendo su formato real, no por autodetección.
- **`updated_at` de `membertrip_subscription` está bulk-touched** (documentado) — confirmar que NADA lo usa para stock histórico ni timing de bajas; el único timestamp confiable ahí es `created_at`.

## Eje 5 — Trazabilidad

- Para cada JSON, ¿está claro en `CLAUDE.md` de qué query sale y qué sección del dashboard lo consume? Señalar JSON "huérfanos" (nadie los lee) o secciones del dashboard que leen un JSON sin que quede claro qué query lo genera.
- El sesgo de supervivencia de `loyalty_miembros.json` / `loyalty_club_despegar.json`: ¿el dashboard lo etiqueta como "foto actual / aprox." en la UI, o lo muestra como serie histórica real? (Eje de trazabilidad porque es sobre si el usuario final entiende qué está viendo.)
- La dependencia cross-repo del P&L (`Inputs_Planning_PnL`): si ese repo cambia los nombres de LOB/línea, el filtro `_loyPnl` se rompe silencioso. ¿Está documentado ese acople? ¿Hay un check?

## Reporte final

Un heading por eje (`## Mapeo de fuentes`, `## Duplicidad de datos`, `## Formato homogéneo`, `## Fechas`, `## Trazabilidad`). Hallazgos con archivo+línea; para duplicidad, nombrar las dos queries involucradas.

Cerrar con:
- Un resumen de una línea por eje.
- Una lista aparte de **hallazgos bloqueantes**: cualquier duplicidad que pueda hacer divergir números, o cualquier riesgo de corrupción de fecha/formato — para que el usuario los vea antes de sumar una query nueva o publicar un JSON nuevo.
