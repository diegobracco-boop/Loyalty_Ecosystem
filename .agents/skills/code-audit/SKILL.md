---
name: code-audit
description: Auditoría completa del repo Loyalty Ecosystem — calidad de código, integridad de datos en el pipeline `loyalty_sync.py`, seguridad de credenciales y consistencia entre el pipeline y la landing GAS. Usar antes de un merge a `main` / `/publicar`, después de cambios grandes en el pipeline o las queries, o cuando el usuario pida "auditar", "revisar todo", "chequear integridad".
---

# Code Audit — Loyalty Ecosystem

Auditoría del repo entero o de un archivo/query puntual, en cuatro ejes independientes. Audita el estado actual del código tal como está (no necesita un diff de comparación).

## 0. Definir alcance

Si el usuario no lo dijo: todo el repo, o un archivo puntual (`loyalty_sync.py`, `Código.js`, `dashboard.html`, una query SQL).

Leer `CLAUDE.md` y `SETUP.md` antes de auditar — ahí está el contrato de datos (qué JSON produce el pipeline, qué lee la landing) y la sección **"Gotchas (aprendidos)"**, que ya documenta la mitad de los hallazgos posibles. No re-reportar un gotcha ya documentado como si fuera nuevo; sí señalar si dejó de ser cierto o si hay uno nuevo del mismo tipo.

## Eje 1 — Calidad de código

Aplica a `loyalty_sync.py` (~100 KB, es el grueso), `Código.js` (GAS), `dashboard.html`.

- **Hardcodeos**: paths absolutos de una máquina específica, credenciales, tokens, IDs de Drive/Sheets pegados en el código en vez de en config. `loyalty_sync.py` ya tuvo este problema (`_ENVS_DIR` / `RUTA_ENV` con fallback) — verificar que no haya vuelto.
- **Manejo de errores**: llamadas a Drive API, ODBC/Datalake, o lectura de la planilla sin try/except; fallos silenciosos que producirían un JSON vacío o parcial sin avisar. `conectar()` ya reintenta 4× — verificar que las queries también tengan un camino de error claro.
- **Duplicación**: lógica repetida entre las ~10 secciones de query de `loyalty_sync.py` (cada `_*_SQL` + su `clean_*`), o entre `Código.js` y el frontend, que debería compartir una función. Las funciones `clean_*` y `to_compact` son el lugar típico.
- **Smell baseline de Fowler** (Mysterious Name, Feature Envy, Data Clumps, Primitive Obsession, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains) — siempre juicio, nunca regla dura; lo que `CLAUDE.md` documenta gana.
- **`--dry-run` intacto**: cualquier cambio nuevo, ¿respeta `DRY_RUN` (no sube a Drive, no lee la planilla)? Un paso que ignore `DRY_RUN` rompe el flujo del analista.

Reportar cada hallazgo con archivo + línea + por qué importa.

## Eje 2 — Integridad de datos

El pipeline produce los JSON que ve finance y el equipo de Loyalty. Un error acá se propaga silenciosamente a todo el dashboard.

- **Esquema de salida**: cada JSON generado, ¿tiene la misma estructura `{meta, data}` que el resto y que la versión previa en Drive? Señalar drift de esquema (una query nueva que emite otras claves de dimensión, `to_compact` vs `to_dict(orient="records")` mezclados).
- **Nulls / vacíos silenciosos**: ¿hay ramas donde una fila sin match (país no mapeado, partner nuevo) se descarta sin loguear, en vez de fallar o reportar? `allow_nan=False` en los `json.dumps` — verificar que un NaN no explote la corrida entera sin mensaje útil.
- **Totales que no cierran**: la pestaña TOTAL suma sobre `COUNTRY_DATAKEYS` (los 8 países), no "todo lo que haya". Verificar que un `Pais` agregado del P&L no se cuele. El SSP difiere ~1% del cierre por `points` vs `points_distribuidos` (documentado) — señalar si esa brecha cambió de magnitud.
- **Sesgo conocido**: `loyalty_miembros.json` y `loyalty_club_despegar.json` son survivorship (altas viejas = solo los que siguen activos). Verificar que el dashboard **etiqueta** esas series como "foto actual / aprox.", no como serie histórica real. Si alguien quita esa etiqueta, es hallazgo.
- **Límite de 50 MB de Apps Script**: los JSON de acum/reden se suben **agregados por mes** justamente por esto. Si un cambio los devuelve fila-por-fila, la serie LY de los charts se cae a cero (`fyYears()` → NaN). Verificar el tamaño de los JSON que emite un cambio.
- **Idempotencia**: correr el pipeline dos veces con el mismo input, ¿produce el mismo output? Los JSON de Drive se sobreescriben sin versión — ¿hay riesgo de carrera si el scheduler y Diego corren a la vez?

Reportar como: `[dato afectado] — [qué puede corromperse] — [cómo verificarlo o reproducirlo]`.

## Eje 3 — Seguridad de credenciales

- Ningún archivo trackeado por git debe contener usuario/password/token en texto plano. Grep por `PASSWORD=`, `token`, `api_key`, credenciales de Datalake (`@ar.infra.d` / `@mx.infra.d`) fuera de `envs/`.
- Confirmar que `token_drive.json`, `service_account.json`, `credentials_drive.json`, `envs/.env*` están en `.gitignore` — no asumir, chequear el archivo. `git log --all --full-history` sobre esos paths para confirmar que nunca se commitearon.
- El repo tiene `credentials_drive.json` (414 bytes) **trackeado** — verificar si es un OAuth client público (no secreto, como en B2B) o si tiene algo sensible. Si tiene un secret real, es bloqueante.

## Eje 4 — Consistencia pipeline ↔ landing

- `Código.js` sirve los ~10 JSON de Drive al frontend. ¿Las claves que usa (`_loyPnl`, los nombres de cada JSON, las dimensiones) coinciden con lo que `loyalty_sync.py` emite hoy? Buscar los nombres de archivo/clave en `Código.js` y `dashboard.html` vs los que realmente sube el pipeline (`upload_to_drive(data, name)` y el array de nombres).
- El **P&L Contable** de la landing NO viene de `loyalty_sync.py` — viene de `Inputs_Planning_PnL` (repo B2B_Ecosystem, folder Drive `1XqQPL…`). Verificar que `Código.js` (`_loyPnl`) lee de ahí y que el filtro de "solo loyalty" del P&L sigue matcheando (si cambian los nombres de LOB/línea en el P&L canónico, este filtro se rompe silencioso).
- Si el pipeline cambia el esquema de un JSON, verificar que el frontend que lo consume no rompa (nombres de clave en `dashboard.html` vs los que emite el builder).

## Reporte final

Agregar los cuatro ejes bajo headings separados (`## Calidad de código`, `## Integridad de datos`, `## Seguridad de credenciales`, `## Consistencia pipeline↔landing`). No mezclar ni reordenar entre ejes.

Cerrar con:
- Un resumen de una línea por eje (cantidad de hallazgos, el más grave si hay).
- Una lista aparte de **hallazgos bloqueantes** — cualquier cosa del Eje 2 o 3 que pueda corromper datos de producción o filtrar credenciales — para que el usuario los vea antes de mergear a `main` o correr `/publicar`.
