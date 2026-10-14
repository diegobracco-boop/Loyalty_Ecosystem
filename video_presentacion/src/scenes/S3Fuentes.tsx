import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Enter, Eyebrow, Title, useProgress } from "../components/anim";
import { C, F, PAD_X } from "../theme";

// 0:15–0:35 · Diagrama del flujo de datos (sin screenshot).
type Box = { x: number; y: number; w: number; h: number; title: string; sub: string; tag?: string };

const SRC_W = 470;
const SRC_H = 118;
const SOURCES: Box[] = [
  { title: "Datalake", sub: "Acumulación, canje y vencimiento", tag: "automático" },
  { title: "P&L contable", sub: "Planning P&L · solo Despegar", tag: "Planning" },
  { title: "Control de Gestión", sub: "Precios, FX, Budget de puntos", tag: "Excel" },
  { title: "Configuración", sub: "Breakage esperado y mapeos", tag: "Google Sheet" },
].map((b, i) => ({ ...b, x: PAD_X, y: 300 + i * 150, w: SRC_W, h: SRC_H }));

const SYNC: Box = { x: 760, y: 455, w: 360, h: 210, title: "Sync de Loyalty", sub: "Agrega por mes, país y programa. Valúa en USD." };
const DRIVE: Box = { x: 1230, y: 500, w: 230, h: 120, title: "Drive", sub: "Un archivo por métrica" };
const TABLERO: Box = { x: 1570, y: 480, w: 230, h: 160, title: "Tablero", sub: "Webapp interna" };

type Pt = [number, number];
const bez = (p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: number): Pt => {
  const u = 1 - t;
  return [
    u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
  ];
};
const right = (b: Box): Pt => [b.x + b.w, b.y + b.h / 2];
const left = (b: Box): Pt => [b.x, b.y + b.h / 2];

// Cada conexión: curva cúbica entre el borde derecho de una caja y el izquierdo de otra
const link = (a: Box, b: Box) => {
  const p0 = right(a);
  const p3 = left(b);
  const mx = (p0[0] + p3[0]) / 2;
  return [p0, [mx, p0[1]] as Pt, [mx, p3[1]] as Pt, p3] as const;
};
const LINKS = [...SOURCES.map((s) => link(s, SYNC)), link(SYNC, DRIVE), link(DRIVE, TABLERO)];

const BoxView: React.FC<{ b: Box; at: number; variant?: "src" | "hub" | "end" }> = ({ b, at, variant = "src" }) => {
  const bg = variant === "hub" ? C.lilaWash : variant === "end" ? C.lila : C.surface;
  const fg = variant === "end" ? "#fff" : C.ink;
  return (
    <Enter at={at} style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          background: bg,
          border: `2px solid ${variant === "src" ? C.line : C.lila}`,
          borderRadius: 18,
          padding: "18px 24px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 6,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 34, color: fg, lineHeight: 1.1 }}>{b.title}</div>
          {b.tag && <div style={{ fontFamily: F.mono, fontSize: 19, color: C.verde }}>{b.tag}</div>}
        </div>
        <div style={{ fontFamily: F.body, fontSize: 23, color: variant === "end" ? C.lilaWash : C.muted, lineHeight: 1.3 }}>{b.sub}</div>
      </div>
    </Enter>
  );
};

export const S3Fuentes: React.FC = () => {
  const frame = useCurrentFrame();
  const draw = useProgress(150, 230);
  const draw2 = useProgress(250, 300);
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <div style={{ position: "absolute", left: PAD_X, top: 80 }}>
        <Enter at={0}>
          <Eyebrow>De dónde salen los números</Eyebrow>
          <Title size={64} style={{ marginTop: 10 }}>
            Cuatro fuentes, un proceso automático
          </Title>
        </Enter>
      </div>

      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {LINKS.map((l, i) => {
          const d = `M${l[0][0]},${l[0][1]} C${l[1][0]},${l[1][1]} ${l[2][0]},${l[2][1]} ${l[3][0]},${l[3][1]}`;
          const p = i < 4 ? draw : interpolate(draw2, [i === 4 ? 0 : 0.5, i === 4 ? 0.5 : 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <path key={i} d={d} fill="none" stroke={C.lilaSoft} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
          );
        })}
        {/* Pulsos de datos viajando por cada conexión, después de que se dibujó todo */}
        {frame > 300 &&
          LINKS.map((l, i) =>
            [0, 0.5].map((phase) => {
              const t = (((frame - 300) / 50 + phase + i * 0.13) % 1 + 1) % 1;
              const [x, y] = bez(l[0], l[1], l[2], l[3], t);
              const fade = interpolate(frame, [300, 320], [0, 1], { extrapolateRight: "clamp" });
              return <circle key={`${i}-${phase}`} cx={x} cy={y} r={8} fill={C.lila} opacity={fade * (0.4 + 0.6 * Math.sin(Math.PI * t))} />;
            }),
          )}
      </svg>

      {SOURCES.map((b, i) => (
        <BoxView key={b.title} b={b} at={30 + i * 22} />
      ))}
      <BoxView b={SYNC} at={170} variant="hub" />
      <BoxView b={DRIVE} at={260} />
      <BoxView b={TABLERO} at={290} variant="end" />

      <div style={{ position: "absolute", left: 760, top: 760 }}>
        <Enter at={400}>
          <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 54, color: C.lila, letterSpacing: "-0.02em" }}>
            Nadie copia números a mano.
          </div>
          <div style={{ fontFamily: F.body, fontSize: 28, color: C.muted, marginTop: 10 }}>
            Los supuestos se editan en planilla.
          </div>
        </Enter>
      </div>
    </AbsoluteFill>
  );
};
