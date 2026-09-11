"""
Guardrail de tipos de punto (diccionario vivo).

La query de Redenciones mapea cada `code` de punto a un `point_type` via un CASE
hardcodeado. El pipeline clasifica cada redencion en 3 hojas SOLO a partir de ese
point_type (general -> Redenciones, SUBSCRIPTION/SUBSCRIPTION_INT -> Redenciones SUBS,
el resto -> Redenciones Otros). Si aparece un `code` nuevo que el CASE no contempla,
la redencion caeria en 'general' por defecto y se clasificaria mal, sin que nadie se
entere.

Para evitarlo, cada corrida del cierre baja de nuevo la tabla completa de tipos de
punto (data.lake.clm_point_types) y compara sus `code` contra el baseline del mes
anterior (referencia/diccionario_puntos.xlsx). Si hay codes nuevos, el pipeline FRENA
y los lista, para que Rosario decida el tratamiento y actualice el CASE de la query de
Redenciones antes de seguir. Una vez resuelto, se acepta el nuevo diccionario como
baseline (aceptar_baseline / flag en run_cierre) y la corrida continua.

NOTA: la columna accum_period viene mal cargada en la tabla origen - se ignora por
completo en esta logica.
"""

import os

import pandas as pd

from pipeline.conexion import fetch
from pipeline.config import cargar_config, ruta_absoluta

COLUMNA_CODE = "code"


class PuntosNuevosError(Exception):
    """Se levanta cuando aparecen codes de punto no vistos en el baseline anterior."""

    def __init__(self, codes_nuevos):
        self.codes_nuevos = codes_nuevos
        super().__init__(
            "Aparecieron tipos de punto nuevos que no estaban el mes anterior: "
            + ", ".join(codes_nuevos)
        )


def _ruta_baseline() -> str:
    cfg = cargar_config()
    return ruta_absoluta(cfg["referencia"]["diccionario_puntos"])


def _ruta_query() -> str:
    cfg = cargar_config()
    return ruta_absoluta("queries", cfg["queries"]["diccionario_puntos"])


def bajar_diccionario_puntos() -> pd.DataFrame:
    with open(_ruta_query(), encoding="utf-8") as f:
        query = f.read()
    return fetch(query, "Diccionario de puntos")


def cargar_baseline() -> pd.DataFrame | None:
    """Diccionario del mes anterior. None si todavia no existe (primera corrida)."""
    ruta = _ruta_baseline()
    if not os.path.exists(ruta):
        return None
    return pd.read_excel(ruta)


def _codes(df: pd.DataFrame) -> set:
    return set(df[COLUMNA_CODE].dropna().astype(str))


def detectar_codes_nuevos(df_actual: pd.DataFrame, df_baseline: pd.DataFrame) -> list:
    """Codes presentes en la bajada de este mes que no estaban en el baseline."""
    return sorted(_codes(df_actual) - _codes(df_baseline))


def guardar_baseline(df: pd.DataFrame) -> str:
    ruta = _ruta_baseline()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    df.to_excel(ruta, index=False)
    return ruta


def verificar(aceptar_nuevos: bool = False) -> pd.DataFrame:
    """Primer paso del cierre: baja el diccionario y lo compara contra el baseline.

    - Primera corrida (sin baseline): lo guarda y sigue.
    - Sin codes nuevos: actualiza el baseline (nombres/atributos pueden haber cambiado) y sigue.
    - Con codes nuevos y aceptar_nuevos=False: FRENA con PuntosNuevosError.
    - Con codes nuevos y aceptar_nuevos=True: guarda el nuevo baseline y sigue
      (se usa despues de que Rosario ya corrigio el CASE de la query de Redenciones).

    Devuelve el DataFrame del diccionario bajado.
    """
    df_actual = bajar_diccionario_puntos()
    baseline = cargar_baseline()

    if baseline is None:
        guardar_baseline(df_actual)
        print("  Diccionario de puntos: baseline inicial creado "
              f"({len(_codes(df_actual))} codes).")
        return df_actual

    nuevos = detectar_codes_nuevos(df_actual, baseline)
    if nuevos and not aceptar_nuevos:
        raise PuntosNuevosError(nuevos)

    guardar_baseline(df_actual)
    if nuevos:
        print(f"  Diccionario de puntos: {len(nuevos)} code(s) nuevo(s) ACEPTADO(s) "
              f"y guardado(s) en baseline: {', '.join(nuevos)}")
    else:
        print(f"  Diccionario de puntos: sin codes nuevos ({len(_codes(df_actual))} codes).")
    return df_actual
