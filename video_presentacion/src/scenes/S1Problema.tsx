import React from "react";
import { AbsoluteFill } from "remotion";
import { Enter, useProgress } from "../components/anim";
import { C, F, PAD_X } from "../theme";

// 0:00–0:08 · Hook: cómo era antes.
export const S1Problema: React.FC = () => {
  const strike = useProgress(110, 140);
  const line = { fontFamily: F.display, fontWeight: 700, fontSize: 104, lineHeight: 1.08, letterSpacing: "-0.03em", color: "#fff" };
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(1200px 800px at 85% 110%, ${C.lilaDeep}, ${C.lila} 70%)`,
        padding: `0 ${PAD_X}px`,
        justifyContent: "center",
        gap: 10,
      }}
    >
      <Enter at={8}>
        <div style={line}>El P&amp;L de Loyalty.</div>
      </Enter>
      <Enter at={30}>
        <div style={{ ...line, color: C.lilaWash }}>8 países · 7 programas.</div>
      </Enter>
      <Enter at={55}>
        <div style={{ ...line, position: "relative", display: "inline-block" }}>
          Días de planillas.
          <div
            style={{
              position: "absolute",
              left: 0,
              top: "54%",
              height: 10,
              width: `${strike * 100}%`,
              background: C.rojo,
              borderRadius: 5,
            }}
          />
        </div>
      </Enter>
      <Enter at={150}>
        <div style={{ ...line, color: C.verdeWash, marginTop: 36 }}>Ahora, un solo tablero.</div>
      </Enter>
    </AbsoluteFill>
  );
};
