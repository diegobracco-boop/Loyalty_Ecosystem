---
name: configurar-entorno
description: "Configura el entorno local del pipeline de Loyalty para un analista que recién clonó el repo: credenciales del datalake, acceso a Google Drive, DSN ODBC y librerías. Invocar cuando el usuario dice 'configurar entorno', 'recién cloné', 'no puedo correr loyalty_sync', 'setup', o falla el sync por credenciales/DSN/Drive."
---

Guiás a un analista a dejar su máquina lista para correr `loyalty_sync.py`. El
diagnóstico canónico es `setup_check.py` — **no adivines el estado, corré el script**.

## Regla de credenciales (importante)

NO pidas, recibas ni escribas la **contraseña del datalake** ni tokens. Para eso el
analista corre él mismo un comando con el prefijo `!` (se ejecuta en su terminal, no
la ves vos). Vos sí manejás lo no-secreto: `pip install`, chequeo de DSN, correr los
scripts de diagnóstico, interpretar resultados.

## Pasos

1. **Diagnóstico inicial.** Corré `python setup_check.py`. Mostrá el reporte al
   analista. Cada línea `[FALTA]` tiene su remediación abajo. Si todo está `[OK]`,
   saltá al paso 6.

2. **Credenciales del datalake** (si `[FALTA] credenciales datalake`).
   Pedile que corra en su terminal:
   ```
   ! python configurar_datalake.py
   ```
   Le va a pedir USER y PASSWORD (sin eco) y los guarda en `envs/.env.<su-usuario>`
   (gitignoreado). Son las mismas credenciales de Metabase / equipo de datos.

3. **DSN ODBC** (si `[FALTA] DSN ODBC`).
   Tiene que existir un DSN de 64-bit llamado exactamente `DataLake Treasure ODBC`
   apuntando al Treasure Data / Presto. Se copia de la config que ya tiene el equipo
   de datos (Mariano Bujía). Decile eso; no lo podés crear vos.

4. **Librerías Python** (si `[FALTA] librerías Python` o `pyodbc`).
   Corré vos: `pip install -r requirements.txt`.

5. **Acceso a Google Drive** (si `[FALTA] Drive`).
   Preguntale si tiene el `service_account.json` compartido del equipo:
   - **Sí** → que lo copie a la carpeta del repo (`Loyalty_Ecosystem/service_account.json`).
     Es el método recomendado (no expira).
   - **No** → que corra:  `! python auth_drive.py`  → abre el navegador, autoriza con
     su cuenta @despegar.com, queda en `token_drive.json`.

6. **Verificación final.** Corré `python setup_check.py --full` (prueba conexión real
   al datalake y a Drive). Repetí desde el paso 1 hasta que dé `Entorno listo`.

7. **Cierre.** Confirmá que puede correr `python loyalty_sync.py`. Mencionale que
   los inputs de negocio (breakage esperado, diccionario de programas) se editan en
   la planilla de Drive *"Loyalty Ecosystem - Config"*, no en el repo — y que para
   cambios de código el flujo es branch + PR (el deploy es automático). Todo el
   detalle está en `SETUP.md`.

## Notas

- `setup_check.py` es idempotente y no imprime secretos — corrélo las veces que haga falta.
- `envs/` está **fuera** del repo (`../envs/` relativo a la carpeta del proyecto). El
  archivo `.env.<usuario>` es local y gitignoreado.
- Si `setup_check.py --full` falla la conexión al datalake con error de password, las
  credenciales pueden haber expirado → rehacer paso 2 / consultar al equipo de datos.
- Windows: si `python` no se encuentra, probá `py` o `python3`.
