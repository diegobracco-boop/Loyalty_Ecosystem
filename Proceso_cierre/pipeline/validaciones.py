"""
Chequeos de cuadre antes/despues de pegar en Asientos. Si algo no cierra, el pipeline
debe frenar y mostrarlo claro (no seguir silenciosamente con datos sospechosos).

Cada bajada tiene su query de control en "Queries Control" (sum points), que recalcula
el total desde cero de forma independiente. Comparamos ese total contra la suma de la
bajada que efectivamente vamos a guardar/pegar - si no coinciden, algo cambio entre las
dos queries (filtro, join, etc.) y hay que revisar antes de seguir.
"""

import os
from datetime import date

from pipeline.bajadas import _cargar_sql, _sustituir_fechas
from pipeline.conexion import fetch
from pipeline.config import cargar_config
from pipeline.referencias import ruta_tc_mensual

TOLERANCIA = 0.01  # margen de redondeo aceptable entre bajada y control
TC_VIGENCIA_DIAS = 45  # ver chequear_vigencia_tc


def _control_acumulaciones(date_from: date, date_to: date):
    cfg = cargar_config()
    sql = _sustituir_fechas(_cargar_sql(cfg["queries"]["control"]["acumulaciones"]), date_from, date_to)
    return fetch(sql, "Control Acumulaciones")


def _control_redenciones(date_from: date, date_to: date):
    cfg = cargar_config()
    sql = _sustituir_fechas(_cargar_sql(cfg["queries"]["control"]["redenciones"]), date_from, date_to)
    return fetch(sql, "Control Redenciones")


def _control_puntos_expirados():
    cfg = cargar_config()
    sql = _cargar_sql(cfg["queries"]["control"]["puntos_expirados"])
    return fetch(sql, "Control Puntos Expirados")


def chequear_sum_points_acumulaciones(df_acumulaciones, date_from: date, date_to: date) -> dict:
    control = _control_acumulaciones(date_from, date_to)
    descartados = df_acumulaciones.attrs.get("descartados_borde_mes", {})
    total_bajada = df_acumulaciones["points"].sum()
    # La query de control tiene el mismo patron {{Desde}}/{{Hasta}} que la de bajada,
    # asi que sufre el mismo desfasaje de huso horario en el borde del mes (ver
    # pipeline/bajadas.py::recortar_borde_mes) - se resta lo ya descartado de la
    # bajada para comparar ambos lados sobre el mismo universo de filas.
    total_control = control["Total_Puntos"].iloc[0] - descartados.get("points", 0)
    diferencia = total_bajada - total_control
    return {
        "nombre": "Acumulaciones - sum points",
        "ok": abs(diferencia) <= TOLERANCIA,
        "total_bajada": total_bajada,
        "total_control": total_control,
        "diferencia": diferencia,
    }


def chequear_sum_points_redenciones(df_redenciones, date_from: date, date_to: date) -> dict:
    control = _control_redenciones(date_from, date_to)
    descartados = df_redenciones.attrs.get("descartados_borde_mes", {})
    total_bajada_raw = df_redenciones["points"].sum()
    total_bajada_distribuido = df_redenciones["points_distribuidos"].sum()
    # Ver comentario equivalente en chequear_sum_points_acumulaciones: la query de
    # control tiene el mismo desfasaje de huso horario que la de bajada.
    total_control_raw = control["total_points_raw"].iloc[0] - descartados.get("points", 0)
    total_control_distribuido = (
        control["total_points_distribuidos"].iloc[0] - descartados.get("points_distribuidos", 0)
    )
    diferencia_raw = total_bajada_raw - total_control_raw
    diferencia_distribuido = total_bajada_distribuido - total_control_distribuido
    return {
        "nombre": "Redenciones - sum points",
        "ok": abs(diferencia_raw) <= TOLERANCIA and abs(diferencia_distribuido) <= TOLERANCIA,
        "total_bajada_raw": total_bajada_raw,
        "total_control_raw": total_control_raw,
        "diferencia_raw": diferencia_raw,
        "total_bajada_distribuido": total_bajada_distribuido,
        "total_control_distribuido": total_control_distribuido,
        "diferencia_distribuido": diferencia_distribuido,
    }


def chequear_sum_points_puntos_expirados(df_puntos_expirados) -> dict:
    control = _control_puntos_expirados()
    total_bajada = df_puntos_expirados["Points"].sum()
    total_control = control["total_points"].iloc[0]
    diferencia = total_bajada - total_control
    return {
        "nombre": "Puntos Expirados - sum points",
        "ok": abs(diferencia) <= TOLERANCIA,
        "total_bajada": total_bajada,
        "total_control": total_control,
        "diferencia": diferencia,
    }


def chequear_vigencia_tc(date_to: date) -> dict:
    """TC_mensual.xlsx no tiene columna de periodo - es un valor "vigente" unico por
    entidad legal que se actualiza a mano cada mes (mail de Finanzas, ver
    INSTRUCCIONES.md). Si alguien se olvida de actualizarlo, cargar_tc_mensual()
    devuelve silenciosamente el TC del mes anterior (afecta el "Reconocimiento de
    Ingresos Diferidos ML" de Redenciones Otros) - sin este chequeo no hay ningun
    error ni NaN que lo delate.

    Proxy aproximado (no hay forma de saber el periodo real desde el contenido del
    archivo): alerta si el archivo no se modifico en los ultimos TC_VIGENCIA_DIAS
    respecto al ultimo dia del mes que se esta cerrando. No reemplaza confirmar con
    Rosario/Finanzas que el TC cargado es el del mes correcto.
    """
    mtime = date.fromtimestamp(os.path.getmtime(ruta_tc_mensual()))
    antiguedad_dias = (date_to - mtime).days
    return {
        "nombre": "TC_mensual.xlsx - vigencia (chequeo aproximado)",
        "ok": antiguedad_dias <= TC_VIGENCIA_DIAS,
        "ultima_modificacion": mtime.isoformat(),
        "antiguedad_dias": antiguedad_dias,
    }


def chequear_filas_vacias(df, columnas_clave: list) -> dict:
    """Alerta si alguna columna clave tiene valores vacios inesperados."""
    conteo_vacios = {col: int(df[col].isna().sum()) for col in columnas_clave if col in df.columns}
    columnas_con_vacios = {col: n for col, n in conteo_vacios.items() if n > 0}
    return {
        "nombre": "Columnas clave sin vacios",
        "ok": len(columnas_con_vacios) == 0,
        "columnas_con_vacios": columnas_con_vacios,
    }


def resumen_final(resultados_chequeos: list) -> bool:
    """Imprime el resumen que ve Rosario al terminar de correr. Devuelve True si todo cerro."""
    print()
    print("=" * 60)
    print("RESUMEN DEL CIERRE")
    print("=" * 60)
    hay_problemas = False
    for r in resultados_chequeos:
        estado = "OK" if r["ok"] else "REVISAR"
        if not r["ok"]:
            hay_problemas = True
        print(f"[{estado}] {r['nombre']}")
        for clave, valor in r.items():
            if clave in ("nombre", "ok"):
                continue
            print(f"    {clave}: {valor}")
    print("=" * 60)
    if hay_problemas:
        print("Hay controles marcados REVISAR - no continuar sin entender por que antes de mandar a Contabilidad.")
    else:
        print("Todos los controles cierran.")
    return not hay_problemas
