import React from "react";
import { C, F } from "../theme";
import { Enter } from "./anim";

// Columna de textos cortos al costado del mockup. Cada nota entra en su frame y queda.
export type Note = { at: number; title: string; sub?: string };

export const SideNotes: React.FC<{ notes: Note[] }> = ({ notes }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 34, width: 470 }}>
    {notes.map((n) => (
      <Enter key={n.title} at={n.at}>
        <div style={{ borderLeft: `4px solid ${C.lila}`, paddingLeft: 22 }}>
          <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: 40, lineHeight: 1.1, color: C.ink }}>{n.title}</div>
          {n.sub && <div style={{ fontFamily: F.body, fontSize: 26, color: C.muted, marginTop: 8, lineHeight: 1.35 }}>{n.sub}</div>}
        </div>
      </Enter>
    ))}
  </div>
);
