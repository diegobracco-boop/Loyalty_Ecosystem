---
name: ux-consistency-review
description: Revisión de estética y experiencia de usuario del `dashboard.html` de Loyalty — uso de la paleta oficial Despegar, tipografía, espaciado, jerarquía visual, accesibilidad, consistencia interna (pestaña TOTAL vs país) y contra el P&L Accounting del ecosistema B2B. Usar antes de publicar un componente nuevo o cuando el usuario pida revisar estética o proponer mejoras de UI.
---

# UX Consistency Review — Loyalty Ecosystem

Revisión del `dashboard.html` de Loyalty (SPA de una sola página, tema claro). Esta skill no corrige HTML/CSS — devuelve un veredicto, hallazgos por eje y una lista de mejoras propuestas para que el usuario decida.

## Veredicto primero (si el usuario dijo para qué se usa)

Cuando el usuario declara un uso ("lo reviso con finance", "lo presento", "es de uso diario del equipo"), **arrancá el reporte con un veredicto de 2-3 líneas**: ¿el diseño y la experiencia están **aprobados para ese uso**, o hay algo que todavía falla? Bloqueantes numerados arriba, antes del reporte por eje. Un hallazgo es **bloqueante para el uso declarado** si rompe la tarea principal de ese usuario (ej. "el chart central no se lee proyectado", "no funciona en mobile"). El resto es pulido.

## Paleta oficial Despegar (referencia — no inventar otros tonos)

Códigos de Google Sheets (para presentaciones, pensados para fondo claro — este dashboard es claro, así que aplican directo):

**LILA** — `#550fed` (1) · `#3d00d1` (2) · `#976cf6` (3) · `#a780ff` (4) · `#a780ff` @44% (5)
**VERDE** — `#029687` (1) · `#009999` (2) · `#a3e6dd` @38% (3) · `#ccf3ee` @33% (4) · `#adeddd` (5) · `#4bb8aa` (6)
**ROJO** — `#ff5454` (1) · `#fa503f` (2) · `#fbbdbd` (3) · `#fff2f2` (4)

Estado conocido (verificar, no asumir): `dashboard.html` hoy define `--accent: #5626e9` (NO es lila oficial), `--green: #16a34a` y `--red: #dc2626` (Tailwind, no Despegar). El P&L Contable de Loyalty y el de B2B (`P&L_Accounting`) comparten la misma fuente de datos (`Inputs_Planning_PnL`) y deberían sentirse de la misma familia visual.

## Eje 1 — Paleta de color

- Grep por hex codes (`#[0-9a-fA-F]{6}`) y `rgba(...)` en `dashboard.html`. Cualquier color con función de marca (positivo/negativo en el P&L, acento lila) que NO esté en la paleta oficial es un hallazgo.
- Uso inconsistente de significado: verde=positivo/rojo=negativo en el Δ del P&L y en las tablitas de altas/bajas — ¿es igual en todas las secciones y pestañas?
- Valores de color repetidos como literales en vez de variable CSS — si el mismo hex aparece hardcodeado en 5+ lugares, candidato a `var()`.

## Eje 2 — Consistencia

**Interna** (pestaña TOTAL vs pestañas de país):
- Mismo tipo de componente debería verse igual: el chart de barras de miembros por tier, la tablita de altas/bajas de Club Despegar, el selector de período (Mes/Q/Half), los badges de Δ. Señalar si la pestaña TOTAL renderiza algo distinto de las de país sin razón.

**Contra el ecosistema B2B** (`P&L_Accounting/dashboard.html`):
- El **P&L Contable** (Baseline vs Goal, selector de período, Δ) es conceptualmente el mismo componente que la vista EPM de P&L Accounting. Comparar tratamiento visual — tabla, colores de Baseline/Goal, waterfall si hay. Loyalty debería reconocerse como parte de la misma familia (misma fuente de datos).
- Header, tabs, tipografía de títulos, selectores.

## Eje 3 — Tipografía y espaciado

- Familia de fuente, tamaños de título/cuerpo, unidades de padding/margin — coherentes internamente y con el estilo del ecosistema.
- Uso de estilos inline vs. clases — no es hallazgo de código, pero sí de mantenibilidad si dificulta aplicar la paleta de forma consistente.
- `body` con `font-size` explícito (no heredar los 16px del browser).

## Eje 4 — Jerarquía visual, legibilidad y accesibilidad

- **Contraste** texto/fondo suficiente (AA = 4.5:1 normal, 3:1 para ≥18px o bold). Chequear `--muted: #64748b` sobre `--bg: #f1f5f9` y sobre `#fff`, y cualquier texto chico sobre fondos de color.
- **Tamaños de fuente** demasiado chicos para datos críticos (montos del P&L, deltas, totales de miembros).
- **Color como único indicador** en los Δ del P&L y en altas/bajas — daltonismo rojo/verde. ¿Hay flecha/signo además del color?
- **Operable por teclado**: los `.ctab` (pestañas de país) y cualquier `<div onclick>` — ¿son focusables y responden a Enter/Espacio? ¿Hay `:focus-visible` visible?
- **Responsive / mobile**: buscar `@media` que escondan navegación (las `.country-tabs` ya tienen `overflow-x: auto`, bien) o contenido sin reemplazo. Confirmar que abajo de ~640px sigue siendo usable.

## Eje 5 — Elección de gráfico y diseño de tablas

- **Tipo de gráfico correcto**: línea para series temporales (evolución mensual de acum/reden, miembros), barras para comparaciones entre categorías (tiers, planes), torta/dona SOLO con <3 categorías. Señalar cualquier chart con el tipo equivocado (ej. una torta de 5 tiers).
- **Diseño de tablas**: texto a la izquierda, números a la derecha (chequear `text-align` en las celdas de monto del P&L y en la tablita de altas/bajas). Celdas concisas.
- **Carga cognitiva**: dato o texto redundante. Criterio: alguien debería entender el estado de una sección en menos de 10 segundos.

## Eje 6 — Plantillas de email

**No aplica.** El dashboard de Loyalty no envía correo (sin `MailApp`/`GmailApp`). Decilo explícitamente y saltealo.

## Reporte final

1. **Veredicto** (si hay uso declarado): 2-3 líneas + bloqueantes numerados.
2. Un heading por eje (`## Paleta de color`, `## Consistencia`, `## Tipografía y espaciado`, `## Jerarquía visual, legibilidad y accesibilidad`, `## Elección de gráfico y diseño de tablas`, `## Plantillas de email`). Hallazgos con línea + valor concreto.
3. **Mejoras propuestas**, separadas en:
   - **Bloquea el uso declarado** (o **Alto impacto** si no hay uso declarado).
   - **Pulido** (inconsistencia entre secciones = Medio, detalles = Bajo).

Cada mejora: qué cambiar, dónde (línea/selector), y a qué valor de la paleta oficial mapea. No aplicar los cambios.
