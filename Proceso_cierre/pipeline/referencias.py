"""
Carga las tablas de referencia (extraidas de 'Regla entidad Legal' y de TC_mensual)
usadas para los VLOOKUP de las columnas derivadas de Etapa 1. Se comparten entre
etapa1_acumulaciones.py y etapa1_redenciones.py.
"""

import pandas as pd

from pipeline.config import cargar_config, ruta_absoluta


def _ruta_referencia(nombre_logico: str) -> str:
    cfg = cargar_config()
    return ruta_absoluta(cfg["referencia"][nombre_logico])


def cargar_entidad_legal() -> dict:
    """clave_pais_producto_business (ej. 'ARCARDOMESTIC') -> entidad_legal (ej. 'ARGENTINA')."""
    df = pd.read_excel(_ruta_referencia("regla_entidad_legal"), sheet_name="entidad_legal")
    return dict(zip(df["clave_pais_producto_business"], df["entidad_legal"]))


def cargar_producto() -> dict:
    """produto_agrupado (string tal cual viene de la query, ej. '["Excursiones"]') -> producto."""
    df = pd.read_excel(_ruta_referencia("regla_entidad_legal"), sheet_name="producto")
    return dict(zip(df["produto_agrupado"], df["producto"]))


def cargar_producto_fallback() -> dict:
    """product (codigo, ej. 'FLIGHT') -> producto_nombre. Fallback cuando 'producto' no matchea."""
    df = pd.read_excel(_ruta_referencia("regla_entidad_legal"), sheet_name="producto_fallback")
    return dict(zip(df["product_code"], df["producto_nombre"]))


def cargar_tc_mensual() -> dict:
    """concat_entidad_legal (ej. 'BRBRASIL') -> tc del mes de cierre."""
    df = pd.read_excel(_ruta_referencia("tc_mensual"))
    return dict(zip(df["concat_entidad_legal"], df["tc"]))


def ruta_tc_mensual() -> str:
    """Ruta absoluta de TC_mensual.xlsx - separado de cargar_tc_mensual() porque
    validaciones.py necesita la ruta (para chequear la fecha de modificacion), no
    el contenido."""
    return _ruta_referencia("tc_mensual")
