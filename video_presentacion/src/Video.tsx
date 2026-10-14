import React from "react";
import { AbsoluteFill, Audio, interpolate, staticFile } from "remotion";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { hasStatic } from "./components/Laptop";
import { S1Problema } from "./scenes/S1Problema";
import { S2Presentacion } from "./scenes/S2Presentacion";
import { S3Fuentes } from "./scenes/S3Fuentes";
import { S4Pnl } from "./scenes/S4Pnl";
import { S5Metricas } from "./scenes/S5Metricas";
import { S6Valuacion } from "./scenes/S6Valuacion";
import { S7Variaciones } from "./scenes/S7Variaciones";
import { S8OneRevenue } from "./scenes/S8OneRevenue";
import { S9Cierre } from "./scenes/S9Cierre";
import { C, s, TRANSITION } from "./theme";

// Duración visible de cada escena (segundos). Cada transición se solapa TRANSITION frames
// con la escena siguiente, así que a cada escena (menos la última) se le suman esos frames.
// music: volumen de la música en esa escena (más bajo en las de features).
export const SCENES = [
  { id: "problema", C: S1Problema, sec: 8, music: 0.3 },
  { id: "presentacion", C: S2Presentacion, sec: 7, music: 0.3 },
  { id: "fuentes", C: S3Fuentes, sec: 20, music: 0.18 },
  { id: "pnl", C: S4Pnl, sec: 30, music: 0.14 },
  { id: "metricas", C: S5Metricas, sec: 30, music: 0.14 },
  { id: "valuacion", C: S6Valuacion, sec: 20, music: 0.14 },
  { id: "variaciones", C: S7Variaciones, sec: 30, music: 0.14 },
  { id: "one-revenue", C: S8OneRevenue, sec: 15, music: 0.18 },
  { id: "cierre", C: S9Cierre, sec: 10, music: 0.3 },
];

export const TOTAL_FRAMES = SCENES.reduce((acc, sc) => acc + s(sc.sec), 0);
const STARTS = SCENES.map((_, i) => SCENES.slice(0, i).reduce((acc, sc) => acc + s(sc.sec), 0));

const musicVolume = (f: number) => {
  // Nivel por escena, con rampa de 1 s en cada cambio
  let level = SCENES[0].music;
  for (let i = 1; i < SCENES.length; i++) {
    level = interpolate(f, [STARTS[i] - 15, STARTS[i] + 15], [level, SCENES[i].music], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  }
  const fadeIn = interpolate(f, [0, s(1.5)], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(f, [TOTAL_FRAMES - s(2), TOTAL_FRAMES], [1, 0], { extrapolateLeft: "clamp" });
  return level * fadeIn * fadeOut;
};

export const LoyaltyVideo: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg }}>
    {hasStatic("music.mp3") && <Audio src={staticFile("music.mp3")} volume={musicVolume} />}
    <TransitionSeries>
      {SCENES.map((sc, i) => {
        const Scene = sc.C;
        const last = i === SCENES.length - 1;
        return (
          <React.Fragment key={sc.id}>
            <TransitionSeries.Sequence durationInFrames={s(sc.sec) + (last ? 0 : TRANSITION)}>
              <Scene />
            </TransitionSeries.Sequence>
            {!last && (
              <TransitionSeries.Transition
                // Slide entre las escenas de contenido, fade en apertura y cierre
                presentation={i === 0 || i >= SCENES.length - 2 ? fade() : slide({ direction: "from-right" })}
                timing={springTiming({ config: { damping: 200 }, durationInFrames: TRANSITION })}
              />
            )}
          </React.Fragment>
        );
      })}
    </TransitionSeries>
  </AbsoluteFill>
);
