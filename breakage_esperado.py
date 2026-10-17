"""Breakage esperado calculado — réplica del Excel de Control de Gestión
("Breakage Esperado <MM'AA>.xlsx", carpeta Cierre/<mes>/Auditoria), armada con los datos del
ecosystem. Es un CONTROL: el valor oficial sigue siendo el del Excel (control contable firmado,
ASC 606) que se carga en la pestaña `breakage_esperado` del Sheet Config.

Regla (carátula del Excel + fórmulas de las solapas "<PAÍS> 2025" y "Breakage Esperado"):

    % del mes M  = vencidos acumulados hasta M (Non Tender + Cobrand)
                   / acumulados hasta M − 19 meses (Non Tender + Cobrand + Partners)
    breakage esperado de M = promedio simple de los últimos 12 % mensuales

- Vencidos: query de breakage (`clm_transactions` PE) desde 2019, clasificados por
  `points_type_id` con `diccionario_point_type.csv` (copia del "Diccionario Point Type" del
  Excel). Solo los grupos Non Tender y Cobrand (quedan afuera R&B, Santander 2, Partner, PAD…).
- Acumulados: hasta 2025-12 la historia OFICIAL del Excel (solapa "Acumulaciones", que sale del
  archivo de cierre) en `breakage_acum_hist.csv` — la fila 2022-12 es el saldo acumulado a esa
  fecha. Desde 2026-01, las acumulaciones del ecosystem (Pasaporte D! -> Non Tender, Cobrand +
  Partners -> Cobrand). Con el rezago de 19 meses, eso recién entra en el % de 2027-08.
- Ajustes del Excel que se replican (AJUSTES_VENCIDOS / INICIO_PROMEDIO).
"""
import csv
from pathlib import Path

import pandas as pd

_DIR = Path(__file__).resolve().parent
DICC_CSV = _DIR / "diccionario_point_type.csv"
ACUM_HIST_CSV = _DIR / "breakage_acum_hist.csv"
BREAKAGE_ESP_FILE = "loyalty_breakage_esperado.json"

# 19 meses: criterio histórico del Excel de Control de Gestión (decisión de Diego, 17-oct).
# Los puntos vencen a los 18 meses y 1 día; con 18 el denominador incluiría el mes M−18, que ya
# venció casi entero en M — se evaluó y se descartó para no cambiar el criterio histórico.
REZAGO_MESES = 19
VENTANA = 12               # "promedio de los últimos 12 meses"
GRUPOS_VENCIDOS = ("Non Tender", "Cobrand")
ULTIMO_MES_HIST = "2025-12"  # último mes de breakage_acum_hist.csv (cierre oficial)

# Ajustes manuales del Excel sobre los vencidos Non Tender, desde el mes indicado.
#   CO: welcome bonus Pasaporte CO vencido en 2024-06 (celda 'CO 2025 '!I8), se resta siempre.
AJUSTES_VENCIDOS = {("CO", "2024-06"): -302123640}
# Países que arrancaron después: el promedio toma los meses disponibles desde acá (hasta 12).
#   PE: el Excel promedia desde 2025-07 ($BD) — los meses anteriores dan valores atípicos.
INICIO_PROMEDIO = {"PE": "2025-07"}


def load_dicc() -> dict:
    with open(DICC_CSV, encoding="utf-8") as f:
        return {int(r["points_type_id"]): r["grupo"] for r in csv.DictReader(f)}


def load_acum_hist() -> pd.DataFrame:
    df = pd.read_csv(ACUM_HIST_CSV)
    return df.rename(columns={"cobrand_partners": "cobrand"})


def acum_from_ecosystem(acum_frames, dict_acum: dict) -> pd.DataFrame:
    """Acumulaciones del ecosystem por mes × país en Non Tender / Cobrand (para meses > hist).
    acum_frames: DataFrames agregados de acumulaciones (processing_date, country_code, partner,
    point_type, points). dict_acum: concatenado (partner+point_type) -> sección del diccionario."""
    fr = [d for d in acum_frames if d is not None and len(d)]
    if not fr:
        return pd.DataFrame(columns=["ym", "country", "non_tender", "cobrand"])
    a = pd.concat(fr, ignore_index=True)
    a["ym"] = a["processing_date"].astype(str).str.slice(0, 7)
    a = a[a["ym"] > ULTIMO_MES_HIST]
    sec = (a["partner"].astype(str) + a["point_type"].astype(str)).map(dict_acum)
    a["points"] = pd.to_numeric(a["points"], errors="coerce").fillna(0)
    a["non_tender"] = a["points"].where(sec == "Pasaporte D!", 0)
    a["cobrand"] = a["points"].where(sec.isin(["Cobrand", "Partners"]), 0)
    out = a.groupby(["ym", "country_code"], as_index=False)[["non_tender", "cobrand"]].sum()
    return out.rename(columns={"country_code": "country"})


def compute(df_venc: pd.DataFrame, acum: pd.DataFrame, hasta_ym: str) -> pd.DataFrame:
    """df_venc: salida de clean_breakage (expiration_date 'MM-YYYY', country, points_type_id,
    points). acum: ym, country, non_tender, cobrand (mensual; la fila 2022-12 = saldo).
    Devuelve una fila por país × mes con numeradores, denominadores, % mensual y promedio 12m."""
    dicc = load_dicc()
    v = df_venc.copy()
    v["ym"] = v["expiration_date"].str.slice(3, 7) + "-" + v["expiration_date"].str.slice(0, 2)
    v["grupo"] = v["points_type_id"].map(dicc).fillna("Sin diccionario")
    v = v[v["grupo"].isin(GRUPOS_VENCIDOS)]
    vm = v.pivot_table(index=["country", "ym"], columns="grupo", values="points", aggfunc="sum").fillna(0)
    vm = vm.reindex(columns=list(GRUPOS_VENCIDOS), fill_value=0).reset_index()
    for (pais, desde), monto in AJUSTES_VENCIDOS.items():
        vm = pd.concat([vm, pd.DataFrame([{"country": pais, "ym": desde, "Non Tender": monto, "Cobrand": 0}])])

    paises = sorted(set(acum["country"]) & set(vm["country"]))
    meses = [str(p) for p in pd.period_range("2021-01", hasta_ym, freq="M")]
    rows = []
    for pais in paises:
        vp = vm[vm["country"] == pais].groupby("ym")[["Non Tender", "Cobrand"]].sum()
        ap = acum[acum["country"] == pais].groupby("ym")[["non_tender", "cobrand"]].sum()
        for m in meses:
            corte = str(pd.Period(m, "M") - REZAGO_MESES)
            vv = vp[vp.index <= m].sum()
            aa = ap[ap.index <= corte].sum()
            den = aa["non_tender"] + aa["cobrand"]
            if den <= 0:
                continue
            rows.append({"country": pais, "ym": m, "corte_acum": corte,
                         "venc_nt": vv["Non Tender"], "venc_cb": vv["Cobrand"],
                         "acum_nt": aa["non_tender"], "acum_cb": aa["cobrand"],
                         "pct_mes": (vv["Non Tender"] + vv["Cobrand"]) / den})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    prom, nmes = [], []
    for pais, g in out.groupby("country", sort=False):
        s = g.set_index("ym")["pct_mes"]
        ini = INICIO_PROMEDIO.get(pais)
        for m in g["ym"]:
            ventana = [str(pd.Period(m, "M") - k) for k in range(VENTANA)]
            if ini:
                ventana = [x for x in ventana if x >= ini]
            vals = s.reindex(ventana).dropna()
            completo = len(vals) == VENTANA or (ini and len(vals) == len(ventana) and len(vals) > 0)
            prom.append(vals.mean() if completo else None)
            nmes.append(len(vals))
    out["prom_12m"] = prom
    out["n_meses"] = nmes
    return out


def build_json(df: pd.DataFrame, meta: dict) -> dict:
    cols = ["country", "ym", "corte_acum", "venc_nt", "venc_cb", "acum_nt", "acum_cb", "pct_mes", "prom_12m", "n_meses"]
    d = df[cols].copy()
    for c in ("venc_nt", "venc_cb", "acum_nt", "acum_cb"):
        d[c] = d[c].round(0)
    for c in ("pct_mes", "prom_12m"):
        d[c] = d[c].astype(float).round(6)
    d = d.astype(object).where(d.notna(), None)
    return {"meta": meta, "cols": cols, "rows": d.values.tolist()}
