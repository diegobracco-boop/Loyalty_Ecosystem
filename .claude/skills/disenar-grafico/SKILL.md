---
name: disenar-grafico
description: "Ayuda a ELEGIR la mejor forma de visualizar un dato del dashboard de Loyalty (no solo a que quede lindo): dado qué pregunta responde el gráfico y qué forma tienen los datos, recomienda el tipo de gráfico correcto, cómo montarlo con los helpers de Chart.js del repo, y qué gotchas del dominio respetar. Invocar cuando el usuario dice 'qué gráfico uso para…', 'cómo muestro esto', 'diseñar un gráfico', 'este chart no se entiende', 'mejor forma de visualizar', o va a agregar/rediseñar un chart en dashboard.html."
---

# Diseñar un gráfico — Loyalty Ecosystem

El objetivo de esta skill es **elegir bien la forma**, no solo el color. Un gráfico
que responde la pregunta equivocada sigue estando mal aunque use la paleta oficial.
El orden es siempre: **pregunta → forma → montaje → estética**. La estética (paleta,
contraste, tipografía) viene al final y la cubre la skill `dataviz` de Anthropic —
cargala **después** de decidir la forma, no antes.

> Esto NO reemplaza a `dataviz` (sistema de color, marks, accesibilidad) ni al agente
> `ux-designer` (`ux-consistency-review`, que audita lo ya construido). Esta skill es
> la decisión de **qué forma** darle a un dato nuevo, específica del dominio Loyalty.

## Paso 1 — Antes de dibujar nada, contestá estas 4 preguntas

Nunca elijas el tipo de gráfico por costumbre ("siempre uso barras"). Elegilo desde
la pregunta. Si el usuario no las dejó claras, preguntá:

1. **¿Qué pregunta responde este gráfico?** Redactala en una frase que empiece con
   "¿Cómo evoluciona…?", "¿Cuánto aporta cada…?", "¿Se cumple la meta de…?",
   "¿Cómo se compara X contra Y?". Si no podés escribir la frase, todavía no hay
   gráfico — hay un dato buscando una excusa.
2. **¿Qué forma tiene el dato?** Serie temporal (mes a mes) · composición (partes de
   un total) · comparación entre categorías (países, tiers, planes) · relación
   (puntos vs GB) · un solo número clave (KPI).
3. **¿Cuál es la comparación que importa?** Contra el año pasado (LY)? Contra la
   meta (Goal/Baseline)? Entre categorías? Contra el mes anterior? **Esa comparación
   define el encoding principal**, no un adorno.
4. **¿Quién lo lee y en cuánto tiempo?** El dashboard es de uso diario de Loyalty +
   Control de Gestión. Criterio: alguien tiene que entender el estado en **<10 s**.
   Si no, la forma está sobrecargada.

## Paso 2 — Elegí la forma (heurística por pregunta)

Buscá la fila de tu pregunta. La columna "Por qué / gotcha" tiene el motivo, no solo
la regla.

| La pregunta es… | Forma correcta | Por qué / gotcha |
|---|---|---|
| **¿Cómo evoluciona un total mes a mes?** (acumulación, redención, stock, altas) | **Barras verticales** por mes, con **línea LY superpuesta** | Es el patrón de siempre del dashboard (`buildBarChart`/`buildStackedBarChart`). Barras = magnitud por período; línea = referencia LY. NO líneas para el CY: el negocio piensa cada mes como un bloque, no como un flujo continuo. |
| **¿De qué se compone ese total?** (revenue = costo SSP + margen; stock por plan; altas por canal) | **Barra apilada** (`buildStackedBarChart`, `stacked=true`) | Apilar solo si las partes **suman al total** y son ≤4-5 categorías. Más de 5 → la de abajo se lee, las de arriba no. Si lo que importa es comparar las partes entre sí (no el total), NO apiles: barras agrupadas. |
| **¿Se cumple la meta?** (P&L: Actual vs Baseline vs Goal) | **Tabla** con Δ coloreado, o barras Baseline/Goal lado a lado | El P&L ya es tabla — respetalo, es la familia visual de B2B (`Inputs_Planning_PnL`). El color del Δ va con **signo/flecha además del color** (daltonismo). |
| **¿Cuánto aporta cada categoría a un total?** (puntos por país, por tier) | **Barras horizontales ordenadas** de mayor a menor | Ordená por valor, no alfabético. Horizontal si las etiquetas son largas (nombres de país/partner). |
| **¿Qué proporción del total es X?** (penetración, % pagado con puntos) | **Un número grande (KPI)** o barra de progreso; torta/dona **solo si son 2-3 partes** | Una torta de 5 tiers es ilegible — es el hallazgo clásico del `ux-designer`. Para "% de un total", casi siempre un KPI con su contexto es más claro que una torta. |
| **¿Cómo se relacionan dos variables?** (ratio de acumulación: puntos vs GB gastado) | **Scatter**, o línea de ratio derivado | Solo si de verdad importa la correlación. Si el ratio es EL número, mostralo como línea/serie derivada, no obligues a leer una nube de puntos. |
| **Un solo número que importa hoy** (padrón total, saldo de pasivo del cierre) | **KPI card** con comparación (vs LY / vs mes anterior) | No hagas un gráfico de una sola barra. El número + su Δ contextual alcanza. |
| **¿Cómo se llega del saldo inicial al final?** (roll-forward de pasivo) | **Waterfall** (saldo + acum − redén − breakage) | Es la forma natural del roll-forward. Hoy la pestaña Pasivo lo hace en tabla/puntos; si se grafica, waterfall es la forma correcta. |

### Descartes rápidos (errores frecuentes en este dashboard)
- **Torta/dona con >3 categorías** → barras ordenadas. Casi siempre.
- **Doble eje Y** (dos escalas distintas en un mismo chart) → separá en dos gráficos
  o normalizá a índice/%. El doble eje engaña sobre la relación entre las series.
- **Líneas para categorías no ordenadas** (países, planes) → barras. La línea implica
  continuidad; entre categorías no hay continuidad.
- **Apilar cosas que no suman a un total con sentido** → agrupá o separá.
- **Charts lado a lado (`grid-2`)**: DESCARTADO por preferencia explícita de Rosario
  (01-sep) — los gráficos van **apilados**, formato de siempre. No reactivar `.grid-2`
  sin confirmarlo con ella. Ver `[[dashboard-design-y-recomendaciones]]`.

## Paso 3 — Gotchas del dominio que la forma DEBE respetar

Estos no son estética — si los ignorás, el gráfico **miente**. Todos ya resueltos en
el código; replicá el criterio en cualquier chart nuevo.

- **Año fiscal abr→mar, no calendario.** Las series mensuales usan `fiscalSeries()`
  (`FISCAL_MONTHS`/`FISCAL_LABELS`). El eje X arranca en abril.
- **Meses futuros del año fiscal = barra CY en 0 con LY real encima.** A mitad del año
  fiscal, oct-mar todavía no pasaron → la barra CY es 0 pero la línea LY ya tiene dato,
  y parece una caída que no existe. **Solución obligatoria:** atenuar el tramo sin dato
  CY con `noDataYet(i)` + `lightenColor()` (alpha .22), como ya hacen `buildBarChart` y
  `buildStackedBarChart`. `lastDataIdx` = último mes con dato CY real sumando **todos**
  los datasets de ESE chart. Ver `[[dashboard-fiscal-year-nodata-gotcha]]`.
- **El mes en curso es parcial** (hasta el último sync) vs un LY completo → otra caída
  aparente. Si el gráfico invita a comparar el último mes, tenelo en cuenta al redactar
  el título/subtítulo.
- **"% vs LY" de los KPIs compara CY parcial vs LY completo** — estructuralmente el CY
  siempre da "menor". Rosario decidió NO tocarlo (08-sep). No lo "arregles" en un chart
  nuevo sin confirmarlo; si tu gráfico depende de esa comparación, aclarala.
- **`getPts()` hace `Math.abs()`** (compartida con redenciones) — un grupo con neto
  negativo (cancelaciones > accrual) se ve como un positivo chico, no negativo. Si tu
  gráfico necesita mostrar netos con signo, no reuses `getPts()` a ciegas.
- **Valor USD tiene 3 métodos excluyentes** (`getAcumUsd`): precio (Cobrand/Partners),
  puntos×SSP (IFOOD/Acciones Mkt/Club Despegar), DRO (Pasaporte D!). No mezcles fuentes
  de valor en una misma serie sin chequear cuál aplica. Ver `[[dro-valor-acumulado-formula]]`.

## Paso 4 — Montaje (reusá, no reinventes)

- **No escribas un chart de Chart.js desde cero.** Usá los helpers existentes en
  `dashboard.html`:
  - `buildBarChart(canvasId, prevValues, currValues, prevLabel, currLabel, color, fmtFn, priceSeries)`
    — barras CY + línea LY (+ línea de precio/pt opcional). Ya trae el atenuado
    `noDataYet`.
  - `buildStackedBarChart(canvasId, datasets, fmtFn, stacked, lineOverlay)` — apiladas
    o agrupadas, con overlay LY opcional. Ya trae `lightenColor`/`noDataYet`.
  - `fiscalSeries(...)` para armar los 12 valores del eje fiscal.
- **Formato de números**: pasá el `fmtFn` correcto (puntos vs USD vs %). No dejes
  números crudos sin separador de miles.
- **Consistencia TOTAL vs país**: el mismo tipo de componente debe verse igual en la
  pestaña TOTAL y en las de país. Si tu chart nuevo aparece en ambas, que use el mismo
  helper y el mismo formato.

## Paso 5 — Recién ahora, la estética

Con la forma decidida y montada, **cargá la skill `dataviz`** para: paleta (lila
oficial Despegar `#550fed` y familias VERDE/ROJO — ver la lista en
`ux-consistency-review`), contraste AA, orden de series, leyendas y tooltips. Reglas
que no se negocian:
- **Paleta oficial Despegar**, no Tailwind. Acento `--accent: #550fed`.
- **Verde=positivo / rojo=negativo** consistente en todo el dashboard, **con signo o
  flecha además del color** (daltonismo).
- **Contraste AA** (4.5:1 texto normal). Ojo con la línea atenuada `.22` — está por
  debajo de 3:1; si el chart depende de que se lea, subí el alpha o cambiá el patrón.
- Si el gráfico usa el atenuado "sin dato todavía" y nadie más lo explica, agregá un
  **texto/tooltip breve** que diga qué significa la línea más clara (hoy no existe en
  ningún chart — buen momento para sumarlo).

## Salida esperada de esta skill

Cuando alguien te pide diseñar un gráfico, respondé con:
1. **La pregunta** que el gráfico responde, en una frase (validada con el usuario).
2. **La forma elegida** + por qué, y qué descartaste.
3. **Cómo montarlo** con qué helper y qué datos, señalando los gotchas del Paso 3 que
   apliquen.
4. Solo entonces, la nota estética (delegando en `dataviz` para el detalle).

Si la pregunta del Paso 1 no se puede escribir, decilo: probablemente no haga falta un
gráfico nuevo (un KPI o una fila de tabla alcanza).
