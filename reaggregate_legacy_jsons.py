"""Re-agrega los JSON crudos ya publicados (sync del 24-ago) al nuevo formato
mensual liviano y los re-sube a Drive. Misma lógica que aggregate_acum/
aggregate_reden en loyalty_sync.py. Fix inmediato sin re-correr el sync completo."""
import io, json, argparse
from pathlib import Path
from collections import defaultdict
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

W = Path(__file__).resolve().parent
LOY_BASE = Path(r"C:\Users\diego.bracco\Proyectos IA\Loyalty_Ecosystem")
FOLDER = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"
AGG_KEYS = ["processing_date", "country", "country_code", "partner", "point_type"]

def expand(raw):
    d = raw.get("data", raw)
    if isinstance(d, list):
        return d
    return [dict(zip(d["cols"], r)) for r in d["rows"]]

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

def agg_acum(rows):
    g = defaultdict(lambda: [0.0, 0.0])  # points, acum_usd_base
    for r in rows:
        k = (str(r.get("processing_date") or "")[:7] + "-01",
             r.get("country"), r.get("country_code"), r.get("partner"), r.get("point_type"))
        base = (num(r.get("comision")) + num(r.get("fee")) + num(r.get("descuentos"))) * (1.0 - num(r.get("pct_pagado_con_puntos")))
        g[k][0] += abs(num(r.get("points")))
        g[k][1] += abs(base)
    cols = AGG_KEYS + ["points", "acum_usd_base"]
    out = [list(k) + [round(v[0], 2), round(v[1], 4)] for k, v in g.items()]
    return cols, out

def agg_reden(rows):
    g = defaultdict(lambda: [0.0, 0.0])  # points, usd
    for r in rows:
        k = (str(r.get("processing_date") or "")[:7] + "-01",
             r.get("country"), r.get("country_code"), r.get("partner"), r.get("point_type"))
        g[k][0] += abs(num(r.get("points")))
        g[k][1] += abs(num(r.get("descuento_consumo_puntos_usd")))
    cols = AGG_KEYS + ["points", "descuento_consumo_puntos_usd"]
    out = [list(k) + [round(v[0], 2), round(v[1], 2)] for k, v in g.items()]
    return cols, out

FILES = {
    "loyalty_acumulaciones_2025.json": agg_acum,
    "loyalty_acumulaciones_2026.json": agg_acum,
    "loyalty_redenciones_2025.json":   agg_reden,
    "loyalty_redenciones_2026.json":   agg_reden,
}

def svc():
    creds = Credentials.from_authorized_user_file(str(LOY_BASE / "token_drive.json"),
                                                  ["https://www.googleapis.com/auth/drive"])
    if not creds.valid:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

def main(upload):
    s = svc() if upload else None
    for fn, fn_agg in FILES.items():
        raw = json.loads((W / fn).read_text(encoding="utf-8"))
        rows = expand(raw)
        cols, out = fn_agg(rows)
        payload = {"meta": raw["meta"], "data": {"cols": cols, "rows": out}}
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        (W / ("agg_" + fn)).write_bytes(data)
        print(f"{fn}: {len(rows):,} -> {len(out):,} filas | {len(data)/1e6:.2f} MB")
        if upload:
            media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
            ex = s.files().list(q=f"name='{fn}' and '{FOLDER}' in parents and trashed=false",
                                fields="files(id)").execute().get("files", [])
            s.files().update(fileId=ex[0]["id"], media_body=media).execute()
            print(f"   [Drive] actualizado {fn}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    main(ap.parse_args().upload)
