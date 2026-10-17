"""
inputs_contables_loyalty.py — Vista de Loyalty de los inputs contables (P&L), solo marca Despegar.

POR QUÉ: los JSON canónicos de Inputs_Planning_PnL (budget.json, forecast.json, runrate.json,
baseline_actuals+projections.json) SUMAN todas las marcas (Despegar + Best Day + Viajanet +
Viajes Falabella) y no traen la columna Marca. Para Loyalty eso infla los Drivers B2C (GB,
Orders, Up Front + Fees) y el GB con el que se calcula la acumulación de Budget de Pasaporte D!
(ej. México: Best Day = 44% del GB B2C de Budget). Las planas intermedias (plana_*.csv,
actuals_fy*.csv) SÍ traen Marca: este script las lee y arma la vista de Loyalty.

NO duplica la homologación contable (Glosario, exclusiones, Reverso AxI, mapeos): eso lo
sigue haciendo Inputs_Planning_PnL (repo B2B_Ecosystem). Acá solo se replica lo que hace
json_builder.py al pasar de plana a JSON (regla RG, colapso de canal no-B2B, suma, sin
ceros) y la composición de forecast/baseline según su config.py — y se filtra:
  - Marca = 'despegar'
  - P&L N1 que contiene 'loyalty'  +  Drivers B2C (LoB b2c): gross bookings / orders
    domestic+international, up front incentives, fees, commercial discounts.

Composición (misma que Inputs_Planning_PnL, leída de su config.py):
  budget   = plana_budget.csv
  runrate  = plana_runrate.csv
  forecast = plana_forecast.csv, con FORECAST_ACTUALS_MONTHS reemplazados por actuals
  baseline = actuals (meses <= LAST_CLOSED_MONTH) + runrate (RUNRATE_MONTHS) + forecast (FORECAST_MONTHS)
  actuals_prev = actuals del FY anterior completo (opcional, para la evolución de One Revenue)

Validación: antes de filtrar, reconstruye TODAS las marcas y compara (por país × N1 × mes,
solo las líneas de Loyalty/Drivers) contra los JSON canónicos PUBLICADOS en Drive. Si
difieren, avisa. Causa típica: el actuals_fy*.csv local no tiene el último mes cerrado
(baseline_builder lo genera y lo borra) -> correr en Inputs_Planning_PnL:
`py plana_actuals_builder.py <FY>` y volver a correr este script.

Salida (folder Drive de Loyalty): loyalty_pnl_baseline.json, loyalty_pnl_budget.json,
loyalty_pnl_forecast.json, loyalty_pnl_runrate.json, loyalty_pnl_actuals_prev.json — mismo formato {meta,cols,rows} que
los canónicos. Los lee Código.js (getLoyBaseline/Budget/Forecast/Runrate); si alguno
falta, cae al canónico de B2B (todas las marcas).

Uso:
  py inputs_contables_loyalty.py            # arma, valida y escribe en _out_pnl/ (no sube)
  py inputs_contables_loyalty.py --upload   # además sube a Drive
Correrlo después de que Inputs_Planning_PnL regenere sus planas (run_all.bat / baseline).
Requiere el repo B2B_Ecosystem al lado de este (o env INPUTS_PNL_DIR).
"""
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_SCRIPT_DIR = Path(__file__).resolve().parent
B2B_DIR = Path(os.environ.get("INPUTS_PNL_DIR") or
               _SCRIPT_DIR.parent / "B2B_Ecosystem" / "Inputs_Planning_PnL")
LOYALTY_FOLDER_ID = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"   # = DRIVE_FOLDER_ID de loyalty_sync.py
MARCA = "despegar"

COLS_OUT = ["LoB", "Canal", "Pais", "Producto",
            "P&L N1", "P&L N2", "P&L N3", "P&L N4", "P&L N5", "P&L N6", "P&L Managerial View",
            "Fecha", "Monto USD"]
GROUP = ["Marca"] + COLS_OUT[:-1]
DRIVERS_N1 = {"gross bookings domestic", "gross bookings international",
              "orders domestic", "orders international",
              "up front incentives", "fees", "commercial discounts"}
CANONICOS = {"budget": "budget.json", "runrate": "runrate.json", "forecast": "forecast.json",
             "baseline": "baseline_actuals+projections.json"}
PNL_FOLDER_ID = "1XqQPL_rlS0NRIPUnPfj5nALBTn7kAOQV"   # folder de los canónicos (= BASELINE_FOLDER_ID de Código.js)
TOL = 1.0   # USD por país × N1 × mes


def _config():
    spec = importlib.util.spec_from_file_location("pnl_config", B2B_DIR / "config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


def _read(name):
    p = B2B_DIR / name
    if not p.exists():
        sys.exit(f"No existe {p}. Correr antes los builders de Inputs_Planning_PnL.")
    df = pd.read_csv(p, low_memory=False)
    df["Fecha"] = df["Fecha"].astype(str).str[:10]
    return df


def _process(df):
    """Igual que json_builder._process() pero conservando Marca."""
    df = df.copy()
    mask = (df["Pais"].astype(str).str.lower() == "rg") & \
           (df["P&L N1"].astype(str).str.lower() == "cost of sales as principal")
    df.loc[mask, "Monto USD"] = 0
    df["Canal"] = df["Canal"].where(df["LoB"].astype(str).str.lower() == "b2b", "total")
    df["Monto USD"] = pd.to_numeric(df["Monto USD"], errors="coerce").fillna(0).round(2)
    for c in GROUP:
        df[c] = df[c].fillna("")
    df = df.groupby(GROUP, as_index=False)["Monto USD"].sum()
    return df[df["Monto USD"] != 0]


def _loyalty_scope(df):
    n1 = df["P&L N1"].astype(str).str.lower()
    lob = df["LoB"].astype(str).str.lower()
    return df[n1.str.contains("loyalty") | (n1.isin(DRIVERS_N1) & (lob == "b2c"))]


def build_all():
    cfg = _config()
    fc_act = set(cfg.FORECAST_ACTUALS_MONTHS)
    act_file = f"actuals_fy{str(cfg.CURRENT_FY)[-2:]}_abr{cfg.CURRENT_FY - 1}_mar{cfg.CURRENT_FY}.csv"
    print(f"Inputs_Planning_PnL: {B2B_DIR}")
    print(f"  FY{str(cfg.CURRENT_FY)[-2:]} · último mes cerrado {cfg.LAST_CLOSED_MONTH} · "
          f"forecast con actuals hasta {cfg.FORECAST_ACTUALS_CUTOFF}")
    act = _process(_read(act_file))
    budget = _process(_read("plana_budget.csv"))
    runrate = _process(_read("plana_runrate.csv"))
    fc_raw = _process(_read("plana_forecast.csv"))
    forecast = pd.concat([fc_raw[~fc_raw["Fecha"].isin(fc_act)], act[act["Fecha"].isin(fc_act)]],
                         ignore_index=True)
    act_months = {d for d in act["Fecha"].unique() if d <= cfg.LAST_CLOSED_MONTH}
    baseline = pd.concat([act[act["Fecha"].isin(act_months)],
                          runrate[runrate["Fecha"].isin(cfg.RUNRATE_MONTHS)],
                          forecast[forecast["Fecha"].isin(cfg.FORECAST_MONTHS)]], ignore_index=True)
    out = {"baseline": baseline, "budget": budget, "forecast": forecast, "runrate": runrate}
    # FY anterior (actuals completos): lo usa la pestaña "Reglas One Revenue" para la
    # evolución FY en curso vs FY anterior. Opcional: si la plana no está, se omite
    # (se genera en Inputs_Planning_PnL con `py plana_actuals_builder.py <FY-1>`).
    fy_prev = cfg.CURRENT_FY - 1
    prev_file = f"actuals_fy{str(fy_prev)[-2:]}_abr{fy_prev - 1}_mar{fy_prev}.csv"
    if (B2B_DIR / prev_file).exists():
        out["actuals_prev"] = _process(_read(prev_file))
        CANONICOS["actuals_prev"] = f"actuals_previos_fy{str(fy_prev)[-2:]}.json"
    else:
        print(f"  [WARN] sin {prev_file}: no se arma loyalty_pnl_actuals_prev.json")
    return out


def _key_sums(df):
    d = df.copy()
    d["k"] = list(zip(d["Pais"].astype(str).str.lower(), d["P&L N1"].astype(str).str.lower(),
                      d["LoB"].astype(str).str.lower(), d["Fecha"].astype(str).str[:10]))
    return d.groupby("k")["Monto USD"].sum()


def validate(esc, df_all):
    """Todas las marcas, scope Loyalty, vs el JSON canónico local."""
    j = _canonico(CANONICOS[esc])
    if j is None:
        print(f"  [{esc}] no se pudo bajar {CANONICOS[esc]} de Drive para validar")
        return True
    can = _loyalty_scope(pd.DataFrame(j["rows"], columns=j["cols"]))
    mine = _key_sums(_loyalty_scope(df_all))
    theirs = _key_sums(can)
    diff = mine.subtract(theirs, fill_value=0)
    bad = diff[diff.abs() > TOL]
    if len(bad):
        print(f"  [WARN] {esc}: {len(bad)} celdas país×N1×mes difieren del canónico "
              f"(máx |Δ| = {bad.abs().max():,.0f} USD). Ej: {list(bad.head(3).items())}")
        return False
    print(f"  [OK] {esc}: reconstrucción (todas las marcas) = canónico ({len(theirs):,} celdas)")
    return True


def emit(esc, df_all):
    sc = _loyalty_scope(df_all)
    marcas = sc.groupby(sc["Marca"].astype(str).str.lower())["Monto USD"].size().to_dict()
    out = sc[sc["Marca"].astype(str).str.lower() == MARCA][COLS_OUT]
    out = out.groupby(COLS_OUT[:-1], as_index=False)["Monto USD"].sum()
    payload = {
        "meta": {"concepto": esc, "marca": MARCA, "filas": len(out),
                 "fechas": sorted(out["Fecha"].astype(str).unique()),
                 "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                 "fuente": f"Inputs_Planning_PnL planas (filas por marca en scope Loyalty: {marcas})"},
        "cols": COLS_OUT,
        "rows": out.values.tolist(),
    }
    return f"loyalty_pnl_{esc}.json", json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                                                default=str).encode("utf-8")


ORDERS_FILE = "loyalty_orders_real.json"
ORDERS_COLS = ["Marca", "LoB", "Canal", "Pais", "Producto", "Viaje", "Fecha", "Orders"]


def build_orders():
    """Órdenes reales (actuals) por Marca × LoB × Canal × País × Producto × Viaje × mes, TODAS
    las marcas y LoB y SIN colapsar el canal de B2C (a diferencia de loyalty_pnl_*.json). Lo usa
    Input proyecciones > Datos reales para puntos redimidos por orden (puntos del Datalake /
    estas órdenes). Junta el FY en curso y el anterior: todos los meses cerrados disponibles."""
    cfg = _config()
    files = []
    for fy in (cfg.CURRENT_FY - 1, cfg.CURRENT_FY):
        f = f"actuals_fy{str(fy)[-2:]}_abr{fy - 1}_mar{fy}.csv"
        if (B2B_DIR / f).exists():
            files.append(f)
        else:
            print(f"  [WARN] orders: sin {f}")
    if not files:
        return None
    df = pd.concat([_read(f) for f in files], ignore_index=True)
    n1 = df["P&L N1"].astype(str).str.strip().str.lower()
    df = df[n1.isin({"orders domestic", "orders international"})].copy()
    df["Viaje"] = n1[df.index].str.replace("orders ", "", regex=False)
    df["Fecha"] = df["Fecha"].str[:7]
    df = df[df["Fecha"] <= str(cfg.LAST_CLOSED_MONTH)[:7]]
    for c in ["Marca", "LoB", "Canal", "Pais", "Producto"]:
        df[c] = df[c].fillna("").astype(str).str.strip().str.lower()
    df["Monto USD"] = pd.to_numeric(df["Monto USD"], errors="coerce").fillna(0)
    out = df.groupby(ORDERS_COLS[:-1], as_index=False)["Monto USD"].sum().rename(columns={"Monto USD": "Orders"})
    out = out[out["Orders"] != 0]
    out["Orders"] = out["Orders"].round(0)
    meses = sorted(out["Fecha"].unique())
    print(f"  orders: {len(out):,} filas · {len(meses)} meses ({', '.join(meses)}) desde {files}")
    payload = {"meta": {"generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "fuente": f"Inputs_Planning_PnL {files} · P&L N1 orders domestic/international",
                        "meses": meses},
               "cols": ORDERS_COLS, "rows": out.values.tolist()}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=Credentials.from_authorized_user_file(
        str(_SCRIPT_DIR / "token_drive.json")))


def _canonico(name):
    """El canónico PUBLICADO en Drive (no la copia local de B2B, que puede estar vieja:
    el baseline se arma mes a mes con --promote-month y no queda copia local actualizada)."""
    try:
        import io
        from googleapiclient.http import MediaIoBaseDownload
        svc = _drive()
        f = svc.files().list(q=f"name='{name}' and '{PNL_FOLDER_ID}' in parents and trashed=false",
                             fields="files(id)").execute().get("files", [])
        if not f:
            return None
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=f[0]["id"]))
        done = False
        while not done:
            _, done = dl.next_chunk()
        return json.loads(buf.getvalue().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] no se pudo leer {name} de Drive: {str(e)[:120]}")
        return None


def _upload(name, data):
    from googleapiclient.http import MediaInMemoryUpload
    svc = _drive()
    media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
    ex = svc.files().list(q=f"name='{name}' and '{LOYALTY_FOLDER_ID}' in parents and trashed=false",
                          fields="files(id)").execute().get("files", [])
    if ex:
        svc.files().update(fileId=ex[0]["id"], media_body=media).execute()
        print(f"  OK Drive: actualizado ({name})")
    else:
        svc.files().create(body={"name": name, "parents": [LOYALTY_FOLDER_ID]},
                           media_body=media, fields="id").execute()
        print(f"  OK Drive: creado ({name})")


if __name__ == "__main__":
    upload = "--upload" in sys.argv
    escs = build_all()
    ok = all([validate(e, df) for e, df in escs.items()])
    out_dir = _SCRIPT_DIR / "_out_pnl"
    out_dir.mkdir(exist_ok=True)
    for esc, df in escs.items():
        name, data = emit(esc, df)
        (out_dir / name).write_bytes(data)
        print(f"  {name}: {len(data) // 1024} KB")
        if upload:
            _upload(name, data)
    orders = build_orders()
    if orders is not None:
        (out_dir / ORDERS_FILE).write_bytes(orders)
        print(f"  {ORDERS_FILE}: {len(orders) // 1024} KB")
        if upload:
            _upload(ORDERS_FILE, orders)
    if not ok:
        print("\n  [WARN] Hubo diferencias contra los canónicos (ver arriba). Revisar antes de confiar.")
