import React from "react";
import { AbsoluteFill, Audio, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Enter } from "../components/anim";
import { hasStatic } from "../components/Laptop";
import { C, F, PAD_X } from "../theme";

const PAISES = ["TOTAL", "Brasil", "México", "Argentina", "Colombia", "Chile", "Perú", "Ecuador", "Uruguay"];

// 0:08–0:15 · Wordmark con spring + tagline + países.
export const S2Presentacion: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame: frame - 4, fps, config: { damping: 12, stiffness: 120, mass: 0.9 } });
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(1100px 700px at 80% 115%, ${C.lilaWash}, ${C.bg} 70%)`,
        padding: `0 ${PAD_X}px`,
        justifyContent: "center",
        gap: 34,
      }}
    >
      {hasStatic("sfx/logo.mp3") && (
        <Sequence from={4} layout="none">
          <Audio src={staticFile("sfx/logo.mp3")} volume={0.6} />
        </Sequence>
      )}
      <div style={{ transform: `scale(${0.6 + 0.4 * pop})`, transformOrigin: "left center", opacity: Math.min(1, pop * 1.5) }}>
        <div style={{ fontFamily: F.mono, fontSize: 26, letterSpacing: "0.18em", color: C.lila, textTransform: "uppercase" }}>
          Despegar · Loyalty
        </div>
        <div style={{ fontFamily: F.display, fontWeight: 800, fontSize: 168, lineHeight: 0.95, letterSpacing: "-0.04em", color: C.ink }}>
          Loyalty <span style={{ color: C.lila }}>Ecosystem</span>
        </div>
      </div>
      <Enter at={40}>
        <div style={{ fontFamily: F.display, fontWeight: 500, fontSize: 64, color: C.muted }}>
          Cuánto vale un <span style={{ color: C.lila, fontWeight: 700 }}>punto</span>.
        </div>
      </Enter>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 10 }}>
        {PAISES.map((p, i) => (
          <Enter key={p} at={85 + i * 5} distance={14}>
            <div
              style={{
                fontFamily: F.mono,
                fontSize: 26,
                padding: "10px 22px",
                borderRadius: 999,
                border: `2px solid ${i === 0 ? C.lila : C.line}`,
                color: i === 0 ? C.lila : C.muted,
                background: C.surface,
              }}
            >
              {p}
            </div>
          </Enter>
        ))}
      </div>
    </AbsoluteFill>
  );
};
