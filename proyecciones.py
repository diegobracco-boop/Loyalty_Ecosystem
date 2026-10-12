"""
proyecciones.py — proyecciones de puntos (Budget / Run Rate) para comparar Real vs Proyección.

Fuente: Excel que mantiene Control de Gestión en OneDrive, uno por escenario, con
las MISMAS solapas y formato (filas = país × clave, columnas = meses abr→mar):
  Input_budget.xlsx   -> escenario 'budget'
  Input_runrate.xlsx  -> escenario 'runrate'   (opcional: si no existe, se omite)

Solapas que se leen (las demás se ignoran):
  Cobrands_Partners  Pais, Partner, <meses>                  puntos acumulados por partner
  Redenciones        Pais, Metrica, Tipo_punto, <meses>      puntos redimidos por tipo
  Breakage           Pais, Metrica, <meses>                  puntos vencidos
  SSP_PrecioPasivo   Pais, Metrica, <meses>                  SSP_Red / SSP / Precio Punto Pasivo
  Ratio_acumulacion  Pais, Producto, Metrica, <meses>        puntos / GB por producto

Salida: loyalty_proyecciones.json  {meta, cols, rows} con una fila por
escenario × bloque × país × clave × mes. El cruce contra los reales lo hace
dashboard.html (selector "Comparar contra" de Métricas de Negocio) con los JSON que ya existen.

Uso:
  py proyecciones.py            # arma el JSON y muestra un resumen (no sube)
  py proyecciones.py --upload   # además lo sube a Drive (folder de loyalty)
Lo importa también loyalty_sync.py, que lo sube en cada corrida.
"""
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_ONEDRIVE_DIR = (Path.home() / "OneDrive - despegar365" / "Control de Gestión - Loyalty"
                 / "Loyalty_Ecosystem")

PROYECCIONES_FILE = "loyalty_proyecciones.json"

# Por escenario: env -> OneDrive -> copia local del repo (fallback, igual que
# Input_Precios.xlsx). La máquina del Task Scheduler puede no tener OneDrive.
ESCENARIOS = {
    "budget":  [os.environ.get("BUDGET_XLSX", ""),
                str(_ONEDRIVE_DIR / "Input_budget.xlsx"),
                str(_SCRIPT_DIR / "Input_budget.xlsx")],
    "runrate": [os.environ.get("RUNRATE_XLSX", ""),
                str(_ONEDRIVE_DIR / "Input_runrate.xlsx"),
                str(_SCRIPT_DIR / "Input_runrate.xlsx")],
}

# solapa -> (bloque, cantidad de columnas de llave antes de los meses, índice de la clave)
SOLAPAS = {
    "Cobrands_Partners": ("acum_partner", 2, 1),   # clave = Partner
    "Redenciones":       ("reden",        3, 2),   # clave = Tipo_punto
    "Breakage":          ("breakage",     2, None),
    "SSP_PrecioPasivo":  ("ssp",          2, 1),   # clave = Metrica
    "Ratio_acumulacion": ("ratio",        3, 1),   # clave = Producto
}

# Nombre de país del Excel -> dataKey del dashboard (COUNTRY_DATAKEYS).
PAIS = {"argentina": "argentina", "brasil": "brasil", "brazil": "brasil",
        "mexico": "mexico", "méxico": "mexico", "colombia": "colombia",
        "peru": "peru", "perú": "peru", "ecuador": "ecuador",
        "uruguay": "uruguay", "chile": "chile"}


def _ym(v):
    if isinstance(v, (datetime, date)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v or "").strip()
    return s[:7] if len(s) >= 7 and s[4] == "-" else None


def _read_xlsx(path, escenario, warns):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = []
    for solapa, (bloque, nkey, kidx) in SOLAPAS.items():
        if solapa not in wb.sheetnames:
            warns.append(f"{escenario}: falta la solapa '{solapa}'")
            continue
        it = wb[solapa].iter_rows(values_only=True)
        header = next(it, None) or ()
        meses = [(i, _ym(h)) for i, h in enumerate(header) if i >= nkey and _ym(h)]
        for r in it:
            if not r or r[0] is None:
                continue
            pais_raw = str(r[0]).strip()
            pais = PAIS.get(pais_raw.lower())
            if pais is None:
                # 'Other Countries' y similares: no hay solapa de país en el dashboard
                continue
            clave = str(r[kidx]).strip() if kidx is not None and r[kidx] is not None else ""
            for i, ym in meses:
                v = r[i] if i < len(r) else None
                if v is None or v == "":
                    continue
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    warns.append(f"{escenario}/{solapa}: valor no numérico {v!r} ({pais_raw} {clave} {ym})")
                    continue
                rows.append([escenario, bloque, pais, clave, ym, v])
    wb.close()
    return rows


def build_proyecciones_json():
    """Devuelve (bytes del JSON | None, resumen legible). Nunca rompe la corrida.
    Por escenario prueba cada candidato en orden (OneDrive -> copia del repo): si
    uno existe pero no se puede leer (bloqueado, sin descargar, formato roto), pasa
    al siguiente. Si no sale NINGUNA fila, devuelve None: el caller no sube nada y
    queda en Drive el loyalty_proyecciones.json anterior (no se pisa con uno vacío)."""
    rows, warns, fuentes = [], [], {}
    for esc, cands in ESCENARIOS.items():
        fuentes[esc] = None
        for path in [p for p in cands if p and Path(p).exists()]:
            try:
                esc_rows = _read_xlsx(path, esc, warns)
            except Exception as e:  # archivo abierto/bloqueado, formato roto, openpyxl faltante...
                warns.append(f"{esc}: no se pudo leer {path}: {str(e)[:150]}")
                continue
            if not esc_rows:
                warns.append(f"{esc}: {path} no trajo filas")
                continue
            rows += esc_rows
            fuentes[esc] = path
            if Path(path).parent == _SCRIPT_DIR:
                mod = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d")
                warns.append(f"{esc}: se usó la COPIA DEL REPO ({Path(path).name}, modificada {mod}) — "
                             "puede estar desactualizada respecto de OneDrive")
            break
        if fuentes[esc] is None and esc == "budget":
            warns.append("budget: Input_budget.xlsx no encontrado o ilegible en todos los candidatos")
    if not rows:
        return None, [f"  [WARN] proyecciones: {w}" for w in warns] + [
            "  [WARN] proyecciones: 0 filas — NO se sube loyalty_proyecciones.json (queda el anterior en Drive)"]
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "fuentes": fuentes,
        "warnings": warns,
        "unidades": {"acum_partner": "puntos", "reden": "puntos", "breakage": "puntos",
                     "ssp": "USD por punto", "ratio": "puntos / USD GB"},
    }
    cols = ["escenario", "bloque", "pais", "clave", "ym", "valor"]
    data = json.dumps({"meta": meta, "cols": cols, "rows": rows}, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    por = {}
    for r in rows:
        por[(r[0], r[1])] = por.get((r[0], r[1]), 0) + 1
    resumen = [f"  {esc:8s} {blq:13s} {n:>5} filas" for (esc, blq), n in sorted(por.items())]
    resumen += [f"  [WARN] proyecciones: {w}" for w in warns]
    return data, resumen


if __name__ == "__main__":
    data, resumen = build_proyecciones_json()
    print(f"{PROYECCIONES_FILE}: {len(data) // 1024 if data else 0} KB")
    print("\n".join(resumen))
    if data is None:
        sys.exit(1)
    if "--upload" in sys.argv:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload
        folder = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"  # = DRIVE_FOLDER_ID de loyalty_sync.py
        svc = build("drive", "v3", credentials=Credentials.from_authorized_user_file(
            str(_SCRIPT_DIR / "token_drive.json")))
        media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
        ex = svc.files().list(q=f"name='{PROYECCIONES_FILE}' and '{folder}' in parents and trashed=false",
                              fields="files(id)").execute().get("files", [])
        if ex:
            svc.files().update(fileId=ex[0]["id"], media_body=media).execute()
            print(f"OK Drive: actualizado ({PROYECCIONES_FILE})")
        else:
            svc.files().create(body={"name": PROYECCIONES_FILE, "parents": [folder]},
                               media_body=media, fields="id").execute()
            print(f"OK Drive: creado ({PROYECCIONES_FILE})")
