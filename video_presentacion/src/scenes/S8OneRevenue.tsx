import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Enter, Eyebrow, Title } from "../components/anim";
import { hasStatic } from "../components/Laptop";
import { C, F, PAD_X } from "../theme";

// 2:25–2:40 · Reglas One Revenue: la cadena del DRO esperado, con la tabla real de fondo.
const TOKENS = [
  { at: 30, t: "GB", s: "P&L actuals" },
  { at: 70, t: "penetración", s: "% del GB que acumula" },
  { at: 110, t: "ratio", s: "puntos por USD" },
  { at: 150, t: "SSP", s: "valor del punto" },
];

const Tok: React.FC<{ t: string; s: string; strong?: boolean }> = ({ t, s, strong }) => (
  <div
    style={{
      background: strong ? C.lila : C.lilaWash,
      borderRadius: 18,
      padding: "20px 28px",
      display: "flex",
      flexDirection: "column",
      gap: 4,
    }}
  >
    <div style={{ fontFamily: F.mono, fontSize: 46, fontWeight: 500, color: strong ? "#fff" : C.lilaDeep }}>{t}</div>
    <div style={{ fontFamily: F.body, fontSize: 25, color: strong ? C.lilaWash : C.muted }}>{s}</div>
  </div>
);

const Op: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontFamily: F.display, fontSize: 56, color: C.muted }}>{children}</div>
);

export const S8OneRevenue: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    {hasStatic("screens/04_one_revenue.png") && (
      <Img
        src={staticFile("screens/04_one_revenue.png")}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.1, filter: "blur(2px)" }}
      />
    )}
    <AbsoluteFill style={{ padding: `80px ${PAD_X}px` }}>
      <Enter at={0}>
        <Eyebrow>Vista 4 · Reglas One Revenue</Eyebrow>
        <Title size={64} style={{ marginTop: 10 }}>
          ¿Diferimos lo que dicen las reglas?
        </Title>
      </Enter>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 90, paddingBottom: 40 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
        {TOKENS.map((k, i) => (
          <React.Fragment key={k.t}>
            <Enter at={k.at}>
              <Tok t={k.t} s={k.s} />
            </Enter>
            <Enter at={k.at + 10}>
              <Op>{i < TOKENS.length - 1 ? "×" : "→"}</Op>
            </Enter>
          </React.Fragment>
        ))}
        <Enter at={200}>
          <Tok t="DRO %GB esperado" s="neto de breakage esperado" strong />
        </Enter>
      </div>
      <Enter at={280}>
        <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
          <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 64, color: C.ink }}>DRO esperado</div>
          <div style={{ fontFamily: F.mono, fontSize: 36, color: C.lila }}>vs</div>
          <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 64, color: C.ink }}>DRO contabilizado</div>
        </div>
        <div style={{ fontFamily: F.body, fontSize: 30, color: C.muted, marginTop: 12 }}>Por país, producto y mes</div>
      </Enter>
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
