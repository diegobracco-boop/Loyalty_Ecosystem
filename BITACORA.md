# Bitácora — Loyalty Ecosystem

Registro cronológico de cambios, incidentes y decisiones relevantes.
Formato: fecha · tipo · descripción · archivos afectados.

---

## 2026-09-15

### feat — Gráfico de mix por tier (% composición mensual)
**Commits:** `8a012ee`
**Archivos:** `dashboard.html`

Nuevo gráfico 100% stacked ("Mix por tier %") debajo del gráfico de absolutos
en la vista "Por Tier" de Pasaporte D!. Muestra la participación porcentual de cada
tier (Viajero / Explorador / Global / Sin tier) por mes.

- Nueva función `buildMixChart()` en `dashboard.html`: normaliza a 100% internamente,
  labels de % dentro del segmento solo si ≥ 8%, leyenda oculta (la provee el gráfico
  de arriba), tooltip detallado por hover.
- Canvas `ch-mix-{suffix}` generado con `display:none` en el HTML; el bloque Por Tier
  lo muestra/oculta según el toggle Total/Por Tier.
- Siempre en puntos, independiente del toggle Q/$ (composición en $ y en Q difiere
  menos de 1-2 pp — no justifica dos vistas de mix).
- Sin cambios en pipeline ni en JSONs.

---

## 2026-09-14

### feat — Vista $ en toggle Por Tier de Pasaporte D!
**Commits:** `32038cb` (feat real, por Claude Code), `8842db3` (fix placeholder pipeline)
**Archivos:** `loyalty_sync.py`, `dashboard.html`

`loyalty_acum_tier.json` ahora incluye columna `acum_usd_base` por fila.
Calculada en la nueva función `enrich_acum_tier_usd()` de `loyalty_sync.py`:
prorrateo desde `_acum_cy_pre`/`_acum_ly_pre` (point_type='general', partner='DP')
según participación de puntos por mes×país×tier. Sin SQL nuevo (límite de 60 stages
de Presto ya alcanzado en `_ACUM_SQL`).

En el dashboard, el bloque "Por Tier" ahora respeta el toggle Q/$:
- `tierPtsMap` (Q) y `tierUsdMap` ($) calculados en la misma pasada por las filas.
- DRO por fila de tier idéntico a `getAcumUsd` (PV/denom × R).
- Línea Total LY: en $ usa `acPrev`; en Q usa `acPtsPrev`.

Validado con `--dry-run` (diff de 0,1% esperado por redondeo) y sync real
(480/501 filas con `acum_usd_base` ≠ 0, `generated_at` 14-sep 18:52).

### fix — SAFEGUARD/Cfar confirmado en regla producto
**Commits:** `67f598c`
**Archivos:** `CLAUDE.md`

Se eliminó el pendiente "que Rosario agregue SAFEGUARD/Cfar a la tabla" —
ya estaba agregado en la planilla Sheet Config.

### incidente — Commits con placeholder literal (d2c2128, 8842db3)
**Commits:** `d2c2128`, `8842db3`

Dos commits consecutivos escribieron el literal `{{loyalty_sync_patched.py}}` /
`{{dashboard_patched.html}}` / `# placeholder — se reemplaza por file_key` en vez
del contenido real de los archivos. Causa: la tool `push_files` y `create_or_update_file`
del agente no soportan `file_key` como referencia a archivos generados en el executor.

Detección: `git pull` + `python loyalty_sync.py` → `NameError: name 'loyalty_sync_patched'`.
Resolución: Claude Code (terminal) reconstruyó ambos archivos desde el commit bueno
`89254c2` + el mensaje del commit roto como spec, commitió correctamente.

**Moraleja:** después de cualquier "restaurar archivo corrupto", grepear el literal
sospechoso antes de confiar en que el commit es correcto.

---

## 2026-09-12

### docs — Manual: ratio de acumulación documentado
**Commits:** `dcf26c8`
**Archivos:** `Manual_Loyalty_Ecosystem/manual.html`

Pipeline pasó de 10 a 11 JSON (se agregó `loyalty_ratio_acumulacion.json`).
Manual actualizado: nueva fila en "Los 11 JSON", nueva fila en "¿Qué vista uso?".

---

## 2026-09-11

### feat — Ratio de acumulación pts/GB por producto en Pasaporte D!
**Commits:** `46a404e`, `d656aba`, `218beeb`, `dca6395`, `33c451`
**Archivos:** `loyalty_sync.py`, `dashboard.html`, `CLAUDE.md`

Nuevo JSON `loyalty_ratio_acumulacion.json`: `SUM(points)/SUM(gb)` por mes×país×grupo_pnl,
solo `point_type='general'`. Grupo P&L mapeado desde la pestaña `regla producto` del
Sheet Config mediante `load_regla_producto()` / `_grupo()`.

Fix clave (commit `218beeb`): orden de match en `_grupo()` corregido a
`purchase_type` (reserva) → `product_type` (línea) → código Comarch. Sin este orden,
paquetes/combos se colaban bajo el componente ancla (FLIGHT), inflando esa categoría.

Gráfico `buildRatioBarChart` en `dashboard.html`: barras lado a lado por producto,
shadow del período anterior, selector Mes/Año independiente del filtro global.

### feat — Módulo Proceso_cierre documentado
**Commits:** `83b85f7`, `c6d7bd8`, `3ac9d2b`
**Archivos:** `Manual_Loyalty_Ecosystem/manual.html`, `Proceso_cierre/conexion.py`

Sección "Proceso de cierre" agregada al manual con flujograma SVG.
Fix: `conexion.py` ahora tiene reintento 4×/backoff en `conectar()` (igual que
`loyalty_sync.py`), hallazgo de la auditoría de código previa.

---

## 2026-09-09

### fix — GB inflado con combos cancelados en _ACUM_SQL
**Commits:** `83dd0bf` (referenciado en gotchas)
**Archivos:** `loyalty_sync.py`

`net_pts_combo = SUM(points) OVER (PARTITION BY dsp_transaction_id, product, business)`
+ gate `AND net_pts_combo > 0` en las 2 columnas de GB de `_ACUM_SQL`. El GB de reservas
cuyos puntos quedaron netos ≤0 ya no se cuenta. Mismo fix validado en cierre contable.

---

## 2026-09-08

### fix — Valor USD de acumulaciones: tres métodos por fila (DRO fix)
**Commits:** `80fd681`, `81fc911`, `77720d2` (referenciados en gotchas)
**Archivos:** `dashboard.html`

`getAcumUsd` reemplazó fórmula inválida (`acum_usd_base × factor SSP`) por DRO correcto.
Tres métodos excluyentes: (1) Cobrand/Partners → `acum_usd_precio`; (2) IFOOD/Acciones
Marketing/Club Despegar → `puntos × SSP`; (3) resto → DRO (`PV/denom × R`).

---

## 2026-09-07

### feat — Infraestructura inicial del pipeline Loyalty
**Commits:** múltiples (ver historial previo al 08-sep)
**Archivos:** `loyalty_sync.py`, `dashboard.html`, `Código.js`, `auth_drive.py`, `SETUP.md`

Pipeline completo: 10 JSON → Drive → GAS webapp. Fixes mayores:
- Bug `abs()` en `aggregate_acum` (sobreestimaba +157% en Pasaporte D!).
- `matchCountryCode` para acum/reden (reemplazó `matchCountryRow` que fallaba con N/D).
- `_ACUM_ER_COUNTRY_SQL` para FORTUNE/MISSIONS sin país.
- OAuth Drive (sin service account, mismo patrón que B2B_Ecosystem).
- `FX_Currency` completado dic-25→ago-26 para CO/CL/PE/UY.
