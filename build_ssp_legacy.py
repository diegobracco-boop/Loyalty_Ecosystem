"""Genera loyalty_ssp.json desde los JSON de redenciones crudos ya bajados
(sync del 24-ago) + breakage_esperado.csv, y lo sube a Drive. Misma lógica que
build_ssp_json en loyalty_sync.py. One-shot para dejar Fase 1 andando sin re-sync."""
import io, json, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

W = Path(__file__).resolve().parent
LOY = Path(r"C:\Users\diego.bracco\Proyectos IA\Loyalty_Ecosystem")
FOLDER = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"
CC_TO_DATAKEY = {"AR":"argentina","BR":"brasil","CO":"colombia","EC":"ecuador",
                 "MX":"mexico","PE":"peru","UY":"uruguay","CL":"chile"}

def expand(fn):
    r = json.loads((W/fn).read_text(encoding="utf-8")); d = r["data"]
    return pd.DataFrame(d["rows"], columns=d["cols"])

df = pd.concat([expand("loyalty_redenciones_2026.json"),
                expand("loyalty_redenciones_2025.json")], ignore_index=True)
df = df[df["point_type"].astype(str).str.lower().isin({"general"})].copy()
df["ym"]     = df["processing_date"].str.slice(0, 7)
df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).abs()
df["usd"]    = pd.to_numeric(df["descuento_consumo_puntos_usd"], errors="coerce").fillna(0).abs()
g = df.groupby(["country_code","ym"], as_index=False).agg(points=("points","sum"), usd=("usd","sum"))
g = g[g["points"] > 0]

be = pd.read_csv(LOY/"breakage_esperado.csv", dtype=str)
be.columns = [c.strip().lower() for c in be.columns]
brk = {}
for _, r in be.iterrows():
    v = pd.to_numeric(r["breakage_esperado"], errors="coerce")
    if pd.isna(v): continue
    brk[(r["country_code"].strip().upper(), r["month"].strip()[:7])] = 1.0 - float(v)

out = {}
for r in g.itertuples():
    dk = CC_TO_DATAKEY.get(r.country_code.strip().upper())
    if not dk: continue
    sc = -abs(r.usd / r.points)
    fac = brk.get((r.country_code.strip().upper(), r.ym), 1.0)
    out.setdefault(dk, {})[r.ym] = {
        "ssp_calculado": round(sc, 6),
        "breakage_esperado": round(1.0 - fac, 4),
        "ssp_facturacion": round(sc * fac, 6),
        "puntos": round(float(r.points), 0),
    }
payload = {"meta": {"generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "fuente": "redenciones Pasaporte D! (point_type=general) / breakage_esperado.csv"},
           "data": out}
data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
(W/"loyalty_ssp.json").write_bytes(data)
print(json.dumps(payload["data"], ensure_ascii=False, indent=1)[:2000])
print("bytes:", len(data))

ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true")
if ap.parse_args().upload:
    creds = Credentials.from_authorized_user_file(str(LOY/"token_drive.json"),
                                                  ["https://www.googleapis.com/auth/drive"])
    if not creds.valid: creds.refresh(Request())
    svc = build("drive", "v3", credentials=creds)
    media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
    ex = svc.files().list(q=f"name='loyalty_ssp.json' and '{FOLDER}' in parents and trashed=false",
                          fields="files(id)").execute().get("files", [])
    if ex:
        svc.files().update(fileId=ex[0]["id"], media_body=media).execute(); print("Drive: actualizado")
    else:
        svc.files().create(body={"name":"loyalty_ssp.json","parents":[FOLDER]},
                           media_body=media, fields="id").execute(); print("Drive: creado")
