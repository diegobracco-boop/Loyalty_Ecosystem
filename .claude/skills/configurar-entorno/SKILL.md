---
name: configurar-entorno
description: "Configura el entorno de un analista o de un operador del pipeline de Loyalty. Invocar cuando el usuario dice 'configurar entorno', 'recién cloné', 'soy nuevo en Loyalty', 'no puedo correr loyalty_sync', 'cómo edito el breakage esperado', 'setup', o falla el sync por credenciales/DSN/Drive."
---

Hay **dos perfiles** y el setup es muy distinto. Preguntá primero cuál es.

## Paso 0 — ¿Qué vas a hacer?

Preguntale:

- **(A) Analista** — editar inputs de negocio (breakage esperado, diccionario de
  programas) y/o proponer cambios de dashboard / queries. **La mayoría es esto.**
  → seguí **Perfil Analista**. No necesita credenciales, Python ni ODBC.
- **(B) Operador del pipeline** — correr o re-correr `loyalty_sync.py` (además del
  Task Scheduler, 1-2 personas).
  → seguí **Perfil Operador**.

---

## Perfil Analista

1. Confirmá que clonó el repo (`git remote -v` apunta a `diegobracco-boop/Loyalty_Ecosystem`).
2. **Accesos a pedirle a Diego** (una vez):
   - Repo GitHub `Loyalty_Ecosystem` → *Write*
   - Planilla Drive **"Loyalty Ecosystem - Config"** → *Editor*
3. **Editar inputs de negocio**: abrir la planilla → pestaña `breakage_esperado`
   (`country_code, month YYYY-MM, breakage_esperado 0..1`) o `diccionario`
   (`partner, point_type, concatenado, seccion`) → editar celdas. El próximo sync
   lo toma. No hay que tocar el repo.
4. **Cambios de dashboard / queries**: `git checkout -b <cambio>` → editar
   `dashboard.html` / `Código.js` / `loyalty_sync.py` → commit → push → abrir PR.
   El deploy a Apps Script es **manual** (`clasp push -f` + `clasp deploy -i <id>`,
   o el comando `/publicar`) — el push a `main` no publica solo.

5. **Si el cambio es en una query SQL** y quiere validarlo localmente antes del PR:
   `python loyalty_sync.py --dry-run` corre las queries y arma los JSON en `_out/`
   sin subir a Drive ni leer la planilla. Necesita datalake + DSN + libs, **no**
   credenciales de Drive → seguí los pasos 2, 3 y 4 del **Perfil Operador** (saltando
   el paso 5 de Drive). Imprime un resumen (redenciones por point_type, SSP por país)
   para chequear el efecto del cambio.

Con eso el analista está listo. **No pidas credenciales de Drive.**

---

## Perfil Operador

**Regla de credenciales:** NO pidas, recibas ni escribas la contraseña del datalake
ni tokens. El operador corre esos pasos él mismo con el prefijo `!` (se ejecuta en
su terminal, no lo ves). Vos hacés lo no-secreto: `pip install`, correr los scripts
de diagnóstico, interpretar.

1. **Diagnóstico.** `python setup_check.py`. Mostrá el reporte. Cada `[FALTA]` tiene
   su remediación abajo. Si todo está `[OK]`, saltá al paso 6.

2. **Credenciales del datalake** (`[FALTA] credenciales datalake`).
   Que corra: `! python configurar_datalake.py` — pide USER y PASSWORD (sin eco),
   guarda en `envs/.env.<su-usuario>` (fuera del repo, gitignoreado). Son las mismas
   de Metabase / equipo de datos.

3. **DSN ODBC** (`[FALTA] DSN ODBC`).
   DSN de 64-bit llamado exactamente `DataLake Treasure ODBC`. Se copia de la config
   del equipo de datos (Mariano Bujía). No lo podés crear vos.

4. **Librerías Python** (`[FALTA] librerías Python` o `pyodbc`).
   Corré vos: `pip install -r requirements.txt`.

5. **Acceso a Google Drive** (`[FALTA] Drive`).
   - **Preferido — service account**: si le pasaron un `service_account.json`, que
     lo copie a `Loyalty_Ecosystem/service_account.json`. No expira, no necesita browser.
   - **Alternativa — OAuth personal**: necesita `credentials_drive.json` (NO está en
     el repo — GitHub bloquea el client secret; se lo pasa Diego o está en el folder
     Drive "Ops" restringido). Con ese archivo en la carpeta, que corra
     `! python auth_drive.py` → browser → cuenta @despegar.com → queda `token_drive.json`.
   - En ambos casos necesita acceso *Editor* al folder Drive `1yCPp6…` (lo da Diego).

6. **Verificación.** `python setup_check.py --full` (prueba conexión real a datalake
   y Drive). Repetí desde el paso 1 hasta `Entorno listo`.

7. **Cierre.** Confirmá que puede correr `python loyalty_sync.py`. Recordale que los
   inputs de negocio se editan en la planilla de Drive, no en el repo. Todo el
   detalle en `SETUP.md`.

## Notas

- `setup_check.py` es idempotente y no imprime secretos.
- `envs/` está **fuera** del repo (`../envs/`). `.env.<usuario>` es local y gitignoreado.
- Si `setup_check.py --full` falla el datalake con error de password → credenciales
  expiradas, rehacer paso 2 / consultar al equipo de datos.
- Windows: si `python` no anda, probá `py`.
