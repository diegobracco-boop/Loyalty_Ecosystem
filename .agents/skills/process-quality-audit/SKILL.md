---
name: process-quality-audit
description: Auditoría de calidad de procesos (no de código) de Loyalty Ecosystem — orden, claridad, escalabilidad, integridad y eficiencia de cómo se ejecutan los flujos (dry-run del analista, corrida real del operador, deploy vía GitHub Action o `/publicar`, edición de la planilla de config). Usar antes de cambiar un proceso, al sumar una persona nueva, o cuando el usuario pida "revisar procesos", "¿esto escala?", "¿es claro este flujo?".
---

# Process Quality Audit — Loyalty Ecosystem

Auditoría del repo entero o de un proceso puntual, en cinco ejes independientes. Audita el PROCESO alrededor del código: cómo alguien ejecuta, documenta y mantiene el trabajo día a día.

## 0. Definir alcance

Si el usuario no lo dijo: todo el repo, o un proceso puntual (corrida real del sync, `--dry-run` del analista, ciclo deploy `clasp push` + `clasp deploy -i` / GitHub Action, edición de la planilla de config, onboarding de una persona nueva).

Leer `CLAUDE.md`, `SETUP.md` y `docs/PENDIENTE-DIEGO.md` — ahí está el proceso documentado y lo que quedó abierto. Si algo del proceso no está escrito, eso ya es un hallazgo del Eje 2.

## Eje 1 — Orden y estructura

- ¿Los pasos de cada proceso están en un orden explícito y reproducible (`/configurar-entorno`, `/publicar`, `python loyalty_sync.py --dry-run`), o dependen de que la persona recuerde la secuencia?
- Pasos ad-hoc que solo una persona sabe hacer — buscar rutas hardcodeadas a la máquina de una sola persona, comentarios tipo "preguntale a Diego", one-shots sin doc que reimplementan lógica del pipeline (patrón que ya causó problemas acá: dos one-shots divergentes que subían a producción, eliminados 2026-09-05 — si vuelve a aparecer uno, es hallazgo).
- Los tres perfiles (Analista / Analista+query / Operador) — ¿el `CLAUDE.md` deja claro qué hace cada uno y qué setup necesita, o hay solapamiento confuso?

## Eje 2 — Claridad

- ¿Una persona nueva podría ejecutar el proceso completo leyendo solo `CLAUDE.md` + `SETUP.md`, sin preguntar? Especialmente: correr el `--dry-run`, editar la planilla de config, abrir un PR.
- Procesos que existen pero no están escritos (scripts o pasos mencionados en commits/código sin doc equivalente).
- Mensajes de error de `loyalty_sync.py` / `setup_check.py` que no explican qué hacer (ej. el `errorCode member not found` del ODBC — ¿el script dice "conectá la VPN y reintentá" o tira el stack pelado?).
- **Planilla vs fallback**: `CLAUDE.md` dice "NO tocar `breakage_esperado.csv` / `Diccionario.xlsx`, son solo fallback". ¿Hay algo que lo impida o lo advierta, o depende de que la persona lea esa línea? ¿El pipeline avisa si terminó usando el fallback en vez de la planilla?

## Eje 3 — Escalabilidad

- Límites hardcodeados: lista de países (`COUNTRY_DATAKEYS`, los 8), mapeo de programas, rutas a `envs/.env.<nombre>` por persona. ¿Agregar un país o un programa nuevo requiere tocar código en varios lugares, o un solo punto de config?
- El JSON de acum/reden ya se tuvo que agregar por mes para no pasar los 50 MB de Apps Script. ¿Qué pasa cuando crezca de nuevo? ¿Hay un check de tamaño antes de subir?
- La corrida real hoy es una sola persona (scheduler) + Diego de backup. ¿Qué pasa si ninguno está? ¿Está documentado cómo lo levanta un tercero?

## Eje 4 — Integridad del proceso

Eje de mayor costo si falla — una corrida olvidada o un fallback silencioso deja Loyalty con números viejos sin que nadie lo note.

- Pasos que dependen de que la persona "se acuerde": después de `clasp push`, el `clasp deploy -i <id>` (documentado como regla, pero ¿hay un check?); correr el sync después de que el analista mergeó un cambio de query.
- **GitHub Action de deploy** (`.github/workflows/deploy-gas.yml`): ¿está viva? Verificar con `gh run list` o revisando el YAML + los secrets que necesita. En el repo B2B la Action equivalente estuvo rota semanas con fallback manual silencioso — chequear que no pase lo mismo acá.
- **Doble fuente de verdad**: la planilla de config vs `breakage_esperado.csv`/`Diccionario.xlsx`. Si divergen y el pipeline cae al fallback sin avisar, los números salen mal. ¿Hay un `print("[WARN] usando fallback")`?
- El P&L Contable viene de OTRO repo (`B2B_Ecosystem/Inputs_Planning_PnL`). Si ese repo cambia el esquema o los nombres de LOB/línea, el filtro `_loyPnl` de Loyalty se rompe silencioso. ¿Hay algo que lo detecte?

**Para CADA gap de integridad, proponé el chequeo más barato que lo detectaría** (un grep, un assert, un `print("[WARN]…")` antes de subir a Drive, un paso en `/publicar`). `setup_check.py` ya es un molde de check de entorno en este repo — el patrón se puede extender a checks de datos/proceso.

## Eje 5 — Eficiencia

- Pasos redundantes o repetidos a mano que podrían ser un script/comando único.
- Tareas manuales frecuentes candidatas a un slash command (`/configurar-entorno`, `/publicar` ya existen — ¿falta uno para "correr el sync real" o "validar contra el cierre"?).
- One-shots o scripts de migración que se corren seguido y deberían integrarse al flujo normal como un flag del pipeline (ej. `--solo-ssp`, `--reagregar`) que reusa la lógica real, en vez de reimplementarla.
- Regenerar algo que no cambió (¿el sync re-corre las 10 queries siempre, aunque solo cambió una?).

## Reporte final

Un heading por eje (`## Orden y estructura`, `## Claridad`, `## Escalabilidad`, `## Integridad del proceso`, `## Eficiencia`), sin mezclar ni reordenar. Cada hallazgo con el archivo/comando/paso concreto — nunca "mejorar la documentación" sin decir cuál.

Cerrar con:
- Un resumen de una línea por eje.
- Una lista aparte de **hallazgos bloqueantes**: cualquier gap del Eje 4 que hoy dependa 100% de que una persona se acuerde de algo, sin ningún check ni fallback — para que el usuario los vea antes de sumar gente nueva al proceso o de cambiarlo.
