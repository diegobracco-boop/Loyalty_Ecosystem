import React from "react";
import { Audio, getStaticFiles, Img, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { C, EASE, F } from "../theme";

// Ventana del screenshot: 16:9 como las capturas (1920x1080)
export const SCREEN_W = 1180;
export const SCREEN_H = Math.round((SCREEN_W * 9) / 16);

// Keyframe de cámara: foco (fx, fy en 0..1 sobre la captura) y zoom.
export type Cam = { at: number; fx: number; fy: number; zoom: number };
// Click del cursor: posición en 0..1 sobre la CAPTURA (igual que el foco de la cámara);
// el cursor sigue al punto aunque la cámara haga zoom.
export type Click = { at: number; x: number; y: number };

const OPT = { easing: EASE, extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const interp = (frame: number, cams: Cam[], key: "fx" | "fy" | "zoom") =>
  cams.length === 1 ? cams[0][key] : interpolate(frame, cams.map((c) => c.at), cams.map((c) => c[key]), OPT);

export const hasStatic = (name: string) => getStaticFiles().some((f) => f.name === name);

const Placeholder: React.FC<{ label: string }> = ({ label }) => (
  <div
    style={{
      width: "100%",
      height: "100%",
      background: `repeating-linear-gradient(135deg, ${C.bg} 0 28px, ${C.lilaWash} 28px 56px)`,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 14,
      color: C.muted,
      fontFamily: F.mono,
      textAlign: "center",
    }}
  >
    <div style={{ fontSize: 30, color: C.lila }}>FALTA SCREENSHOT</div>
    <div style={{ fontSize: 24 }}>public/{label}</div>
    <div style={{ fontSize: 20 }}>1920 × 1080 · png</div>
  </div>
);

// Transformación de cámara en un frame: zoom + traslado, sin mostrar bordes vacíos
const camAt = (frame: number, cams: Cam[]) => {
  const zoom = interp(frame, cams, "zoom");
  const fx = interp(frame, cams, "fx");
  const fy = interp(frame, cams, "fy");
  const maxX = ((zoom - 1) * SCREEN_W) / 2;
  const maxY = ((zoom - 1) * SCREEN_H) / 2;
  const tx = Math.max(-maxX, Math.min(maxX, -(fx - 0.5) * SCREEN_W * zoom));
  const ty = Math.max(-maxY, Math.min(maxY, -(fy - 0.5) * SCREEN_H * zoom));
  return { zoom, tx, ty };
};

const Cursor: React.FC<{ clicks: Click[]; cams: Cam[] }> = ({ clicks, cams }) => {
  const frame = useCurrentFrame();
  if (clicks.length === 0) return null;
  // El cursor entra desde abajo a la derecha y llega a cada click 8 frames antes.
  const start = Math.max(0, clicks[0].at - 45);
  const times = [start, ...clicks.flatMap((c) => [c.at - 8, c.at])];
  const xs = [0.95, ...clicks.flatMap((c) => [c.x, c.x])];
  const ys = [0.95, ...clicks.flatMap((c) => [c.y, c.y])];
  const cx = interpolate(frame, times, xs, OPT);
  const cy = interpolate(frame, times, ys, OPT);
  const { zoom, tx, ty } = camAt(frame, cams);
  // Punto de la captura → punto de la ventana visible
  const x = SCREEN_W / 2 + (cx - 0.5) * SCREEN_W * zoom + tx;
  const y = SCREEN_H / 2 + (cy - 0.5) * SCREEN_H * zoom + ty;
  const appear = interpolate(frame, [start, start + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const last = [...clicks].reverse().find((c) => frame >= c.at);
  const since = last ? frame - last.at : 99;
  const press = since < 8 ? interpolate(since, [0, 3, 8], [1, 0.82, 1]) : 1;
  const ring = Math.min(1, since / 18);
  const sfx = hasStatic("sfx/click.mp3");
  return (
    <>
      {sfx &&
        clicks.map((c) => (
          <Sequence key={c.at} from={c.at} durationInFrames={20} layout="none">
            <Audio src={staticFile("sfx/click.mp3")} volume={0.5} />
          </Sequence>
        ))}
      {since < 18 && (
        <div
          style={{
            position: "absolute",
            left: x - 40,
            top: y - 40,
            width: 80,
            height: 80,
            borderRadius: 40,
            border: `4px solid ${C.lila}`,
            opacity: 1 - ring,
            transform: `scale(${0.3 + ring})`,
          }}
        />
      )}
      <svg
        width={40}
        height={40}
        viewBox="0 0 24 24"
        style={{
          position: "absolute",
          left: x - 4,
          top: y - 2,
          opacity: appear,
          transform: `scale(${press})`,
          transformOrigin: "4px 2px",
          filter: "drop-shadow(0 3px 5px rgba(27,21,48,.35))",
        }}
      >
        <path d="M4 2 L4 20 L9 15.5 L12.5 22.5 L15.5 21 L12 14 L19 14 Z" fill={C.ink} stroke="#fff" strokeWidth={1.6} strokeLinejoin="round" />
      </svg>
    </>
  );
};

export const Laptop: React.FC<{ file: string; cams: Cam[]; clicks?: Click[]; scale?: number }> = ({
  file,
  cams,
  clicks = [],
  scale = 1,
}) => {
  const frame = useCurrentFrame();
  const { zoom, tx, ty } = camAt(frame, cams);
  const exists = hasStatic(file);
  const bezel = 22;

  return (
    <div style={{ transform: `scale(${scale})`, transformOrigin: "left top" }}>
      <div
        style={{
          width: SCREEN_W + bezel * 2,
          padding: bezel,
          paddingTop: bezel + 6,
          background: "#16121f",
          borderRadius: "28px 28px 0 0",
          boxShadow: "0 40px 80px -30px rgba(61,0,209,.35)",
        }}
      >
        <div style={{ width: SCREEN_W, height: SCREEN_H, overflow: "hidden", position: "relative", background: C.surface, borderRadius: 6 }}>
          <div style={{ width: SCREEN_W, height: SCREEN_H, transform: `translate(${tx}px, ${ty}px) scale(${zoom})` }}>
            {exists ? (
              <Img src={staticFile(file)} style={{ width: SCREEN_W, height: SCREEN_H, objectFit: "cover", objectPosition: "top left" }} />
            ) : (
              <Placeholder label={file} />
            )}
          </div>
          <Cursor clicks={clicks} cams={cams} />
        </div>
      </div>
      <div
        style={{
          width: SCREEN_W + bezel * 2 + 80,
          marginLeft: -40,
          height: 24,
          background: "linear-gradient(#d9d4e6, #b9b2cc)",
          borderRadius: "0 0 30px 30px",
        }}
      />
    </div>
  );
};
