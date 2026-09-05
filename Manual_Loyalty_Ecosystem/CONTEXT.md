# Manual Loyalty Ecosystem

Landing GAS de **solo lectura** que sirve el manual técnico del repo Loyalty Ecosystem: arquitectura, glosario, recetas por tarea, quién hace qué, referencia del pipeline y los datos. Mismo patrón que `Manual_B2B_WLs` en `B2B_Ecosystem`.

## Stack

- **`manual.html`** — todo el contenido (una sola página, CSS + JS inline). Navegación por `showSection(name)`.
- **`Codigo.js`** — solo `doGet()` → devuelve `manual.html`. Sin `doPost`, sin formularios.
- No tiene Python, ni JSON, ni pipeline. No consume datos.

## Estructura del repo

Subcarpeta de `Loyalty_Ecosystem/` con su **propio `.clasp.json`** (el repo de Loyalty es plano; esto es la excepción, replicando el patrón de B2B). Los comandos clasp del dashboard se corren desde la raíz; los de este manual, desde `Manual_Loyalty_Ecosystem/`.

- **scriptId**: `1SrytXvn5f44QzqanJGfuJQI80K4A9-oFDebmc2Bj791pDwSWRkWv_6Xq`
- **`.claspignore`**: allowlist `appsscript.json` / `Codigo.js` / `manual.html`.

## Deploy

```powershell
cd Manual_Loyalty_Ecosystem
clasp push -f
clasp deploy -i <deploymentId> -d "descripción"
```

El deploymentId estable se completa después del primer deploy (`clasp deployments`).

## Cómo mantenerlo

El contenido se mantiene **a mano**. Cuando cambie el pipeline, las queries, los IDs de Drive, el mapeo de programas o la arquitectura, actualizar `manual.html` también.
