import React from "react";
import { AbsoluteFill } from "remotion";
import { Enter } from "../components/anim";
import { C, F, PAD_X } from "../theme";

// 2:40–2:50 · Cierre: qué funciona, próximos pasos y dónde verlo.
const HOY = ["Actualización automática", "P&L solo Despegar vs Goal", "7 programas × 8 países", "Variaciones por volumen y precio"];
const PROX = ["DRO de México con Contabilidad", "Precio pasivo real del breakage", "Run Rate de puntos", "Penetración por canal"];

const Item: React.FC<{ text: string; done: boolean }> = ({ text, done }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 18, fontFamily: F.body, fontSize: 32, color: "#fff" }}>
    <div
      style={{
        width: 18,
        height: 18,
        borderRadius: 9,
        background: done ? C.verdeWash : "transparent",
        border: `3px solid ${done ? C.verdeWash : C.lilaLight}`,
        flex: "none",
      }}
    />
    {text}
  </div>
);

const Head: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontFamily: F.mono, fontSize: 24, letterSpacing: "0.16em", textTransform: "uppercase", color: C.lilaWash }}>{children}</div>
);

export const S9Cierre: React.FC = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(1200px 800px at 85% 110%, ${C.lilaDeep}, ${C.lila} 70%)`,
      padding: `90px ${PAD_X}px`,
      justifyContent: "space-between",
    }}
  >
    <Enter at={0}>
      <div style={{ fontFamily: F.display, fontWeight: 800, fontSize: 104, lineHeight: 1, letterSpacing: "-0.035em", color: "#fff" }}>
        Fuente única del P&amp;L de Loyalty
      </div>
    </Enter>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <Enter at={25}>
          <Head>Funciona hoy</Head>
        </Enter>
        {HOY.map((t, i) => (
          <Enter key={t} at={35 + i * 10}>
            <Item text={t} done />
          </Enter>
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <Enter at={90}>
          <Head>Próximos pasos</Head>
        </Enter>
        {PROX.map((t, i) => (
          <Enter key={t} at={100 + i * 10}>
            <Item text={t} done={false} />
          </Enter>
        ))}
      </div>
    </div>
    <Enter at={170}>
      <div style={{ fontFamily: F.mono, fontSize: 28, color: C.lilaWash }}>Manual Loyalty Ecosystem → Presentación</div>
    </Enter>
  </AbsoluteFill>
);
