# Instructivo — Automatización Cierre Mensual Loyalty

## Para qué sirve esta carpeta

Automatiza el cierre mensual de Loyalty: baja las 3 queries del Datalake, calcula las columnas derivadas, arma el archivo de cierre del mes (con Etapa 1 y Etapa 2 en el mismo libro), y completa `Asientos Cierre Loyalty.xlsx` — el archivo que lee Contabilidad.

Esta carpeta es **autocontenida**: tiene todo el código, las queries y los archivos de referencia que hacen falta. No depende de nada fuera de ella (salvo tus credenciales del Datalake, que van aparte — ver más abajo).

## Estructura de la carpeta

```
Automatizacion Cierre/
├── INSTRUCCIONES.md              <- este archivo
├── requirements.txt              <- dependencias de Python
├── config.yaml                   <- lo único que se edita cada mes (fechas, rutas)
├── .env.example                  <- plantilla de credenciales (NO completar acá)
├── run_cierre_backup_manual.py   <- primer script que corrés cada mes
├── escribir_asientos.py          <- segundo script (después del refresco de Excel)
├── pipeline/                     <- código: bajadas, cálculos, guardrails, escritura
├── pipeline_backup/              <- código: escritura del archivo de cierre, lectura post-refresco
├── queries/                      <- las queries SQL (Data / Control / Guardrail)
└── referencia/                   <- tipo de cambio, reglas de entidad legal, baselines
```

**Importante**: la carpeta del *mes que se está cerrando* (donde viven `Asientos Cierre Loyalty.xlsx` y el archivo de cierre) es OTRA carpeta, en SharePoint, y NO vive dentro de esta. Esta carpeta es el código (no cambia mes a mes); la carpeta del mes es la data (cambia cada mes). `config.yaml` conecta una con la otra.

## Preparación (una sola vez por persona)

1. **`config.yaml`**: copiá `config.yaml.example` a `config.yaml` (mismo directorio) y completá los valores marcados `<...>` (tu carpeta de SharePoint, el mes, etc.). `config.yaml` es personal/mensual y por eso está gitignoreado — no se versiona, cada persona tiene el suyo local.
2. **Python** con las dependencias instaladas:
   ```
   py -m pip install -r requirements.txt
   ```
3. **VPN / red de la empresa** conectada (hace falta cada vez que corrés el pipeline, no solo la primera vez) y el DSN ODBC **"Datalake Treasure ODBC"** configurado en Windows (pedí ayuda si no lo tenés armado — es el mismo que usa cualquier otra conexión al Datalake).
4. **Tus credenciales del Datalake, en un archivo aparte** (no en esta carpeta — ver la sección de abajo, es importante).

### Tus credenciales del Datalake — por qué van en otro lado

Esta carpeta está pensada para compartirse por SharePoint/OneDrive entre todo el equipo. Si tu usuario/contraseña del Datalake vivieran en un `.env` *dentro* de esta carpeta, se sincronizarían automáticamente con todos los que tengan acceso — es decir, cualquiera vería tu contraseña.

Por eso, el código busca tus credenciales en una ruta fija de **tu** usuario de Windows, fuera de cualquier carpeta sincronizada:

```
C:\Users\<tu.usuario>\.automatizacion_cierre\.env
```

Pasos (una sola vez, no hace falta repetirlo cada mes):
1. Creá la carpeta `C:\Users\<tu.usuario>\.automatizacion_cierre\`.
2. Adentro, creá un archivo llamado `.env` (mirá `.env.example`, en esta carpeta, para el formato exacto) con:
   ```
   DATALAKE_USER=nombre.apellido@ar.infra.d
   DATALAKE_PASSWORD=tu_contraseña
   ```
3. Listo — cada persona que use esta carpeta hace lo mismo con su propio usuario, sin pisar el de nadie más.

## Cada mes, antes de correr nada

1. **Duplicar la carpeta del mes anterior** (en SharePoint, `.../Control de Gestión - Loyalty/<año>/Cierre/`) hacia una carpeta nueva con el nombre del mes que se cierra — esto arrastra `Asientos Cierre Loyalty.xlsx` con el histórico acumulado, y el archivo de cierre con las fórmulas de Etapa 2 ya armadas. Renombrar el archivo de cierre al mes nuevo (ej. `Cierre 2026 06.xlsx` → `Cierre 2026 07.xlsx`).
   - Si el archivo duplicado todavía tiene tablas dinámicas (pivots) — quedan de meses viejos — hay que sacarlas a mano en Excel antes de seguir. Abrir el archivo con Python (`openpyxl`) en modo escritura con pivots adentro puede consumir 8+ GB de RAM y romper el archivo.
2. **Actualizar `config.yaml`**:
   - `cierre.anio` / `cierre.mes`: el mes que se está cerrando.
   - `cierre.hasta_override` (opcional): para un cierre parcial ("lo que va del mes") en vez del mes completo — ver más abajo.
   - `rutas.carpeta_cierre`: la ruta de la carpeta nueva del mes.
   - `backup_manual.archivo_cierre`: el nombre del archivo de cierre ya renombrado.
3. **Actualizar `referencia/TC_mensual.xlsx`** con el tipo de cambio del mes (mail de Finanzas) — es el único archivo de referencia que cambia todos los meses.
4. **Calcular Breakage Esperado a mano** (con la bajada de puntos expirados) y pegarlo en la solapa **"Breakage Esperado"** del archivo de cierre. Sin esto, SSP Facturación (y todo lo que depende de ella: Cobrand, Partners, Control de Pasivo ML) recalcula con un breakage viejo o vacío.

### Cierres parciales ("lo que va del mes")

`cierre.hasta_override` en `config.yaml` (formato `"YYYY-MM-DD"`) permite bajar datos hasta una fecha específica en vez del mes completo — por ejemplo `"2026-07-26"` trae todo lo cargado hasta el 25/07 inclusive (Hasta es siempre exclusive, por eso un día más). Sacar esa línea (o dejarla vacía) vuelve al comportamiento normal de mes completo.

## El flujo de trabajo

El cierre se corre con **2 scripts, con un paso manual en el medio** — no porque falte terminar algo, sino porque Excel necesita recalcular sus propias fórmulas entre uno y otro (ver la explicación técnica más abajo).

### 1. Bajar los datos y armar el archivo de cierre

```
py run_cierre_backup_manual.py
```

Este script:
1. Corre los guardrails (tipos de punto nuevos, columnas/cobertura de las queries) — si encuentran algo, frenan y te dicen exactamente qué revisar.
2. Baja las 3 queries del Datalake (Acumulaciones, Redenciones, Puntos Expirados) y guarda las bajadas crudas en `Auditoria/Bajadas`.
3. Chequea que los totales de puntos coincidan con los controles.
4. Calcula las columnas derivadas de Etapa 1.
5. Pega todo (bajadas + filtros + Diccionario de puntos) en el archivo de cierre del mes — con backup automático antes de escribir.
6. Guarda un estado intermedio para que el siguiente script no tenga que volver a bajar nada.

Al terminar, **frena con instrucciones** — todavía no toca `Asientos Cierre Loyalty.xlsx`.

Si un guardrail frena, el mensaje te dice qué revisar. Una vez resuelto, corré de nuevo agregando el flag correspondiente:
```
py run_cierre_backup_manual.py --aceptar-puntos-nuevos
py run_cierre_backup_manual.py --aceptar-cambios-queries
```

### 2. Refrescar el archivo de cierre en Excel

`openpyxl` (la librería que usa el código para escribir Excel) **no recalcula fórmulas** — solo escribe el texto de la fórmula y deja el último valor que Excel haya calculado antes. Por eso, antes de seguir:

1. Si todavía no lo hiciste, pegá Breakage Esperado a mano (ver arriba).
2. Abrí el archivo de cierre en Excel, refrescá con **Ctrl+Alt+F9**, y guardalo.

Recién ahí SSP Facturación, Cobrand, Partners, Control de Pasivo ML y Accounting quedan con los valores del mes nuevo — antes de refrescar, tenían valores viejos cacheados de la corrida anterior.

### 3. Completar y escribir Asientos

```
py escribir_asientos.py
```

Este script:
1. Recupera el estado guardado por el script anterior.
2. Lee, ya recalculadas, las columnas que antes había que completar a mano en Etapa 2: Puntos Valuados / DRO / DRO - up fronts / DRO -Fee + Descuentos (Generación) y Reconocimiento de Ingresos Diferidos ML (Redenciones / Redenciones SUBS).
3. Lee la solapa Accounting, ya recalculada.
4. Pega todo en `Asientos Cierre Loyalty.xlsx` — Accounting se pega **a valor** (es una copia exacta de la solapa homónima del archivo de cierre).

Si el número de filas leído no coincide con lo esperado (por ejemplo, si corriste el primer script de nuevo para otro mes sin correr este), el script frena con un error explícito en vez de pegar datos desalineados.

### 4. Revisar

- El resumen que imprime cada script al terminar — si dice "REVISAR" en algún control, no continuar sin entender por qué antes de mandarlo a Contabilidad.
- Abrir `Asientos Cierre Loyalty.xlsx` y confirmar que las filas nuevas se ven bien.

## Problemas comunes

- **Error de conexión al Datalake** (`pyodbc.Error`, timeouts, "Server returned nothing"): revisar la VPN y reintentar — suele ser transitorio. Si falla varias veces seguidas, puede ser un problema del lado del Datalake, no tuyo.
- **`PermissionError` / archivo bloqueado**: el archivo de cierre está abierto en Excel — cerralo (sin dejarlo en un estado "sin guardar" a medio reparar) y volvé a correr.
- **Excel dice "hemos encontrado un problema con el contenido" al abrir el archivo de cierre**: normalmente indica una referencia rota (vínculo externo viejo, tabla dinámica mal formada, o un AutoFilter desincronizado en alguna hoja) — no es normal, hay que investigar antes de seguir. Ver Bitácora Automatización Cierre (secciones 29, 34, 35) para varios casos ya resueltos.
- **El guardrail de puntos o de columnas frena**: no es un error del script — es el script haciendo su trabajo. Revisar el mensaje antes de forzar con el flag correspondiente.
- **Dudas de fondo sobre la lógica de negocio o el diseño**: ver `Bitacora Automatizacion Cierre.md` en la carpeta de trabajo (`Loyalty_cierre_contable`), o consultar con Rosario Arancedo (mantiene las queries y la lógica de negocio).

## Qué NO tocar sin avisar

Las queries SQL (`queries/`) las mantiene Rosario — si algo parece un bug de una query, casi siempre se puede resolver ajustando el código Python que la envuelve en vez de tocar el `.sql`. Si de verdad hace falta cambiar una query, confirmar con ella antes.
