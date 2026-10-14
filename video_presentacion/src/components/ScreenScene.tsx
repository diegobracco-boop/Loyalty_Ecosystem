import React from "react";
import { AbsoluteFill } from "remotion";
import { C, PAD_X } from "../theme";
import { Enter, Eyebrow, Title } from "./anim";
import { Cam, Click, Laptop } from "./Laptop";
import { Note, SideNotes } from "./SideNotes";

// Layout común de las escenas con screenshot: encabezado arriba, laptop a la izquierda, notas a la derecha.
export const ScreenScene: React.FC<{
  eyebrow: string;
  title: string;
  file: string;
  cams: Cam[];
  clicks?: Click[];
  notes: Note[];
}> = ({ eyebrow, title, file, cams, clicks, notes }) => (
  <AbsoluteFill style={{ background: C.bg, padding: `72px ${PAD_X}px`, display: "flex", flexDirection: "column", gap: 40 }}>
    <Enter at={0}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <Title size={60} style={{ marginTop: 10 }}>
        {title}
      </Title>
    </Enter>
    <div style={{ display: "flex", gap: 60, alignItems: "flex-start" }}>
      <Enter at={8} distance={40} style={{ width: 1126, height: 702 }}>
        <Laptop file={file} cams={cams} clicks={clicks} scale={0.92} />
      </Enter>
      <div style={{ paddingTop: 40 }}>
        <SideNotes notes={notes} />
      </div>
    </div>
  </AbsoluteFill>
);
