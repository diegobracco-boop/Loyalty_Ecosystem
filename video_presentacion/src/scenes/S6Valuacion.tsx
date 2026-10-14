import React from "react";
import { AbsoluteFill } from "remotion";
import { Enter, Eyebrow, Title } from "../components/anim";
import { C, F, PAD_X } from "../theme";

// 1:35–1:55 · Tres métodos de valuación según quién paga el punto.
const METODOS = [
  { at: 50, color: C.lila, title: "Lo paga un banco", who: "Cobrand · Partners", f: ["pts × precio facturación", "× FX del mes"] },
  { at: 150, color: C.verde, title: "Lo regalamos", who: "iFood · Marketing · Club", f: ["pts × SSP", "SSP = valor real de canje"] },
  { at: 250, color: C.lilaDeep, title: "Viene con una venta", who: "Pasaporte D!", f: ["DRO = PV / (PV + R) × R", "PV = pts × SSP · R = margen"] },
];

export const S6Valuacion: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg, padding: `80px ${PAD_X}px` }}>
    <Enter at={0}>
      <Eyebrow>Cómo se valúa un punto</Eyebrow>
      <Title size={64} style={{ marginTop: 10 }}>
        Tres métodos, según quién paga
      </Title>
    </Enter>
    <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 60, paddingBottom: 40 }}>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 48 }}>
      {METODOS.map((m) => (
        <Enter key={m.title} at={m.at}>
          <div style={{ borderTop: `8px solid ${m.color}`, paddingTop: 28, display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 50, lineHeight: 1.05, color: C.ink }}>{m.title}</div>
            <div style={{ fontFamily: F.body, fontSize: 32, color: C.muted }}>{m.who}</div>
            <div
              style={{
                fontFamily: F.mono,
                fontSize: 27,
                lineHeight: 1.6,
                background: C.surface,
                border: `2px solid ${C.line}`,
                borderRadius: 16,
                padding: "22px 26px",
                color: C.ink,
              }}
            >
              <div style={{ color: m.color, fontWeight: 500 }}>{m.f[0]}</div>
              <div style={{ color: C.muted }}>{m.f[1]}</div>
            </div>
          </div>
        </Enter>
      ))}
    </div>
    <Enter at={380}>
      <div style={{ fontFamily: F.mono, fontSize: 28, color: C.muted }}>SSP de facturación = SSP × (1 − breakage esperado)</div>
    </Enter>
    </div>
  </AbsoluteFill>
);
