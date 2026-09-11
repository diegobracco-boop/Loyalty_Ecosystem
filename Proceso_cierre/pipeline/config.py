"""Carga config.yaml y resuelve rutas relativas a la carpeta del pipeline."""

import os
from datetime import date

import yaml

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def cargar_config():
    ruta_config = os.path.join(RAIZ, "config.yaml")
    with open(ruta_config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def ruta_absoluta(*partes):
    """Resuelve una ruta relativa a la carpeta raiz del pipeline (donde vive config.yaml)."""
    return os.path.join(RAIZ, *partes)


def ruta_cierre(*partes):
    """Resuelve una ruta relativa a rutas.carpeta_cierre (la carpeta del mes que se
    esta cerrando - ej. Asientos Cierre Loyalty.xlsx, Auditoria/Bajadas, backups).
    Distinta de ruta_absoluta(): esa es relativa a la carpeta del pipeline (queries/,
    referencia/), que no cambia mes a mes."""
    cfg = cargar_config()
    return os.path.join(cfg["rutas"]["carpeta_cierre"], *partes)


def fechas_cierre():
    """Calcula el {{Desde}}/{{Hasta}} de las queries a partir de cierre.anio/cierre.mes
    de config.yaml - es lo UNICO que se edita mes a mes (ver INSTRUCCIONES.md), no hay
    que tipear fechas en ningun otro lado.

    2026-07-22: Desde/Hasta son SIEMPRE primer dia del mes de cierre (inclusive) / primer
    dia del mes SIGUIENTE (exclusive) - asi estan disenadas las queries (processing_date
    < {{Hasta}}, no <=). Usar el ultimo dia calendario del mes de cierre como Hasta con
    un <= era un bug: como processing_date es TIMESTAMP, "<= DATE('2026-06-30')" trunca a
    2026-06-30 00:00:00 y descarta casi todo el 30 (todo lo que no sea exactamente
    medianoche). Ver Bitacora.

    2026-07-27: `cierre.hasta_override` (opcional, formato "YYYY-MM-DD") permite un
    corte PARCIAL del mes (ej. "lo que va del mes" antes del cierre final) - si esta
    definido, se usa como Hasta (exclusive, mismo criterio de siempre) en vez del dia
    1 del mes siguiente. Sin este campo (o vacio), el comportamiento es el de siempre
    (mes completo)."""
    cfg = cargar_config()
    anio = cfg["cierre"]["anio"]
    mes = cfg["cierre"]["mes"]
    date_from = date(anio, mes, 1)
    hasta_override = cfg["cierre"].get("hasta_override")
    if hasta_override:
        date_to = date.fromisoformat(str(hasta_override))
    elif mes == 12:
        date_to = date(anio + 1, 1, 1)
    else:
        date_to = date(anio, mes + 1, 1)
    return date_from, date_to
