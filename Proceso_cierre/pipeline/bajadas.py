"""
Etapa 1 - Paso 1: bajar las 3 queries del Datalake y guardarlas en Auditoria/Bajadas
tal cual vienen (a valor, sin modificar).

Las queries (queries/Queries Data/*.sql) son las que Rosario escribio en Metabase como
Native Query, con variables {{Desde}}/{{Hasta}}/{{Pais}}/{{Partner}}. Para correrlas desde
Python (sin pasar por Metabase) reemplazamos esas variables por texto SQL valido, tal como
hace daily_sync_grego.py, y dejamos el resto de la query intacta (no se reescribe a mano
por el riesgo de introducir errores en una query tan larga).

Puntos Expirados es la excepcion: no tiene variables {{Desde}}/{{Hasta}} - confirmado con
Rosario (2026-07-17) que no hace falta acotarla por fecha, se trae completa tal cual esta
en Metabase.
"""

from datetime import date

import pandas as pd

from pipeline.conexion import fetch
from pipeline.config import ruta_absoluta, cargar_config


def _cargar_sql(ruta_relativa: str) -> str:
    ruta = ruta_absoluta("queries", ruta_relativa)
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _sustituir_fechas(sql: str, date_from: date, date_to: date) -> str:
    return (
        sql.replace("{{Desde}}", f"DATE('{date_from}')")
        .replace("{{Hasta}}", f"DATE('{date_to}')")
    )


def build_acumulaciones_query(date_from: date, date_to: date) -> str:
    """Adapta la query de Acumulaciones (Metabase Native Query) a SQL parametrizado en Python."""
    cfg = cargar_config()
    sql = _cargar_sql(cfg["queries"]["data"]["acumulaciones"])
    sql = _sustituir_fechas(sql, date_from, date_to)
    # Sin filtro de pais/partner: siempre traemos todo (equivalente a elegir "TODOS" en Metabase).
    sql = sql.replace("{{Pais}}", "'TODOS'").replace("{{Partner}}", "'TODOS'")
    return sql


def build_redenciones_query(date_from: date, date_to: date) -> str:
    """Adapta la query de Redenciones. No tiene variables {{Pais}}/{{Partner}}, solo fecha."""
    cfg = cargar_config()
    sql = _cargar_sql(cfg["queries"]["data"]["redenciones"])
    return _sustituir_fechas(sql, date_from, date_to)


def build_puntos_expirados_query() -> str:
    """Sin variables de fecha - se trae el historico completo tal cual (ver docstring del modulo)."""
    cfg = cargar_config()
    return _cargar_sql(cfg["queries"]["data"]["puntos_expirados"])


def bajar_acumulaciones(date_from: date, date_to: date):
    query = build_acumulaciones_query(date_from, date_to)
    return fetch(query, "Acumulaciones")


def bajar_redenciones(date_from: date, date_to: date):
    query = build_redenciones_query(date_from, date_to)
    return fetch(query, "Redenciones")


def bajar_puntos_expirados(date_from: date, date_to: date):
    # date_from/date_to se ignoran (ver docstring del modulo) - se mantienen en la firma
    # para que run_cierre.py pueda llamar a las 3 bajadas de forma uniforme.
    query = build_puntos_expirados_query()
    return fetch(query, "Puntos Expirados")


def recortar_borde_mes(
    df: pd.DataFrame,
    columna_fecha: str,
    date_from: date,
    date_to: date,
    label: str,
    columnas_suma: list,
) -> pd.DataFrame:
    """Recorta defensivamente filas con `columna_fecha` fuera de [date_from, date_to).

    2026-08-03 (cierre 07/2026): tanto Acumulaciones como Redenciones trajeron filas
    con processing_date del primer dia del mes SIGUIENTE pese al filtro SQL
    `< {{Hasta}}` (confirmado leyendo la bajada real - desfasaje de huso horario del
    motor del Datalake en el borde del mes, ver Bitacora). No se toca la query - se
    recorta aca del lado de Python, DESPUES de guardar la bajada cruda en
    Auditoria/Bajadas (esa se sigue guardando tal cual viene, sin modificar -
    constraint de auditoria, ver guardar_bajada_auditoria()). Llamar a esta funcion
    recien despues de ese guardado.

    Las queries de "Queries Control" (sum points) tienen el mismo patron de fecha, asi
    que sufren el mismo desfasaje - por eso esta funcion guarda en `df.attrs
    ["descartados_borde_mes"]` la suma de `columnas_suma` de las filas descartadas,
    para que pipeline/validaciones.py pueda restarla del total del control antes de
    comparar (si no, el chequeo de cuadre quedaria roto todos los meses por este
    recorte, comparando un lado ya corregido contra el otro lado que sigue con el
    mismo desfasaje).
    """
    fechas = pd.to_datetime(df[columna_fecha])
    ts_desde = pd.Timestamp(date_from)
    ts_hasta = pd.Timestamp(date_to)
    fuera_de_rango = (fechas < ts_desde) | (fechas >= ts_hasta)
    descartados = {col: 0 for col in columnas_suma}
    if fuera_de_rango.any():
        filas_fuera = df[fuera_de_rango]
        print(
            f"  AVISO: se descartaron {len(filas_fuera)} filas de {label} con "
            f"{columna_fecha} fuera de [{date_from}, {date_to}) - desfasaje de huso "
            f"horario del Datalake en el borde del mes (la bajada cruda en "
            f"Auditoria/Bajadas no se ve afectada)."
        )
        descartados = {col: filas_fuera[col].sum() for col in columnas_suma}
        df = df[~fuera_de_rango].copy()
    df.attrs["descartados_borde_mes"] = descartados
    return df


def guardar_bajada_auditoria(df, nombre_archivo: str, carpeta_bajadas: str):
    """Guarda la bajada cruda tal cual viene, sin modificar (constraint de auditoria)."""
    import os

    os.makedirs(carpeta_bajadas, exist_ok=True)
    ruta = os.path.join(carpeta_bajadas, nombre_archivo)
    df.to_excel(ruta, index=False)
    print(f"  Guardado en auditoria: {ruta}")
    return ruta
