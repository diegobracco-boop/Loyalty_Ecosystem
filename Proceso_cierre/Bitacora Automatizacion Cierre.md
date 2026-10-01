# Bitácora — Automatización Cierre Contable Loyalty


Documento vivo. Acá vamos guardando decisiones tomadas, mapeos hechos y dudas de lógica a medida que avanzamos con la automatización en Python/pandas. Última actualización: 2026-09-24.

**2026-09-24 — Reubicación del documento.** Se movió este archivo de `C:\Users\rosario.arancedo\Proyectos IA\Loyalty_cierre_contable\Bitacora Automatizacion Cierre.md` a `C:\Users\rosario.arancedo\despegar365\Control de Gestión - Loyalty\2026\Cierre\Automatizacion Cierre\Bitacora Automatizacion Cierre.md`, para que quede sincronizado en SharePoint.

## 1. Objetivo

Automatizar el cierre mensual de Loyalty en dos etapas:

- **Etapa 1** — Bajadas de Metabase, cálculo de columnas derivadas, pegado a valor en `Asientos Cierre Loyalty.xlsx`. Documentada en `Proceso Cierre.pdf`.
- **Etapa 2** — Procesos más calculados: SSP, Cobrand (MX/AR/BR), Partners, Manual Accrual, Control de Pasivo ML, Breakage Esperado, Accounting. **No estaba documentada en ningún lado** — se mapeó completa en esta sesión leyendo fórmulas directamente de los Excel.

## 2. Constraints inamovibles

- `Auditoria/Bajadas/` — las 3 bajadas crudas de Metabase se guardan tal cual vienen.
- `Asientos Cierre Loyalty.xlsx` — mismo formato, solapas y contenido (lo lee Contabilidad).
- La hoja "Breakage Esperado" del archivo `Breakage Esperado MM'YY.xlsx` debe quedar igual como output — la forma de calcularlo puede cambiar.
- Fuera de scope: `Subscripciones/`, `Revisiones adhoc/`, todo lo de "Canje Crypto" (Query/Redenciones Canje Crypto).
- **Las queries SQL de `Queries Data/` y `Queries Control/` no se modifican salvo pedido explícito de Rosario** — las mantiene ella.
- **El rango de fechas de las bajadas usa `Hasta` = primer día del mes siguiente al de cierre** (no el último día calendario del mes) — así están diseñadas las queries (`processing_date <= {{Hasta}}` sobre un timestamp; usar el último día del mes con `<=` truncaba a medianoche y descartaba casi todo ese día). Calculado en `fechas_cierre()` (`pipeline/config.py`), comentado también en `config.yaml`. Ver sección 25.

## 3. Mapa de archivos

### 3.1 `Cierre 2026 06.xlsx` (archivo de trabajo principal — candidato a eliminarse, reemplazado por el pipeline)

**Solapas etapa 1** (bajadas + filtros, documentadas en el PDF, versión actualizada 2026-07-16):

| Solapa | Filas reales | Notas |
|---|---|---|
| Query Acumulaciones | 112.397 | se reemplaza cada mes (no acumula histórico) |
| Query Redenciones | 266.505 | ídem, un mes |
| Breakage | 5.641 | bajada de puntos expirados de un mes |
| Acumulacion Non Tender | — | filtro de Query Acumulaciones por point_type general/GENERAL INTER/GENERAL LOCAL/LOCAL **Y partner="DP"** (agregado 2026-07-29, ver sección 38) — **se copian solo columnas A-S** (18 cols, hasta gb_basebi_2) |
| Redenciones | — | filtro de Query Redenciones por point_type="general" — **se copian solo columnas A-Y** (25 cols, hasta concatenado; legal_entity/moneda_local/cotizacion_usd/descuento_consumo_puntos_usd de la Query NO se copian) |
| Redenciones SUBS | — | filtro por point_type in [SUBSCRIPTION, SUBSCRIPTION_INT] — ídem A-Y |
| Redenciones Otros | — | filtro por los 11 point_types de "Diccionario" col B (excluye SUBS) — ídem A-Y |
| Diccionario | 13 filas | Point Type (código numérico) → Descripcion (string usado para filtrar) |

El PDF `Proceso Cierre.pdf` fue actualizado por Rosario para reflejar esto explícitamente (antes decía solo "copiar y pegar esa selección", ahora especifica el rango exacto de columnas).

**Tipo de cambio**: NO hay solapas "TC PROMEDIO"/"TC COBRAND" separadas — viven dentro de **"Control de Pasivo ML"**: B2="TC PROMEDIO" (filas 3-9, países x meses), B11="TC Cobrand (Cierre)" (filas 11-17). Para el mes de cierre, TC Cobrand = `=TC_Promedio` (mismo valor); meses pasados son valores distintos pegados a mano. **Regla de negocio (Caratula A49): todos los países usan TC promedio, salvo Argentina que usa TC de cierre.**

Cada hoja (Redenciones/SUBS/Otros) tiene una mini-tabla auxiliar manual `$AF$2:$AG$16` con claves tipo `BRBRASIL`→`='Control de Pasivo ML'!AI3` (TC del mes actual por Concat Entidad Legal), usada por VLOOKUP en las columnas calculadas.

**Columnas calculadas — Redenciones** (fórmulas verificadas, idénticas fila a fila):
- `Descuento por Consumo de Puntos` = `-IF(country_code="MX", (points_distribuidos*ratio_prd)/1.16, points_distribuidos*ratio_prd)` — ajuste 1.16 = IVA México.
- `Reconocimiento de Ingresos Diferidos ML` = `VLOOKUP(Concat Entidad Legal, 'Control de Pasivo ML'!$A$1:$AM$542, 35, FALSE) * points_distribuidos` — busca en un bloque de "Control de Pasivo ML" por Entidad Legal (columna 35 = mes de cierre), no está resuelto a qué línea exacta del bloque apunta (ver dudas).
- `Entidad Legal` = `VLOOKUP(country_code&product&business, 'Regla entidad Legal'!$A$1:$B$99, 2, 0)`.
- `Concat Entidad Legal` = `country_code & Entidad Legal`.
- `Producto` = `VLOOKUP(produto_agrupado, 'Regla entidad Legal'!$F:$G, 2, 0)`.
- `Reducción del pasivo` = `Reconocimiento_ML / VLOOKUP(Concat Entidad Legal, $AF$2:$AG$16, 2, 0)` (convierte a USD con el TC).
- `DRI` = `Descuento_por_Consumo + Reducción_del_pasivo`.
- Tabla de control `AJ:AM` (headers desactualizados) compara el total calculado acá contra `'Control de Pasivo ML'!AI<fila>`, restando además Redenciones Canje Crypto para MX/AR. Es un cuadre, no data transaccional.

**Redenciones SUBS**: mismas fórmulas Y-AE que Redenciones, **excepto** `Entidad Legal` = simplemente `=country` (sin VLOOKUP contra Regla entidad Legal). Sin tabla de control AJ:AM.

**Redenciones Otros**: `Descuento por Consumo de Puntos` idéntico. `Reconocimiento de Ingresos Diferidos ML` = `Descuento * VLOOKUP(Concat Entidad Legal, $AF$2:$AG$16, 2, 0)` — **lógica inversa a "Redenciones"** (acá multiplica por TC en vez de buscar en Control de Pasivo ML). `Entidad Legal` = `=pais` (sin VLOOKUP, igual que SUBS). `Reconocimiento de Ingresos Diferidos USD` = `=Descuento_por_Consumo` (mismo valor, sin transformar).

**Acumulacion Non Tender** — columnas calculadas:
- `Revenue` = `SUM(comision:descuentos) * (1 - % Pagado con Puntos)`.
- `Puntos Valuados` = si Revenue≥0: `-points * XLOOKUP(country_code, 'SSP Facturación'!B8:B14, C8:C14)`, si no 0.
- `DRO` = si Revenue>0: `PuntosValuados/(ABS(PuntosValuados)+Revenue)*Revenue`, si no `PuntosValuados`.
- `DRO - up fronts` = si Revenue≤0: `50%*DRO`, si no `DRO * comision/(comision+fee+descuentos)`.
- `DRO -Fee + Descuentos` = si Revenue≤0: `50%*DRO`, si no `DRO * (fee+descuentos)/(comision+fee+descuentos)`.
- `Entidad Legal` = doble VLOOKUP con fallback contra 'Regla entidad Legal' (por concat country+product+business, o por country+Entidad Legal+business).
- `Producto` = VLOOKUP contra 'Regla entidad Legal' F:G (con excepción manual: CFAR/FLIGHT → "Vuelos" fijo).
- `% Pagado con Puntos` = `-VLOOKUP(dsp_transaction_id, Redenciones!..., col="descuentos") / SUMIF(misma transacción, gb_basebi_2)` — cruza contra Redenciones por transacción.
  - ⚠️ **Bug detectado en el Excel**: en la fila 1000, el SUMIF usa `A1007` en vez de `A1000` (desfasaje de 7 filas dentro de la misma fórmula arrastrada). No asumir que el arrastre de fórmulas es perfecto — puede haber más casos.
- `Producto homologado` = VLOOKUP por business contra 'Regla entidad Legal' N:O.

**Regla entidad Legal** (537 filas) — no es una tabla única, son 5 mini-diccionarios lado a lado sin headers: A:B (país+producto+business → Entidad Legal), F:G (producto → nombre español), J:K (código producto → nombre español), N:O (business → categoría P&L), U:V (código país ISO → nombre país).

**Solapas etapa 2 (no documentadas en el PDF, mapeadas esta sesión):**

- **Caratula**: no es tabla, es el instructivo de proceso completo (incluye control de desvío SSP del 10%, roles: preparador Rosario Arancedo, revisor Diego Bracco, y un bloque "Check Queries" que compara bajada en Cierre vs Metabase).
- **Control de Pasivo ML** (422 filas): 14 bloques de roll-forward de pasivo por Entidad Legal (BR/AR/MX/EC/CO/PE/UY x Local/Travel), con conceptos `(+) Generación Non Tender/Manual/Partners/Cobranded`, `(-) Redención`, `(-) Breakage`, `Saldo`. El precio de redención es un **costo promedio ponderado móvil** (weighted average). Filas 401-420 = bloque **"Control"**: columna `Archivos` (AN) recalcula cada total desde cero cruzando las fuentes crudas (independiente del modelo waterfall) y columna `AO` = diferencia (debe dar ~0). Esto es lo que menciona el PDF ("revisar a partir de fila 403").
- **SSP** (pivots): calcula el costo real del punto (`Descuento/Puntos distribuidos`) por país y lo compara contra el SSP contractual ("standard"). **Control de desvío: `IF(ABS(desvío)>0.1,"REVISAR","OK")`** — el 10% mencionado en Caratula.
- **SSP Facturación**: SSP ajustado = `SSP_Calculado_país * (1 - Breakage Esperado del país)` — este es el costo por punto usado para devengamiento/facturación (distinto del SSP crudo).
- **Breakage Esperado** (dentro de este archivo, tabla chica 9x4): `C4:C9` son **valores pegados a mano** desde el archivo separado `Breakage Esperado MM'YY.xlsx` (sin ninguna fórmula ni vínculo). `D` = `1 - C` ("Se reconoce"). ⚠️ Header C2 dice "abril" en un archivo de junio — etiqueta desactualizada, verificar que el valor sí sea de junio.
- **Manual Accrual**: por país, `Amount USD` usa SSP crudo para categorías "DP"/general, pero SSP Facturación (ajustado) para "Otros Manuales"/subscripción — inconsistencia entre categorías dentro de la misma hoja.
- **Cobrand MX / AR / BR**: por tier de tarjeta, `Puntos` = SUMIF contra Query Acumulaciones, `Precio` contractual (hardcodeado por año de contrato), `SSP` = costo (usa SSP Facturación en AR/BR, recalculo manual distinto en MX), `Bank Revenue` = ingreso ponderado − SSP. Genera el asiento Concepto/Importe/Cuenta/Item que después referencia Accounting.
  - ⚠️ **Cobrand BR usa precio de un archivo externo congelado a feb-2025** (`Contratos con partners - precio de los puntos.xlsx`, vínculo externo `[1]`) — no se actualiza mes a mes.
  - ⚠️ **Cobrand AR tiene SUMIFS con rango hardcodeado hasta la fila 53.811 de Query Acumulaciones**, pero este mes Query Acumulaciones tiene 112.397 filas reales — riesgo de estar cortando datos.
- **Partners** (~15 partners): mismo patrón (Puntos, Precio, SSP, Partner Revenue) por partner, agregado a Concepto/Importe por país.
- **Accounting**: consolida todo lo anterior en Concepto/Cuenta/Item/Importe USD/Importe ML por país. Esta es la solapa que se copia (o debería copiarse) a `Asientos Cierre Loyalty.xlsx`.
- **Santander Bank**: asiento histórico **congelado desde 2022** (TC y SSP de esa fecha), separado del cálculo mensual vivo de Cobrand BR. Solo la conversión a moneda local (`Importe ML`) se actualiza cada mes con el TC corriente.
- **Regla entidad Legal**, **Query/Redenciones Canje Crypto**: ver arriba / fuera de scope.

### 3.2 `Breakage Esperado 06'26.xlsx` (en `Auditoria/`)

17 solapas, varias ocultas (backups históricos, no forman parte del flujo activo: "Breakage Esperado junio", "Breakage esperado BR/AR/MX", "Points Type", una solapa "Breakage" oculta de 680K filas).

- **Query Breakage**: bajada de puntos expirados (5.605 filas) + columna `Point Type` = VLOOKUP contra "Diccionario Point Type".
- **Solapas de país** (AR/BR/MX/CO/PE/EC 2025, también aparece UY en los datos): un bloque vertical por mes histórico, cada uno = pivot (fuente: Query Breakage) + tabla manual "% Expiración" = `Puntos Vencidos / Acumulación de puntos a la fecha`. **El mecanismo de "Acumulación" migró con el tiempo**: bloques viejos vinculaban a un archivo de Cierre externo cerrado de esa fecha (`[2]Control de Pasivo USD`), bloques recientes (2025-2026) usan la solapa local **"Acumulaciones"** (tabla chica de acumulados mensuales por país) vía SUMIFS — evita vínculos rotos.
- **Breakage Esperado**: fila 1 = fechas mensuales (ene-2022 a jun-2026). Filas 2-7 = `AVERAGE` rolling de 12 meses del % breakage "Total" de cada país (BR/AR/MX/EC/CO/PE). Filas 9+ = evolución mensual por país (Non Tender/Cobrand/Total), donde "Total" de la última columna = referencia directa a la celda "Total" del último bloque de la solapa de ese país (ej. `='BR 2025'!$E511`).
- **Confirmado**: las celdas que se pegan a `Cierre MM YYYY.xlsx!Breakage Esperado C4:C9` son exactamente las filas 2-7 de la última columna de esta solapa.

### 3.3 `Asientos Cierre Loyalty.xlsx` (output final, formato fijo)

Solapas: `Plan de trabajo, Control, Generacion, Breakage, Redenciones, Redenciones Subs, Redenciones Otros, Datos MxTravel, vlookup, TC, Accounting`.

**(2026-09-24) 2 solapas nuevas agregadas por Rosario, mapeadas esta sesión** — ver sección 47 para el detalle completo. No afectan el bloque de copiado/pegado a valor (Generacion/Breakage/Redenciones/Redenciones Subs/Redenciones Otros): son 100% fórmulas que se recalculan solas al abrir/refrescar, downstream de `Accounting`.

- **Generacion / Breakage / Redenciones / Redenciones Subs / Redenciones Otros**: fila 1 = subtotales de control, fila 2 = headers reales, datos desde fila 3. ~~acumulan histórico mes a mes (no se sobrescriben — confirmado por cantidad de filas: Redenciones tiene 184.864 filas acumuladas)~~ **CORREGIDO (ver sección 16, 2026-07-21): esto estaba MAL — era una suposición mía, no un hecho confirmado.** El archivo NO acumula histórico entre meses: cada mes se borra la base del mes anterior y se pega la del mes nuevo (una carpeta por mes, ver sección 15). Las 184.864 filas de Redenciones eran el volumen real de transacciones de UN solo mes, no de varios acumulados. Columnas después del bloque pegado arman el asiento contable (Cuenta, Subcuenta, RC, Producto2, Depto, Canal, Importe USD/ML, DEBE/HABER) vía VLOOKUP fijo contra las solapas `vlookup` y `TC` — **estas sí son fórmulas que se recalculan solas**, no se pegan a valor.
  - **"Generacion" — header real actualizado, versión final (releído 2026-07-17 13:17, después de la corrección de Rosario)**: A-R = 18 campos raw (sin `total_passengers_quantity`). **S=pct_pagado_con_puntos, T=Revenue, U=Puntos Valuados, V=DRO, W=DRO-up fronts, X=DRO-Fee+Descuentos, Y=Filtro P&L, Z=Entidad Legal, AA=Producto, AB=Points ABS** — Rosario corrigió el orden para que **coincida exactamente con "Acumulacion Non Tender"** (en vez de tener "% Pagado con Puntos" al final, como había quedado en la versión anterior). AC en adelante arranca el asiento fijo (EL, Cuenta, Subcuenta, RC, Producto2, Depto, Canal, Tipo de cliente, Tipo de cobro, Negocio, Fut, Importe contable USD, DEBE/HABER USD, TC, Up Front DEBE/HABER ML, Saldo, Comentario — y un segundo bloque espejo BG en adelante para "Fee + Descuentos"), sin cambios de posición respecto de antes.
    - **Chequeo de integridad (2026-07-17)**: como el reordenamiento de S-AB corrió las columnas Entidad Legal (Y→Z), Producto (Z→AA), DRO-up fronts (V→W) y DRO-Fee+Descuentos (W→X) una posición, revisé que las fórmulas fijas que las referencian por letra se hayan actualizado. **Están todas bien actualizadas, no se rompió nada**:
      - `EL` (AC): `=+VLOOKUP(Z3,...)` — Z ahora es Entidad Legal ✓ (antes era `Y3`, cuando Entidad Legal vivía en Y).
      - `Producto2` (AG): `...VLOOKUP(CONCATENATE(L3," ",AA3),...)` — AA ahora es Producto ✓ (antes era `Z3`).
      - `Importe contable USD` (AN, bloque Up Fronts): `=+W3` — W ahora es DRO-up fronts ✓ (antes era `V3`).
      - `Importe contable USD2` (BG, bloque Fee+Descuentos): `=+X3` — X ahora es DRO-Fee+Descuentos ✓ (antes era `W3`).
      - Fila 1 (subtotales de control): `V1=SUBTOTAL(V)` (DRO), `W1=SUBTOTAL(W)` (DRO-up fronts), `X1=SUBTOTAL(X)` (DRO-Fee+Descuentos) — todas apuntan a su propia columna, correctamente corridas. Los checks `AU47=+AN1-W1` y `BN66=+BG1-X1` también quedaron consistentes con las nuevas posiciones.
      - `RC` (AF) y `Tipo de cobro` (AK), que referencian columnas que NO se movieron (`AC`=EL, `I`=payment_type), quedaron sin cambios — correcto, no debían tocarse.
    - Con esto, el punto de decisión de la duda 3 (sección 5) queda resuelto: Rosario optó por reordenar "Generacion" para que coincida con "Acumulacion Non Tender", en vez de al revés.
  - Redenciones / Redenciones Otros tienen además un bloque "MxTravel" que hace VLOOKUP contra `Datos MxTravel` para transacciones con Entidad Legal = "MXTRAVEL".
- **TC**: 7 países (BR/AR/MX/EC/CO/PE/UY), cada celda es **referencia externa viva** a `Cierre 2026 06.xlsx!Control de Pasivo ML` (no se pega a valor — vínculo `[47]` en `xl/externalLinks`).
- **Accounting** (115 filas, 7 países: BR/AR/MX/EC/CO/PE/UY, no solo 3 como se pensaba): **100% fórmulas con vínculo externo** al archivo `Cierre 2026 06.xlsx` (mismas solapas Cobrand BR/AR/MX, Partners, Manual Accrual, SSP, Control de Pasivo ML, Redenciones Canje Crypto). **No se pega a valor, se vincula en vivo.**
  - Subcategorías por país: Brasil (Cobrand, Partner, Manual Accrual, Marketing), Argentina (Cobrand, Partner, Manual Accrual, Redención Crypto, Suscripción), Mexico (Cobrand, Partner, Manual Accrual, Redención Crypto), Ecuador/Uruguay (solo Manual Accrual), Colombia/Peru (Manual Accrual, Flash Points).
- **Datos MxTravel / vlookup**: diccionarios chicos usados por las fórmulas de asiento de las demás hojas.

## 4. Decisiones tomadas

**(2026-07-16) Etapa 1 — decisiones confirmadas por Rosario:**

1. **"% Pagado con Puntos" pasa a ser una bajada directa de Metabase**, ya no se calcula en Excel con VLOOKUP+SUMIF contra "Redenciones" (ahí vivía el bug de desfasaje de fila). Se agrega como columna nueva en "Query Acumulaciones" y se replica (por el filtro) en "Acumulacion Non Tender". En "Acumulacion Non Tender" queda pegada a valor en la **columna T**, empujando el resto de las columnas calculadas una posición a la derecha:
   - T = % Pagado con Puntos (valor, desde Metabase)
   - U = Revenue (fórmula: `SUM(comision:descuentos)*(1-T)`, ahora usa el valor de T en vez de recalcularlo)
   - V = Puntos Valuados, W = DRO, X = DRO - up fronts, Y = DRO - Fee + Descuentos, Z = Filtro P&L (clave concat), AA = Entidad Legal, AB = Producto, AC = Points ABS
   - AD = Producto homologado, AE = Pts > 0, AF = GB pts > 0 — **estas quedan en la misma posición que antes** (el corrimiento +1 por la inserción en T se compensa exactamente con la eliminación de la vieja columna "% Pagado con Puntos" que estaba en AC).
   - La columna vieja "% Pagado con Puntos" (calculada, con el bug) desaparece — reemplazada por la nueva columna de Metabase.
   - **Chequeo de referencias cruzadas (2026-07-17)**: se revisó el XML interno de `Cierre 2026 06.xlsx`, `Asientos Cierre Loyalty.xlsx` y `Breakage Esperado 06'26.xlsx` buscando cualquier fórmula que use "% Pagado con Puntos" fuera de la propia "Acumulacion Non Tender". **No hay ninguna fórmula activa que dependa de esta columna en otra solapa u otro archivo.** Único hallazgo: una tabla dinámica vieja/desactualizada (`TablaDinámica8`, en la solapa "Breakage" de `Cierre 2026 06.xlsx`, y su espejo en `Asientos Cierre Loyalty.xlsx`) tiene esta columna en su caché de datos (junto con las otras ~32 columnas de Acumulacion Non Tender), pero **sin usarla en ninguna fila/columna/dato del pivot** (no tiene rol asignado) y con un caché desactualizado (3.441 registros, muy por debajo del volumen real actual de ~112K-250K filas, última actualización por Diego Bracco). Conclusión: es seguro mover esta columna sin romper nada activo; la tabla dinámica vieja puede ignorarse (parece un remanente de revisión que no se refresca hace tiempo).
2. **Entidad Legal se calcula igual en las tres hojas** (Redenciones, Redenciones SUBS, Redenciones Otros): `VLOOKUP(country_code & product & business, 'Regla entidad Legal', 2)` — se elimina la variante simplificada (`=country`/`=pais`) que tenían SUBS y Otros. "Concat Entidad Legal" (`country_code & Entidad Legal`) se mantiene igual en las tres.
   - "Reconocimiento de Ingresos Diferidos ML" **NO se toca** — está bien que Redenciones (general) y Redenciones Otros lo calculen de forma distinta (uno vía Control de Pasivo ML, el otro vía Descuento×TC). No unificar esta parte.
3. Todo lo relacionado a **Canje Crypto se ignora** por completo (incluido el ajuste de la tabla de control AJ:AM que restaba Redenciones Canje Crypto para MX/AR).
4. **TC promedio = TC cierre, por ahora son independientes** (no hay que replicar la regla especial de Argentina con TC de cierre distinto al promedio). Ojo: es "por ahora" — puede cambiar más adelante, revisar si Rosario lo menciona de nuevo.
5. **"Reconocimiento de Ingresos Diferidos ML" (y las columnas que dependen de ella: "Reducción del pasivo" y "DRI") se sacan de etapa 1 y pasan a ser un paso extra de etapa 2**, porque dependen del "Precio Redención" de Control de Pasivo ML (roll-forward de saldo). Afecta a "Redenciones" (col Z/AD/AE) y "Redenciones SUBS" (col Z/AD/AE) — "Redenciones Otros" no se ve afectada (su cálculo es independiente, se queda en etapa 1). Detalle completo y tabla de columnas afectadas en `Pendientes Etapa 2.md`.
   - **Confirmado**: en etapa 1 se pega igual todo el resto en `Asientos Cierre Loyalty.xlsx` (Redenciones / Redenciones Subs), **dejando la columna Z vacía** hasta que el paso extra de etapa 2 la calcule y la complete.
6. **"Query Redenciones" — la columna "descuento_consumo_puntos_usd" (ya viene de Metabase) se reposiciona a la columna Y**. Como Y ya era la primera columna calculada en "Redenciones"/"SUBS"/"Otros" (`Descuento por Consumo de Puntos`, con la fórmula `-IF(country_code="MX",...)`), este cambio **no corre ninguna columna** — simplemente Y pasa de ser una fórmula calculada a ser un valor pegado directo de Metabase, en la misma posición. Aplica a las 3 hojas (Redenciones, Redenciones SUBS, Redenciones Otros), ya que las 3 heredan la columna Y del filtro sobre Query Redenciones.
7. **"Acumulacion Non Tender" — mismo tratamiento que Reconocimiento ML**: las columnas que dependen de "SSP Facturación" (etapa 2, que a su vez depende de Breakage Esperado) se sacan de etapa 1 y pasan a ser un paso extra de etapa 2. Ver detalle en `Pendientes Etapa 2.md`. Al igual que con Redenciones, en etapa 1 se pega todo en `Asientos!Generación` salvo estas columnas, que quedan vacías hasta el paso extra de etapa 2.

**(2026-07-17) Re-chequeo con el Excel ya guardado — mapeo real (reemplaza los puntos 8 y 9 anteriores, que estaban basados en una copia vieja sin guardar):**

8. **"Query Acumulaciones" — cambios reales confirmados**:
   - **Se eliminó la columna `total_passengers_quantity`** de la query. **Confirmado por Rosario (2026-07-17): es intencional**, para reducir el nivel de apertura innecesario de la query — reduce el volumen en ~20.000 filas.
   - **Nueva columna `pct_pagado_con_puntos`**, insertada justo después de `gb_basebi_2` (reemplaza al viejo cálculo con VLOOKUP+SUMIF con el bug de desfasaje — esta es la implementación real de la decisión 1).
   - **Nueva columna `descuento_consumo_puntos_usd`**, agregada al final del bloque de campos "core" (después de `legal_entity`). No se usa en ninguna fórmula de "Acumulacion Non Tender" — parece incluida solo para trazabilidad/auditoría a nivel Query, no se filtra hacia Acumulacion Non Tender (queda fuera del rango A-S).
9. **"Acumulacion Non Tender" — layout real resultante** (por el efecto combinado de sacar `total_passengers_quantity` e insertar `pct_pagado_con_puntos`, las posiciones NO quedaron como se había anticipado en la decisión 1 — la resta de una columna y la inserción de otra no cayeron en el mismo lugar):

   | Col | Contenido | vs. layout viejo |
   |---|---|---|
   | A-R | campos raw (18, sin `total_passengers_quantity`) | -1 col respecto al viejo A-S |
   | **S** | **pct_pagado_con_puntos** (valor, de Metabase) | nueva, ocupa el lugar que dejó `total_passengers_quantity` |
   | T | Revenue (`SUM(comision:descuentos)*(1-S)`) | **misma posición que antes** |
   | U | Puntos Valuados | misma posición que antes |
   | V | DRO | misma posición que antes |
   | W | DRO - up fronts | misma posición que antes |
   | X | DRO - Fee + Descuentos | misma posición que antes |
   | Y | Filtro P&L | misma posición que antes |
   | Z | Entidad Legal | misma posición que antes |
   | AA | Producto | misma posición que antes |
   | AB | Points ABS | misma posición que antes |
   | AC | Producto homologado | **se corrió una posición hacia arriba** (antes AD) — la vieja columna calculada "% Pagado con Puntos" (en AC) desapareció sin reemplazo en ese lugar, así que todo lo que venía después se corre -1 |
   | AD | Pts > 0 | antes AE |
   | AE | GB pts > 0 | antes AF |

   O sea: T a AB quedan **exactamente donde estaban** (el -1 de sacar `total_passengers_quantity` y el +1 de insertar `pct_pagado_con_puntos` se cancelan ahí), pero AC en adelante sí se corre -1 porque el reemplazo de "% Pagado con Puntos" no ocurrió en su vieja posición (AC) sino mucho antes (S).

10. **Corrección de mi lectura anterior sobre el rango de pegado a `Asientos!Generación`**: el PDF pasó de "columna A a la AC" a "columna A a la AB". Con el layout real de arriba, **esto NO excluye `pct_pagado_con_puntos`** (vive en S, y S está dentro del rango A-AB) — mi hallazgo anterior de una "tensión" era incorrecto, estaba basado en la copia vieja del archivo (sin guardar) donde el layout todavía no reflejaba estos cambios. Lo que el rango "A-AB" realmente hace es **excluir "Producto homologado" en adelante** (igual que el viejo "A-AC" excluía desde "Producto homologado" en su vieja posición AD) — es decir, el rango de pegado sigue teniendo el mismo alcance semántico ("todo hasta Points ABS"), solo cambió la letra porque el layout interno cambió. `pct_pagado_con_puntos` **sí se sigue pegando en Asientos**, ahora en la posición S en vez de AC.
   - ⚠️ **Punto real a confirmar con Rosario**: `Asientos!Generación` acumula histórico mes a mes con una estructura de columnas ya fija (heredada de meses anteriores, que sí tenía `total_passengers_quantity` en la posición 9 y "% Pagado con Puntos" al final, en AC). Si este mes se pega el nuevo layout de "Acumulacion Non Tender" **por posición** (A a AB tal cual), las columnas quedarían desalineadas contra los headers históricos de Asientos (ej. lo que hoy cae en la posición 9 — `payment_type` — pisaría la columna histórica "total_passengers_quantity"). Esto es un problema real para el proceso manual en Excel. **Para el pipeline Python no es un problema** porque vamos a mapear por nombre de columna, no por posición — pero hay que decidir qué hacer con el header "total_passengers_quantity" en `Asientos!Generación` (¿se elimina la columna del archivo final, o se deja vacía de acá en adelante?) y dónde debe vivir el header de `pct_pagado_con_puntos` en la estructura fija de Asientos.

## 5. Dudas de lógica pendientes — Etapa 1

1. ~~¿La eliminación de `total_passengers_quantity` de "Query Acumulaciones" es intencional?~~ **Resuelto**: sí, intencional (reduce apertura innecesaria de la query, ~20.000 filas menos).
2. ~~Estructura fija de `Asientos!Generación`~~ **Resuelto en parte**: Rosario ya actualizó "Generacion" — confirmado que `total_passengers_quantity` se eliminó del todo (no quedó como columna vacía) y los datos históricos se realinearon a la estructura nueva. Ver sección 3.3 para el header real completo.
3. ~~Orden de columnas entre "Acumulacion Non Tender" y "Generacion"~~ **Resuelto**: Rosario corrigió "Generacion" para que coincida exactamente con el orden de "Acumulacion Non Tender" (S=pct_pagado_con_puntos, T=Revenue, ..., AB=Points ABS). Se revisaron todas las fórmulas fijas que referenciaban columnas movidas (EL, Producto2, Importe contable USD ×2, subtotales/control de fila 1) y quedaron correctamente actualizadas — no se rompió nada. Detalle completo en sección 3.3.

_(sin dudas abiertas de etapa 1 por el momento)_

Preguntas de etapa 2 (SSP, Cobrand, Partners, Manual Accrual, Control de Pasivo ML, Breakage Esperado, Accounting) están en `Pendientes Etapa 2.md` — se retoman cuando cerremos etapa 1.

## 6. Próximos pasos

1. ~~Conexión con Metabase/Datalake~~ **Resuelta (2026-07-17)**: no se usa la API de Metabase — se conecta directo al Datalake (Treasure Data) vía ODBC, igual que el script `daily_sync_grego.py` de Gregorio Minetti. DSN confirmado: `Datalake Treasure ODBC`, usuario formato `nombre.apellido@ar.infra.d`. Probado y funcionando (`test_conexion_datalake.py`, en esta carpeta).
2. **Carpeta de producción creada**: `Proyectos IA/Cierre Loyalty - Pipeline/` — es la carpeta limpia que Rosario va a abrir y correr cada mes (NO mezclar con esta carpeta de trabajo/pruebas). Contiene `INSTRUCCIONES.md`, `config.yaml`, `run_cierre.py`, `queries/` (SQL de las 3 bajadas) y `pipeline/` (módulos, todavía esqueletos sin implementar). Por ahora solo cubre Etapa 1.
3. **Subcarpeta "Etapa 1 Backup Manual" agregada (2026-07-17)**, dentro de `Cierre Loyalty - Pipeline/`: variante de respaldo que hace todo lo del pipeline normal Y ADEMÁS pega las bajadas + filtros (pasos 1-2 de `Proceso Cierre.pdf`) en el archivo `Cierre MM YYYY.xlsx`, para que Rosario pueda seguir la Etapa 2 a mano (paso 3 en adelante del PDF) sin depender de que la automatización de Etapa 2 esté lista. No recalcula las columnas de fórmulas (Revenue, DRO, Entidad Legal, etc.) — esas ya viven en el Excel reutilizado mes a mes y se recalculan solas al abrir/refrescar. Contiene su propio `INSTRUCCIONES.md`, `run_cierre_backup_manual.py` y `pipeline_backup/escritura_cierre_manual.py` (esqueletos), reutilizando los módulos de `pipeline/` de la carpeta padre.
4. Conseguir el SQL de las queries de Redenciones y Puntos Expirados (solo tenemos el de Acumulaciones, `acumulaciones_con_pct_puntos.sql`, ya copiado a `queries/acumulaciones.sql`). Ojo: ese SQL todavía tiene `total_passengers_quantity` en el SELECT — falta reconciliar con la eliminación de esa columna ya aplicada en el Excel.
5. Implementar la lógica real dentro de `pipeline/` y `pipeline_backup/` (bajadas, columnas derivadas, escritura en Asientos, escritura en Cierre MM YYYY, validaciones) — hoy son solo esqueletos con TODO.
6. Validar output de etapa 1 contra el cierre real de 06/2026.
7. Retomar etapa 2 (`Pendientes Etapa 2.md`).

**(2026-07-17) Avance de implementación:**

- **Referencias extraídas** del Excel a `Cierre Loyalty - Pipeline/referencia/`: `regla_entidad_legal.xlsx` (5 mini-tablas separadas por hoja: entidad_legal, producto, producto_fallback, producto_homologado, paises), `diccionario_point_types.xlsx`, `TC_mensual.xlsx` (con los valores reales de junio 2026 ya cargados: BR=5.1617, AR=1483.45, MX=17.4877, EC=1, CO=3429.48, PE=3.4089, UY=40.12, por Concat Entidad Legal incluyendo las variantes TRAVEL).
- **`pipeline/config.py`** creado (carga `config.yaml`, resuelve rutas).
- **`pipeline/conexion.py`** implementado con la lógica probada de conexión al Datalake.
- **`pipeline/bajadas.py`**: `bajar_acumulaciones()` implementado — adapta `queries/acumulaciones.sql` reemplazando `{{Desde}}/{{Hasta}}/{{Pais}}/{{Partner}}` (sintaxis Metabase) por SQL parametrizado en Python, sin reescribir la query a mano (por el riesgo de error en una query tan larga). `bajar_redenciones()` y `bajar_puntos_expirados()` quedan con `NotImplementedError` hasta conseguir esos SQL.
- ⚠️ **Duda importante detectada, sin resolver**: la fórmula SQL de `pct_pagado_con_puntos` multiplica por 100 (`... * 100`), sugiriendo que es un número 0-100 (ej. `15` = 15%), no una fracción 0-1. La fórmula de Excel `Revenue = SUM(comision:descuentos)*(1-%PagadoConPuntos)` necesita una fracción (0-1) para dar bien. Si no se divide por 100 en algún punto, Revenue va a salir mal. No se pudo verificar con datos reales: la solapa "Acumulacion Non Tender" del archivo de prueba solo tiene 3.441 filas de datos reales (no las ~112K esperadas de junio — coincide con el caché desactualizado que ya habíamos detectado, o sea son datos viejos/de prueba, no el mes real todavía) y esa columna está vacía en todas. **Hay que confirmar con Rosario la escala correcta antes de implementar `etapa1_acumulaciones.py`.**

## 7. Queries reales — subidas por Rosario (2026-07-17)

Rosario organizó `queries/` (en `Cierre Loyalty - Pipeline/`) en dos subcarpetas:
- **`Queries Data/`**: las 3 queries de bajada (Acumulaciones, Redenciones, Puntos Expirados) — las que se guardan en `Auditoria/Bajadas`.
- **`Queries Control/`**: 3 queries de "sum points" — recalculan el total de puntos de forma independiente, para chequear que la bajada no perdió/duplicó nada (ver `pipeline/validaciones.py`).

**Duda de la sección anterior, resuelta**: la query real de Acumulaciones calcula `pct_pagado_con_puntos = COALESCE(SUM(descuento_consumo_puntos_usd) / NULLIF(SUM(gb_basebi_2) + ABS(SUM(descuentos)), 0), 0)`, **sin `*100`** — es una fracción 0-1, compatible directo con `Revenue = SUM(comision:descuentos)*(1-%PagadoConPuntos)`. No hace falta ninguna conversión de escala.

Notas de implementación:
- **Acumulaciones**: confirma el layout ya documentado (sin `total_passengers_quantity`, con `pct_pagado_con_puntos` y `descuento_consumo_puntos_usd` agregadas) — 22 columnas en la SELECT final. Tiene `{{Desde}}/{{Hasta}}/{{Pais}}/{{Partner}}`.
- **Redenciones**: 29 columnas en la SELECT final (incluye `gb_total_carrito`, `peso_producto`, `points_distribuidos`, `moneda_local`, `cotizacion_usd`, `descuento_consumo_puntos_usd`). Solo tiene `{{Desde}}/{{Hasta}}` (sin variables de país/partner).
- **Puntos Expirados**: 5 columnas (`Expiration_Date, country, tier, points_type_id, Points`), **sin ninguna variable de fecha** — no filtra por `transaction_date`, solo por `transaction_type = 'PE'`. **Confirmado con Rosario: es intencional**, no hace falta acotarla por fecha, se trae completa igual que en Metabase.

`config.yaml` ahora tiene una sección `queries` con las rutas a las 6 SQL (data + control). `pipeline/bajadas.py` reescrito: `bajar_acumulaciones()`, `bajar_redenciones()` y `bajar_puntos_expirados()` ya implementados (los 3, ya no quedan `NotImplementedError`).

`pipeline/validaciones.py` implementado: `chequear_sum_points_acumulaciones()`, `chequear_sum_points_redenciones()` (compara `points` y `points_distribuidos` contra `total_points_raw`/`total_points_distribuidos` de la query de control), `chequear_sum_points_puntos_expirados()`, `chequear_filas_vacias()` y `resumen_final()` (imprime OK/REVISAR por chequeo). Tolerancia de redondeo: 0.01.

## 8. Formato nuevo de TC — solapa "TC" en `Cierre 2026 06.xlsx` (2026-07-17)

Rosario armó una solapa nueva llamada **"TC"** dentro de `Cierre 2026 06.xlsx` (25 solapas en total ahora) con el formato en el que quiere ingresar el tipo de cambio de acá en adelante: 3 columnas sin encabezado — **A: país** (nombre completo: Brasil, Argentina, Mexico, Ecuador, Colombia, Travel, Peru, Uruguay), **B: clave concat** (`BRBRASIL`, `ARARGENTINA`, etc. — 15 filas, incluye las 7 variantes `*TRAVEL`), **C: TC** (hoy fórmula a `'Control de Pasivo ML'!AI3:AI9`, salvo Travel que es `1` constante y las filas `*TRAVEL` que son `=C2`/`=C3`/etc.).

**Verificado**: los valores calculados de esta hoja (BR=5.1617, AR=1483.45, MX=17.4877, EC=1, CO=3429.48, PE=3.4089, UY=40.12) coinciden exactamente con los valores reales de junio 2026 ya confirmados — Rosario corrigió la columna `AI` de "Control de Pasivo ML" para que cuadren.

**Acción tomada**: se reescribió `referencia/TC_mensual.xlsx` para adoptar este mismo formato de 3 columnas (antes tenía solo 2: `concat_entidad_legal`, `tc`, sin país). Nueva estructura: `pais | concat_entidad_legal | tc`, mismo orden de filas que la solapa "TC", con los valores de junio 2026 ya confirmados (valores constantes, no fórmulas — este archivo lo usa el pipeline en Python, no depende de `Cierre 2026 06.xlsx`).

## 9. `etapa1_acumulaciones.py` implementado (2026-07-17)

Antes de programar, se releyeron las fórmulas EXACTAS (no el resumen) de `Cierre 2026 06.xlsx`!Acumulacion Non Tender, fila 3, para no adivinar lógica contable:

- **Revenue (T)**: `=SUM(TablaANT[[#This Row],[comision]:[descuentos]])*(1-TablaANT[[#This Row],[pct_pagado_con_puntos]])` → `(comision+fee+descuentos)*(1-pct_pagado_con_puntos)`.
- **Producto (AA)**: `=IFERROR(IF(OR(product="CFAR",product="FLIGHT"),"Vuelos",VLOOKUP(produto,'Regla entidad Legal'!$F$1:$G$500,2,0)),VLOOKUP(product,'Regla entidad Legal'!$J$2:$K$10,2,FALSE))` — "Vuelos" fijo si `product` (columna G) es CFAR o FLIGHT; si no, VLOOKUP de `produto` (columna M, el campo tipo-lista de Metabase) contra la hoja `producto` de `regla_entidad_legal.xlsx`; si eso falla, fallback por `product` contra la hoja `producto_fallback`.
- **Filtro P&L (Y)**: `=CONCAT(B3,G3,F3)` = `country_code & product & business`.
- **Entidad Legal (Z)**: `=IFERROR(VLOOKUP(Y3,'Regla entidad Legal'!$A$1:$B$115,2,FALSE),VLOOKUP($B3&$AA3&$F3,'Regla entidad Legal'!$A$1:$B$113,2,FALSE))` — VLOOKUP por Filtro P&L contra la hoja `entidad_legal`; si falla, fallback por `country_code & Producto(AA, ya calculado) & business`. **Importante**: el fallback usa el "Producto" ya resuelto, no el `product` crudo — por eso Producto se calcula antes que Entidad Legal en el código. (Nota menor: el rango del VLOOKUP principal llega a fila $115 y el del fallback a fila $113 — discrepancia real del Excel, sin impacto porque en Python se usa la tabla completa en ambos casos.)
- **Points ABS (AB)**: `=ABS(D3)` = `abs(points)`.

Se confirmó además que los headers reales de A-R en "Acumulacion Non Tender" son exactamente los 18 campos raw de la query nueva (sin `total_passengers_quantity`), en el mismo orden — no hizo falta ningún reordenamiento al mapear por nombre de columna.

**Archivos creados**:
- `pipeline/referencias.py` (nuevo, compartido con el futuro `etapa1_redenciones.py`): `cargar_entidad_legal()`, `cargar_producto()`, `cargar_producto_fallback()`, `cargar_tc_mensual()` — leen las hojas de `regla_entidad_legal.xlsx` y `TC_mensual.xlsx` como diccionarios clave→valor.
- `pipeline/etapa1_acumulaciones.py` reescrito: `filtrar_acumulacion_non_tender(df, point_types)` + `calcular_columnas_derivadas(df)` (Revenue, Producto, Filtro P&L, Entidad Legal, Points ABS, todo vectorizado con `.map()`, sin loops fila a fila) + `procesar(df, point_types)` como wrapper.

**Probado con datos sintéticos** (caso CFAR, caso FLIGHT, caso VLOOKUP normal contra la tabla "producto", caso de un point_type que debe quedar afuera del filtro) — los 3 casos de Producto/Entidad Legal y el filtro de point_type dieron el resultado esperado. No se probó todavía contra un volumen real de Query Acumulaciones (pendiente cuando se conecte el pipeline completo).

**Fuera de este módulo, intencionalmente**: Puntos Valuados/DRO/DRO-up fronts/DRO-Fee+Descuentos (dependen de SSP Facturación, Etapa 2) y Producto homologado/Pts>0/GB pts>0 (no se pegan en Asientos, quedan fuera del rango A-AB).

## 10. `etapa1_redenciones.py` implementado (2026-07-17)

Igual que con Acumulaciones, se releyeron las fórmulas EXACTAS de `Cierre 2026 06.xlsx` en las 3 hojas (Redenciones, Redenciones SUBS, Redenciones Otros), fila 3.

**Confirmado**: el bloque raw A-X (24 campos) es idéntico en las 3 hojas y en el mismo orden que la query real (`processing_date`...`gb_basebi_2`) — sin sorpresas de reordenamiento. Los headers D/M/P están renombrados cosméticamente en "Redenciones Otros" (`country`/`pais`/`tipopago` en vez de `country_code`/`country`/`payment_type`) pero son el mismo dato subyacente.

- **Descuento por Consumo de Puntos (Y)** — igual en las 3 hojas. **Corrección (2026-07-20, avisada por Rosario)**: la fórmula `=-IF(country_code="MX",(points_distribuidos*ratio_prd)/1.16,points_distribuidos*ratio_prd)` que se había leído del Excel de prueba está **desactualizada** — esto ya lo teníamos resuelto en la sección 4, decisión 6 (2026-07-16: "la columna `descuento_consumo_puntos_usd` ya viene de Metabase... simplemente Y pasa de ser una fórmula calculada a ser un valor pegado directo, en la misma posición"), pero al escribir `etapa1_redenciones.py` la primera vez se volvió a implementar como cálculo en Python en vez de tomar el valor de la bajada. **Corregido**: ahora `Descuento por Consumo de Puntos` = `df["descuento_consumo_puntos_usd"]` directo, sin ningún cálculo — la query ya aplica el ajuste 1.16 de México internamente.
- **Entidad Legal (AA)**: la fórmula real en "Redenciones" es `=VLOOKUP(CONCATENATE(country_code,product,business),'Regla entidad Legal'!$A$1:$B$99,2,0)` — **sin fallback** (a diferencia de la de Acumulaciones). En el Excel de prueba, "Redenciones SUBS" y "Redenciones Otros" **todavía tienen el atajo viejo** (`=country` / `=pais`) — pero la decisión 2 de la sección 4 (confirmada 2026-07-16) dice explícitamente que las 3 hojas deben unificarse con el VLOOKUP completo. Se implementó la versión unificada (decisión > formula desactualizada de la copia de prueba).
- **Concat Entidad Legal (AB)**: `= country_code & Entidad Legal`, igual en las 3.
- **Producto (AC)**: `=VLOOKUP(produto_agrupado,'Regla entidad Legal'!F:G,2,0)`, igual en las 3, sin fallback.
- **Reconocimiento de Ingresos Diferidos ML (Z)**: en Redenciones/SUBS depende de `'Control de Pasivo ML'!$A$1:$AM$542` columna 35 (Etapa 2) → queda vacío en Etapa 1. En **Redenciones Otros** la fórmula real es `=Descuento_por_Consumo_de_Puntos * VLOOKUP(Concat_Entidad_Legal, $AF$2:$AG$16, 2, 0)` — la mini-tabla `$AF$2:$AG$16` resultó ser **exactamente** la misma tabla que ya reconstruimos en `referencia/TC_mensual.xlsx` (sección 8), así que se reutiliza `cargar_tc_mensual()` sin crear ninguna tabla nueva. Esto SÍ se calcula completo en Etapa 1 (confirma lo ya documentado en `Pendientes Etapa 2.md`: "Redenciones Otros" no depende de Etapa 2).
- **Reconocimiento de Ingresos Diferidos USD (AD, solo Otros)**: `=Descuento_por_Consumo_de_Puntos` (mismo valor).
- **Reducción del pasivo / DRI** (solo Redenciones/SUBS): no se pegan en Asientos (fuera del rango A-AC) y dependen de Z (Etapa 2) — no se calculan en este módulo.

**⚠️ Caveat de datos detectado** (los 3 códigos `IFOOD_RWB`/`IF_MISSION`/`IF_CAMPAI` que estaban en el Diccionario viejo pero no en el `CASE` de la query) → **RESUELTO de raíz en la sección 11** (2026-07-21): se rehizo toda la lógica del diccionario.

**Archivos**: `pipeline/etapa1_redenciones.py` (nuevo) — ver sección 11 para la versión final de la lógica de clasificación (la primera versión usaba el Diccionario viejo, ya reemplazada).

**Probado con datos sintéticos**: ajuste 1.16 para México, filtro de los 3 sub-conjuntos (general/SUBS/Otros) separando correctamente las filas, Reconocimiento ML vacío en Redenciones/SUBS vs. calculado en Otros, y el caso de un VLOOKUP de Entidad Legal sin match — confirmado que "Concat Entidad Legal" queda `NaN` limpio (no genera el string `"ZZnan"`) gracias a que la concatenación se hace con Series de pandas y no con `.astype(str)` manual.

## 11. Diccionario de puntos rehecho + guardrail de puntos nuevos (2026-07-21)

**Problema de fondo** (el caveat de la sección 10): la clasificación de redenciones en 3 hojas dependía del `diccionario_point_types.xlsx` estático (12 códigos), pero ese diccionario tenía códigos (`IFOOD_RWB`, `IF_MISSION`, `IF_CAMPAI`) que el `CASE` de la query de Redenciones no mapeaba — caían en `'general'` y se clasificaban mal. Además, la tabla origen `data.lake.clm_point_types` tiene la columna `accum_period` **mal cargada** (nula para códigos que deberían tener 18), así que no se puede usar para clasificar.

**Decisión de Rosario (2026-07-21) — lógica nueva, de cero**:
1. **La clasificación ahora es 100% por el `point_type` que ya sale mapeado de la query de Redenciones** (Rosario corrigió el `CASE` para que mapee bien todos los códigos con actividad). Regla: `general`→Redenciones, `SUBSCRIPTION`/`SUBSCRIPTION_INT`→Redenciones SUBS, **todo el resto (complemento)**→Redenciones Otros. Ya no hay lista hardcodeada de "Otros".
2. **Guardrail de puntos nuevos**: el primer paso del cierre baja de nuevo `data.lake.clm_point_types` (query `queries/diccionario_puntos.sql` = `select * from data.lake.clm_point_types`) y compara sus `code` contra el baseline del mes anterior (`referencia/diccionario_puntos.xlsx`). Si aparece un `code` nuevo, **el pipeline FRENA y lo lista**, para que Rosario decida el tratamiento y actualice el `CASE` de la query de Redenciones antes de seguir. Una vez resuelto, se acepta el nuevo baseline (`verificar(aceptar_nuevos=True)`) y la corrida continúa. Esto es lo que hace segura la definición de "Otros" por complemento: no puede colarse un `point_type` inesperado sin que el guardrail avise.
3. **`accum_period` se ignora** por completo (dato mal cargado en origen).

**Baseline inicial establecido (2026-07-21)**: se bajó la tabla completa — **107 códigos** — y se guardó como `referencia/diccionario_puntos.xlsx`. Estos 107 son el punto de partida "bendecido" (la query de Redenciones ya los mapea bien). De acá en adelante, cualquier código nº 108 dispara el guardrail.

**Archivos**:
- `queries/Queries Guardrail/diccionario_puntos.sql` (nuevo — carpeta nueva, decidida el 2026-07-21: esta query no es "Data" (no se pega en ningún lado) ni "Control" (no es un chequeo de sum points), es una tercera categoría de query — guardrails de esquema/diccionario. Si a futuro se suma la query de columnas para `validacion_queries.py`, también iría acá).
- `pipeline/diccionario_puntos.py` (nuevo): `bajar_diccionario_puntos()`, `cargar_baseline()`, `detectar_codes_nuevos()`, `guardar_baseline()`, `verificar(aceptar_nuevos=False)` (orquesta: primera corrida crea baseline; sin nuevos actualiza y sigue; con nuevos frena con `PuntosNuevosError` salvo `aceptar_nuevos=True`).
- `config.yaml`: sección `queries.diccionario_puntos` + `referencia.diccionario_puntos`; se sacó `referencia.diccionario_point_types` (obsoleto) y se reescribió el comentario de `point_types` (Otros = complemento).
- `pipeline/etapa1_redenciones.py`: `filtrar_redenciones_otros(df, point_types_general, point_types_subs)` ahora es por complemento; se eliminó `resolver_point_types_otros()`; `procesar_redenciones_otros(df, point_types_general, point_types_subs)` cambió de firma.
- `pipeline/referencias.py`: se eliminó `cargar_diccionario_point_types()` (ya no se usa).
- `referencia/diccionario_point_types.xlsx`: **obsoleto**, se elimina.

**Probado**: (a) guardrail — bajada idéntica al baseline no detecta nada, un código simulado se detecta y `PuntosNuevosError` se arma con el mensaje correcto; (b) clasificación por complemento — `FORTUNE` e `IF_MISSION` caen ambos en "Otros" (antes `IF_MISSION` se perdía), `SUBSCRIPTION`+`SUBSCRIPTION_INT` van a SUBS, `general` a Redenciones.

**Pendiente para run_cierre**: cablear `diccionario_puntos.verificar()` como primer paso. **Decisión tomada (2026-07-21) sobre cómo "aceptar" puntos nuevos**: se hace con el MISMO comando `run_cierre.py` + un flag `--aceptar-puntos-nuevos`, no con un script aparte ni un flag persistente en config (Rosario no quiere desviarse del proceso normal). Flujo: `py run_cierre.py` frena y lista los códigos nuevos con el mensaje exacto a correr → Rosario corrige el `CASE` de la query de Redenciones → corre `py run_cierre.py --aceptar-puntos-nuevos`, que en la MISMA corrida bendice el baseline nuevo (`verificar(aceptar_nuevos=True)`) y sigue el cierre completo. Ventaja sobre el flag de config: el `--aceptar-puntos-nuevos` es efímero (vale solo para esa corrida), no queda prendido para olvidarse de apagarlo. Falta implementar el parseo del argumento en `run_cierre.py` cuando se arme la orquestación.

## 12. Cambios reales en las queries de Acumulaciones y Redenciones (2026-07-21) + `validacion_queries.py`

Rosario avisó que había cambiado cosas en ambas queries de Data. Se re-leyeron los 2 archivos (`Acumulaciones cierre - con filtro de fecha general.sql`, `Redencion trazabilidad - con filtro fecha general.sql`) y se diffearon línea por línea contra la versión leída al principio de esta sesión (`Compare-Object` de PowerShell, no "a ojo").

**Resultado del diff**:
- **Acumulaciones**: **sin cambios** — diff vacío, byte a byte igual a la versión ya mapeada (22 columnas, mismas fórmulas). No requiere ningún ajuste en `pipeline/etapa1_acumulaciones.py` ni `pipeline/bajadas.py`.
- **Redenciones**: **un solo cambio real**, dentro del `CASE` que arma `point_type` en el CTE `final_base` — se agregaron 6 ramas explícitas: `IFOOD_RWB`, `IF_MISSION`, `IF_CAMPAI`, `IFOOD_WELCOME`, `IFOOD_PROMO`, `MISSIONS` (antes caían en el `ELSE 'general'`). **Esto es exactamente la corrección del caveat detectado en la sección 10** — Rosario ya lo arregló del lado de la query. El resto de la query (columnas, `descuento_consumo_puntos_usd`, joins, `tipopunto`) es idéntico. **No requiere ningún ajuste en `pipeline/etapa1_redenciones.py`**: la lógica de clasificación ya es por complemento (sección 11), así que absorbe el cambio automáticamente sin tocar código — es justamente el escenario para el que se diseñó.

**Paso nuevo: `pipeline/validacion_queries.py`** (guardrail de esquema, corre antes de bajar los datos reales). Dos chequeos:

1. **Columnas de las 3 queries de Data**: pide el esquema con `SELECT * FROM (<query>) AS _validacion_columnas LIMIT 0` (no trae filas, solo columnas — probado contra el Datalake real, responde rápido) y compara el conjunto de nombres contra el baseline del mes anterior (`referencia/columnas_queries.json`, JSON simple `{query: [columnas]}`, actualizado por el propio pipeline). Si hay columnas **agregadas o eliminadas** → `CambiosColumnasError`, lista el detalle. **Reordenar columnas NO frena** (el código ya mapea por nombre, no por posición — confirmado con un test que reordena y da `{}`).
2. **Cobertura del `CASE` de `point_type` en Redenciones**: chequeo **estático por texto** (sin conexión a datos) — extrae por regex la lista de códigos "no reembolsables/campaña" del `IN(...)` de la rama de cancelaciones (CTE `tipopunto`) y la lista de códigos explícitamente mapeados en el `CASE` de `point_type`; si hay algún código en la primera lista que no está en la segunda → `CoberturaPointTypeError`. Esto es justo el chequeo que habría detectado el bug de la sección 10 antes de que pasara desapercibido. **Probado**: sobre la query actual (ya corregida) da `[]` (pasa); simulando el bug viejo (sacando `IF_MISSION`/`IF_CAMPAI` del `CASE` a propósito) el chequeo los detecta correctamente.

**Baseline de columnas establecido (2026-07-21)**, corriendo `verificar()` contra el Datalake real con `LIMIT 0`:
- `acumulaciones`: 22 columnas (`processing_date` ... `descuento_consumo_puntos_usd`).
- `redenciones`: 29 columnas (`processing_date` ... `descuento_consumo_puntos_usd`, incluye `concatenado`/`legal_entity`/`moneda_local`/`cotizacion_usd` que el pipeline no usa).
- `puntos_expirados`: 5 columnas (`Expiration_Date, country, tier, points_type_id, Points`).

Las 3 coinciden exactamente con lo ya documentado en secciones anteriores — confirma que no hace falta tocar código esta vez.

**Archivos**:
- `pipeline/validacion_queries.py` (nuevo): `verificar(date_from, date_to, aceptar_cambios=False)`, `chequear_cobertura_point_type()`, `obtener_columnas_actuales()`, `detectar_cambios_columnas()`, `cargar_baseline_columnas()` / `guardar_baseline_columnas()`, excepciones `CambiosColumnasError` y `CoberturaPointTypeError`.
- `config.yaml`: `referencia.columnas_queries` (ruta al baseline JSON).
- `referencia/columnas_queries.json` (nuevo, baseline inicial ya generado).

**Pendiente para run_cierre**: igual que con `diccionario_puntos`, cablear `validacion_queries.verificar()` como paso 0 (antes que `diccionario_puntos.verificar()` o después, a definir el orden), y sumar su propio flag efímero — probablemente `--aceptar-cambios-queries` — al mismo `run_cierre.py`, siguiendo el patrón ya acordado en la sección 11 (mismo comando, no un script aparte).

## 13. `escritura_asientos.py` implementado (2026-07-21)

Antes de escribir código que modifica `Asientos Cierre Loyalty.xlsx` (176 MB, el archivo que lee Contabilidad), se inspeccionó a fondo su estructura real para las 4 hojas que Etapa 1 pega (Generacion, Redenciones, Redenciones Subs, Redenciones Otros).

**Hallazgo 1 — `ws.max_row` no sirve para saber dónde agregar filas**: el archivo tiene colas enormes de filas "fantasma" (con formato pero sin datos) después del último dato real — ej. Generacion reporta `max_row=211613` pero el último dato real está en la fila **3443**. Hay que usar otra fuente de verdad.

**Hallazgo 2 — esa fuente de verdad son las Tablas de Excel (ListObject)**: las 4 hojas tienen una Tabla definida cuyo `ref` coincide EXACTO con la última fila de datos real: `Tabla1` (Generacion, `A2:BP3443`), `Tabla2` (Redenciones, `A2:BH156096`), `Tabla28` (Redenciones Subs, `A2:AV3185`), `Tabla25` (Redenciones Otros, `A2:BH107229`). Verificado con un segundo escaneo fila por fila que la última fila real coincide exactamente. `escritura_asientos.py` usa el `ref` de la tabla (no `max_row`) para saber dónde empezar a escribir, y lo EXTIENDE después de pegar (si no, las filas nuevas quedan fuera de la tabla y rompen fórmulas que la referencian por nombre, ej. `Redenciones!AR1 = SUBTOTAL(9,Tabla2[Saldo Redenciones])`).

**Hallazgo 3 — los headers reales de destino NO coinciden literalmente con los nombres de columna que usa el código** (confirmado leyendo la fila 2 real de cada hoja):
- En las 3 hojas de Redenciones, Asientos llama `country` a lo que la query/DataFrame trae como `country_code`, `pais` a lo que trae como `country`, y `tipopago` a lo que trae como `payment_type`.
- "Redenciones Otros" además: `channel_condition` → `parentchannel`, y `Reconocimiento de Ingresos Diferidos ML` → `Descuento por Consumo de PuntosML` (mismo dato, nombre de columna distinto en el destino).
- "Generacion" no tiene este problema — sus headers coinciden literalmente con los nombres que produce `etapa1_acumulaciones.py`.

Por esto el mapeo en `escritura_asientos.py` es una lista explícita `(header literal en Asientos, columna del DataFrame)` por hoja, no una simple igualdad de nombres.

**Hallazgo 4 — regla de fórmulas vs. valores constantes, confirmada por Rosario (2026-07-21)**: en el bloque de asiento contable fijo (AC+ en Generacion, AD+ en Redenciones/SUBS/Otros), las celdas que son **valores hardcodeados** (ej. `Cuenta`=42101, `Subcuenta`="0000", `Comentario`=texto fijo) son **iguales para todas las filas** — se copian tal cual. Las celdas que son **fórmulas** (ej. `EL`=`VLOOKUP(Z3,...)`, `Importe contable USD`=`ROUND(...)`) se replican ajustando el número de fila de las referencias relativas (sin `$`), igual que un arrastre de Excel — las referencias con `$` (ej. `vlookup!$W$3:$X$19`, `TC!$B$4:$C$10`) quedan intactas a propósito. Confirmado celda a celda en Generacion fila 3: `AD3`/`AE3`/`AU3` son constantes, el resto (`AC3, AF3, AG3, AN3-AT3`) son fórmulas.

**Hallazgo 5 (no era un bug — confirmado por Rosario 2026-07-21)**: `Redenciones!AP1` y `Redenciones Subs!AP1` tienen un `SUBTOTAL` con rango que arranca muy por delante del final real de los datos (`AP184862:AP1048576` cuando los datos terminan en la fila 156096; `AP31951:AP1048576` cuando terminan en 3185). Inicialmente lo marqué como un error porque ese control da 0 en vez de sumar "DEBE ML". **Rosario confirmó que está bien formulado así, es esperado que algunas celdas de control den 0** — no hay que tocarlo. `escritura_asientos.py` no lo modifica de todos modos (solo agrega filas nuevas al final de la tabla, no toca la fila 1 de subtotales).

**Chequeo de seguridad antes de escribir código de escritura real**: como `Asientos Cierre Loyalty.xlsx` tiene vínculos externos vivos (`TC` y `Accounting` dependen de `Cierre 2026 06.xlsx`), y `openpyxl` reescribe el archivo COMPLETO al guardar (aunque no se toquen esas hojas), se lanzó una prueba de round-trip (abrir con `load_workbook` normal + guardar sin cambios, sobre una COPIA) para confirmar que los vínculos externos sobreviven intactos antes de arriesgar el archivo real. *(resultado de esta prueba: ver próxima entrada de la bitácora cuando esté disponible)*.

**Archivos**:
- `pipeline/config.py`: nueva función `ruta_cierre(*partes)` — resuelve rutas relativas a `rutas.carpeta_cierre` (la carpeta del mes), distinta de `ruta_absoluta()` (relativa a la carpeta del pipeline).
- `config.yaml`: nueva `rutas.carpeta_backups_asientos` (`Auditoria/Backups Asientos`).
- `pipeline/escritura_asientos.py` reescrito: `MAPEO_GENERACION` / `MAPEO_REDENCIONES` / `MAPEO_REDENCIONES_SUBS` / `MAPEO_REDENCIONES_OTROS` (listas explícitas header↔columna), `hacer_backup()`, `_ajustar_filas_formula()` (regex de arrastre), `_header_a_columna()`, `_pegar_hoja()`, `pegar_generacion()`, `pegar_redenciones()`, `pegar_todo()` (punto de entrada único: backup + abrir + pegar las 4 hojas + guardar).

**Probado** (sobre un `.xlsx` sintético chico, misma estructura que Generacion, no toca el archivo real): la extensión del `ref` de la Tabla, el pegado de 2 filas nuevas con nombres de columna, las columnas de Etapa 2 pendiente quedando `None` (porque el DataFrame simplemente no las trae), la fórmula de `EL` replicándose con el número de fila ajustado (`Z3`→`Z4`/`Z5`), y los valores constantes (`Cuenta`, `Comentario`) copiándose idénticos en ambas filas nuevas — todo dio lo esperado.

## 14. `fechas_cierre()` + bug real encontrado y corregido en la query de Acumulaciones (2026-07-21)

Rosario preguntó dónde se ingresan las fechas `Desde`/`Hasta` de las bajadas — no había ningún lado: `config.yaml` solo tenía `cierre.anio`/`cierre.mes`, y en las pruebas de esta sesión las fechas se habían estado pasando a mano (`date(2026,6,1)`, `date(2026,6,30)`), no desde config. Se cerró el hueco: **`pipeline/config.py` → `fechas_cierre()`** calcula `(date_from, date_to)` = primer y último día calendario del mes, a partir de `cierre.anio`/`cierre.mes` — sigue siendo cierto que `config.yaml` (mes/año) es lo único que se edita mes a mes, ahora también para las fechas de las queries.

**Bug real encontrado al implementar esto** (confirmado por Rosario, no intencional): dentro de `Queries Data/Acumulaciones cierre - con filtro de fecha general.sql`, el CTE `tipopunto` filtraba `processing_date >= Desde AND processing_date <= Hasta` (inclusive), pero las ramas `ACCUMULATION` y `CANCELLATION` (las que agregan los puntos reales por transacción, fuente de la columna `points`) filtraban con `< Hasta` (**exclusive**). Con `Hasta` = último día del mes (tal cual documenta el propio header de la query: `{{Hasta}} → Fecha fin ej: 2026-06-30`), esto excluía **todas las transacciones del último día del mes** en esas 2 ramas — un día entero de acumulaciones/cancelaciones se habría perdido silenciosamente cada cierre.

**Corregido**: se cambió `<` por `<=` en las 2 ramas de `Queries Data/Acumulaciones cierre - con filtro de fecha general.sql` (líneas ~186 y ~401), y en su query de control **`Queries Control/Acumulaciones cierre - Sum Points.sql`** (mismo patrón, mismas 2 ramas) — necesario para que el chequeo de cuadre (`pipeline/validaciones.py`) compare manzanas con manzanas; si solo se corregía la query de Data, el control habría quedado sistemáticamente desalineado por el volumen del último día de cada mes.

**Verificado que Redenciones (Data y Control) no tiene este problema**: ya era consistentemente `<=` en las 3 hojas/ramas donde filtra por fecha — el bug era exclusivo de Acumulaciones. Puntos Expirados no tiene filtro de fecha (no aplica).

## 15. Aclaración de diseño clave — la carpeta del mes NO es fija, se duplica hacia adelante (2026-07-21)

Rosario preguntó cómo queda el procedimiento completo del cierre mes a mes. Al responder surgió una aclaración importante que **corrige una suposición implícita** que veníamos arrastrando: pensábamos que `Asientos Cierre Loyalty.xlsx` era un archivo único que vivía para siempre en un solo lugar, acumulando filas indefinidamente. **No es así.**

**Confirmado por Rosario**: cada mes tiene su **propia carpeta**, que queda como una foto congelada con todo el histórico acumulado hasta ese mes — para poder consultar cualquier mes pasado sin depender de una única copia viva compartida entre todos los meses. El mecanismo real:

1. Rosario duplica a mano la carpeta del mes anterior (dentro de la carpeta de SharePoint compartida por el equipo: `C:\Users\rosario.arancedo\despegar365\Control de Gestión - Loyalty\<año>\Cierre\`, con una carpeta por año) y la renombra para el mes nuevo.
2. Actualiza `config.yaml` → `rutas.carpeta_cierre` (apunta a la carpeta nueva) y `cierre.anio`/`cierre.mes`.
3. Actualiza `referencia/TC_mensual.xlsx` a mano con el tipo de cambio del mes (mail de Finanzas) — sigue siendo el único archivo de referencia que cambia todos los meses.
4. Corre el pipeline.

**Corrección inmediata (ver sección 16): el punto 4 estaba mal entendido acá** — en esta entrada asumí que el pipeline "agrega las filas nuevas encima de lo ya heredado" (acumulación). Rosario corrigió esto enseguida: el archivo NO acumula, se reemplaza. Ver sección 16 para el detalle correcto y la reescritura de `escritura_asientos.py` que esto implicó.

**Ojo para cuando se implemente `run_cierre.py`**: la carpeta real de producción (SharePoint) todavía no se usó en ninguna prueba — todo lo hecho hasta ahora corrió contra `Loyalty_cierre_contable/Cierre 06.2026 COPIA PRUEBA` (una copia de prueba, sin relación con la ruta real de SharePoint). Antes de la primera corrida real hay que actualizar `config.yaml -> rutas.carpeta_cierre` a la ruta de SharePoint del mes correspondiente. **Confirmado por Rosario (2026-07-21): por ahora seguir probando contra COPIA PRUEBA, no tocar SharePoint todavía.**

**Archivos**: `INSTRUCCIONES.md` (carpeta `Cierre Loyalty - Pipeline/`) actualizado con una sección nueva "La carpeta del mes" que documenta este procedimiento, y una aclaración explícita de que `run_cierre.py` todavía no está terminado de cablear (para no dar a entender que ya se puede correr con un solo comando hoy).

## 16. CORRECCIÓN IMPORTANTE — Asientos NO acumula histórico, se REEMPLAZA cada mes (2026-07-21)

Justo después de la sección 15, Rosario corrigió algo que veníamos dando por sentado en varias entradas anteriores (secciones 3.3 y 13): **`Asientos Cierre Loyalty.xlsx` no acumula las bases de los meses.** Cada mes se borra la base pegada a valor del mes anterior y se inserta la del mes nuevo, para que el archivo (de esa carpeta/mes puntual) tenga **solo** los datos de ese mes. Del archivo heredado (por la duplicación de carpeta, sección 15) **solo se reutiliza la estructura** — headers, Tabla de Excel, y el patrón de fórmulas/valores del asiento contable — no su contenido.

Esto explica retroactivamente algo que había interpretado mal en la sección 13: los volúmenes grandes de filas que encontré en la copia de prueba (Redenciones 156.096 filas, Redenciones Otros 107.229, etc.) **no son histórico acumulado de varios meses** — es simplemente el volumen real de transacciones de **un solo mes** (Redenciones es a nivel transacción×producto×tipo de punto, así que un volumen de 100K+ filas por mes es perfectamente normal). Corrijo also la sección 3.3 más arriba en este documento: donde dice "acumulan histórico mes a mes (no se sobrescriben)" — **eso está mal, era una suposición incorrecta, no un hecho confirmado.**

**Reescritura de `pipeline/escritura_asientos.py`** (`_pegar_hoja`), mecánica nueva por hoja:
1. Capturar el patrón de fórmulas/valores constantes del bloque de asiento contable fijo, tomado de la **fila 3** (fila plantilla) — ANTES de borrar nada, porque una vez pisados los datos del mes anterior ya no queda de dónde copiarlo.
2. Escribir los datos del mes nuevo (bloque raw + calculadas) arrancando siempre en la fila 3 — pisa lo que hubiera ahí.
3. Para cada fila nueva, replicar la plantilla capturada en el paso 1 (fórmulas con el número de fila ajustado, constantes tal cual).
4. **Si el mes anterior tenía MÁS filas que el mes nuevo**, borrar el remanente (todas las columnas, de A a la última) para que no queden filas viejas colgando después de las nuevas.
5. Ajustar el rango de la Tabla de Excel (`ref`) al tamaño EXACTO del mes nuevo — puede crecer o achicarse respecto del mes anterior (antes solo se contemplaba que creciera).

**Bug real de openpyxl encontrado al implementar el paso 4** (importante, afecta cualquier escritura de celdas a `None`): `ws.cell(row=r, column=c, value=None)` **NO limpia la celda** — la implementación interna de openpyxl solo asigna el valor si `value is not None`, así que pasar `None` explícito es un no-op silencioso; la celda conserva lo que tuviera antes. Verificado con un repro mínimo. Esto habría sido un problema serio: tanto el borrado del remanente (paso 4) como cualquier columna que debe quedar vacía en una fila que YA tenía datos del mes anterior (ej. las columnas de Etapa 2 pendiente, si la celda ya tenía un valor viejo) se habrían quedado con el dato viejo en vez de vaciarse. **Corregido**: se agregó un helper `_set_cell(ws, row, col, value)` que asigna con `.value = valor` (atributo directo, sí limpia bien) y se usa en todos los lugares donde antes se llamaba a `ws.cell(..., value=...)` para escribir.

**Probado** (3 casos, sobre archivos sintéticos, sin tocar nada real):
- **Mes nuevo con MENOS filas que el anterior** (el caso crítico): las filas que sobran del mes anterior quedan completamente vacías (no solo la primera columna — se verificó las 31 columnas), la Tabla se achica a la medida exacta del mes nuevo.
- **Mes nuevo con MÁS filas que el anterior**: todas las filas nuevas con la fórmula del asiento contable correctamente ajustada por fila, la Tabla se agranda.
- **Mes con 0 filas nuevas** (por si algún filtro de Etapa 1 no trae ninguna transacción ese mes): se borra todo el remanente del mes anterior, la hoja queda con header y sin datos, Tabla con rango `A2:AB2` (0 filas de datos).

**Sin cambios**: el mapeo de columnas por nombre (con los alias de Redenciones/Otros), la detección de la última fila vía el `ref` de la Tabla (no `ws.max_row`), el backup con timestamp antes de escribir, y el trato de los 2 controles `AP1` que Rosario confirmó que están bien así (sección 13) — todo eso sigue vigente, solo cambió la mecánica de "agregar" a "reemplazar".

## 17. Investigación de performance — por qué `Asientos Cierre Loyalty.xlsx` es lento de abrir/guardar (2026-07-21/22)

Antes de arriesgar el archivo real con `openpyxl` en modo escritura, se lanzaron pruebas de round-trip (abrir+guardar sin cambios, sobre copias, nunca el original) para confirmar que los vínculos externos (`TC`/`Accounting` dependen de `Cierre 2026 06.xlsx`, 48 `externalLinkN.xml`) sobreviven intactos. Mientras se esperaba el resultado, surgió la pregunta de qué hace lento el archivo, y Rosario limpió manualmente "filas fantasma" (formato aplicado sin datos) en Excel.

**Filas fantasma antes/después de la limpieza de Rosario** (Ctrl+Fin → seleccionar desde la primera fila vacía real → Eliminar filas):

| Hoja | Fantasma antes | Fantasma después | ¿Se limpió? |
|---|---|---|---|
| Generacion | 208.170 (la más grande de las 4) | 372 | Sí |
| Redenciones | 28.768 | 28.768 | No (pendiente) |
| Redenciones Subs | 28.768 | 1.900 | Sí |
| Redenciones Otros | 3.552 | 3.552 | No (pendiente) |

Tamaño de archivo: 176 MB → ~159,8 MB (~9,3% menos). Ningún dato real se perdió (última fila real idéntica en las 4 hojas, las 4 Tablas de Excel siguen con su `ref` correcto).

**Hallazgo más importante — el verdadero cuello de botella no son las filas fantasma**: el archivo pesa 159,8 MB comprimido pero **~1,46 GB descomprimido**. Desglose de los archivos internos más pesados (vía `zipfile`, sin necesidad de abrir con `openpyxl`):

| Archivo interno | Tamaño descomprimido | Qué es |
|---|---|---|
| `xl/worksheets/sheet5.xml` (Redenciones) | 574 MB | la hoja más pesada |
| `xl/worksheets/sheet7.xml` (Redenciones Otros) | 420 MB | |
| `xl/calcChain.xml` | 182 MB | orden de cálculo de todas las fórmulas del libro |
| `xl/pivotCache/pivotCacheRecords1.xml` | 150 MB | caché de tabla dinámica (ver más abajo) |
| `xl/pivotCache/pivotCacheRecords4.xml` | 102 MB | ídem |

**Redenciones y Redenciones Otros son ~60 columnas × 100K+ filas reales cada una (≈9,4M y ≈6,4M celdas respectivamente)** — cada fila de transacción arrastra ~35 columnas de fórmulas del asiento contable. Esto es dato/fórmula legítimo, no desperdicio — no se puede "limpiar" sin perder información real. La limpieza de filas fantasma ayuda pero es secundaria comparada con este volumen.

**Hallazgo nuevo sobre las tablas dinámicas** (`pivotCacheRecords*.xml`, ~256 MB combinados): a diferencia de una tabla dinámica vieja/desactualizada encontrada en `Cierre 2026 06.xlsx` en una sesión anterior, **las 4 cachés de este archivo (`Asientos Cierre Loyalty.xlsx`) están vivas y al día** — sus `recordCount` (156.094 / 107.227 / 3.441 / 555) coinciden EXACTO con el volumen real actual de Redenciones / Redenciones Otros / Generacion / Breakage respectivamente, refrescadas por Diego Bracco (revisor) en la solapa "Control" (5 tablas dinámicas chicas, ej. `Control!A3:B12`). **No son basura, no se deben borrar sin hablar con Diego Bracco.** La palanca de tamaño sin tocar funcionalidad: desactivar "Guardar datos de origen con el archivo" en las opciones de cada tabla dinámica — el archivo deja de embeber la copia de ~256 MB de datos, a cambio de que Diego tenga que apretar "Actualizar" la primera vez que abre el archivo cada mes. Pendiente de charlar con él antes de aplicarlo.

**Estado del round-trip de seguridad**: se relanzó sobre el archivo YA limpiado (después de la limpieza de Generacion/Redenciones Subs) para medir tiempos reales con `time.perf_counter()` y confirmar que los vínculos externos sobreviven — en curso, sin resultado final todavía al momento de esta entrada.

## 18. Cambio de la query de Redenciones — menos filas, menos columnas, `legal_entity` pass-through (2026-07-22)

Rosario reescribió `Queries Data/Redencion trazabilidad - con filtro fecha general.sql` con dos objetivos: traer menos filas y menos columnas.

**Menos filas**: la query ahora agrega a un grano más grueso — el `GROUP BY` final ya no incluye `dsp_transaction_id` ni `transaction_code` como clave (se sacaron del todo), sumando `points`, `points_distribuidos`, `comision`, `fee`, `descuentos`, `gb_basebi`, `gb_basebi_2` y `descuento_consumo_puntos_usd` al nuevo grano (`processing_date, product, country_code, partner, point_type, business, country, produto_original, channel_condition, payment_type, produto_agrupado, concatenado, legal_entity, moneda_local`). Esto reduce sustancialmente el volumen de filas (ya no hay una fila por transacción, sino por esa combinación de dimensiones).

**Menos columnas**: se eliminaron del todo `dsp_transaction_id`, `gb_total_carrito`, `peso_producto`, `transaction_code`, `transaction_type`, `ratio_prd` (y `cotizacion_usd`, que no se pega pero también desapareció del `SELECT` final). La query final ahora tiene 22 columnas (antes 29): `processing_date, product, country_code, partner, points, point_type, points_distribuidos, business, country, produto_original, channel_condition, payment_type, produto_agrupado, comision, fee, descuentos, gb_basebi, gb_basebi_2, descuento_consumo_puntos_usd, legal_entity, concatenado, moneda_local`.

**`legal_entity` pass-through, reemplaza el VLOOKUP de "Entidad Legal"**: la columna `legal_entity` (ya existía en la query, calculada con un `CASE` sobre `business`/`product`/`country`) se reposicionó para quedar inmediatamente después de `descuento_consumo_puntos_usd` — mismo patrón que ya se usó con "Descuento por Consumo de Puntos" (decisión 2026-07-16): pasa de ser una columna que Python calculaba (VLOOKUP contra `Regla entidad Legal`, ver sección 10) a ser un valor pegado directo de la query. **Confirmado**: Rosario ya aplicó este mismo reordenamiento en las 3 hojas de `Cierre 2026 06.xlsx` (el archivo de fórmulas/referencia que se duplica cada mes) — ahí la columna aparece como `legal_entity` (minúsculas) en la posición **T**, inmediatamente después de `descuento_consumo_puntos_usd` (S). Esto confirma el rango de pegado nuevo: **de "Query Redenciones" se pegan las columnas A-T** (18 campos raw + descuento_consumo_puntos_usd + legal_entity), en vez de A-Y como antes.

**⚠️ Punto pendiente, sin resolver**: `Asientos Cierre Loyalty.xlsx` (el archivo DESTINO real que lee Contabilidad, no la referencia) **todavía no fue restructurado** — se verificó su header real (fila 2) en las 3 hojas y sigue con el layout viejo: tiene columnas para los 6 campos eliminados (`dsp_transaction_id`, `gb_total_carrito`, `peso_producto`, `transaction_code`, `transaction_type`, `ratio_prd`, en B/H/I/L/R/S) y "Entidad Legal" sigue en su posición vieja (AA, después de "Reconocimiento de Ingresos Diferidos ML"/"Concat Entidad Legal" en Z/AB), no al lado de "Descuento por Consumo de Puntos" (Y). Falta decidir con Rosario: ¿se restructura también `Asientos Cierre Loyalty.xlsx` (mover Entidad Legal, sacar las 6 columnas huérfanas — cambio más invasivo, similar al que se hizo con "Generacion" en su momento) o el pipeline simplemente deja esas 6 columnas vacías de acá en más y sigue pegando "Entidad Legal" en su posición vieja (AA), alimentada ahora por el pass-through en vez del VLOOKUP?

**Archivos**:
- `pipeline/etapa1_redenciones.py` reescrito: `CAMPOS_RAW` bajó de 24 a 18 campos (sin las 6 columnas eliminadas). Se eliminó `_entidad_legal()` (el VLOOKUP) — `Entidad Legal` ahora es `df["legal_entity"]` directo (pass-through), igual patrón que "Descuento por Consumo de Puntos". `Concat Entidad Legal` y `Producto` sin cambios de lógica. Ya no importa `cargar_entidad_legal` de `referencias.py` (se verificó que esa función sigue en uso por `etapa1_acumulaciones.py`, que no cambió — no se tocó `referencias.py`).
- **Probado**: `CAMPOS_RAW` confirmado en 18 campos sin ninguno de los 6 eliminados; `Entidad Legal` es pass-through exacto de `legal_entity` (incluido el caso de `legal_entity` nulo desde la query, que da `NaN` limpio en Concat Entidad Legal, no un string tipo "ZZNone"); filtrado por complemento en las 3 hojas sigue funcionando igual que antes.
- `escritura_asientos.py`: **sin cambios todavía** — sigue mapeando "Entidad Legal" a la posición vieja de Asientos (AA), que es donde hoy realmente vive esa columna en el archivo destino. Si se decide restructurar Asientos (ver punto pendiente arriba), hay que actualizar `MAPEO_REDENCIONES`/`_SUBS`/`_OTROS` para reflejar el header nuevo.

**Decisión de Rosario (2026-07-22) sobre el punto pendiente**: SÍ va a restructurar `Asientos Cierre Loyalty.xlsx` (ella misma, a mano) — pero primero pidió mapear todos los cambios y revisar el archivo completo `Cierre 2026 06.xlsx` por si algo se rompió, aunque sea en partes de Etapa 2. Ver sección 19 para el resultado de esa revisión. También avisó que ya actualizó `Proceso Cierre.pdf` con el nuevo rango de pegado.

**Además, un segundo cambio importante que no se había registrado explícitamente**: al restructurar las 3 hojas de `Cierre 2026 06.xlsx`, Rosario no solo reordenó columnas — también **renombró los headers de la Tabla de Excel**: lo que antes decía "Descuento por Consumo de Puntos" y "Entidad Legal" ahora son literalmente `descuento_consumo_puntos_usd` y `legal_entity` (los nombres crudos de la query, no una etiqueta en español). Esto tiene consecuencias para Etapa 2 — ver sección 19.

## 19. Revisión de integridad de `Cierre 2026 06.xlsx` tras el cambio de Redenciones (2026-07-22)

A pedido de Rosario, se hizo una revisión exhaustiva y de solo lectura de las 25 hojas de `Cierre 2026 06.xlsx` para confirmar que el cambio de la sección 18 (columnas eliminadas + reordenamiento + renombre de "Descuento por Consumo de Puntos"/"Entidad Legal" a `descuento_consumo_puntos_usd`/`legal_entity`) no rompió nada en Etapa 2.

**Lo bueno**:
- **Cero celdas con `#REF!`** en todo el workbook (ni en texto de fórmula, ni en valor cacheado de error).
- Las únicas referencias cruzadas hacia Redenciones/Redenciones SUBS/Redenciones Otros desde el resto del libro son **71 fórmulas, todas en "Control de Pasivo ML"**, y **todas usan referencias estructuradas de Tabla** (`TablaRed[points_distribuidos]`, `TablaRed[Concat Entidad Legal]`, etc.) — se ajustan solas al reordenamiento/eliminación de columnas, no dependen de la posición física. Ninguna otra hoja (SSP, SSP Facturación, Cobrand MX/AR/BR, Partners, Manual Accrual, Breakage Esperado, Accounting, Santander Bank) referencia estas 3 hojas directamente.
- Dentro de las propias hojas Redenciones/SUBS/Otros, la mini-tabla de control (`Z:AA`, TC por Concat Entidad Legal) y las fórmulas de verificación (`AF`/`AG` en Redenciones) tampoco dependen de la posición de columnas propias — apuntan a `'Control de Pasivo ML'!` por celda fija o son auto-copias dentro de `Z:AA`.

**⚠️ El problema real encontrado — 5 Tablas Dinámicas con caché desactualizado**: hay 3 pivotCaches (uno por cada tabla `TablaRed`/`TablaRedOtros`/`TablaRedSUBS`, refrescados por Diego Bracco antes de este cambio) que todavía tienen la lista VIEJA de 31 campos (incluye las 6 columnas eliminadas) y, más importante, **usan los nombres viejos de columna que ya no existen** (`"Descuento por Consumo de Puntos"`, `"Entidad Legal"`). 5 tablas dinámicas construidas sobre esos caches:

| Tabla dinámica | Vive en | Campo afectado |
|---|---|---|
| pivotTable2 (cache TablaRed) | SSP, B3:D11 | "Descuento por Consumo de Puntos" (dataField) |
| pivotTable3 (cache TablaRedOtros) | SSP, K3:N16 | "Descuento por Consumo de Puntos" (dataField) |
| pivotTable1 (cache TablaRedSUBS) | SSP, K22:N25 | "Descuento por Consumo de Puntos" (dataField) |
| pivotTable4 (cache TablaRed) | Redenciones, AD3:AE12 | "Entidad Legal" (rowField) |
| pivotTable5 (cache TablaRed) | Redenciones, AD17:AE26 | "Entidad Legal" (rowField) |

Ninguno de los 3 caches tiene `refreshOnLoad` — o sea, hoy siguen mostrando valores **congelados de ANTES del cambio**, no se auto-actualizan al abrir el archivo. **Ya hay evidencia de que esto va a doler**: en la hoja "SSP", con los valores cacheados actuales, ya aparecen `#N/A`/`#DIV/0!` en filas borde (fila "Total general" del pivot, y el país EC) — acotado por ahora, pero si alguien aprieta "Actualizar todo" en Excel, es esperable que Excel no pueda resolver los nombres viejos de campo contra el header nuevo, y el problema se generalice a toda la columna (que además alimenta `Control de Pasivo ML!$AM$3:$AM$9` en cascada, afectando el roll-forward de pasivo).

**Acción pendiente antes de refrescar esos 5 pivots**: reasignar manualmente el campo de fila/valor de cada uno para que apunte a `legal_entity` / `descuento_consumo_puntos_usd` (nombres nuevos) en vez de dejar que Excel intente resolver el nombre viejo solo.

**Hallazgos menores, no relacionados a este cambio (FYI, sin acción urgente)**:
- `Cobrand BR!E35` = `#DIV/0!` cacheado, preexistente, sin relación con Redenciones.
- Nombre de rango `_xlnm._FilterDatabase` de las 3 hojas apunta hasta columna W (no Y) — parece desactualizado de antes, bajo riesgo.
- Conexión huérfana `WorksheetConnection_Redemption Analitico` (9.380 filas) apuntando a una hoja "Redemption Analitico" que ya no existe en el libro — basura vieja, no vinculada a ningún pivotCache activo, se podría limpiar desde Consultas y Conexiones / Administrador de Nombres.

## 20. Rosario restructuró `Asientos Cierre Loyalty.xlsx` a mano — verificado y sano (2026-07-22)

Se releyó el archivo real después de que Rosario aplicara el cambio de la sección 18/19 directamente sobre `Asientos Cierre Loyalty.xlsx` (no solo sobre `Cierre 2026 06.xlsx`): sacó las 6 columnas (`dsp_transaction_id`, `gb_total_carrito`, `peso_producto`, `transaction_code`, `transaction_type`, `ratio_prd`) y movió "Entidad Legal" al lado de "Descuento por Consumo de Puntos" en las 3 hojas de Redenciones.

**Verificado, todo sano**: los headers quedaron exactamente como se esperaba (Entidad Legal en la columna que sigue a "Descuento por Consumo de Puntos", antes de "Reconocimiento de Ingresos Diferidos ML"/"Descuento por Consumo de PuntosML"). Más importante: **todas las fórmulas del bloque de asiento contable (EL, Cuenta, Subcuenta, RC, Producto2, Importe/DEBE/HABER ML) en las 3 hojas ya apuntan correctamente a las columnas nuevas** — ninguna quedó apuntando a la posición vieja. Las Tablas de Excel (`Tabla2`/`Tabla28`/`Tabla25`) tienen su `ref` exacto a la última fila real. La hoja "Generacion" no fue tocada y sigue sana.

**2 roturas reales encontradas y ya corregidas por Rosario**: `Redenciones!AJ1` y `Redenciones Subs!AJ1` (celdas de control/subtotal en fila 1, no en el asiento contable en sí) daban `#REF!` porque apuntaban a una de las 6 columnas eliminadas.

**Hallazgo viejo, no causado por este cambio (FYI)**: en "Redenciones Otros", la fórmula de la columna EL referencia `Tabla2` (la tabla de "Redenciones") en vez de `Tabla25` (la propia) — se repite en las 17.078 filas, parece un arrastre de copiar/pegar de antes de esta sesión. Funciona igual porque usa `#This Row`, pero es confuso — queda anotado por si en algún momento se quiere prolijar.

**Hallazgo crítico de performance — causa raíz encontrada y resuelta**: al restructurar Redenciones, el archivo bajó de 159,8 MB a 39,5 MB (-74%), pero cargarlo en modo escritura con `openpyxl` (necesario para `escritura_asientos.py`) igual llegó a consumir **23+ GB de RAM en 13 minutos y seguía subiendo** — hubo que cortar el proceso manualmente antes de arriesgar la máquina. Esto probaba que el tamaño del archivo NO era la causa principal.

**Decisión de Rosario**: sacó las hojas **"Control"** y **"Accounting"** de `Asientos Cierre Loyalty.xlsx` por completo (las guardó en un archivo aparte, `Solapa Accounting de Asientos.xlsx`) — eran las que concentraban los vínculos externos y, sobre todo, **5 Tablas Dinámicas con ~256 MB de cachés combinados** (ver sección 17, esas mismas tablas vivían en "Control").

**Resultado, probado con un vigilante de memoria externo (subprocess + psutil, con corte de seguridad automático a los 8 GB o 5 minutos, para no repetir el riesgo de la vez anterior)**:
- Archivo: 39,5 MB → **18,9 MB**. Contenido descomprimido interno: ~1,46 GB → **~0,157 GB** (9,3x menos).
- Pivots/cachés: **0** (antes 4 cachés / 5 tablas). Vínculos externos: 46 (quedan en "TC", antes 48).
- Carga en modo escritura: **15,8 segundos, pico de memoria 927 MB, crecimiento lineal y prolijo** — sin necesidad de cortar nada.

**Causa raíz confirmada**: las Tablas Dinámicas de "Control" (con sus cachés grandes) eran responsables del consumo descontrolado de memoria — `openpyxl` en modo escritura reconstruye/retiene los pivot caches de forma muy costosa. El tamaño del archivo en sí, y los 46 vínculos externos restantes, no generan ningún problema. Con "Control"/"Accounting" afuera, el archivo es perfectamente manejable con `openpyxl` en modo escritura, sin riesgo para la máquina.

**⚠️ Punto a tener en cuenta (no resuelto, no es código)**: sacar "Accounting" de `Asientos Cierre Loyalty.xlsx` es un cambio de alcance respecto a la constraint original documentada ("mismo formato, solapas y contenido idéntico — lo lee Contabilidad", sección 2). "Accounting" era la solapa que consolida todo en Concepto/Cuenta/Item/Importe por país (sección 3.3) — si Contabilidad depende de recibir esa información dentro del mismo archivo, hay que confirmar cómo se le sigue entregando ahora que vive en `Solapa Accounting de Asientos.xlsx` (¿se manda como archivo aparte, se pega en otro lado, etc.?). No es una pregunta técnica de este pipeline, es un tema de proceso/entrega que Rosario ya debe tener resuelto o en mente.

**Archivos**: no hubo cambios de código en esta sección — solo verificación e investigación de performance sobre archivos que Rosario ya modificó a mano. `escritura_asientos.py` sigue sin necesitar cambios de lógica (nunca tocó Control/Accounting), pero ahora sí es seguro asumir que `load_workbook()` en modo normal funciona sin riesgo sobre este archivo restructurado.

**Confirmación aislando la variable (2026-07-22)**: Rosario volvió a agregar "Accounting" a `Asientos Cierre Loyalty.xlsx` (dejando "Control" afuera) para confirmar cuál de las 2 hojas era realmente la causa. Resultado del mismo test con vigilante de memoria:
- **Solo "Accounting" (sin "Control")**: 18,83 MB de archivo, 47 vínculos externos, **0 pivots** — carga en modo escritura: **15,95 s, pico de 918,6 MB**, curva lineal. Prácticamente idéntico al caso sin ninguna de las 2 hojas (15,8 s / 927 MB).

**Confirmado sin ambigüedad**: la causa raíz es específicamente la hoja **"Control"** (por sus 5 tablas dinámicas), no "Accounting" ni sus vínculos externos. Rosario puede mantener "Accounting" dentro de `Asientos Cierre Loyalty.xlsx` sin riesgo de performance — "Control" es la que debe quedar afuera (o resolverse de otra manera, ej. sin tablas dinámicas, si hace falta más adelante).

## 21. `run_cierre.py` implementado y probado (2026-07-22)

Con el problema de performance resuelto (sección 20), se armó el orquestador que faltaba — hasta ahora todos los módulos de Etapa 1 estaban implementados y probados por separado, pero no existía un punto de entrada único.

**Flujo cableado**: `pipeline.diccionario_puntos.verificar()` → `pipeline.validacion_queries.verificar()` → `pipeline.bajadas` (3 queries + guardado en Auditoria/Bajadas con el mes en el nombre del archivo, ej. `redenciones_2026_06.xlsx`) → `pipeline.validaciones` (chequeo de sum points) → `pipeline.etapa1_acumulaciones.procesar()` → `pipeline.etapa1_redenciones.procesar_redenciones/_subs/_otros()` (+ chequeo de filas vacías en "Entidad Legal"/"Producto" de las 4 hojas) → `pipeline.escritura_asientos.pegar_todo()` → `pipeline.validaciones.resumen_final()`.

**Flags de CLI implementados** (via `argparse`): `--aceptar-puntos-nuevos` y `--aceptar-cambios-queries`, tal como se había decidido en las secciones 11/12 — efímeros, solo valen para esa corrida. Cuando un guardrail frena, el script imprime el comando exacto a correr para aceptar y seguir.

**Probado exhaustivamente con mocks** (sin tocar el Datalake real ni escribir en el archivo real de Asientos):
- **Orquestación completa**: con 3 DataFrames sintéticos (uno por point_type: general/SUBSCRIPTION/FORTUNE), se confirmó que `diccionario_puntos.verificar()` y `validacion_queries.verificar()` se llaman con los argumentos correctos (incluyendo el rango de fechas de `fechas_cierre()`), que las 3 bajadas se guardan en auditoría con el nombre de archivo correcto (`acumulaciones_2026_06.xlsx`, etc.), que el filtrado por point_type separa bien las filas entre Generacion/Redenciones/SUBS/Otros (1 fila en cada una, como se esperaba), y que `escritura_asientos.pegar_todo()` recibe los 4 DataFrames correctos.
- **Los 3 caminos de frenado** (`PuntosNuevosError`, `CoberturaPointTypeError`, `CambiosColumnasError`): se confirmó que cada uno termina la corrida con `sys.exit(1)`, imprime un mensaje claro con el próximo paso, y — crítico — **nunca llega a bajar datos reales** (se verificó que `bajadas.bajar_acumulaciones` no se invoca en ningún caso de frenado).

**Archivos**:
- `run_cierre.py` reescrito por completo (antes era `print("TODO...")`).
- `INSTRUCCIONES.md` actualizado: sacada la advertencia de "todavía sin terminar de cablear", agregada la explicación de los 2 guardrails y los flags de aceptación, y aclarado que "Etapa 1 Backup Manual" sigue como alternativa para quien necesite continuar con Etapa 2 a mano.

**Pendiente — todavía no se corrió con datos reales**: todo lo de Etapa 1 (`etapa1_acumulaciones`, `etapa1_redenciones`, `escritura_asientos`) solo se probó con datos sintéticos chicos. Falta la primera corrida real contra el Datalake y contra el `Asientos Cierre Loyalty.xlsx` de la copia de prueba — es esperable que aparezcan sorpresas puntuales de datos reales (valores sin match en alguna tabla de referencia, etc.), no necesariamente errores de código.

## 22. `Etapa 1 Backup Manual` implementado y probado (2026-07-22)

Antes de hacer la primera corrida real de `run_cierre.py`, Rosario pidió revisar y terminar también la variante de respaldo (`Etapa 1 Backup Manual/`), que hasta ahora seguía siendo un esqueleto con TODOs y con documentación desactualizada (decía "pegar columnas A-Y" en Redenciones, cuando el rango real ahora es A-T tras el cambio de la sección 18).

**Mapeo fresco de `Cierre 2026 06.xlsx`** (no se asumió nada de investigaciones anteriores, se releyeron las 7 hojas de cero): confirmado que "Query Acumulaciones"/"Query Redenciones" son volcados planos sin ninguna fórmula (headers = nombres nativos de la query, sin alias), "Breakage" tiene 1 sola columna con fórmula (F="Aplica", VLOOKUP estructurado), y "Acumulacion Non Tender"/"Redenciones"/"Redenciones SUBS"/"Redenciones Otros" tienen una MEZCLA de fórmulas con referencia estructurada de Tabla (`TablaXXX[[#This Row],[columna]]`) y fórmulas con referencia de celda relativa simple (`T2`, `U2`, etc.) — headers confirmados letra por letra para las 7 hojas (ver docstring de `escritura_cierre_manual.py` para el detalle completo).

**⚠️ Hallazgo real durante el mapeo, no relacionado a ningún cambio reciente**: "Query Acumulaciones" tiene **~58.588 filas de datos reales por fuera del `ref` declarado de su Tabla** (`TablaQAc` dice terminar en la fila 53.811, pero hay datos reales hasta la fila 112.399, con solo un pequeño gap en blanco en el medio) — un remanente que quedó huérfano en algún momento anterior, nunca absorbido correctamente por la Tabla estructurada. Como el diseño es "reemplazar el mes, no acumular" (igual que Asientos), esto se resuelve solo: la detección de "última fila a borrar" no confía en el `ref` de la Tabla, escanea la hoja completa por la columna A — así el remanente huérfano también se limpia como parte normal del reemplazo mensual. Probado explícitamente con un caso sintético que reproduce el mismo patrón (Tabla con `ref` corto + datos reales más allá).

**Diseño clave, distinto de `escritura_asientos.py`**: para las 4 hojas filtradas (Acumulacion Non Tender, Redenciones, SUBS, Otros), el módulo NO usa el DataFrame ya calculado por Python (`etapa1_acumulaciones.procesar()` / `etapa1_redenciones.procesar_*()`) — usa solo las funciones de FILTRADO (`filtrar_acumulacion_non_tender()`, `filtrar_redenciones_general/subs/otros()`), porque en este archivo las columnas calculadas (Revenue, Entidad Legal, Producto, etc.) siguen siendo fórmulas en vivo, no valores pegados — se replican desde la plantilla de la fila 2, igual mecanismo que `escritura_asientos.py` (`_ajustar_filas_formula`/`_set_cell`, reutilizados por import directo en vez de duplicar código). Confirmado que las fórmulas con `[#This Row]` se copian **idénticas sin ajustar** (el token ya es relativo a la fila que sea), mientras que las fórmulas de celda simple sí se ajustan por fila — probado explícitamente con un caso sintético que mezcla ambos tipos en la misma hoja (igual patrón que "Redenciones" real).

**Archivos**:
- `Etapa 1 Backup Manual/pipeline_backup/escritura_cierre_manual.py` reescrito por completo: `HOJAS_RAW`/`HOJAS_FILTRADAS` (mapeos por hoja), `_pegar_hoja()` (genérica, header en fila 1 / plantilla en fila 2, a diferencia de Asientos que usa fila 2/3), `_ultima_fila_real()` (escanea en vez de confiar en el `ref` de la Tabla), `pegar_query_acumulaciones/_redenciones()`, `pegar_breakage()`, `pegar_acumulacion_non_tender()`, `pegar_redenciones_filtradas()`, `hacer_backup()` (carpeta propia, `rutas.carpeta_backups_cierre_mensual`, nueva en `config.yaml`), `pegar_todo_manual()` (punto de entrada único).
- `Etapa 1 Backup Manual/run_cierre_backup_manual.py` reescrito: mismo flujo que `run_cierre.py` (guardrails, bajadas, chequeos, columnas derivadas, pegado en Asientos) + el paso extra `escritura_cierre_manual.pegar_todo_manual()`. Mismos flags `--aceptar-puntos-nuevos`/`--aceptar-cambios-queries`.
- `config.yaml`: nueva `rutas.carpeta_backups_cierre_mensual` (`Auditoria/Backups Cierre Mensual`), separada de la de Asientos.
- Bug propio encontrado y corregido ANTES de dejarlo en el módulo: un primer intento de `guardar_con_backup()` intentaba "parchear" el dict de config en memoria para reusar `escritura_asientos.hacer_backup()` apuntando a otra carpeta — no funciona, porque esa función vuelve a leer `config.yaml` de disco por su cuenta. Se corrigió escribiendo una función `hacer_backup()` propia en este módulo.

**Probado** (sobre archivos sintéticos, sin tocar nada real): el caso de la Tabla con `ref` desactualizado + datos huérfanos (se limpian correctamente), el caso de fórmulas mixtas estructuradas/simples en la misma hoja (ambas se replican correctamente), y la orquestación completa de `run_cierre_backup_manual.py` con mocks (confirmado que llama a `pegar_todo_manual()` con los 3 DataFrames crudos correctos, sin calcular).

## 23. `Cierre 2026 06.xlsx` también tenía el problema de memoria — se separó en 2 archivos (2026-07-22)

Antes de dar por lista la implementación de la sección 22, Rosario preguntó algo clave: si `Cierre 2026 06.xlsx` (el archivo combinado, ~171MB, con Control de Pasivo ML/SSP/Cobrand/Partners/Manual Accrual/Accounting Y las 7 hojas livianas que escribe Python en el mismo libro) tenía el mismo riesgo de memoria que ya habíamos encontrado y resuelto en `Asientos Cierre Loyalty.xlsx` (sección 20).

**Se probó con el mismo método cuidadoso** (subprocess + psutil, corte duro a 8GB/6min): **confirmado que sí, y peor** — 12 tablas dinámicas (vs. 5 en Asientos) y ~208MB de cachés. La carga en modo escritura ya había llegado a 8,25 GB en 142 segundos, con la curva acelerándose sin señales de estabilizarse.

**Por qué la solución de Asientos (sacar "Control"/"Accounting" a un archivo aparte) NO aplica igual acá**: en Asientos, esas 2 hojas eran de consolidación/revisión que el pipeline nunca tocaba. Acá, `Cierre 2026 06.xlsx` es el archivo de TRABAJO ACTIVO de Rosario para Etapa 2 (Control de Pasivo ML, SSP, Cobrand, etc.) — no se puede simplemente sacarlas sin romper su flujo de trabajo manual.

**Solución propuesta por Rosario, mejor que la de Asientos**: separar el archivo en 2, al revés que en Asientos — sacar las hojas LIVIANAS (las que escribe Python) a un archivo nuevo chico, y dejar las hojas PESADAS (con las tablas dinámicas, que Python nunca necesita tocar) en el archivo original. Como el pipeline solo necesita escribir en las hojas livianas, nunca vuelve a abrir el archivo pesado — su tamaño deja de importar por completo. Rosario sigue usando el archivo pesado en Excel normalmente para Etapa 2 (el problema de memoria es específico de `openpyxl`, no de Excel real).

**Archivos nuevos creados por Rosario** (viven en `Cierre Loyalty - Pipeline/Etapa 1 Backup Manual/`, una ruta FIJA — no en la carpeta de SharePoint del mes como Asientos):
- `Cierre Backup Manual Bases.xlsx` — el liviano: Query Acumulaciones, Query Redenciones, Breakage, Acumulacion Non Tender, Redenciones, Redenciones SUBS, Redenciones Otros. Es el ÚNICO que Python abre/escribe.
- `Cierre 2026 06 Backup Manual.xlsx` — el pesado: Control de Pasivo ML, SSP, SSP Facturación, Cobrand MX/AR/BR, Partners, Manual Accrual, Breakage Esperado, Accounting, Santander Bank, Regla entidad Legal, Diccionario, TC, y las tablas dinámicas. Python NUNCA lo abre.

**Referencias cruzadas entre los 2 archivos** (ya mapeadas en la sección 19, ahora convertidas a vínculos externos de Excel en ambos sentidos):
- Las 71 fórmulas de "Control de Pasivo ML" (queda en el pesado) que referencian `TablaRed`/`TablaRedOtros`/`TablaRedSUBS` (ahora en Bases) — sintaxis `[2]!TablaRed[...]`.
- La mini-tabla `Z:AA` y la fórmula de "Reconocimiento de Ingresos Diferidos ML" dentro de Redenciones/SUBS/Otros (ahora en Bases) que referencian `'Control de Pasivo ML'!` (queda en el pesado) — sintaxis `='[1]Control de Pasivo ML'!AI3`.

**2 rondas de verificación** (siempre `read_only=True` para el archivo pesado, nunca modo escritura):
1. **Primera ronda**: encontró que "Breakage" no se había movido a Bases (quedó en el pesado), y que Bases se había llevado 6 tablas dinámicas por error (terminó pesando MÁS descomprimido — 407MB — que el archivo "pesado", 138MB) — contradecía el objetivo del split.
2. **Rosario corrigió**: movió "Breakage" a Bases, sacó las 6 tablas dinámicas de Bases, y aprovechó para eliminar un agregado manual viejo en "Query Acumulaciones" (resto de un ajuste del cierre anterior por datos no procesados) que era la causa del desajuste que tenía `TablaQAc` entre su `ref` declarado y los datos reales (~58.588 filas de diferencia, ver sección 22) — con esto, además de resolver el split, se resolvió ese problema pendiente de raíz (ya no hace falta que el escaneo defensivo de `_ultima_fila_real()` compense un desajuste real, aunque se deja como salvaguarda igual).
3. **Segunda ronda, todo confirmado en orden**: Bases con las 7 hojas exactas (sin faltantes ni extras), 0 pivots/pivotCaches, las 7 Tablas con `ref` alineado exacto a los datos reales (incluida `TablaQAc` ya corregida), vínculos externos verificados en ambos sentidos con el índice correcto. **Test de carga en modo escritura sobre Bases: 24,27 segundos, pico de memoria 1,8 GB** — muy por debajo del límite de seguridad, problema resuelto.

**Código actualizado**:
- `config.yaml`: nueva sección `backup_manual` (`archivo_bases`, `archivo_pesado`, `carpeta_backups`).
- `escritura_cierre_manual.py`: `ruta_cierre_mensual()` y `hacer_backup()` resuelven estas rutas. El resto del módulo (mapeos de columnas, nombres de hoja/Tabla, lógica de `_pegar_hoja`) no necesitó ningún cambio — el split de archivos no afecta la estructura interna de las 7 hojas que Python escribe.

**Probado end-to-end contra la ESTRUCTURA REAL** (sobre una COPIA de `Cierre Backup Manual Bases.xlsx`, nunca el original): `pegar_todo_manual()` con DataFrames sintéticos completó sin errores, pegando correctamente en las 7 hojas — confirma que los nombres de hoja/Tabla que asume el código coinciden con el archivo real tal como quedó después del split.

**Punto abierto — RESUELTO (2026-07-22)**: al armar la carpeta de prueba real (`Cierre 06.2026 TRIAL`, ver sección 24), Rosario puso los 2 archivos de Backup Manual DENTRO de esa carpeta del mes — confirmando que sí, van con una copia por mes (igual que Asientos), no en una ubicación fija del pipeline como se había configurado en un primer momento. Se corrigió `config.yaml` (`backup_manual.archivo_bases`/`archivo_pesado`/`carpeta_backups` ahora son rutas relativas a `rutas.carpeta_cierre`, vía `ruta_cierre()`) y `escritura_cierre_manual.py` (`ruta_cierre_mensual()`/`hacer_backup()` actualizados para usar `ruta_cierre()` en vez de `ruta_absoluta()`). Verificado que ambas rutas (Bases y Asientos) resuelven correctamente contra la carpeta TRIAL real.

## 24. Primera corrida real — carpeta "Cierre 06.2026 TRIAL" (2026-07-22)

Rosario armó una carpeta de simulación nueva para la primera corrida real de punta a punta: `Loyalty_cierre_contable/Cierre 06.2026 TRIAL/`, con `Asientos Cierre Loyalty.xlsx` (la versión ya restructurada: sin las 6 columnas eliminadas, Entidad Legal al lado de Descuento por Consumo de Puntos, con "Accounting" adentro y "Control" afuera) y los 2 archivos de Backup Manual (`Cierre Backup Manual Bases.xlsx`, `Cierre 2026 06 Backup Manual.xlsx`) copiados ahí adentro. `config.yaml -> rutas.carpeta_cierre` se actualizó para apuntar a esta carpeta nueva (reemplaza a `Cierre 06.2026 COPIA PRUEBA`, que fue la carpeta de pruebas usada durante toda la sesión hasta ahora).

Empieza por correr `run_cierre_backup_manual.py` (no `run_cierre.py` solo), ya que hace todo lo del pipeline normal más el paso extra de pegado en `Cierre Backup Manual Bases.xlsx`.

La corrida terminó sin errores (con `--aceptar-cambios-queries`, tras un reintento por un límite transitorio de memoria de 90GB en Presto). Generación: 19.503 filas. Rosario reportó 2 problemas al revisar el resultado en `Asientos Cierre Loyalty.xlsx`, corregidos en la sección 25.

## 25. Dos bugs reales encontrados tras la primera corrida completa (2026-07-22)

**1. Rango de fechas de las queries — `Desde`/`Hasta` debe ser exclusivo en `Hasta`.**

`fechas_cierre()` (`pipeline/config.py`) calculaba `Hasta` como el último día calendario del mes de cierre (ej. `2026-06-30`), y las 4 queries (Data y Control, Acumulaciones y Redenciones) filtran con `processing_date <= {{Hasta}}`. Como `processing_date` es TIMESTAMP, `<= DATE('2026-06-30')` en Presto trunca a `2026-06-30 00:00:00` — descarta casi todo el 30 (todo lo que no sea exactamente medianoche).

Corregido SOLO del lado de Python — las queries no se tocan (Rosario las mantiene ella, ver constraint): `fechas_cierre()` ahora devuelve `Hasta` = primer día del mes SIGUIENTE (ej. `2026-07-01`). Con el operador `<=` que ya tienen las queries, `processing_date <= DATE('2026-07-01')` en la práctica captura TODO el mes de cierre completo (el único caso que quedaría afuera es una transacción con timestamp exactamente `2026-07-01 00:00:00`, un caso de borde despreciable) — por eso alcanza con este único cambio, sin editar ningún `.sql`.

**2. `#REF!` en columnas calculadas de `Asientos Cierre Loyalty.xlsx` — bug real en `_ajustar_filas_formula()`.**

Rosario reportó `#REF!` en varias columnas de fórmula (Redenciones: AE, AG, AN; Redenciones Subs: AE, AG, AO, AP; Redenciones Otros: AE, AG, AI-AN; Generación: AJ, AL, BC, BE, BO, BP), correctas en la fila 1 o 2 y rotas de ahí en más.

Causa raíz: el regex `_CELL_REF_RE` de `pipeline/escritura_asientos.py` (usado por `_ajustar_filas_formula()` para "arrastrar" fórmulas al pegar cada fila nueva) no exigía que la referencia de celda empezara en un límite de palabra. Las fórmulas de estas columnas usan referencias estructuradas de Tabla (`Tabla2[[#This Row],[channel_condition]]`, `Tabla25[[#This Row],[...]]`, etc.) — y el regex matcheaba el SUFIJO del nombre de la tabla como si fuera una celda: en `"Tabla2[..."` matcheaba `"bla2"` (columna `"bla"`, fila `"2"`), y al ajustar la fila reescribía el nombre completo de la tabla (`Tabla2` → `Tabla3` → `Tabla4` → `Tabla5`... según cuántas filas de arrastre). Como esas tablas con numeración más alta no existen (o son otras tablas sin relación), la fórmula quedaba rota → `#REF!` a partir de la fila donde el número ya no correspondía a ninguna tabla real — coincide exactamente con lo reportado (1-2 filas "por casualidad" válidas, después roto).

Afecta solo a `Asientos Cierre Loyalty.xlsx` (tablas `Tabla1`/`Tabla2`/`Tabla25`/`Tabla28`, con sufijo numérico). Se revisó `Cierre Backup Manual Bases.xlsx` (mismo mecanismo, mismo `_ajustar_filas_formula()`) y no está afectado, porque sus tablas (`TablaANT`, `TablaRed`, `TablaRedSUBS`, `TablaRedOtros`, `TablaBr`, `TablaQAc`, `TablaQRed`) no terminan en un dígito — no hay nada para el regex viejo para matchear mal.

Fix: se agregó un negative lookbehind `(?<![A-Za-z0-9_])` antes del grupo de letras en `_CELL_REF_RE`, para que solo matcheen referencias de celda que empiezan en un límite real (no en medio de un nombre de tabla). Verificado con test sintético contra los patrones reales (`Tabla2[[#This Row],[channel_condition]]`, `Tabla25[[#This Row],[...]]`, arrastre de fila 3 a 19505) y contra la batería de regresión existente — todo OK.

**Pendiente:** como el archivo `Asientos Cierre Loyalty.xlsx` de la carpeta TRIAL ya quedó escrito con las fórmulas corrompidas (corrida anterior al fix), hace falta volver a correr el pipeline para que las reemplace por las correctas — el diseño de "reemplaza el mes" hace que esto sea automático, sin pasos manuales extra.

## 26. Conectado el síntoma "Vínculo Externo Recuperado" con el bug de la sección 25 + guardrail nuevo (2026-07-23)

Rosario reportó que, después de la corrida del 2026-07-22, al abrir "cualquier archivo Excel" del proyecto aparece el cartel de "recuperar datos", y cualquier celda con vínculo externo pasó a mostrar `[Vínculo Externo Recuperado]` en vez de apuntar al libro real.

**Investigado antes de tocar código** — se probó (sobre una copia, no el archivo real) si un `load_workbook()` + `wb.save()` puro de `openpyxl` corrompe los vínculos externos por sí solo: se comparó byte a byte todo `xl/externalLinks/`, `workbook.xml` (`<externalReferences>`) y `workbook.xml.rels` antes/después de un round-trip sin tocar celdas — **idénticos**. Conclusión: `openpyxl` en esta versión (3.1.5) preserva bien los vínculos externos en un guardado simple; la corrupción real viene de otro lado.

**Causa real confirmada**: el archivo `Cierre 06.2026 TRIAL\Asientos Cierre Loyalty.xlsx` (el mismo que quedó pendiente de re-generar al final de la sección 25) tiene, HOY, miles de fórmulas con referencias estructuradas a tablas que no existen (`Tabla3[`, `Tabla4[`, `Tabla5[`... incrementando por fila, hasta pasar `Tabla90`) — es exactamente el bug de `_ajustar_filas_formula()` de la sección 25, ya corregido en el código pero nunca "sanado" en el archivo (seguía pendiente el re-run). Un archivo con miles de referencias a tablas inexistentes rompe la integridad del paquete OOXML; Excel, al abrirlo, dispara una reparación global del archivo — y esa reparación, como daño colateral, invalida TODOS los vínculos externos del libro (no solo la parte rota), sustituyéndolos por el placeholder genérico `[Vínculo Externo Recuperado]`. Es decir: el síntoma que vio Rosario no es un bug nuevo ni un problema de `openpyxl` con vínculos externos — es la consecuencia visible, en Excel, del bug de la sección 25 que todavía no se había sanado en el archivo.

**Guardrail nuevo agregado** (para que esto no dependa de que el bug de arrastre de fórmulas esté 100% libre de casos futuros): `_validar_referencias_estructuradas()` en `pipeline/escritura_asientos.py` (y su equivalente en `pipeline_backup/escritura_cierre_manual.py`, reutilizando `_tablas_reales()`/`_TABLE_REF_RE` importados del primero). Corre justo antes de `wb.save()` en `pegar_todo()` / `pegar_todo_manual()`: escanea el bloque de fórmulas de cada hoja pegada, extrae toda referencia con forma `NombreTabla[...]` y la compara contra el set real de nombres de Tabla del workbook (`ws.tables` de todas las hojas). Si encuentra una referencia a una tabla que no existe, **frena con `ValueError` y NO guarda el archivo** — así cualquier bug futuro de arrastre de fórmulas (no solo este) se detecta antes de escribir el archivo real, en vez de descubrirse recién cuando alguien lo abre en Excel.

**Verificado**: se corrió el guardrail nuevo contra el archivo real corrupto de la carpeta TRIAL (cargado con `openpyxl`, sin guardar) — detectó correctamente las referencias rotas (`Tabla4`, `Tabla5`, `Tabla6`, `Tabla7`... en `Generacion!AJ`/`AL`), confirmando que el chequeo funciona sobre datos reales.

**Pendiente (sigue abierto, hereda de la sección 25)**: el archivo `Cierre 06.2026 TRIAL\Asientos Cierre Loyalty.xlsx` en disco sigue corrupto — el fix de código no repara retroactivamente un archivo ya escrito. Falta volver a correr el pipeline completo (que ahora, con el guardrail, además queda protegido si algo vuelve a salir mal) para regenerarlo limpio, o restaurar desde un backup de `Auditoria/Backups Asientos` anterior al 2026-07-22. Mismo chequeo pendiente para `Cierre Backup Manual Bases.xlsx` si se usó `run_cierre_backup_manual.py` en esa misma corrida.

## 27. Prioridad del proyecto = `Etapa 1 Backup Manual` + refresco de "Diccionario" en el archivo pesado (2026-07-24)

Rosario definió que, de ahora en más y hasta nuevo aviso, el foco del proyecto es la variante **backup manual** (`Etapa 1 Backup Manual/run_cierre_backup_manual.py`) — el pipeline "normal" (`run_cierre.py`, sin el paso extra de `Cierre MM YYYY.xlsx`) queda en standby, pero se sigue actualizando junto con `pipeline/` porque `run_cierre_backup_manual.py` reutiliza esos mismos módulos.

**Cambio agregado**: nuevo paso `[0b]` en `run_cierre_backup_manual.py`, entre el guardrail de diccionario de puntos (`[0a]`) y el guardrail de columnas/cobertura (ahora `[0c]`). Baja `Queries Data/Diccionario Puntos Excl.sql` y pisa la solapa **"Diccionario"** del archivo **pesado** (`backup_manual.archivo_pesado`, ej. `Cierre 2026 06 Backup Manual.xlsx`) — se borra lo que había antes y se pega el resultado de la query.

**Decisión de riesgo (Python nunca abría el archivo pesado)**: la sección 23 estableció que Python nunca abre el archivo pesado por el problema de memoria de `openpyxl` (8+ GB de RAM sin estabilizarse, por los pivots). Antes de tocar esto se inspeccionó el `.xlsx` como zip: la hoja "Diccionario" es chica (`A1:D16` en ese momento), sin Tabla propia y sin ningún `pivotCacheDefinition` que la use como fuente — segura de tocar sola. Se implementó `pipeline_backup/escritura_diccionario.py`, que **no usa openpyxl**: edita directamente el XML de `xl/worksheets/sheetN.xml` de la hoja Diccionario dentro del `.zip` del `.xlsx` (resolviendo el nombre de hoja → archivo interno vía `workbook.xml`/`workbook.xml.rels`, sin asumir `sheet16.xml` fijo), copiando el resto de las ~137 partes del zip sin tocarlas. Probado contra una copia del archivo pesado real (28 MB): el round-trip preserva las 18 hojas intactas y escapa bien caracteres especiales (`&`, `<`, comillas). Hace backup con timestamp antes de pisar, mismo patrón que `escritura_cierre_manual.hacer_backup()`.

**Cambio de formato de la hoja "Diccionario"** (decisión de Rosario): antes tenía 4 columnas — A=Point Type (id), B=code (mal rotulada "Descripcion" en el header), C=constante `"N/A"` (header "No aplica"), D=description (header "Comentarios"). La columna C se usaba como marcador en un VLOOKUP de `Cierre Backup Manual Bases.xlsx!Breakage!F` (`IFERROR(VLOOKUP(TablaBr[Point Type], [1]Diccionario!$A:$C, 3, 0), "Si")`) — si encontraba el Point Type devolvía el contenido de C ("N/A"), si no lo encontraba cae en "Si". Rosario decidió pisar directo con el formato de la query (A=id, B=code, C=description, 3 columnas) y ya reescribió esa fórmula de Breakage para no depender del esquema viejo — confirmado que no rompe nada porque además no se encontró ninguna otra fórmula en el archivo pesado ni en Bases que referencie "Diccionario" (barrido de las 18 hojas del pesado + las 7 de Bases).

**Nota**: la query `Diccionario Puntos Excl.sql` (que ya existía en `Queries Data/`, sin usarse desde ningún script) trae los point types cuyo `code` cae en el `CASE` de tratamiento distinto de `general`/`SUBSCRIPTION`/`SUBSCRIPTION_INT` — es decir, exactamente el conjunto de tipos "especiales" que antes vivía como lista estática en el Diccionario viejo (ver sección 11). No tiene relación con la lógica de clasificación de "Redenciones Otros" en Python, que sigue siendo el complemento calculado en `etapa1_redenciones.filtrar_redenciones_otros()` a partir de `config.yaml` — el Diccionario es solo una referencia manual para Rosario / el VLOOKUP de Breakage, Python no lo consulta para clasificar nada.

**Archivos tocados**: `config.yaml` (nueva entrada `queries.data.diccionario_excl`), `Etapa 1 Backup Manual/pipeline_backup/escritura_diccionario.py` (nuevo), `Etapa 1 Backup Manual/run_cierre_backup_manual.py` (nuevo paso `[0b]`, renumerado `[0c]` en adelante), `Etapa 1 Backup Manual/INSTRUCCIONES.md`.

## 28. Rosario re-unificó `Cierre 2026 06.xlsx` y sacó varios pivots — mapeo del estado actual + el pivot de "Manual Accrual" SÍ se usa (2026-07-24)

Rosario, a mano, (1) volvió a unificar `Cierre 2026 06.xlsx` (en `Cierre 06.2026 COPIA PRUEBA/`, no en la carpeta TRIAL) — dejó de estar separado en Bases+Pesado, ahora es un solo archivo de 25 hojas de nuevo — y (2) sacó varias tablas dinámicas reemplazándolas por tablas manuales, tanto ahí como en `Asientos Cierre Loyalty.xlsx`, dejando todo en el mismo lugar. Pidió releer ambos archivos, mapear los cambios y confirmar si el pivot de "Manual Accrual" se sigue usando.

**Nota de método**: no existe un snapshot "antes" guardado de estos 2 archivos exactos (son ediciones manuales de Rosario, no pasan por backup de Python) - el mapeo de abajo es del ESTADO ACTUAL (post-edición), inspeccionado como zip/XML sin abrir los archivos con openpyxl (37 MB y 55 MB, liviano hacerlo así). No es un diff línea a línea contra un "antes".

**Estado actual `Asientos Cierre Loyalty.xlsx`** (11 hojas): CERO pivots/pivot caches. 5 Tablas manuales: `Tabla1` (Generacion, A2:BP3443), `Tabla3` (Breakage, A2:AC557), `Tabla2` (Redenciones, A2:BB16682), `Tabla28` (Redenciones Subs, A2:AP3184), `Tabla25` (Redenciones Otros, A2:BB17080). Esto es BUENA noticia para el pipeline: `pipeline/escritura_asientos.py` solo busca Tablas (`ws.tables[...]`) para pegar y para el guardrail de referencias estructuradas — nunca dependió de pivots acá, así que sacarlos no rompe nada del lado Python.

**Estado actual `Cierre 2026 06.xlsx`** (25 hojas, incluye de nuevo `Query Acumulaciones`/`Query Redenciones` + las hojas de Etapa 2): quedan 5 pivot caches (antes eran 8 en la versión "pesado" de TRIAL) y 8 instancias de pivot en las hojas. Se sacaron los caches/pivots de `TablaBr` (Breakage), `TablaANT` (Acumulacion Non Tender) y `TablaRedSUBS` (Redenciones SUBS) — Breakage ahora tiene una tabla manual nueva (`Tabla10`, K3:S821) al lado de `TablaBr`. Quedan vivos: 3 pivots sobre `Query Acumulaciones` (cacheId 14 y 16), 1 sobre `Query Redenciones` (cacheId 15), 1 en `SSP` sobre `TablaRedOtros` (cacheId 20), 2 en `Redenciones` sobre `TablaRed` (cacheId 19), y **1 en `Manual Accrual`** (`TablaDinámica9`, `L2:O64`, cacheId 16, fuente=`TablaQAc`/Query Acumulaciones).

**Respuesta a la pregunta de Rosario: el pivot de Manual Accrual SÍ se usa, y bastante.** Cadena de dependencia confirmada leyendo fórmulas reales (no es un "por las dudas", son fórmulas vivas):

1. El pivot vuelca sus filas en `Manual Accrual!L2:O64` (L=código país/negocio, M=código partner, N=otro código, O=puntos).
2. Columna `P` (`Manual Accrual!P3` en adelante) es una fórmula `IFERROR(VLOOKUP($M,$Y$1:$Z$4,2,0), IFERROR(VLOOKUP($N,$U$2:$V$14,2,0), N))` que clasifica cada fila del pivot en una categoría ("Otros Manuales", "Non Tender", etc.) - depende de M/N, que son columnas del pivot.
3. Columna `D` (filas 4-42, ej. `D4`, `D5`, `D40`) son `SUMIFS` que agregan `$O:$O` filtrando por `$L:$L`/`$M:$M`/`$P:$P` — es decir, agregan DIRECTAMENTE la salida del pivot usando la columna P como categoría.
4. `E` depende de `D` (`(-VLOOKUP(...))*D4`), `F` depende de `E` (`E4*'Control de Pasivo ML'!$AM$4`).
5. Esos D/E/F/G de Manual Accrual (filas puntuales: 4,5,6,7,8,9-13,14-18,19-21,22-26,27-30,31-34) se consumen en:
   - **`Control de Pasivo ML`** (misma hoja del archivo, `Cierre 2026 06.xlsx`) — decenas de celdas en las columnas `AI:AM` (filas 28-410), ej. `AI28='Manual Accrual'!$D13`, `AI29='Manual Accrual'!$E13*AI11`.
   - **`Accounting`** de **`Asientos Cierre Loyalty.xlsx`** (vínculo externo `[47]` que apunta directo a este mismo `Cierre 2026 06.xlsx`) — filas 21-115, ej. `B21='[47]Manual Accrual'!E9+'[47]Manual Accrual'!E10`.
   - **`Pivots Asientos Loyalty 2026 06.xlsx`** (uno de los "otros dos archivos" que preguntó Rosario) — vínculo externo `[48]`, apuntando a una ruta vieja de SharePoint de este mismo archivo — mismas ~90 celdas en sus hojas `sheet9`/`sheet10`, ej. `'[48]Manual Accrual'!F9+'[48]Manual Accrual'!F10`. Es un vínculo desactualizado (apunta a una ruta de SharePoint, no al archivo local), pero la referencia POR NOMBRE de celda sigue viva en la fórmula.
   - **`Actuals vs RR.xlsx`** (el otro de "los otros dos archivos"): tiene un vínculo externo declarado a `Cierre 2026 05.xlsx` (mayo, viejo) cuya lista de hojas incluye "Manual Accrual", pero NINGUNA fórmula local realmente lo referencia — **no lo usa**.

**Conclusión**: sacar o romper el pivot de Manual Accrual rompería en cascada `Control de Pasivo ML` (mismo archivo) y el `Accounting` de `Asientos Cierre Loyalty.xlsx` (vínculo externo real y activo). `Pivots Asientos Loyalty 2026 06.xlsx` también lo referencia pero por un vínculo ya desactualizado (no es la ruta real del archivo actual). `Actuals vs RR.xlsx` no lo usa.

**Pendiente**: Rosario mencionó haber cambiado "varias fórmulas" además de sacar pivots — no hay snapshot previo de estos archivos para diffear formula por fórmula; si quiere un mapeo más fino de qué fórmula cambió respecto a qué, hace falta o bien decirme las hojas/celdas puntuales, o comparar contra un backup anterior a esta sesión de edición manual (no existe ninguno en `Auditoria/` de `COPIA PRUEBA`).

## 29. Segundo mapeo tras más cambios manuales — 2 referencias rotas encontradas + 1 masiva (2026-07-27)

Rosario sacó más pivots de `Cierre 2026 06.xlsx` (COPIA PRUEBA) y reescribió fórmulas (el archivo bajó de 54,7 MB a 41,7 MB; de 25 a 23 hojas — borró `Redenciones Canje Crypto` y `Query Canje Crypto`, las que memoria tenía marcadas como "no eliminar pero ignorar" — decisión de Rosario, ya no aplica esa nota). Pidió re-mapear, chequear referencias rotas, y confirmar si faltó sacar algún pivot. Mismo método que la sección 28 (zip/XML, sin abrir con openpyxl).

**El pivot de Manual Accrual (el que la sección 28 marcó como load-bearing) YA NO EXISTE** — Rosario lo sacó. Buena noticia: **lo reemplazó bien** - reescribió la columna D (filas 4-34) para leer directo de `TablaQAc` vía `SUMIFS(TablaQAc[points], TablaQAc[point_type], ...)` en vez de agregar sobre la salida del pivot (L:O). Esto es correcto y no depende de ningún pivot.

**PERO se encontraron 3 problemas reales, en orden de severidad:**

1. **`Breakage!P4:P5641` (~4929 celdas) usa un vínculo externo `[2]!TablaANT[...]` en vez de la referencia local `TablaANT[...]`.** `[2]` apunta a un archivo externo cuya lista de hojas declarada es CASI IDÉNTICA a las hojas de este mismo workbook (incluye "Redenciones Canje Crypto"/"Query Canje Crypto", que ya no existen acá) — es casi con certeza un vínculo viejo a una versión anterior/autoguardado de este mismo archivo (`Cierre 2026 06 (version 1).xlsb`, visto en la sección 24 antes de la re-unificación). Como `Acumulacion Non Tender`/`TablaANT` ahora vive EN ESTE MISMO archivo (se re-unificó), la fórmula debería ser local, sin el `[2]!`. Efecto real: `P` da 0 en todas las filas (el vínculo viejo no tiene datos que matcheen), lo que en cascada da `#DIV/0!` en `Q` (~100+ filas) y `#N/A` en `R` (mismo rango) — es el origen de la enorme lista de errores en Breakage. **Esto es lo que hay que arreglar**: reemplazar `[2]!TablaANT[` por `TablaANT[` en esas ~4929 celdas (buscar y reemplazar en Excel alcanza, no hace falta tocar Python - esto es 100% un archivo editado a mano, el pipeline no lo escribe).
2. **`Control de Pasivo ML!AN405`**: fórmula con un `#REF!` literal (`+SUM(TablaRed[[#All],[points_distribuidos]])+SUM(#REF!)-...`) → error real, no de datos. `AO405` (`=AN405-AI405`) hereda el error.
3. **`Redenciones!AG4, AG8, AG18, AG22`**: fórmula `+AE{n}-AF{n}-#REF!` → mismo patrón, `#REF!` literal en la fórmula (probablemente del borrado de una columna o de las hojas Canje Crypto).
4. **`Manual Accrual!E22` referencia `D24` (debería ser `D22`) y `E23` referencia `D25` (debería ser `D23`)** — desalineación de 2 filas, probablemente de arrastrar/pegar una fórmula sin ajustar la referencia. Con los datos actuales D22/D24/D25 dan 0 así que no se nota, pero es un bug real que se activaría con otros datos.
5. **`Manual Accrual!D40`** (`SUMIFS($O2:$O64,$P$2:$P64,"Otros manuales")+SUMIFS(...,"BONDA_WELCOME_BONUS")+O24`) quedó huérfana: sigue apuntando a las columnas L:O que ANTES ocupaba el pivot que se sacó, ahora vacías → da 0 en vez del valor real. `D42 = D39-D40` hereda el problema. Hay que reescribir esta fórmula para que agregue sobre `TablaQAc` igual que el resto de la columna D.

**No se encontraron** referencias rotas a Tablas inexistentes (`Tabla2[`, `Tabla3[`, etc. - 0 matches) ni fórmulas `GETPIVOTDATA` huérfanas. El resto de los ~1670 valores de error en el barrido son ruido esperado: `Breakage!Q:R` en cascada del punto 1, y algunos `#DIV/0!`/`#N/A` sueltos preexistentes (`Cobrand BR!E35`, `Query Acumulaciones!Z5/Z15`, `SSP!E14:E19`) sin relación con los cambios de esta sesión.

**Pivots que quedan (4)**: 2 en `Redenciones` (`TablaDinámica19`/`TablaDinámica4`, fuente `TablaRed`, salidas de 1-2 celdas en `AD3:AD4`/`AD17:AD18`) y 2 en `Query Acumulaciones` (`TablaDinámica2`/`TablaDinámica7`, fuente `TablaQAc`, en `AA47:AB54`/`AF2:AG77`). El intento de chequear si alguno se usa como referencia en otro lado dio falsos positivos (el regex matcheaba cualquier celda `AA50`/`AF2` sin relación real) — **no se pudo confirmar de forma confiable si estos 4 sirven para algo o son scratch de Rosario**; pendiente si hace falta saberlo con certeza.

### 29 bis. Tercer chequeo (2026-07-27, más tarde) — confirmado: 0 pivots

Rosario sacó los 4 pivots que quedaban. Reinspeccionado: **0 Pivot Cache Definitions, 0 Pivot Table en todo el archivo** (bajó a 122 entradas en el zip, de 31 MB). Las 4 ubicaciones donde vivían esos pivots (`Redenciones!AD3:AD4`/`AD17:AD18`, `Query Acumulaciones!AA47:AB54`/`AF2:AG77`) quedaron vacías o con datos sueltos sin fórmulas colgando - no se repitió el patrón de fórmula huérfana de la sección 29.

Estado de los 3 problemas de la sección 29 en esta nueva versión:
- `Control de Pasivo ML!AN405`: **arreglado** (ya no tiene el `#REF!`, calcula 14.141.766,2 OK).
- `Redenciones!AG4/AG8/AG18/AG22`: el `#REF!` desapareció pero quedaron vacías (sin fórmula) - a confirmar con Rosario si eso es lo esperado o si esas celdas deberían tener algo.
- **Sin resolver todavía**: `Manual Accrual!E22`/`E23` (siguen refiriendo `D24`/`D25`), `Manual Accrual!D40` (sigue huérfana sobre L:O vacío, `D42` depende de ella), y `Breakage!P` (~1639 celdas en error) sigue con el vínculo externo viejo `[2]!TablaANT[...]` en vez de `TablaANT[...]` local - sigue siendo la fuente de casi todos los errores del archivo.

## 30. Cambios de esta sesión (2026-07-27): código de escritura auditado + columna "tratamiento" en vez de "description"

**Auditoría del código de escritura** (pedido de Rosario: que no pase lo mismo que con Asientos — tablas mal armadas rompiendo fórmulas, y el síntoma de "Vínculo Externo Recuperado"): se releyó `pipeline/escritura_asientos.py` y `pipeline_backup/escritura_cierre_manual.py` — **ambos ya tienen las 2 protecciones** de las secciones 25/26: `_ajustar_filas_formula` con el lookbehind que evita mangular nombres de Tabla (`Tabla2` no matchea como celda), y `_validar_referencias_estructuradas()` que frena con `ValueError` y NO guarda si aparece una referencia a una Tabla inexistente, antes de `wb.save()`. No hizo falta cambiar nada ahí. `pipeline_backup/escritura_diccionario.py` (el módulo nuevo que pega el resultado de la query en la solapa Diccionario) no corre ningún riesgo de esta clase de bug porque no toca fórmulas en absoluto - solo reemplaza valores planos vía cirugía de XML, y no reconstruye ninguna otra parte del paquete OOXML (los vínculos externos, calcChain, etc. quedan exactamente iguales byte a byte).

**Nota importante**: estas protecciones viven en el código que escribe `Asientos Cierre Loyalty.xlsx` y `Cierre Backup Manual Bases.xlsx`/archivo pesado dentro de `Cierre 06.2026 TRIAL/` (la carpeta que usa `run_cierre_backup_manual.py` según `config.yaml`). El archivo `Cierre 2026 06.xlsx` de `Cierre 06.2026 COPIA PRUEBA/` que Rosario edita a mano (secciones 28/29) **no lo escribe ningún script Python** - los problemas ahí (sección 29) son de edición manual en Excel, no del pipeline.

**Columna "tratamiento" en vez de "description"** (pedido explícito de Rosario, 2026-07-27): el paso `[0b]` de `run_cierre_backup_manual.py` ahora pega `id, code, tratamiento` en la solapa Diccionario (antes era `id, code, description`, decisión de la sección 27). Se agregó `tratamiento` al SELECT externo de `Queries Data/Diccionario Puntos Excl.sql` (antes solo se calculaba en la subquery para el WHERE, no se exponía) - único cambio a esa query. Se actualizó `pipeline_backup/escritura_diccionario.py` (`HEADERS` y el mapeo de columnas) acorde. Probado con datos sintéticos, funciona igual que antes.

## 31. Rediseño del orden del proceso: Breakage Esperado primero, ya no haría falta Etapa 2 separada (2026-07-27)

**Idea de Rosario**: en vez del flujo actual (bajar → calcular → pegar Asientos → pegar archivo de cierre), invertir el orden: (1) Rosario calcula Breakage Esperado a mano con la bajada de puntos expirados y lo pega en la solapa "Breakage Esperado" del archivo de cierre; (2) **recién ahí** corre el proceso: primero escribe el archivo de cierre (Bases + Diccionario), y al final escribe Asientos - de forma que, para cuando se escribe Asientos, las columnas que hoy quedan "pendientes de Etapa 2" ya deberían estar calculables. Objetivo: eliminar la necesidad de una Etapa 2 separada.

**Cadena de dependencias verificada leyendo las fórmulas reales** (no es una suposición):
- **Puntos Valuados / DRO / DRO-up fronts / DRO-Fee+Descuentos** (Generacion, vía Acumulacion Non Tender cols U-X): `SSP Facturación!C8 = XLOOKUP(...,SSP!...) * IFERROR(XLOOKUP(B8,'Breakage Esperado'!$B$4:$B$9,'Breakage Esperado'!$D$4:$D$9),1)`. Cadena corta: **Breakage Esperado → SSP Facturación → estas 4 columnas**. `SSP` (crudo) es autosuficiente: `SUMIF(TablaRed[...],...)` + `TC` (ya se mantiene todos los meses, fuera de Etapa 2), sin ninguna otra entrada manual.
- **Reconocimiento de Ingresos Diferidos ML** (Redenciones/Redenciones SUBS): cadena más larga - **Breakage Esperado → SSP Facturación → Cobrand MX/AR/Partners → Control de Pasivo ML → columna ML**. Confirmado que Cobrand AR (`D36 = -'SSP Facturación'!C8*D35`) y Cobrand MX (ya unificado, ver más abajo) dependen de `SSP Facturación`, y Partners depende de `Breakage Esperado` directo (`Partners!H35 = ...*IF(B35='Breakage Esperado'!$B$4,...)`). Ningún nodo de esta cadena tiene otra entrada manual de Etapa 2 aparte de Breakage Esperado.

**Conclusión**: la hipótesis de Rosario es correcta — Breakage Esperado es la única entrada manual verdadera que falta para que toda la cadena de Etapa 2 recalcule sola, siempre que el archivo se recalcule de verdad (ver limitación técnica abajo).

**Limitación técnica clave (confirmada, no es teórica)**: `openpyxl` NO recalcula fórmulas. Si Python pega los datos nuevos del mes en el archivo de cierre, las celdas de fórmula (SSP Facturación, Cobrand, Control de Pasivo ML, etc.) van a seguir mostrando el valor cacheado VIEJO hasta que el archivo se abra en Excel real y se refresque (Ctrl+Alt+F9) - sin este paso, leer esos valores para pegarlos en Asientos pegaría números viejos, silenciosamente.

**Decisión de Rosario sobre el recálculo (2026-07-27)**: pausa manual en dos pasos, NO automatizar con Excel/COM. El proceso queda:
1. Rosario calcula Breakage Esperado a mano y lo pega en el archivo de cierre.
2. `run_cierre_backup_manual.py` (reordenado): guardrails → bajar → escribir archivo de cierre (Bases + Diccionario) → **FRENA con instrucciones**: "abrí el archivo en Excel, Ctrl+Alt+F9, guardá, y corré el segundo comando".
3. Un segundo comando/script lee las columnas ya recalculadas del archivo de cierre (Puntos Valuados/DRO/DRO-up fronts/DRO-Fee+Descuentos de Acumulacion Non Tender, Reconocimiento ML de Redenciones/Redenciones SUBS, y la solapa Accounting completa) y recién ahí escribe `Asientos Cierre Loyalty.xlsx`.

**Dudas de Pendientes Etapa 2.md resueltas en esta sesión** (bloqueaban confiar en la cadena de arriba - ver detalle en `Pendientes Etapa 2.md`, sección "Resueltas"):
- SSP "REVISAR" (>10% desvío): NO frena el proceso, solo queda marcado.
- Cobrand BR: **está apagada** — el pipeline no la toca/calcula, solo pega lo que hay para conservar el template por si se reactiva. El precio congelado de Cobrand BR queda sin efecto mientras tanto.
- Cobrand AR (corte en fila 53.811): NO es bug — eran filas ad-hoc que Rosario va a borrar. El rango de la fórmula está bien.
- Cobrand MX: ya unificado por Rosario, usa el mismo mecanismo que AR (`SSP Facturación`).
- Manual Accrual (mezcla SSP crudo/ajustado por categoría): intencional.
- Santander Bank: remanente, no se toca ni se automatiza.
- **Accounting de `Asientos Cierre Loyalty.xlsx`**: deja de depender del vínculo externo vivo — pasa a ser una **copia a valor** de la solapa "Accounting" del archivo de cierre (ya recalculada), copiada tal cual (no por mapeo de estructura por país, así que no importa si esa estructura es estable).

## 32. Implementado el rediseño de la sección 31: proceso en 2 pasos (2026-07-27)

**Reordenado `run_cierre_backup_manual.py`** (ahora "paso 1/2"): guardrails → bajar → chequear → calcular Etapa 1 → **pegar archivo de cierre (Bases + Diccionario)** → guardar estado intermedio → frenar con instrucciones. Ya NO escribe Asientos - eso se movió al paso 2.

**Nuevo `escribir_asientos.py`** (paso 2/2, mismo folder): carga el estado intermedio, lee las columnas de Etapa 2 ya recalculadas, y pega Asientos (incluido Accounting a valor).

**Nuevo `pipeline_backup/estado_intermedio.py`**: persiste (con `pandas.to_pickle`/`read_pickle`, en `Auditoria/estado_intermedio_asientos.pkl` - nueva entrada `rutas.estado_intermedio` en `config.yaml`) los DataFrames de Generacion/Redenciones/Redenciones SUBS/Redenciones Otros que calcula el paso 1, para que el paso 2 no tenga que volver a bajar/filtrar nada (elimina cualquier riesgo de desalineación de filas entre las 2 corridas). `cargar()` frena con `ValueError` si el mes/año guardado no coincide con `config.yaml` - evita mezclar por accidente el estado de una corrida vieja.

**Nuevo `pipeline_backup/lectura_etapa2.py`**: lee (nunca escribe) del archivo de cierre ya recalculado - `leer_columnas_generacion()` (Puntos Valuados/DRO/DRO-up fronts/DRO-Fee+Descuentos de "Acumulacion Non Tender", Bases), `leer_reconocimiento_ml(hoja)` (Redenciones/Redenciones SUBS, Bases), y `leer_accounting()` (solapa Accounting del archivo pesado). El archivo pesado se abre con `read_only=True, data_only=True` - confirmado liviano (no dispara el problema de RAM de la sección 23, que es específico del modo escritura).

**`pipeline/escritura_asientos.py`**: nueva función `pegar_accounting(wb, valores)` + parámetro opcional `valores_accounting` en `pegar_todo()` (si se omite, no toca Accounting - no rompe a `run_cierre.py`, que sigue sin pasarlo). Encontrado y resuelto probando contra una copia real: la solapa Accounting tiene **celdas combinadas** (texto explicativo en varias filas) - openpyxl no permite escribir en una `MergedCell`, así que `pegar_accounting` desarma todos los combinados de la hoja antes de pegar los valores. También: la fuente (archivo pesado) tiene MÁS columnas que el destino (A:L vs A:E en Asientos - las columnas de más son ayudas tipo "partner"/"point_type", no parte del asiento) - `pegar_accounting` respeta el ancho EXISTENTE de `Asientos!Accounting` (no el de la fuente) para no agregar columnas de más.

**`config.yaml`**: nueva `rutas.estado_intermedio`; se eliminó la sección `columnas_pendientes_etapa_2` (ya no aplica - todas las columnas quedan resueltas en el paso 2); actualizado el comentario de `archivo_pesado` (ya no es 100% cierto que "Python nunca lo abre" - ahora lo lee en modo `read_only` para Etapa 2, y lo edita vía cirugía de XML para Diccionario).

**Probado** (antes de tocar ningún archivo real, contra copias en un area de prueba aislada): `estado_intermedio.guardar()`/`cargar()` (incluido el chequeo de mes/año distinto), `lectura_etapa2` contra los archivos reales de `Cierre 06.2026 TRIAL` (headers coinciden exactamente con lo esperado), y `pegar_accounting()` contra una copia real de `Asientos Cierre Loyalty.xlsx` (con datos sintéticos Y con los datos reales de Accounting - incluido el fix de celdas combinadas).

**Pendiente real** (no es código, es el primer uso real del flujo completo): correr el paso 1 con VPN conectada, pegar Breakage Esperado a mano, refrescar Excel, y correr el paso 2 - para validar el flujo de punta a punta con datos reales del mes.

## 33. Vuelta a UN solo archivo de cierre (no Bases+Pesado) + primera corrida real, cierre parcial de julio (2026-07-27)

**Contexto**: Rosario pidió correr el flujo para "lo que va de julio" (datos hasta el 25/07), en una carpeta nueva: `C:\Users\rosario.arancedo\despegar365\Control de Gestión - Loyalty\2026\Cierre\Cierre 07.2026` (la carpeta real sincronizada de SharePoint, no una carpeta de prueba). Al inspeccionarla, los 4 archivos ahí adentro resultaron ser copias EXACTAS (mismo tamaño/hash) de los que Rosario venía editando toda la sesión en `Loyalty_cierre_contable\Cierre 06.2026 COPIA PRUEBA\` - confirmado con Rosario: así es como funciona el proceso mes a mes (se duplica la carpeta del mes anterior entera, se renombran los archivos al mes nuevo, y se corre el pipeline sobre la carpeta nueva) - **esto ya debería estar en la Bitácora/Instrucciones y no lo estaba con este nivel de detalle**, corregido acá.

**Hallazgo clave**: el archivo de cierre llegó con un typo (`Cierre 2027 06.xlsx`, año y mes mal) - Rosario ya lo corrigió a mano a `Cierre 2026 07.xlsx` antes de que seachequeara.

**Decisión grande - se vuelve a UN solo archivo de cierre** (ya no Bases + Pesado, ver secciones 23 y 28-32 para toda la historia del split): Rosario confirmó que pasó gran parte de la sesión sacando TODOS los pivots tanto del archivo de cierre como de `Asientos Cierre Loyalty.xlsx`, justamente para poder volver a un archivo único sin el problema de RAM original. **Se verificó empíricamente antes de asumir nada**: abrir el archivo de julio (ya sin pivots) con `openpyxl.load_workbook()` en modo escritura normal (no read_only) usa **~2.1 GB / 31 segundos** - muy lejos de los 8+ GB sin estabilizar de la sección 23. Confirma la hipótesis: sacar los pivots era la causa raíz del problema de memoria, no el tamaño del archivo en sí.

**Refactor de código** (probado contra copias del archivo real de julio antes de tocar el original):
- `config.yaml`: `backup_manual.archivo_bases` + `archivo_pesado` → un solo `backup_manual.archivo_cierre: "Cierre 2026 07.xlsx"`. `rutas.carpeta_cierre` apunta a la carpeta real de SharePoint. `cierre.mes/anio` → 7/2026. Nueva `cierre.hasta_override: "2026-07-26"` (ver más abajo).
- `pipeline/config.py` → `fechas_cierre()`: nuevo soporte para `cierre.hasta_override` (fecha "YYYY-MM-DD" opcional) - si está definida, se usa como Hasta (exclusive) en vez del día 1 del mes siguiente, para poder correr cierres PARCIALES ("lo que va del mes"). Sin esa clave, el comportamiento es el de siempre (mes completo).
- `pipeline_backup/escritura_cierre_manual.py`: absorbe todo lo que hacía `pipeline_backup/escritura_diccionario.py` (`bajar_diccionario_excl()` + una nueva `pegar_diccionario(wb, df)` que ya NO hace cirugía de XML - se pega como cualquier otra hoja, en la misma sesión de `wb` que el resto de las hojas de Etapa 1, en un solo `load_workbook`/`save`). **`escritura_diccionario.py` se eliminó** (superado).
  - **Bug encontrado y corregido probando contra una copia real**: el archivo de julio (heredado de COPIA PRUEBA, nunca tocado por `escritura_diccionario.py`) todavía tenía el esquema VIEJO de Diccionario (4 columnas, ver sección 27). `pegar_diccionario()` solo limpiaba las 3 columnas nuevas, dejando un remanente sucio en la vieja columna D (header y datos viejos). Corregido: ahora detecta el ancho viejo real de la hoja (`ws.max_column` + escaneo de la columna extra) y limpia cualquier columna de más, no solo filas de más.
- `pipeline_backup/lectura_etapa2.py`: ahora lee TODO (Puntos Valuados/DRO, Reconocimiento ML, Accounting) de un solo archivo en vez de Bases+Pesado separados.
- `run_cierre_backup_manual.py`: ya no hay paso `[0b]` separado para Diccionario - se baja la query en `[0b]` pero se pega junto con el resto en `[5]` (una sola escritura de archivo). Mensaje final actualizado (ya no dice "liviano y pesado").
- `escribir_asientos.py`: sin cambios de lógica (ya usaba `lectura_etapa2`, que ahora apunta a un solo archivo).

**Probado** contra una copia del archivo REAL de julio (no el original) con datos sintéticos: `pegar_todo_manual()` completo (7 hojas + Diccionario, un solo `load_workbook`/guardado) y `lectura_etapa2` (Generacion/ML/Accounting) - ambos OK, guardrail de referencias estructuradas pasó sin problemas.

**Pendiente real**: correr `run_cierre_backup_manual.py` de punta a punta contra el archivo real de julio con VPN conectada (paso 1), pegar Breakage Esperado a mano si no está, refrescar Excel, y correr `escribir_asientos.py` (paso 2).

## 34. Primera corrida real del paso 1 (julio parcial) + bug real encontrado y corregido en `_pegar_hoja` (2026-07-28)

**Primera corrida real**: `run_cierre_backup_manual.py` contra el archivo real de julio, VPN conectada. El guardrail de diccionario de puntos frenó primero por 12 codes nuevos (`C_BC_BL_BO`, `C_BC_BL_GE`, `C_BC_BL_WE`, `C_BC_CL_BO`, `C_BC_CL_GE`, `C_BC_CL_WE`, `C_BC_GO_BO`, `C_BC_GO_GE`, `C_BC_GO_WE`, `C_BC_PL_BO`, `C_BC_PL_GE`, `C_BC_PL_WE`) - **decisión de Rosario: aceptarlos, quedan clasificados como "general" por ahora** (no se tocó el CASE de ninguna query). Corrida con `--aceptar-puntos-nuevos`: bajó 18.232 filas de Acumulaciones / 10.621 de Redenciones / 5.804 de Puntos Expirados, los 3 controles de suma de puntos dieron OK (diferencia 0), y se pegó todo en el archivo de cierre (backup hecho antes, ver Auditoria/Backups Cierre Mensual).

**REVISAR encontrado**: 8 filas de Generacion con "Entidad Legal"/"Producto" vacíos. Investigado (leyendo la query real `Acumulaciones cierre - con filtro de fecha general.sql`, sin modificarla, y despues confirmando con una consulta de solo lectura al datalake): `product`/`business` son pass-through DIRECTO desde `data.lake.comarch_accumulation_report` (no los calcula la query) - las 8 filas resultaron ser **acreditaciones manuales de puntos** (`dsp_transaction_type = 'MANUAL_ACCRUAL'`, partner "DP", países BR/AR/CO), que por diseño no tienen product/business asociado (no vienen de una reserva). **Decisión de Rosario: dejarlas vacías, no tocar nada del código** (no vale la pena agregar `dsp_transaction_type` a la query solo para esto - eso implicaría tocar el `GROUP BY` en varios niveles anidados y revalidar los totales de control).

**Bug real encontrado y corregido** (Rosario abrió el archivo de cierre en Excel tras la corrida y reportó: (1) cartel de "recuperar" al abrir, no puede guardar sobre el original; (2) fórmulas de Breakage columnas P:S rotas, referencian "libros viejos"):

- **Parte 1 (ya conocida, no nueva)**: las fórmulas de `Breakage!P` (dentro de `Tabla10`, la tabla manual de Rosario en K3:S821) usaban `[2]!TablaANT[...]` - vínculo externo viejo, mismo hallazgo que la sección 29. Confirmado comparando contra el backup automático hecho ANTES de esta corrida: **ya estaba así antes de que el pipeline tocara el archivo** - no lo introdujo Python. Rosario lo corrigió a mano en su archivo base (`Loyalty_cierre_contable\Cierre 06.2026 COPIA PRUEBA\Cierre 2026 06.xlsx`, que sigue siendo la plantilla de referencia): reemplazó `[2]!TablaANT[` por `TablaANT[` en toda la columna P, y sacó una nota suelta que había en `K1` ("Actualizar colores; formulas tmb de pasivo" - no era un header real, el header real de Tabla10 está en la fila 3).

- **Parte 2 (bug real de `pipeline_backup/escritura_cierre_manual.py::_pegar_hoja`, SÍ introducido por el pipeline)**: `ultima_col_idx` (el límite derecho hasta donde se replica la "plantilla" de fórmulas en cada hoja) se calculaba con `max(encabezados.values())` - escaneando TODA la fila 1 de la hoja buscando cualquier celda no vacía, sin limitarse a las columnas propias de la Tabla que esa función está pegando. En `Breakage`, que comparte la hoja con `Tabla10` (tabla manual, no relacionada con `TablaBr`), la nota suelta en `K1` se contaba como si fuera un header más -> el código extendía la plantilla de `Breakage!F` (Aplica) hasta la columna `K`, y al pegar las 5.804 filas nuevas de puntos expirados, escribía `None` en las columnas G-K de esas filas - pisando el inicio de los datos manuales de `Tabla10` (columnas `country_code`/`Entidad Legal` etc., filas 4 en adelante) en el rango donde se solapaban con las filas nuevas de `TablaBr`.

  **Corregido**: `ultima_col_idx` ahora se deriva del `ref` DECLARADO de la Tabla que se está pegando (mismo patrón que ya usaba `_validar_referencias_estructuradas` para su propio `col_fin_idx` - ese guardrail nunca tuvo este bug), no de un escaneo ciego de la fila 1. Esto es además más robusto en general: no depende de que la fila 1 esté "limpia" de notas o contenido de otras tablas que compartan la hoja.

  **Probado**: contra una copia del backup real (el que se generó automáticamente ANTES de la corrida de julio, que tiene el escenario exacto del bug - nota en K1 + Tabla10 real) - se corrió `pegar_breakage()` ya corregido con 5.804 filas sintéticas y se confirmó que `Tabla10` (`K4`/`L4`/`K821`/`L821`) queda intacta.

**Pendiente real para Rosario**: el archivo real de julio (`Cierre 2026 07.xlsx`) todavía tiene el problema (el fix de código no lo repara retroactivamente) - hay que volver a correr el paso 1 (ahora con el fix) para regenerar `Breakage` limpio, o arreglar a mano en el archivo real las mismas 2 cosas que ya arregló en el archivo base (fórmulas de columna P + nota en K1). El cartel de "recuperar" al abrir en Excel debería dejar de aparecer una vez que el archivo esté limpio de esto.

## 35. Reinicio de julio desde cero + 2 rondas más del mismo síntoma ("recuperar contenido") + causa raíz final: `pegar_diccionario` nunca actualizaba el AutoFilter/dimension de la hoja (2026-07-28)

**Reinicio limpio**: Rosario cerró Excel sin guardar, eliminó el `Cierre 2026 07.xlsx` dañado, y duplicó su archivo base ya corregido (`COPIA PRUEBA\Cierre 2026 06.xlsx`, sin pivots, sin nota en K1, con `TablaANT[...]` local) como el nuevo `Cierre 2026 07.xlsx`. Verificado antes de dar luz verde: 0 pivots, K1 vacío, fila 3 de Tabla10 con headers reales, `P4` con referencia local - archivo sano confirmado por chequeo directo (sin abrir en Excel).

**Corrida 2 del paso 1**: encontró un problema de conectividad transitorio con el datalake (reintentar solucionó) y un `PermissionError` (archivo bloqueado por Excel - cerrar Excel lo resolvió). La corrida en sí completó bien, pero **volvió a aparecer el cartel de "recuperar contenido"** al abrir en Excel, con mensajes de reparación en: vínculos externos 1 y 2, y "Tabla de table6.xml" (=Tabla10). Investigado comparando contra el backup automático de ANTES de esta corrida: **el problema YA estaba ahí antes de correr nada** - Rosario había duplicado julio desde una versión de COPIA PRUEBA anterior a su propio fix de la nota en K1/columna P, así que julio nació ya con el problema viejo, y la sección 34 lo agravó una vez más (mismo bug, ya corregido en código para la corrida siguiente, pero no reparado retroactivamente en el archivo que ya estaba dañado). Encontrada además otra zona con el mismo vínculo viejo: **celdas `I19:I25` de Breakage** (7 celdas, 21 referencias `[2]!TablaBr[...]`, una zona de resumen fuera de las columnas de `TablaBr`/`Tabla10` - contenido manual de Rosario, no generado por Python). Rosario corrigió ambas cosas (Tabla10 + I19:I25) en su archivo base, confirmado con 0 ocurrencias de `[2]!` en ambos archivos (base y julio).

**Corrida 3 del paso 1**: sobre el archivo ya limpio de `[2]!` en todo el libro (confirmado por chequeo automatizado: 0 tablas con `ref`/columnas inconsistentes, 0 celdas `[1]!`/`[2]!`, XML de todas las hojas parsea bien, sin caracteres de control invalidos) - **el cartel de "recuperar" volvió a aparecer una tercera vez**, esta vez sin relación con Breakage/Tabla10/vínculos externos en absoluto.

**Causa raíz real, encontrada por descarte sistemático** (probado un chequeo a la vez: pivots, tablas vs headers, `[N]!` en formulas, `[Content_Types].xml` vs partes reales del zip, caracteres de control XML invalidos, `sharedStrings.xml` ausente - todos limpios): la hoja **"Diccionario" tiene su PROPIO `AutoFilter`** (`ws.auto_filter.ref`, ej. `"A1:D120"`) - a diferencia del resto de las hojas que Python toca, esta no tiene Tabla (`ws.tables`), así que no hay un `tabla.ref` que mantener sincronizado automáticamente. `pipeline_backup/escritura_cierre_manual.py::pegar_diccionario()` (agregado en la sección 33) nunca tocaba `ws.auto_filter` - solo vaciaba celdas de más con `_set_cell(..., None)`, que NO borra la celda (solo el valor, el objeto y su estilo siguen existiendo). Resultado: el `AutoFilter` seguía declarando `A1:D120` (esquema viejo de 4 columnas/120 filas, previo a la sección 27) mucho después de que los datos reales pasaran a ser 3 columnas y ~16 filas - un `AutoFilter`/`_FilterDatabase` apuntando a una columna sin header ni datos es justo el tipo de inconsistencia que Excel detecta como "problema con el contenido" al abrir el archivo.

**Corregido** en `pegar_diccionario()`:
1. `fila_vieja_max`/`col_vieja_max` ahora se toman de `ws.max_row`/`ws.max_column` (las propiedades reales de openpyxl, que cuentan celdas con estilo aunque no tengan valor) en vez de `_ultima_fila_real()` (que solo mira VALORES) - se encontraron filas 17-120 sin valor pero con estilo residual que `_ultima_fila_real` no detectaba.
2. Las columnas/filas de más ahora se **BORRAN de verdad** (`ws.delete_cols()` / `ws.delete_rows()`), no solo se vacían - así la `dimension` real de la hoja queda acotada a los datos actuales, no solo los valores.
3. `ws.auto_filter.ref` se re-acota explícitamente al rango nuevo (`A{header}:C{última_fila}`) después de pegar.

**Probado** contra copias frescas del archivo real (no el original): antes del fix, `auto_filter.ref` quedaba en `"A1:D120"` pese a pegar solo 3 filas nuevas; después del fix, `auto_filter.ref` y `dimension` coinciden exactamente (`"A1:C4"` con esos datos de prueba). Corrida completa de `pegar_todo_manual()` (7 hojas + Diccionario) contra una copia del archivo real de julio, más un chequeo automatizado final (parseo XML de las 23 hojas, consistencia de las 9 tablas, `#REF!` literal, `[N]!` residual) - todo limpio.

**Estado**: el archivo real de julio (`Cierre 2026 07.xlsx`) sigue por corregir - Rosario tiene que volver a correr el paso 1 (ahora con este fix) para que Diccionario quede con el AutoFilter/dimension correctos. Si el cartel de "recuperar" vuelve a aparecer una cuarta vez, revisar primero si hay OTRA hoja sin Tabla con un AutoFilter propio desincronizado (candidatas: cualquier hoja donde Python pega datos sin pasar por `_pegar_hoja`/una Tabla real).

**Cuarta ronda**: volvió a aparecer el cartel, pero esta vez el mensaje de reparación fue mucho más leve - solo "Referencia de fórmula externa de externalLink1.xml (Valores en caché...)". Ese vínculo es el LEGÍTIMO (Cobrand BR → archivo de precios "Contratos con partners..."), no un vínculo viejo/roto. Es una limitación conocida de `openpyxl` (no actualiza bien el caché de vínculos externos al reescribir el libro) - inofensivo, se resuelve solo al refrescar en Excel. Rosario decidió además editar esos vínculos a mano para que no molesten más, y va a rearmar `Cierre 2026 07.xlsx` desde cero (duplicando su archivo base ya corregido) antes de la próxima corrida.

## 36. Reorganización completa: nace `Automatizacion Cierre/`, carpeta autocontenida y compartible por SharePoint (2026-07-28)

Rosario pidió reorganizar "la carpeta backup manual" (`Etapa 1 Backup Manual/`) para poder compartirla por SharePoint con el resto del equipo - hoy dependía de `pipeline/`, `queries/`, `referencia/` y `config.yaml` en la carpeta PADRE (`Cierre Loyalty - Pipeline/`), lo cual la hacía imposible de compartir sola.

**Decisiones de Rosario** (confirmadas antes de mover nada):
- Renombrar `Etapa 1 Backup Manual/` → **`Automatizacion Cierre/`** y unificar TODO ahí adentro (no una carpeta nueva aparte).
- `run_cierre.py` (standby) queda AFUERA de lo que se comparte - se deja en la carpeta padre, apuntando a `pipeline/` en la carpeta nueva vía `sys.path`.
- Los 2 archivos xlsx de prueba viejos (~50 MB, del esquema Bases+Pesado ya superado) se sacan de la carpeta de código y se guardan en `Loyalty_cierre_contable/Archivos viejos Bases+Pesado/`.

**Reorganización de archivos**:
- `pipeline/`, `queries/`, `referencia/`, `config.yaml` se movieron de la carpeta padre a `Automatizacion Cierre/` (ahora autocontenida - no depende de nada fuera de sí misma, salvo las credenciales, ver abajo).
- `run_cierre_backup_manual.py` y `escribir_asientos.py`: `sys.path.insert` simplificado (ya no hace falta subir a la carpeta padre, `pipeline/`/`pipeline_backup/` son ahora hermanas directas del script).
- `run_cierre.py` (queda en la carpeta padre): se le agregó un `sys.path.insert` apuntando a `Automatizacion Cierre/` (antes no tenía ninguno - dependía de que `pipeline/` estuviera en su misma carpeta, cosa que dejó de ser cierta).
- Nuevo `requirements.txt` (pandas, openpyxl, pyodbc, PyYAML, python-dotenv) - no existía ningún listado de dependencias antes.
- `INSTRUCCIONES.md` de `Automatizacion Cierre/` reescrito de punta a punta: instructivo unificado para gente nueva, sin la nomenclatura "paso 1/paso 2" (pedido explícito de Rosario) - se describe como un flujo continuo de 4 partes (bajar y armar el archivo de cierre → refrescar Excel → completar y escribir Asientos → revisar), con estructura de carpeta, troubleshooting, y qué no tocar sin avisar. Los `print()` de banner y el `--help` de ambos scripts tambien se actualizaron para sacar "PASO 1/2"/"PASO 2/2".
- `INSTRUCCIONES.md` de la carpeta padre (para `run_cierre.py`) actualizado con una nota al principio explicando que quedó en standby y redirigiendo a `Automatizacion Cierre/`.

**Credenciales del Datalake - separadas de la carpeta compartida**: como `Automatizacion Cierre/` va a subirse a SharePoint, un `.env` con la contraseña de Rosario adentro se compartiría con todo el mundo con acceso a la carpeta. Corregido en `pipeline/conexion.py`: `load_dotenv()` ahora apunta explícitamente a `Path.home() / ".automatizacion_cierre" / ".env"` - una ruta fija del usuario de Windows de cada persona, nunca sincronizada con OneDrive/SharePoint. Se movió el `.env` real de Rosario a `C:\Users\rosario.arancedo\.automatizacion_cierre\.env`, y se reescribió `.env.example` (queda dentro de la carpeta compartida, es solo una plantilla sin secretos) explicando el motivo y los pasos para armar el archivo real. Cada persona que use la carpeta hace lo mismo con su propio usuario/contraseña.

**Probado** (antes de avisarle a Rosario que estaba listo): compilación de los 16 módulos Python movidos + `run_cierre.py`; carga de `config.yaml`/`fechas_cierre()`/resolución de rutas de queries y referencia desde la nueva ubicación (todas existen); resolución de `pipeline` desde `run_cierre.py` vía el nuevo `sys.path`; y que `RUTA_ENV` encuentra el `.env` ya movido y carga `DATALAKE_USER` correctamente - todo OK.

**Estructura final**:
```
Cierre Loyalty - Pipeline/
├── run_cierre.py              (standby, sys.path -> Automatizacion Cierre/pipeline)
├── INSTRUCCIONES.md           (nota de standby + redirección)
├── output/
└── Automatizacion Cierre/     (autocontenida, para compartir por SharePoint)
    ├── INSTRUCCIONES.md       (reescrito de punta a punta)
    ├── requirements.txt       (nuevo)
    ├── config.yaml
    ├── .env.example
    ├── run_cierre_backup_manual.py
    ├── escribir_asientos.py
    ├── pipeline/
    ├── pipeline_backup/
    ├── queries/
    └── referencia/

C:\Users\rosario.arancedo\.automatizacion_cierre\.env   <- credenciales reales, fuera de todo lo sincronizado
```

## 37. Bug real encontrado y corregido: `country_code` de "Acumulacion Non Tender" se pegaba en la columna equivocada (2026-07-28)

Tras la primera corrida real contra la carpeta `Cierre 06.2026 COPIA PRUEBA` (archivo `Cierre 2026 06 version 2.xlsx`), Rosario reportó un dato que "no tenía sentido": en "Query Acumulaciones" no hay ninguna fila con `country_code` vacío para `point_type = general`, pero en "Acumulacion Non Tender" (que se arma FILTRANDO ese mismo DataFrame por `point_type`, sin tocar `country_code`) había 16.744 filas con `country_code` vacío para `general`/`GENERAL INTER`/`GENERAL LOCAL`.

**Investigación**: inspección read-only (`openpyxl.load_workbook(..., read_only=True, data_only=True)`, sin abrir en modo escritura) de los headers reales de ambas hojas. "Query Acumulaciones" no tenía duplicados. "Acumulacion Non Tender" sí: el header `country_code` aparece DOS veces - una en la columna B (la real, parte de `TablaANT`, `ref` declarado `A1:AE20186`) y otra en la columna AI (0-index 34), fuera del `ref` de la tabla, parte de una mini-tabla de referencia/lookup manual que Rosario tiene más a la derecha en la misma hoja (headers `Producto`, `country`, `country_code`, `Producto`, `GB`, `POINTS`, `Ratio de acumulación` - también con `country`/`Producto` duplicados).

**Causa raíz confirmada**: `_header_a_columna()` armaba el diccionario header→columna escaneando la fila 1 ENTERA de la hoja (sin límite de columnas). Al iterar de izquierda a derecha, la ÚLTIMA coincidencia de un nombre pisa al diccionario - así que `encabezados["country_code"]` terminaba apuntando a la columna AI (la tabla de referencia ajena) en vez de la columna B real. Verificado celda a celda: las filas con `general` y `country_code` (col B) vacío SÍ tenían el país correcto (`BR`, `AR`, `MX`, `PE`, `CO`...) en la columna AI - es decir, el dato se pegó, pero en el lugar equivocado, pisando la tabla de referencia manual de Rosario y dejando la columna real de `TablaANT` vacía.

Es la MISMA familia de bug que la sección 34 (`ultima_col_idx` escaneando toda la fila 1 sin limitarse a la Tabla propia de la hoja, con Tabla10/Breakage), pero esta vez en la función de lookup de headers en vez de en el cálculo de última columna. Moraleja repetida: en una hoja compartida con contenido manual ajeno a la Tabla de Python, CUALQUIER escaneo de la fila de headers (o de filas/columnas en general) tiene que limitarse al `ref` propio de la Tabla - nunca escanear la hoja entera.

**Corregido** en `pipeline_backup/escritura_cierre_manual.py`: `_header_a_columna()` ahora acepta `min_col`/`max_col` opcionales (por defecto `None` = toda la fila, para hojas sin Tabla como Diccionario). `_pegar_hoja()` ahora calcula `col_inicio_idx` (antes solo se calculaba `ultima_col_idx`) a partir del `ref` declarado de la Tabla y se lo pasa a `_header_a_columna()` junto con `ultima_col_idx`, limitando el escaneo de headers a las columnas propias de la Tabla de esa hoja.

**Pendiente para Rosario**: el archivo `Cierre 2026 06 version 2.xlsx` actual (carpeta COPIA PRUEBA) tiene los datos de `Acumulacion Non Tender` de esta corrida pegados en el lugar equivocado (columna AI en vez de B, pisando la tabla de referencia manual). Con el fix ya no va a volver a pasar, pero hay que volver a correr `run_cierre_backup_manual.py` para esta hoja (o rehacer el archivo desde cero, según prefiera) para que los datos queden en la columna correcta y la tabla de referencia de la derecha recupere su contenido original (si es que no se pisó de forma irrecuperable - conviene que Rosario revise esa zona antes de decidir cómo seguir).

## 38. Nuevo requisito de filtro para "Acumulacion Non Tender": partner = "DP" (2026-07-29)

Rosario pidió agregar un segundo requisito al filtro de las filas de Query Acumulaciones que quedan pegadas en "Acumulacion Non Tender": además del `point_type` (general/GENERAL INTER/GENERAL LOCAL/LOCAL, config.yaml `point_types.acumulacion_non_tender`), ahora también se exige `partner` (columna C) = `"DP"`. Aclaró que el archivo de Excel (fórmulas, Etapa 2) lo actualiza ella misma - lo que pidió es que el cambio de lógica quede reflejado en el código, para todo el proceso.

**Implementado** en `pipeline/etapa1_acumulaciones.py::filtrar_acumulacion_non_tender()`: el filtro pasa de `point_type.isin(point_types)` a `point_type.isin(point_types) & (partner == "DP")`.

**Por qué un solo cambio alcanza para "todo el proceso"**: esta función es el único punto de filtrado de Acumulacion Non Tender, y la llaman DOS consumidores distintos que por eso quedan sincronizados automáticamente:
- `pipeline_backup/escritura_cierre_manual.py::pegar_acumulacion_non_tender()` → pega la hoja "Acumulacion Non Tender" del archivo de cierre.
- `run_cierre_backup_manual.py` (paso "Calculando columnas derivadas - Generacion") → llama a `etapa1_acumulaciones.procesar()` (que internamente llama a `filtrar_acumulacion_non_tender()`) para armar `df_generacion`, que se guarda en `estado_intermedio` y más tarde `escribir_asientos.py` lo usa (ya filtrado) para pegar `Asientos!Generacion`.

No hizo falta tocar ninguna query SQL ni el guardrail de control de sumas (`validaciones.chequear_sum_points_acumulaciones()` compara la bajada CRUDA completa contra la Query Control, sin filtrar por point_type/partner - no está afectado por este cambio).

## 39. Mapeo de cambios de fórmulas en `Cierre 2026 07.xlsx` (real, SharePoint) antes de la primera corrida de julio (2026-08-03)

Rosario pidió correr el cierre en la carpeta real `Cierre 07.2026` (SharePoint), pero primero mapear "un par de cambios en fórmulas" que hizo hoy en `Cierre 2026 07.xlsx` (modificado 2026-08-03 11:12, mientras seguía abierto en Excel) — **todavía no se corrió nada del pipeline sobre esta carpeta**, esto es solo el mapeo previo pedido.

**Nota de método**: no hay snapshot "antes" de este archivo puntual (como en las secciones 28/29, es edición manual de Rosario). Se comparó contra la base de la que salió: de los 2 candidatos en `Cierre 06.2026 COPIA PRUEBA/` (`Cierre 2026 06.xlsx` y `Cierre 2026 06 version 2.xlsx`), se confirmó por evidencia (mismos `sheetId` no correlativos, mismo `ref` de `TablaRed`/`TablaRedSUBS`/`TablaANT`/`TablaQAc`/`TablaQRed` byte a byte) que **`Cierre 2026 06.xlsx`** (29/7, 30.148.333 bytes) es la base real — `version 2.xlsx` (31/7, 25.600.325 bytes, sheetId correlativos 1-23) queda descartada, es una reconstrucción distinta. Archivo abierto en Excel al momento de inspeccionar → se trabajó sobre una copia de solo bytes, nunca el original, con `zipfile` + `ElementTree.iterparse` en streaming (nunca `openpyxl` en modo escritura).

**23 hojas, ninguna agregada/sacada. 18 sin ningún cambio** (Caratula, Sheet1, SSP, SSP Facturación, Breakage, Acumulacion Non Tender, Breakage Esperado, Manual Accrual, Cobrand MX/AR/BR, Partners, Accounting, Query Acumulaciones, Query Redenciones, Regla entidad Legal, Diccionario, Santander Bank) — verificadas explícitamente, no solo asumidas. 0 pivots/pivot caches en ningún archivo (sigue así, no reaparecieron).

**Cambios reales encontrados:**

1. **Redenciones / Redenciones SUBS / Redenciones Otros — bloque auxiliar `AA2:AA16`** (fuera de la Tabla de Excel, que llega hasta Y; es un área de trabajo manual al costado, usada por el `VLOOKUP($Z...,$Z$2:$AA$16,...)` de dentro de la tabla): Rosario reemplazó la cadena vieja (`AA2:AA9` = `='Control de Pasivo ML'!AI3..AI9`; `AA10:AA16` = auto-referencias a celdas de más arriba, con un hueco real en `AA7` sin fórmula y un salto irregular en `AA15`) por **`=VLOOKUP(Zn,TC!C$2:D$16,2,FALSE)`** en las 16 filas de las 3 hojas — ahora el tipo de cambio para esta tabla sale directo de la hoja `TC` en vez de depender indirectamente de `Control de Pasivo ML!AI`. Idéntico en las 3 hojas.

2. **Control de Pasivo ML — bloque de control filas 403-409** (columnas AI="Control" v1 / AJ="Control" v2 / AN="Archivos" / AO=diferencia): `AO404`/`AO405` pasaron de comparar contra `AI` a comparar contra `AJ` (`=AN404-AI404` → `=AN404-AJ404`, ídem 405); `AO408`/`AO409` antes no tenían fórmula, ahora sí (`=AN408-AJ408`, `=AN409-AJ409`). Consistente con el cambio 1: el cuadre de control también migró de referenciar la columna `AI` a la `AJ`.

3. **`TC!D2`/`D3`** (valores estáticos, sin fórmula): BR 5,1617→5,0729, AR 1483,45→1487,66 — es la actualización mensual normal del tipo de cambio, no un cambio de lógica.

**⚠️ Migración incompleta detectada (AI→AJ/TC)**: el cambio 1+2 de arriba sugiere que Rosario está migrando de "tipo de cambio vía columna AI de Control de Pasivo ML" a "tipo de cambio vía columna AJ / hoja TC directa". Pero **`Query Acumulaciones` (columnas AC/AD, ~12 referencias) sigue referenciando `'Control de Pasivo ML'!AI` sin cambios** — no se tocó. Si la intención es deprecar `AI` del todo, esta hoja quedó pendiente. **A confirmar con Rosario**: ¿es intencional (todavía no le tocó el turno a esa hoja) o se le pasó?

**Hallazgo adicional, no relacionado a fórmulas**: **cero vínculos externos (`xl/externalLinks/`) en los 3 archivos** (julio y ambas versiones de junio) — ni siquiera el de Cobrand BR a `Contratos con partners - precio de los puntos.xlsx` que la sección 3.3 documentaba como "congelado a feb-2025". Hoy Cobrand BR calcula con `SUMIF(TablaQAc[point_type],...)` local, sin archivo externo. Consistente con que "Cobrand BR está apagada" (sección 31) — no parece ser un cambio de esta sesión de edición, es el estado que ya tenía la base de junio también.

**Reordenamiento cosmético**: la pestaña oculta "Sheet1" pasó de estar después de "Control de Pasivo ML" a estar antes, en julio. Sin impacto funcional.

**Bugs conocidos, re-chequeados, siguen sin tocar** (siguen igual en julio y en la base, Rosario no los tocó en esta edición): `Manual Accrual!E22`/`E23` (siguen refiriendo `D24`/`D25` en vez de `D22`/`D23`), `Manual Accrual!D40` (sigue dependiendo de rango `O:P` en vez de `SUMIFS` sobre `TablaQAc`). `Breakage!Tabla10 col P`, `Breakage!I19:I25`, `Control de Pasivo ML!AN405` y `Redenciones!AG4/AG8/AG18/AG22` — todos OK / sin `#REF!` / vacías como se espera, sin cambios. Barrido global de las 23 hojas: 0 `#REF!` literales, 0 referencias `[N]!` en ninguna hoja.

**Estado**: mapeo completo. Rosario confirmó que lo de `Query Acumulaciones` sin migrar no importa (no hace falta tocarlo). **`config.yaml` ya actualizado (2026-08-03)** para apuntar a la carpeta real de julio: `cierre.mes: 7`, `rutas.carpeta_cierre` → `Cierre 07.2026` (SharePoint), `backup_manual.archivo_cierre: "Cierre 2026 07.xlsx"`. `cierre.hasta_override` sigue comentado/vacío (mes completo, no corte parcial).

## 40. Primera corrida real de julio completo — `run_cierre_backup_manual.py` (2026-08-03)

Corrida contra el Datalake real (VPN conectada), mes completo (01/07 al 01/08, sin `hasta_override`). Archivo verificado LIBRE antes de correr (no estaba abierto en Excel).

**Resultado**: bajó 22.746 filas de Acumulaciones / 12.883 de Redenciones / 5.858 de Puntos Expirados. Guardrails `[0a]` (diccionario de puntos) y `[0c]` (columnas/cobertura) sin novedades (119 codes, sin cambios de columnas, cobertura del CASE OK). Los 3 controles de suma de puntos dieron OK (diferencia 0). Pegado en el archivo de cierre: backup automático creado (`Auditoria/Backups Cierre Mensual/20260803_124053_Cierre 2026 07.xlsx`) antes de escribir, guardado OK. Estado intermedio guardado (`Auditoria/estado_intermedio_asientos.pkl`) para el paso siguiente.

Filas pegadas: Query Acumulaciones 22.746, Query Redenciones 12.883, Breakage 5.858, Acumulacion Non Tender 22.295, Redenciones 5.031, Redenciones SUBS 1.019, Redenciones Otros 6.833, Diccionario 15.

**[REVISAR] esperado, ya investigado y aceptado**: 16 filas de Generacion con "Entidad Legal"/"Producto" vacíos. Confirmado (leyendo la bajada real, filtro `point_type` ANT + `partner="DP"`) que las 16 tienen la misma firma que el caso ya investigado y aceptado en la sección 34 (business/product/payment_type/trip_type/produto vacíos, `channel_condition="Site"`, países BR/AR/CO/MX) — acreditaciones manuales sin producto/negocio, no un bug. El script frena solo (exit code 1) cuando hay algo REVISAR, por diseño — no avanza solo al paso 2.

**⚠️→✅ Falsa alarma sobre "Breakage Esperado", corregida**: en la sección 39 se había marcado esta hoja como "sin ningún cambio" respecto a la base de junio, y de ahí infería (sin chequearlo) que `C4:C9` todavía tenía el % de junio. **Rosario confirmó (2026-08-03) que el valor pegado ya es el de julio** — la explicación real es que la base de `COPIA PRUEBA` ya tenía pegado el valor de julio ANTES de duplicarse a la carpeta real, así que el diff (que compara contra esa base) no podía mostrar diferencia aunque el valor sí fuera el correcto del mes. Lección: "sin cambios contra la base" no es lo mismo que "sin actualizar para el mes real" - la base también puede venir pre-actualizada. Sin pendiente real acá.

**Próximos pasos** (sin automatizar, decisión de la sección 31): (1) Rosario pega/confirma Breakage Esperado de julio real, (2) abre `Cierre 2026 07.xlsx` en Excel, Ctrl+Alt+F9, guarda, (3) avisa para correr `escribir_asientos.py` (lee las columnas ya recalculadas y pega `Asientos Cierre Loyalty.xlsx`, incluido Accounting a valor).

## 41. Bug real: Acumulaciones y Redenciones traían filas del 1° de agosto pese al filtro `< {{Hasta}}` — corregido del lado de Python (2026-08-03)

Rosario reportó que la corrida de la sección 40 trajo datos del 1°/08 en Acumulaciones y Redenciones. Confirmado leyendo las bajadas reales guardadas en `Auditoria/Bajadas`: `acumulaciones_2026_07.xlsx` tenía 410 filas con `processing_date = 2026-08-01` (de 22.746) y `redenciones_2026_07.xlsx` tenía 198 (de 12.883), pese a que las 2 queries de Data filtran `processing_date >= {{Desde}} AND processing_date < {{Hasta}}` (con `{{Hasta}}` = `DATE('2026-08-01')`, sustituido por `pipeline/bajadas.py::_sustituir_fechas` — comportamiento correcto, ver sección 25).

**No es un bug de `config.yaml`/`fechas_cierre()`** (Hasta sigue siendo el día 1 del mes siguiente, exclusive, como debe ser) **ni de las queries** (el filtro está bien escrito). Es un desfasaje de huso horario del propio motor del Datalake en el borde del mes: el predicado `WHERE` y el valor que termina devolviendo la columna no quedan evaluados en el mismo huso horario, así que algunas filas de la madrugada del 1°/08 (huso local) pasan el filtro igual. **Las 2 queries de Control ("sum points") tienen el mismo patrón `{{Desde}}`/`{{Hasta}}`, así que sufren el mismo desfasaje** — por eso el chequeo de cuadre de la sección 40 dio "diferencia 0": estaba comparando dos totales igualmente contaminados con las mismas filas de más.

**Fix (sin tocar ningún `.sql`, ver [[feedback_no_modificar_queries]])**: nueva función `pipeline/bajadas.py::recortar_borde_mes(df, columna_fecha, date_from, date_to, label, columnas_suma)` — recorta en Python cualquier fila fuera de `[Desde, Hasta)`. Se llama en `run_cierre_backup_manual.py` y `run_cierre.py` **DESPUÉS** de `guardar_bajada_auditoria()` (la bajada cruda en `Auditoria/Bajadas` sigue guardándose tal cual viene, sin tocar — constraint inamovible) y antes de los chequeos de cuadre y del cálculo de columnas derivadas. Guarda la suma de puntos descartados en `df.attrs["descartados_borde_mes"]`; `pipeline/validaciones.py` la resta del total de la query de Control antes de comparar, para no romper el guardrail de cuadre con un desfasaje que ahora solo existe de un lado.

Verificado corriendo `recortar_borde_mes` sobre las 2 bajadas reales de julio ya descargadas: descarta las 410/198 filas de agosto correctamente (`processing_date` máximo queda en `2026-07-31`).

**Pendiente**: el archivo de cierre (`Cierre 2026 07.xlsx`) ya tiene pegados los datos CONTAMINADOS de la corrida de la sección 40 (Query Acumulaciones/Redenciones/Breakage/Acumulacion Non Tender/Redenciones/SUBS/Otros/Diccionario). Como `escribir_asientos.py` todavía no corrió, alcanza con volver a correr `run_cierre_backup_manual.py` (ya con el fix) para que baje de nuevo y pise esas solapas con la versión correcta — crea backup automático antes de escribir, como la vez anterior.

## 42. Mapeo de qué se puede borrar del archivo de cierre + chequeo de reconciliación nuevo antes de `escribir_asientos.py` (2026-08-03)

Rosario preguntó si puede eliminar filas de `Query Acumulaciones` y, después, de `Acumulacion Non Tender`/`Redenciones`/`Redenciones SUBS`/`Redenciones Otros`.

**Mapeo de dependencias (releyendo `pipeline_backup/lectura_etapa2.py` y `escritura_asientos.py`):**
- `Query Acumulaciones`: Python la pega una vez y nunca la vuelve a leer — solo la consumen fórmulas de Excel (Cobrand/Partners vía SUMIF). Riesgo ya documentado ahí (no nuevo): Cobrand AR usa un SUMIFS con rango **hardcodeado hasta la fila 53.811** en vez de referencia estructurada a `TablaQAc` — borrar filas antes de esa posición corre todo hacia arriba y ese rango fijo termina sumando un conjunto distinto, sin ningún error.
- `Acumulacion Non Tender` / `Redenciones` / `Redenciones SUBS`: **SÍ tienen una protección explícita** en `escribir_asientos.py` — antes de pegar en Asientos compara la cantidad de filas leídas de la hoja (después del refresco de Excel) contra la cantidad de filas que Python calculó originalmente (guardada en `estado_intermedio`). Si no coinciden, `ValueError` y frena — no sigue con datos desalineados. Matiz: el chequeo es de CANTIDAD, no de identidad; si el conteo total coincidiera por casualidad tras un borrado + agregado, no habría error.
- `Redenciones Otros`: nunca se vuelve a leer (lo que llega a Asientos sale directo del pickle) — borrar filas ahí no rompe nada del lado de Python, pero tampoco hay ningún chequeo que avise.

**Pedido nuevo de Rosario**: antes de correr `escribir_asientos.py` ("la parte 2"), chequear si lo guardado en `estado_intermedio` (la corrida) difiere de lo que hay AHORA en la Tabla de cada una de esas 4 hojas — y si difiere, preguntar por consola (una pregunta POR HOJA que difiera, no una sola global) cómo seguir: (1) ignorar y pegar la versión guardada de la bajada, o (2) usar la versión nueva del archivo de cierre. Alcance pedido explícitamente por Rosario: comparación fila por fila, pero **solo dentro del `ref` de la Tabla de Excel** (`TablaANT`/`TablaRed`/`TablaRedSUBS`/`TablaRedOtros`) — no le importan celdas/tablas auxiliares al costado (ej. el bloque `$AF$2:$AG$16` de TC por transacción, o la tabla de referencia manual al lado de `TablaANT` que motivó el bug de la sección 37).

**Implementado**: `pipeline_backup/reconciliacion_cierre.py` (nuevo módulo), enchufado en `escribir_asientos.py` como paso `[1b]`, entre cargar `estado_intermedio` y leer las columnas de Etapa 2. Detalles de diseño:
- Compara solo las columnas que existen en AMBOS lados (DataFrame guardado ∩ columnas de la Tabla) — las columnas 100% Etapa 2 (`Puntos Valuados`/`DRO`/etc en Acumulacion Non Tender) no están en el DataFrame guardado, quedan afuera solas. Excepción a mano: `Reconocimiento de Ingresos Diferidos ML` en Redenciones/Redenciones SUBS SÍ está en el DataFrame guardado pero como placeholder fijo (`None`, pendiente de Etapa 2) — se excluye explícitamente (si no, compararía `None` contra el valor real de Excel y marcaría diferencia TODOS los meses).
- Columnas numéricas: tolerancia de 0.01 (mismo criterio que `pipeline/validaciones.py`) para no disparar falsos positivos por redondeo entre el cálculo de Python (pickle) y la fórmula de Excel del mismo valor.
- **Detalle técnico no trivial**: `ws.tables` (necesario para saber el `ref` de la Tabla y no leer nada por fuera) **no está disponible en modo `read_only`** de openpyxl (confirmado con una prueba sintética: `ReadOnlyWorksheet` no tiene ese atributo) — a diferencia de `lectura_etapa2.py`, que sí puede usar `read_only=True` porque lee por nombre de columna sin necesitar el `ref` de ninguna Tabla. Por eso este módulo abre el archivo en modo NORMAL (mismo costo ya aceptado en `pegar_todo_manual`, ~2.1 GB/30s) — pero UNA sola vez, cacheada a nivel módulo, reusada para las 4 hojas (`reconciliacion_cierre.cerrar()` la libera al final).
- Verificado con un archivo sintético (Tabla + columna auxiliar fuera del `ref`, simulando el caso real de `Acumulacion Non Tender`): sin cambios → coincide; valor editado → difiere; fila borrada → difiere; columna auxiliar fuera del `ref` correctamente ignorada.

**Pendiente de verificar en vivo**: el archivo real (`Cierre 2026 07.xlsx`) estuvo abierto/en uso durante esta sesión y no se pudo correr el chequeo contra él todavía - falta probarlo de punta a punta la próxima vez que se corra `escribir_asientos.py`.

## 43. Segunda corrida de julio (con el fix de la sección 41) + re-chequeo del caso "16 filas sin Entidad Legal/Producto" (2026-08-03)

Se corrió de nuevo `run_cierre_backup_manual.py` (ya con `recortar_borde_mes`, ver sección 41). Resultado: 408/198 filas descartadas por el desfasaje de huso horario (Acumulaciones/Redenciones), los 3 controles de suma de puntos con `diferencia: 0`, y el mismo `[REVISAR]` de siempre: 16 filas de "Generacion" (el DataFrame de Python que después se pega en `Asientos Cierre Loyalty.xlsx!Generacion` - no existe ninguna solapa "Generacion" en el archivo de cierre) con "Entidad Legal"/"Producto" vacíos.

Filas pegadas esta corrida (más bajas que la sección 40 al sacar las de agosto): Query Acumulaciones 22.341, Query Redenciones 12.685, Breakage 5.858, Acumulacion Non Tender 21.900, Redenciones 4.935, Redenciones SUBS 1.002, Redenciones Otros 6.748, Diccionario 15. Backup automático creado (`20260803_140940_Cierre 2026 07.xlsx`), estado intermedio regrabado.

Rosario preguntó por qué decía "Generacion" si esa solapa no existe en el archivo de cierre - aclarado: es el nombre interno del DataFrame de Python (calculado a partir de `Acumulacion Non Tender`, columnas Z="Entidad Legal"/AA="Producto" en esa hoja, mismo orden que en `Asientos!Generacion`), todavía no pegado en ningún lado visible porque `escribir_asientos.py` no corrió.

Antes de asumir que estas 16 filas eran el mismo caso ya aceptado en la sección 34/40, se planteó una hipótesis alternativa: Python calcula "Filtro P&L" concatenando `country_code+product+business` con el operador `+` de pandas - si `product`/`business` son `NaN` (confirmado: lo son, para estas 16 filas), el resultado es `NaN` y el VLOOKUP-por-diccionario nunca puede matchear nada. En Excel, en cambio, concatenar una celda en blanco con `&` da `""` (no error) - la clave podría quedar parcial en vez de nula, y en teoría podría matchear alguna fila de `Regla entidad Legal` que Python jamás podría alcanzar. **Rosario confirmó que esto NO está pasando** - las 16 filas quedan en blanco tanto en Python como en Excel, es el mismo caso aceptado de siempre (acreditaciones manuales sin producto/negocio, países BR/AR/CO/MX, partner="DP"). Sin divergencia real entre Python y Excel para este caso - la hipótesis quedó descartada, no hace falta ningún ajuste de lógica.

## 47. 2 solapas nuevas en `Asientos Cierre Loyalty.xlsx` — "Alocacion Cobrand-Partners" y "NUEVA V Contabilidad" (2026-09-24)

Rosario modificó `Asientos Cierre Loyalty.xlsx` (carpeta `Cierre 09.2026`, mes de cierre agosto/septiembre 2026) y pidió mapear el cambio en la bitácora, confirmando que no debería romper nada del copiado/pegado porque la idea es que se recalculen solas.

**Inspección del `.xlsx` real** (vía `xl/workbook.xml`, sin abrir el archivo en Excel): el libro pasó de las 11 solapas documentadas en la sección 3.3 a **13 solapas**. Dos no estaban documentadas:

| Solapa | sheetId | Contenido |
|---|---|---|
| **Alocacion Cobrand-Partners** | 14 | Tabla chica (B1:T103, ~100 filas) de reglas de alocación contable. 100% fórmulas: concatena claves de cuenta contable (`D4&"."&N2&"."&...`) y referencia `Accounting!$S$2` para prorratear importes. No tiene ningún bloque de datos crudos pegados a valor — es solo lógica de mapeo. |
| **NUEVA V Contabilidad** | 15 | Tabla grande (A1:O11197, ~11.000 filas). 100% fórmulas, **sin ninguna celda pegada a valor**: `SUMIFS([49]!Tabla1[...], ...)`, `VLOOKUP(..., [49]vlookup!..., FALSE)` — `[49]` es el mismo vínculo externo que ya usan `Accounting` y `TC` (a `Cierre 2026 06.xlsx`/equivalente del mes). Fila 1 = subtotales `SUBTOTAL(9,...)` de control, igual patrón que `Generacion`/`Breakage`/`Redenciones`. Todo se recalcula solo al abrir/refrescar el archivo — no depende de ningún paso manual de copiado.|

**Conclusión — no rompe el proceso existente**:
- Ninguna de las dos solapas nuevas forma parte del bloque de copiado/pegado a valor de Etapa 1 (`Query Acumulaciones`, `Query Redenciones`, `Breakage`, `Acumulacion Non Tender`, `Redenciones`, `Redenciones SUBS`, `Redenciones Otros`, `Diccionario` — esas siguen viviendo en `Cierre MM.YYYY.xlsx`, no en `Asientos Cierre Loyalty.xlsx`).
- Tampoco tocan las solapas de `Asientos Cierre Loyalty.xlsx` donde sí se pega a valor (`Generacion`/`Breakage`/`Redenciones`/`Redenciones Subs`/`Redenciones Otros`) ni el pipeline Python (`escribir_asientos.py`), que solo lee/escribe esas hojas por nombre de Tabla — no toca "Alocacion Cobrand-Partners" ni "NUEVA V Contabilidad", así que **agregarlas no requiere ningún cambio de código**.
- Ambas son downstream de `Accounting` (y, en el caso de "NUEVA V Contabilidad", del mismo vínculo externo `[49]` que ya usaban `Accounting`/`TC`) — consistentes con el patrón ya documentado en la sección 3.3 de solapas que se recalculan en vivo sin pegado manual.

**Acción tomada**: se actualizó la lista de solapas de la sección 3.3 para reflejar las 13 solapas actuales. No se tocó ningún módulo de `pipeline_backup/` — no hacía falta.

**Propósito de negocio (confirmado por Rosario, 2026-09-24)**: "NUEVA V Contabilidad" reemplaza lo que antes se entregaba en un excel de pivots separado ("Asientos Loyalty") — ahora vive como solapa dentro de `Asientos Cierre Loyalty.xlsx` en vez de en un archivo aparte.

## 48. Bug real en el chequeo de reconciliación (sección 42): filas vacías "en el medio" desalineaban Etapa 1 vs Etapa 2, rompiendo fórmulas en Asientos (2026-09-24)

Rosario reportó: el fix de la sección 42 (que le permite editar a mano la base del archivo de cierre — Acumulacion Non Tender/Redenciones/SUBS/Otros — antes de correr `escribir_asientos.py`, con el chequeo `[1b]` que pregunta si usar la versión guardada o la nueva) **"no copia y pega bien las modificaciones"** — eligiendo la opción `[2]` ("usar la versión nueva del archivo de cierre") en el prompt, el resultado en `Asientos Cierre Loyalty.xlsx` terminaba con **fórmulas rotas**.

**Causa raíz encontrada (releyendo `reconciliacion_cierre.py` y `lectura_etapa2.py` en paralelo)**: los dos módulos que leen el archivo de cierre para esta parte del flujo tenían un criterio DISTINTO para filas completamente vacías dentro del rango de la Tabla de Excel:
- `reconciliacion_cierre._leer_tabla()` (lee la versión "nueva" editada, para Etapa 1) **no filtraba filas vacías en absoluto** — si Rosario borraba el CONTENIDO de una fila con Supr (en vez de borrar la fila entera de Excel), esa fila quedaba como una fila de puros `None` dentro del rango de la Tabla, y se colaba tal cual en el DataFrame "nuevo".
- `lectura_etapa2._leer_columnas_por_header()` (lee las columnas de Etapa 2 ya recalculadas — Puntos Valuados/DRO/Reconocimiento ML) hacía lo opuesto: **cortaba la lectura en la PRIMERA fila completamente vacía que encontraba** (pensado originalmente para no leer el padding de filas formateadas sin datos al final de la Tabla) — si esa fila vacía no estaba al final sino en el medio (justamente el caso de un Supr accidental), perdía en silencio TODAS las filas reales que venían después.

Resultado: con una fila vaciada a mano en el medio de la tabla, los dos lectores devolvían **cantidades de filas distintas** (uno la incluye como fantasma, el otro corta ahí) - `escribir_asientos.py` pega las columnas de Etapa 2 por POSICIÓN contra las de Etapa 1 (`df_generacion[columna] = df_cols_generacion[columna].values`, sin index), así que a partir de esa fila todo quedaba corrido una posición - cada fila del asiento contable terminaba con datos de la fila siguiente/anterior, y las fórmulas fijas (que arrastran por fila, ver `_ajustar_filas_formula`) heredaban esa referencia ya desalineada -> fórmulas con resultados sin sentido en Asientos. El chequeo de longitud de `escribir_asientos.py` (`if len(df_cols_generacion) != len(df_generacion): raise ValueError`) no lo agarraba porque, si el corte temprano de `lectura_etapa2` perdía la MISMA cantidad de filas que `reconciliacion_cierre` de más agregaba por la fila fantasma en otro punto, ambos largos podían coincidir por casualidad — pasaba el chequeo y el desalineamiento quedaba invisible hasta abrir el Excel.

**Fix aplicado** (`pipeline_backup/reconciliacion_cierre.py::_leer_tabla` y `pipeline_backup/lectura_etapa2.py::_leer_columnas_por_header`): unificado el criterio en ambos — **saltear (no cortar) cualquier fila completamente vacía, esté donde esté dentro del rango** — así los dos lectores del mismo archivo siempre ven la misma cantidad de filas, en el mismo orden relativo, sin importar en qué posición haya quedado una fila vaciada a mano. De paso se corrigió un bug latente en `_leer_tabla`: ignoraba el número de fila de inicio del `ref` de la Tabla (`min_row=1` hardcodeado) — no afectaba hoy porque las 4 Tablas relevantes arrancan en la fila 1, pero quedaba frágil si alguna vez no fuera así. Ambas funciones ahora imprimen por consola cuántas filas vacías saltearon, como aviso de que probablemente fue un Supr accidental en vez de un borrado de fila real.

**Recomendación operativa para Rosario**: al modificar filas a mano en la base antes de correr `escribir_asientos.py`, **borrar la fila entera de Excel** (click derecho -> Eliminar fila, o seleccionar la fila y Ctrl+"-") en vez de seleccionar el contenido y apretar Supr — así la Tabla se achica de verdad y no queda un hueco vacío en el medio. Con el fix de hoy un hueco accidental ya no rompe el pegado, pero sigue siendo la forma más prolija de editar.

**Pendiente de verificar en vivo**: no se pudo reproducir con el archivo real de Rosario (no se identificó la fila puntual que causó el síntoma) - el fix quedó validado por lectura de código (ambas funciones ahora comparten el mismo criterio), falta confirmar en la próxima corrida real de `escribir_asientos.py` con una edición a mano que antes rompía.

**(2026-09-24) Corrección sobre esta sección**: Rosario confirmó que **nunca usó Supr** para borrar filas - siempre elimina la fila entera de Excel. La hipótesis de esta sección (fila vaciada a mano en el medio de la Tabla) queda **descartada como causa del bug real** que reportó ("se rompen las fórmulas"). El fix de arriba (saltear filas vacías en vez de cortar) sigue siendo una mejora de robustez válida y se dejó aplicada solo en la copia de `Proyectos IA` (nunca se sincronizó a la carpeta real de `despegar365`), pero no resuelve el problema real - ver secciones 49-51 para la investigación que sí encontró causas reales.

## 49. La causa real de "se rompen las fórmulas": vínculos externos + `openpyxl` no preserva la extensión `xxl21:alternateUrls` (2026-09-24)

Después de descartar la hipótesis de la sección 48, se reprodujo el problema real con una corrida de prueba en una carpeta sandbox (`Loyalty_cierre_contable/Cierre 09.2026`, copia de la carpeta real). Historia completa, en orden:

1. Rosario agregó 2 solapas nuevas a `Asientos Cierre Loyalty.xlsx` (ver sección 47: "Alocacion Cobrand-Partners" y "NUEVA V Contabilidad", esta última reemplazando el excel de pivots viejo) - **ambas con fórmulas apuntando a archivos externos** (una a `Pivots Asientos Loyalty 2026 08.xlsx`, la otra a un archivo en `C:\Users\rosario.arancedo\Downloads\` - vínculos mal armados, apuntando a lugares que no correspondían).
2. A partir de ahí, Excel empezó a mostrar al abrir el archivo: `Registros reparados: Referencia de fórmula externa de /xl/externalLinks/externalLinkNN.xml parte (Valores en caché de referencia de fórmula externa)`.
3. Rosario corrigió esos 2 vínculos (los convirtió a fórmulas internas, sin archivo externo) - **el cartel de reparación siguió apareciendo igual.**

**Causa raíz real (confirmada byte a byte)**: comparando el `.xlsx` antes y después de que `pipeline/escritura_asientos.py::pegar_todo()` lo abre y guarda con `openpyxl`, se confirmó que **`openpyxl` descarta la extensión `xxl21:alternateUrls`** (una URL alternativa que Excel/SharePoint agrega a cada vínculo externo, namespace `xmlns:xxl21="http://schemas.microsoft.com/office/spreadsheetml/2021/extlinks2021"`) de **absolutamente todos** los `xl/externalLinks/externalLinkN.xml` del paquete, cada vez que guarda - no es selectivo, no importa si el vínculo está en uso o no. El archivo queda con una parte técnicamente incompleta respecto de lo que Excel espera, y Excel lo nota al abrir y dispara su reparación automática, invalidando en el proceso el caché de todos los vínculos externos del archivo.

**Detalle importante (aprendido a los golpes en esta sesión, ver más abajo el resumen de los 2 intentos fallidos)**: Excel **no borra la "ficha" de un vínculo externo (el `externalLinkN.xml` y sus referencias en `workbook.xml`/`workbook.xml.rels`/`[Content_Types].xml`) solo porque dejaste de usarlo en una fórmula** - queda declarada/huérfana en el archivo indefinidamente, aunque nadie la use. Mientras esa ficha exista y le falte la extensión `xxl21`, el cartel de reparación sigue apareciendo, la use alguien o no.

**2 intentos de arreglo, ambos rompieron algo real antes de encontrar el camino correcto - documentado para no repetir el error:**

- **Intento 1 (revertido)**: agregar a `escritura_asientos.py` un paso que, después de `wb.save()`, reabre el `.xlsx` como zip y reinserta el bloque `xxl21:alternateUrls` tomándolo de un backup previo. Rosario pidió explícitamente que no se tocara el código de esta forma (prefiere no tener parches automáticos silenciosos en el pipeline para esto) - revertido sin aplicar.
- **Intento 2 (rompió "Control" temporalmente, después re-corregido)**: se intentó sacar del archivo, a mano (edición directa del `.xlsx` como zip, quitando la ficha de `[Content_Types].xml` + `workbook.xml.rels` + `workbook.xml` + los 2 archivos `externalLinkN.xml`/`.rels`), el vínculo que en ESE momento parecía huérfano. **Error real cometido**: el chequeo de "¿está en uso?" se hizo sobre el archivo YA PROCESADO por `escribir_asientos.py` (que pisa `Accounting` con valores fijos, ver `pegar_accounting`) - en ese archivo procesado, efectivamente ya no quedaba ningún uso. Pero el vínculo SÍ estaba en uso en el archivo ORIGINAL (antes de correr el script): la hoja `Accounting` tenía 171 celdas con fórmulas reales tipo `=[Cierre 2026 08.xlsx]Partners!P5` (además de un bloque chico de verificación cruzada en columnas R:S, ver sección 51). Al sacar la ficha del vínculo con esas fórmulas todavía vivas en el archivo de origen, se rompió Accounting de verdad la primera vez que se probó.
- **Corrección final (aplicada, funcionó)**: se re-verificó, esta vez **sobre el archivo real antes de que Python lo tocara** (no sobre la salida de mi propio script), que **ningún** vínculo externo estuviera en uso - ni por fórmulas de celda (todas las hojas escaneadas), ni por nombres definidos, ni por ninguna otra parte del XML. Solo entonces se sacó la ficha huérfana (`externalLink47`, la única que apuntaba al archivo de cierre real, `Cierre 2026 08.xlsx`) de los 3 lugares donde está declarada. Verificado: 0 rastros de esa ficha en todo el paquete, el archivo abre bien, y **el cartel de reparación desapareció** (confirmado por Rosario abriendo el archivo en Excel).

**Lección operativa para el futuro** (para Rosario y para no repetir el error): antes de sacar CUALQUIER ficha de vínculo externo de un `.xlsx`, hay que confirmar que no está en uso **en el archivo tal cual lo entrega/edita Rosario**, nunca en una copia ya procesada por el pipeline (que puede haber pisado con valores la hoja que usaba el vínculo, ocultando el uso real). Buscar en: fórmulas de celda de TODAS las hojas, nombres definidos (`workbook.xml!definedNames`), y cualquier otra parte del XML que pueda referenciar el `rId` del vínculo.

**Nota aparte, no resuelta, fuera de alcance por pedido explícito de Rosario**: el archivo tiene ~46 fichas de vínculos externos adicionales, **heredadas de hace años** (planillas de Brasil/Francia, ~2002-2018, ej. `Modelo CCDI 3007.xls`, `Balanço Difusão 2009.xls`) y ~6.471 nombres definidos heredados (la mayoría ya en `#REF!`), de los cuales ~429 referencian esos vínculos viejos. Esas fichas nunca dispararon el cartel de reparación (a diferencia de la que sí se usaba activamente) porque son de un formato de Excel más viejo que nunca tuvo la extensión `xxl21` para empezar - `openpyxl` no tiene nada que "perder" ahí, así que nunca las corrompe. Rosario pidió explícitamente NO tocar esto ("no amplíes el alcance") - queda documentado como deuda técnica conocida, no como una tarea pendiente activa.

## 50. Nueva sección "Cobrand" en Colombia dentro de `Accounting` (archivo de cierre) - septiembre 2026 (2026-09-24)

Rosario agregó una sección "Cobrand" para Colombia en la hoja `Accounting` del archivo de cierre (`Cierre 09.2026/Cierre 2026 09.xlsx`), país que hasta agosto solo tenía "Manual Accrual" y "Flash Points redimidos" (ver sección 3.3: "Colombia/Peru (Manual Accrual, Flash Points)" - ahora desactualizado para Colombia, sigue vigente para Peru).

**Mapeo exacto del cambio** (comparando `Cierre 2026 08.xlsx` real, 115 filas totales en Accounting, contra `Cierre 2026 09.xlsx` real, 120 filas):
- Agosto: fila 86 `Colombia` → fila 87 `Manual Accrual` directo.
- Septiembre: fila 86 `Colombia` → fila 87 `Cobrand` (nuevo) → filas 88-91 (`Concepto/Importe USD/Importe ML/Cuenta/Item` con 3 conceptos: `Bank Revenue`, `SSP [Programa de puntos Despegar]`, `Crédito COBRANDED ICBC`) → fila 92 `Manual Accrual` (lo que antes era la fila 87, corrido +5).
- Neto: **+5 filas** insertadas dentro del bloque de Colombia, todo lo que viene después se corre +5 filas respecto de agosto.

**Impacto en el pipeline - ninguno en la lectura, uno real en el pegado (ver sección 51)**:
- `pipeline_backup/lectura_etapa2.py::leer_accounting()` lee la hoja `Accounting` entera con `ws.iter_rows(values_only=True)` sin ningún límite de filas hardcodeado - **ya se adapta sola** a que la hoja ahora tenga 120 filas en vez de 115, sin ningún cambio de código necesario.
- `pipeline/escritura_asientos.py::pegar_accounting()` (que pega esto en `Asientos!Accounting`) también maneja el cambio de cantidad de filas sin problema (`filas_nuevas = len(valores)`, `fila_max = max(fila_vieja_max, filas_nuevas)` - ya contemplaba que la fuente creciera o se achicara). **El problema no fue el cambio de filas de Colombia en sí** - fue un bug de ancho de columnas ya latente, que la sección 51 explica y corrige.

## 51. Bug corregido en `pegar_accounting()`: pisaba con blanco 2 bloques agregados a mano al costado de Accounting (2026-09-24)

Rosario migró a `Asientos Cierre Loyalty.xlsx!Accounting` **dos bloques distintos** que antes vivían en el excel de pivots viejo (`Pivots Asientos Loyalty 2026 08.xlsx`, que se está dejando de usar - ver sección 47, mismo criterio que "NUEVA V Contabilidad": la idea es que queden 100% fórmula, sin que haga falta copiar/pegar nada ahí nunca). Ambos ya están armados como fórmulas 100% internas (sin ningún vínculo a archivo externo, confirmado leyendo el archivo real):

- **Columnas I:N** (~130 filas): tabla grande de detalle "Partner Revenue" por país/producto - `Concepto`, `Moneda`, `Importe ML`, `Cuenta`, `Item`. La columna `Importe ML` (L) es formula interna contra la otra solapa nueva: ej. `L6: ='Alocacion Cobrand-Partners'!Q4`.
- **Columnas R:S** (~15 filas): mini tabla de verificación cruzada ("Check") - ej. `R2: Partner Revenue BR` / `S2: =C15` (`C15` es una celda de la propia hoja Accounting, columna C = Importe ML del bloque principal A:E).

**Bug**: `pegar_accounting()` calculaba el ancho de columnas a pegar como `ws.max_column` **del destino** (`Asientos!Accounting`, tal cual estaba ANTES de pegar) - un criterio que tenía sentido en su diseño original (ver Bitácora sección 31: en ese momento la FUENTE, el archivo de cierre, tenía más columnas que el destino - A:L contra A:E - y se quería recortar la fuente al ancho angosto del destino). Pero al agregar Rosario los bloques I:N y R:S, `ws.max_column` del destino pasó a ser 19 en vez de 5 - y la función, al pegar los valores de la fuente (que siempre fueron angostos, A:E = 5 columnas, confirmado en `Cierre 2026 09.xlsx`: las 120 filas tienen uniformemente 5 columnas), **escribía `None` en las columnas 6 a 19 de cada fila** porque el `valor = fila[j-1] if j-1 < len(fila) else None` no tenía nada que copiar ahí - pisando ambos bloques (I:N y R:S) con blanco en cada corrida.

Esto explica por qué "antes no rompía": mientras `Asientos!Accounting` fue angosta (A:E, antes de que existieran estos bloques), `ws.max_column` coincidía con el ancho real de la fuente y no había ningún problema. El bug se activó recién cuando Rosario extendió la hoja con I:N y R:S - la primera corrida de `escribir_asientos.py` después de eso los borró.

**Fix aplicado** (`pipeline/escritura_asientos.py::pegar_accounting`, tanto en la carpeta real `despegar365/.../Automatizacion Cierre` como en la copia de `Proyectos IA`): el ancho de pegado ahora se calcula desde la FUENTE (`columnas_destino = max((len(fila) for fila in valores), default=0)`), nunca desde el destino. Con esto, `pegar_accounting` nunca toca ninguna columna más allá de las que trae el archivo de cierre (A:E) - sin importar qué se agregue a mano al costado en `Asientos!Accounting` (I:N, R:S, o cualquier otro bloque futuro), ni cuánto crezca o se achique la fuente mes a mes (ver sección 50: el caso de Colombia +5 filas ya funcionaba bien independientemente de este bug, porque nunca dependió del ancho).

**Pendiente de confirmar por Rosario**: falta correr `escribir_asientos.py` con el fix aplicado sobre `Cierre 2026 09.xlsx` (el mes real, septiembre) y confirmar que los bloques I:N y R:S en `Asientos!Accounting` quedan intactos y que la sección Cobrand Colombia se pega bien en las filas nuevas.
