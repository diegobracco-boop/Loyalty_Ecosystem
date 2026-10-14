import { loadFont as loadDisplay } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadBody } from "@remotion/google-fonts/IBMPlexSans";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";
import { Easing } from "remotion";

// Paleta oficial Despegar (ver .agents/skills/ux-consistency-review/SKILL.md)
export const C = {
  lila: "#550fed",
  lilaDeep: "#3d00d1",
  lilaSoft: "#976cf6",
  lilaLight: "#a780ff",
  lilaWash: "#efe9ff",
  verde: "#029687",
  verdeWash: "#ccf3ee",
  rojo: "#ff5454",
  rojoWash: "#fff2f2",
  bg: "#f6f4fb",
  surface: "#ffffff",
  ink: "#1b1530",
  muted: "#5e5874",
  line: "#e2dcf2",
};

export const F = {
  display: loadDisplay("normal", { weights: ["500", "700", "800"], subsets: ["latin"] }).fontFamily,
  body: loadBody("normal", { weights: ["400", "500", "600"], subsets: ["latin"] }).fontFamily,
  mono: loadMono("normal", { weights: ["400", "500"], subsets: ["latin"] }).fontFamily,
};

export const FPS = 30;
export const W = 1920;
export const H = 1080;
// Margen lateral común a todas las escenas
export const PAD_X = 120;
export const PAD_Y = 96;
// Duración del fade entre escenas (frames). Se solapa con la escena siguiente.
export const TRANSITION = 15;

export const EASE = Easing.bezier(0.22, 0.8, 0.24, 1);
export const s = (sec: number) => Math.round(sec * FPS);
