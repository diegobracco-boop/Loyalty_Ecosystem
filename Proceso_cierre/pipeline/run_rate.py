"""Completa el bloque "Run Rate" de la solapa 'P&L Actuals vs RR' de Asientos Cierre Loyalty.xlsx
con el ultimo run rate (runrate.json de Inputs_Planning_PnL), para compararlo contra lo que se
manda a contabilizar (bloque "Debe - Haber" de la misma solapa, que sale de las otras hojas).

Reglas (decididas por Diego el 2026-10-03):
  - Fuente: `run_rate.archivo` de config.yaml (runrate.json, formato {meta, cols, rows}).
  - Solo la LoB de `run_rate.lob` (default b2c: los asientos son todo B2C de Loyalty).
  - Mes = cierre.anio / cierre.mes de config.yaml.
  - 'Loyalty - Rewards & Benefits' y '... Cost' son lo mismo para el RR: el RR solo trae
    'loyalty - rewards & benefits cost'. Va en la columna "... Cost"; la columna sin sufijo
    queda vacia y "Suma Reward & Benefits" = suma de ambas.
  - 'others countries' -> fila "Others". 'rg' queda FUERA salvo `run_rate.rg_en_others: true`
    (ojo: en el RR 'rg' compensa el Deferred Revenue In de 'others countries' - ver INSTRUCCIONES).

Si algo falta (archivo, solapa, mes) NO frena el cierre: avisa y sigue.
"""

import json
import os
from datetime import datetime

# encabezado de la solapa (en minusculas) -> P&L N1 del run rate
COLUMNA_A_N1 = {
    "loyalty - deferred revenue out": "loyalty - deferred revenue out",
    "loyalty - deferred revenue in": "loyalty - deferred revenue in",
    "loyalty - breakage revenue": "loyalty - breakage revenue",
    "loyalty - bank revenue": "loyalty - bank revenue",
    "loyalty - partners revenue": "loyalty - partner revenue",
    "loyalty - rewards & benefits cost": "loyalty - rewards & benefits cost",
}
ENCABEZADO_SUMA_RB = "suma reward & benefits"
ENCABEZADO_RB = "loyalty - rewards & benefits"
ENCABEZADO_RB_COST = "loyalty - rewards & benefits cost"

SOLAPA = "P&L Actuals vs RR"
ANCLA = "run rate"  # celda de la columna A que marca el encabezado del bloque


def _fila_pais(pais: str, rg_en_others: bool):
    """Nombre de fila de la solapa (en minusculas) para un 'Pais' del run rate, o None si va afuera."""
    pais = (pais or "").strip().lower()
    if pais == "others countries":
        return "others"
    if pais == "rg":
        return "others" if rg_en_others else None
    return pais


def agregar_run_rate(cfg: dict) -> dict:
    """Devuelve {"montos": {(fila, n1): usd}, "mes": "YYYY-MM-01", "archivo": ruta, ...}
    o lanza FileNotFoundError / ValueError con un mensaje claro."""
    rr = cfg.get("run_rate") or {}
    archivo = rr.get("archivo")
    if not archivo:
        raise ValueError("config.yaml no tiene run_rate.archivo")
    if not os.path.exists(archivo):
        raise FileNotFoundError(f"no existe el archivo de run rate: {archivo}")
    lob = (rr.get("lob") or "b2c").lower()
    rg_en_others = bool(rr.get("rg_en_others", False))
    mes = f"{int(cfg['cierre']['anio']):04d}-{int(cfg['cierre']['mes']):02d}-01"

    with open(archivo, encoding="utf-8") as f:
        datos = json.load(f)
    cols = datos["cols"]
    i_lob, i_pais, i_n1 = cols.index("LoB"), cols.index("Pais"), cols.index("P&L N1")
    i_fecha, i_monto = cols.index("Fecha"), cols.index("Monto USD")

    montos = {}
    n_filas = 0
    for r in datos["rows"]:
        if r[i_fecha] != mes or (r[i_lob] or "").lower() != lob:
            continue
        n1 = (r[i_n1] or "").lower()
        if not n1.startswith("loyalty"):
            continue
        fila = _fila_pais(r[i_pais], rg_en_others)
        n_filas += 1
        if fila is None:
            continue
        montos[(fila, n1)] = montos.get((fila, n1), 0.0) + float(r[i_monto])
    if n_filas == 0:
        raise ValueError(f"el run rate no tiene filas de Loyalty ({lob}) para {mes} "
                         f"(meses disponibles: {datos.get('meta', {}).get('fechas')})")
    return {
        "montos": montos, "mes": mes, "archivo": archivo, "lob": lob,
        "rg_en_others": rg_en_others,
        "archivo_fecha": datetime.fromtimestamp(os.path.getmtime(archivo)).strftime("%Y-%m-%d %H:%M"),
    }


def completar_run_rate(wb, cfg: dict) -> dict:
    """Escribe el bloque Run Rate en `wb[SOLAPA]`. Devuelve un resumen {encabezado: total}
    o {} si no se pudo (avisa por consola, no lanza)."""
    if SOLAPA not in wb.sheetnames:
        print(f"  Run Rate: no existe la solapa '{SOLAPA}' en Asientos - se omite.")
        return {}
    try:
        rr = agregar_run_rate(cfg)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"  Run Rate: se omite ({e}).")
        return {}

    ws = wb[SOLAPA]
    fila_enc = next((c.row for c in ws["A"] if str(c.value or "").strip().lower() == ANCLA), None)
    if fila_enc is None:
        print(f"  Run Rate: no encuentro la celda '{ANCLA}' en la columna A de '{SOLAPA}' - se omite.")
        return {}

    # columnas por encabezado (hasta la primera celda vacia a la derecha)
    columnas = {}
    col = 2
    while ws.cell(fila_enc, col).value:
        columnas[str(ws.cell(fila_enc, col).value).strip().lower()] = col
        col += 1

    # filas por pais (hasta 'Total')
    filas = {}
    r = fila_enc + 1
    while ws.cell(r, 1).value and str(ws.cell(r, 1).value).strip().lower() != "total":
        filas[str(ws.cell(r, 1).value).strip().lower()] = r
        r += 1
    fila_total = r

    # los paises del RR que no tienen fila en la solapa no se pierden en silencio
    sin_fila = {f for (f, _n1) in rr["montos"] if f not in filas}
    if sin_fila:
        total_sin_fila = sum(v for (f, _n1), v in rr["montos"].items() if f in sin_fila)
        print(f"  Run Rate: AVISO - paises del RR sin fila en la solapa (no se pegan): "
              f"{sorted(sin_fila)} (suma {total_sin_fila:,.0f} USD).")

    for pais, fila in filas.items():
        for encabezado, n1 in COLUMNA_A_N1.items():
            c = columnas.get(encabezado)
            if c:
                ws.cell(fila, c).value = round(rr["montos"].get((pais, n1), 0.0), 2)
        c_rb, c_cost, c_suma = (columnas.get(ENCABEZADO_RB), columnas.get(ENCABEZADO_RB_COST),
                                columnas.get(ENCABEZADO_SUMA_RB))
        if c_rb:
            ws.cell(fila, c_rb).value = None  # el RR no tiene linea aparte: todo va en "... Cost"
        if c_suma and c_rb and c_cost:
            a, b = ws.cell(fila, c_rb).coordinate, ws.cell(fila, c_cost).coordinate
            ws.cell(fila, c_suma).value = f"=SUM({a}:{b})"

    # nota de trazabilidad, a la derecha del bloque (no pisa nada de la tabla)
    c_nota = (max(columnas.values()) + 2) if columnas else 11
    ws.cell(fila_enc, c_nota).value = (
        f"Fuente: {os.path.basename(rr['archivo'])} (archivo del {rr['archivo_fecha']}) | "
        f"LoB {rr['lob']} | mes {rr['mes'][:7]} | USD"
    )
    ws.cell(fila_enc + 1, c_nota).value = (
        "'rg' incluido en Others" if rr["rg_en_others"] else "'rg' excluido de Others"
    )

    resumen = {}
    for encabezado in COLUMNA_A_N1:
        resumen[encabezado] = round(sum(
            ws.cell(f, columnas[encabezado]).value or 0 for f in filas.values()
        ), 2) if encabezado in columnas else None
    resumen["_filas_total_sheet"] = fila_total
    return resumen
