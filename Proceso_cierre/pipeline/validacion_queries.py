"""
Validacion de queries (guardrail de esquema) - paso anterior a la corrida del cierre.

Las queries de Metabase pueden cambiar mes a mes (Rosario las edita directo en
Metabase/el archivo .sql). El pipeline mapea columnas por NOMBRE, no por posicion,
asi que un cambio de columnas (agregar/sacar/renombrar) puede romper silenciosamente
`pipeline/bajadas.py`, `pipeline/etapa1_acumulaciones.py` o `pipeline/etapa1_redenciones.py`
si nadie se entera. Este modulo corre 2 chequeos ANTES de bajar los datos reales:

1. **Columnas de las 3 queries de Data** (Acumulaciones, Redenciones, Puntos Expirados):
   se pide el esquema de salida con un `LIMIT 0` (rapido, sin traer filas) y se compara
   contra el baseline del mes anterior (`referencia/columnas_queries.json`). Si hay
   columnas agregadas o eliminadas, FRENA y las lista - hay que revisar si el codigo de
   Etapa 1 necesita ajustarse antes de seguir. Los REORDENAMIENTOS de columnas no frenan
   (el codigo ya mapea por nombre, no por posicion - ver Bitacora seccion 3.3).

2. **Cobertura del CASE de point_type en la query de Redenciones**: chequeo ESTATICO
   (por texto, sin conexion a datos) que confirma que todo codigo de la lista de "no
   reembolsables / campaña" (el IN(...) de la rama de cancelaciones dentro del CTE
   tipopunto) este tambien mapeado explicitamente en el CASE final que arma point_type.
   Si un codigo esta en esa lista pero NO en el CASE, cae silenciosamente en 'general'
   y termina mal clasificado (asi se detecto el bug real de 2026-07-21, resuelto por
   Rosario agregando IFOOD_RWB/IF_MISSION/IF_CAMPAI/IFOOD_WELCOME/IFOOD_PROMO/MISSIONS
   al CASE - ver Bitacora seccion 11/12).

Uso: verificar(date_from, date_to, aceptar_cambios=False) como primer paso de
run_cierre.py, antes de pipeline.bajadas.
"""

import json
import os
import re

from pipeline.bajadas import (
    build_acumulaciones_query,
    build_redenciones_query,
    build_puntos_expirados_query,
)
from pipeline.conexion import fetch
from pipeline.config import cargar_config, ruta_absoluta


class CambiosColumnasError(Exception):
    """Se levanta cuando alguna query de Data agrego o elimino columnas vs el mes anterior."""

    def __init__(self, cambios: dict):
        self.cambios = cambios
        detalle = "; ".join(
            f"{query}: agregadas={c['agregadas']}, eliminadas={c['eliminadas']}"
            for query, c in cambios.items()
        )
        super().__init__(f"Cambios de columnas detectados en queries de Data: {detalle}")


class CoberturaPointTypeError(Exception):
    """Se levanta cuando la query de Redenciones tiene codigos 'no reembolsables' sin
    mapear en el CASE de point_type - caerian silenciosamente en 'general'."""

    def __init__(self, codigos_faltantes: list):
        self.codigos_faltantes = codigos_faltantes
        super().__init__(
            "La query de Redenciones tiene codigo(s) de punto en la lista de "
            "'no reembolsables/campaña' que NO estan mapeados en el CASE de point_type "
            "(caerian en 'general' sin que nadie se entere): " + ", ".join(codigos_faltantes)
        )


def _ruta_baseline_columnas() -> str:
    cfg = cargar_config()
    return ruta_absoluta(cfg["referencia"]["columnas_queries"])


def _obtener_columnas(query_sql: str, label: str) -> list:
    """Pide el esquema de salida de una query con LIMIT 0 - no trae filas, solo columnas."""
    envuelta = f"SELECT * FROM (\n{query_sql}\n) AS _validacion_columnas LIMIT 0"
    df = fetch(envuelta, f"{label} (validacion de columnas)")
    return list(df.columns)


def obtener_columnas_actuales(date_from, date_to) -> dict:
    return {
        "acumulaciones": _obtener_columnas(build_acumulaciones_query(date_from, date_to), "Acumulaciones"),
        "redenciones": _obtener_columnas(build_redenciones_query(date_from, date_to), "Redenciones"),
        "puntos_expirados": _obtener_columnas(build_puntos_expirados_query(), "Puntos Expirados"),
    }


def cargar_baseline_columnas():
    ruta = _ruta_baseline_columnas()
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_baseline_columnas(columnas: dict) -> str:
    ruta = _ruta_baseline_columnas()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(columnas, f, ensure_ascii=False, indent=2)
    return ruta


def detectar_cambios_columnas(actuales: dict, baseline: dict) -> dict:
    """Compara por CONJUNTO de nombres (no por orden) - reordenar columnas no es un
    cambio real porque el codigo ya mapea por nombre."""
    cambios = {}
    for query, cols_actuales in actuales.items():
        cols_baseline = set(baseline.get(query, []))
        agregadas = sorted(set(cols_actuales) - cols_baseline)
        eliminadas = sorted(cols_baseline - set(cols_actuales))
        if agregadas or eliminadas:
            cambios[query] = {"agregadas": agregadas, "eliminadas": eliminadas}
    return cambios


# --- Chequeo estatico: cobertura del CASE de point_type en Redenciones ---

def _extraer_lista_no_reembolsables(sql_text: str) -> set:
    """Codigos dentro del IN(...) de la rama de cancelaciones no-reembolsables
    (CTE tipopunto, subquery con `t.transaction_type = 'GR' AND pt.code IN (...)`)."""
    match = re.search(
        r"AND\s+t\.transaction_type\s*=\s*'GR'\s+AND\s+pt\.code\s+IN\s*\(([^)]+)\)",
        sql_text,
        re.IGNORECASE,
    )
    if not match:
        return set()
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _extraer_lista_mapeada_case(sql_text: str) -> set:
    """Codigos con `WHEN cc.point_code = 'X' THEN ...` en el CASE final de point_type."""
    return set(re.findall(r"WHEN\s+cc\.point_code\s*=\s*'([^']+)'", sql_text, re.IGNORECASE))


def chequear_cobertura_point_type(ruta_sql_redenciones: str = None) -> list:
    """Devuelve los codigos de la lista 'no reembolsable' que NO estan en el CASE."""
    if ruta_sql_redenciones is None:
        cfg = cargar_config()
        ruta_sql_redenciones = ruta_absoluta("queries", cfg["queries"]["data"]["redenciones"])
    with open(ruta_sql_redenciones, encoding="utf-8") as f:
        sql_text = f.read()
    no_reembolsables = _extraer_lista_no_reembolsables(sql_text)
    mapeados = _extraer_lista_mapeada_case(sql_text)
    return sorted(no_reembolsables - mapeados)


def verificar(date_from, date_to, aceptar_cambios: bool = False):
    """Primer paso del cierre. Frena con CoberturaPointTypeError o CambiosColumnasError
    si encuentra algo que revisar; aceptar_cambios=True acepta el nuevo baseline de
    columnas y sigue (igual mecanismo que pipeline.diccionario_puntos.verificar)."""
    faltantes = chequear_cobertura_point_type()
    if faltantes:
        raise CoberturaPointTypeError(faltantes)
    print("  Validacion de queries: cobertura del CASE de point_type (Redenciones) OK.")

    actuales = obtener_columnas_actuales(date_from, date_to)
    baseline = cargar_baseline_columnas()

    if baseline is None:
        guardar_baseline_columnas(actuales)
        print("  Validacion de queries: baseline de columnas creado.")
        return

    cambios = detectar_cambios_columnas(actuales, baseline)
    if cambios and not aceptar_cambios:
        raise CambiosColumnasError(cambios)

    guardar_baseline_columnas(actuales)
    if cambios:
        print(f"  Validacion de queries: cambios de columnas ACEPTADOS y guardados: {cambios}")
    else:
        print("  Validacion de queries: sin cambios de columnas.")
