import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EASE, F } from "../theme";

// Entrada con spring: opacidad + leve subida. `at` = frame de entrada dentro de la escena.
export const useEnter = (at: number, distance = 28) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - at, fps, config: { damping: 200, mass: 0.8 } });
  return {
    opacity: interpolate(frame - at, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    transform: `translateY(${(1 - p) * distance}px)`,
  } as React.CSSProperties;
};

export const Enter: React.FC<{ at: number; distance?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({
  at,
  distance,
  style,
  children,
}) => <div style={{ ...useEnter(at, distance), ...style }}>{children}</div>;

// Progreso 0→1 con easing entre dos frames
export const useProgress = (from: number, to: number) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [from, to], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

export const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.lila }) => (
  <div style={{ fontFamily: F.mono, fontSize: 24, letterSpacing: "0.16em", textTransform: "uppercase", color }}>
    {children}
  </div>
);

export const Title: React.FC<{ children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties }> = ({
  children,
  size = 76,
  color = C.ink,
  style,
}) => (
  <div
    style={{
      fontFamily: F.display,
      fontWeight: 700,
      fontSize: size,
      lineHeight: 1.05,
      letterSpacing: "-0.02em",
      color,
      textWrap: "balance",
      ...style,
    }}
  >
    {children}
  </div>
);
