import React from "react";
import { ScreenScene } from "../components/ScreenScene";

// 0:35–1:05 · P&L Contable. Focos y clicks en coordenadas 0..1 de la captura:
// ajustarlos cuando esté public/screens/01_pnl.png.
export const S4Pnl: React.FC = () => (
  <ScreenScene
    eyebrow="Vista 1 · P&L Contable"
    title="Baseline contra Goal"
    file="screens/01_pnl.png"
    cams={[
      { at: 0, fx: 0.5, fy: 0.5, zoom: 1 },
      { at: 60, fx: 0.5, fy: 0.5, zoom: 1 },
      { at: 120, fx: 0.45, fy: 0.22, zoom: 1.7 }, // Drivers B2C
      { at: 330, fx: 0.45, fy: 0.22, zoom: 1.7 },
      { at: 400, fx: 0.85, fy: 0.08, zoom: 1.9 }, // selector Budget / Run Rate
      { at: 560, fx: 0.85, fy: 0.08, zoom: 1.9 },
      { at: 630, fx: 0.5, fy: 0.85, zoom: 1.7 }, // TOTAL LOYALTY y Δ
      { at: 790, fx: 0.5, fy: 0.85, zoom: 1.7 },
      { at: 870, fx: 0.5, fy: 0.5, zoom: 1 },
    ]}
    clicks={[
      { at: 460, x: 0.86, y: 0.08 },
      { at: 520, x: 0.93, y: 0.08 },
    ]}
    notes={[
      { at: 90, title: "Actuals + Run Rate", sub: "contra Budget, Run Rate o Forecast" },
      { at: 270, title: "Drivers B2C arriba", sub: "Orders, GB, Up Front + Fees" },
      { at: 450, title: "Solo marca Despegar", sub: "Mes, Q o Half" },
      { at: 650, title: "% sobre GB", sub: "Comparable entre países" },
    ]}
  />
);
