# Video de presentación del Loyalty Ecosystem (Remotion)

Video animado de 2:50 (1920×1080, 30 fps) para presentar el ecosistema a dirección. Misma historia que `Manual_Loyalty_Ecosystem/presentacion.html`, en formato MP4 con texto y música.

```bash
npm install
npm run studio     # Remotion Studio en http://localhost:3000
npm run render     # MP4 en out/loyalty_ecosystem.mp4
```

## Assets (`public/`)

| Archivo | Qué es | Si falta |
|---|---|---|
| `screens/01_pnl.png` | P&L Contable, pestaña TOTAL, con los Drivers B2C visibles | placeholder rayado "FALTA SCREENSHOT" |
| `screens/02_metricas.png` | Gráfico de acumulación de Pasaporte D! con las 3 barras (FY26 · Budget · FY27) | placeholder |
| `screens/03_variaciones.png` | Waterfall de Análisis variaciones + tabla de efectos | placeholder |
| `screens/04_one_revenue.png` | Tabla de Reglas One Revenue (va de fondo, atenuada) | fondo liso |
| `music.mp3` | Música de fondo (fade in, fade out en los últimos 2 s, más baja en las escenas de vistas) | sin música |
| `sfx/click.mp3`, `sfx/logo.mp3` | Opcionales: click del cursor y aparición del logo | sin efecto |

Capturas en **1920×1080 PNG**. El dashboard pide login de Despegar, así que se sacan a mano.

## Ajustar después de cargar las capturas

En `src/scenes/S4Pnl.tsx`, `S5Metricas.tsx` y `S7Variaciones.tsx`, `cams` define a dónde hace zoom la cámara y `clicks` dónde hace clic el cursor. Las dos usan coordenadas 0..1 **sobre la captura** (0,0 = arriba a la izquierda). Están puestas aproximadas; corregirlas mirando la captura real en Studio.

Duraciones y volumen de música por escena: `SCENES` en `src/Video.tsx`.
