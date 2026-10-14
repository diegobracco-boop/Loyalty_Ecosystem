import React from "react";
import { ScreenScene } from "../components/ScreenScene";

// 1:55–2:25 · Análisis variaciones. Ajustar focos cuando esté public/screens/03_variaciones.png.
export const S7Variaciones: React.FC = () => (
  <ScreenScene
    eyebrow="Vista 3 · Análisis variaciones"
    title="Del Budget al Actual"
    file="screens/03_variaciones.png"
    cams={[
      { at: 0, fx: 0.5, fy: 0.5, zoom: 1 },
      { at: 70, fx: 0.5, fy: 0.5, zoom: 1 },
      { at: 140, fx: 0.15, fy: 0.35, zoom: 1.7 }, // barra Budget
      { at: 260, fx: 0.5, fy: 0.35, zoom: 1.7 }, // Δ por línea
      { at: 400, fx: 0.85, fy: 0.35, zoom: 1.7 }, // barra Actual
      { at: 470, fx: 0.85, fy: 0.35, zoom: 1.7 },
      { at: 560, fx: 0.5, fy: 0.8, zoom: 1.6 }, // tabla de efectos
      { at: 800, fx: 0.5, fy: 0.8, zoom: 1.6 },
      { at: 870, fx: 0.5, fy: 0.5, zoom: 1 },
    ]}
    clicks={[{ at: 620, x: 0.3, y: 0.78 }]}
    notes={[
      { at: 100, title: "Budget → Actual", sub: "El Δ de cada línea del P&L" },
      { at: 420, title: "Volumen", sub: "ΔQ × precio Budget" },
      { at: 540, title: "Precio", sub: "ΔP × cantidad Budget" },
      { at: 660, title: "Cruzado y no explicado", sub: "Por país, mes y producto" },
    ]}
  />
);
