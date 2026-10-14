import React from "react";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from "remotion";
import { Enter, Eyebrow, Title } from "../components/anim";
import { ScreenScene } from "../components/ScreenScene";
import { C, F, PAD_X } from "../theme";

// 1:05–1:35 · Métricas de Negocio: primero el ciclo del punto, después el screenshot.
const CYCLE_END = 200;

const Stage: React.FC<{ at: number; title: string; sub: string; bg: string }> = ({ at, title, sub, bg }) => (
  <Enter at={at}>
    <div style={{ background: bg, borderRadius: 24, padding: "36px 40px", width: 460 }}>
      <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 54, color: C.ink }}>{title}</div>
      <div style={{ fontFamily: F.body, fontSize: 30, color: C.muted, marginTop: 10 }}>{sub}</div>
    </div>
  </Enter>
);

const Chev: React.FC<{ at: number }> = ({ at }) => (
  <Enter at={at}>
    <div style={{ fontFamily: F.display, fontSize: 90, color: C.lilaSoft, lineHeight: 1 }}>›</div>
  </Enter>
);

const Cycle: React.FC = () => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [CYCLE_END - 15, CYCLE_END + 10], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: C.bg, padding: `80px ${PAD_X}px`, opacity: out }}>
      <Enter at={0}>
        <Eyebrow>Vista 2 · Métricas de Negocio</Eyebrow>
        <Title size={64} style={{ marginTop: 10 }}>
          La vida de un punto
        </Title>
      </Enter>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 40, paddingBottom: 80 }}>
        <Stage at={20} title="Acumulación" sub="Al comprar o vía un banco" bg={C.lilaWash} />
        <Chev at={45} />
        <Stage at={50} title="Stock" sub="Pasivo con el cliente" bg={C.surface} />
        <Chev at={75} />
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <Stage at={80} title="Redención" sub="Se canjea" bg={C.verdeWash} />
          <Stage at={100} title="Breakage" sub="Vence sin usarse" bg={C.rojoWash} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const S5Metricas: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={CYCLE_END - 5}>
      <ScreenScene
        eyebrow="Vista 2 · Métricas de Negocio"
        title="Siete programas, año fiscal"
        file="screens/02_metricas.png"
        cams={[
          { at: 0, fx: 0.5, fy: 0.5, zoom: 1 },
          { at: 60, fx: 0.5, fy: 0.5, zoom: 1 },
          { at: 130, fx: 0.4, fy: 0.5, zoom: 1.6 }, // las 3 barras
          { at: 330, fx: 0.4, fy: 0.5, zoom: 1.6 },
          { at: 400, fx: 0.9, fy: 0.12, zoom: 1.9 }, // toggle Q / $
          { at: 560, fx: 0.9, fy: 0.12, zoom: 1.9 },
          { at: 650, fx: 0.5, fy: 0.5, zoom: 1 },
        ]}
        clicks={[{ at: 460, x: 0.9, y: 0.12 }]}
        notes={[
          { at: 40, title: "Por programa y país", sub: "Pasaporte D!, Cobrand, iFood y más" },
          { at: 150, title: "FY26 · Budget · FY27", sub: "Tres barras por mes" },
          { at: 470, title: "En puntos o en USD", sub: "Un clic cambia la vista" },
        ]}
      />
    </Sequence>
    <Sequence durationInFrames={CYCLE_END + 10}>
      <Cycle />
    </Sequence>
  </AbsoluteFill>
);
