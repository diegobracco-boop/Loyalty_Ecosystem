"""
Persiste, entre las 2 corridas del cierre separadas por el refresco manual de Excel
(ver Bitacora seccion 31), los DataFrames de Etapa 1 ya calculados (Generacion,
Redenciones, Redenciones SUBS, Redenciones Otros).

run_cierre_backup_manual.py los guarda aca justo despues de calcularlos (antes de
pegar el archivo de cierre). escribir_asientos.py los recupera de aca en vez de
volver a bajar/filtrar los datos - evita cualquier riesgo de desalineacion de filas
si algo cambiara entre las 2 corridas (nueva bajada con otro orden, etc.).
"""

import pandas as pd

from pipeline.config import cargar_config, ruta_cierre


def _ruta() -> str:
    cfg = cargar_config()
    return ruta_cierre(cfg["rutas"]["estado_intermedio"])


def guardar(df_generacion, df_redenciones, df_redenciones_subs, df_redenciones_otros,
            mes: int, anio: int) -> str:
    ruta = _ruta()
    estado = {
        "mes": mes,
        "anio": anio,
        "generacion": df_generacion,
        "redenciones": df_redenciones,
        "redenciones_subs": df_redenciones_subs,
        "redenciones_otros": df_redenciones_otros,
    }
    pd.to_pickle(estado, ruta)
    return ruta


def cargar(mes: int, anio: int):
    """Devuelve (df_generacion, df_redenciones, df_redenciones_subs, df_redenciones_otros).

    Frena si el estado guardado es de otro mes - para no mezclar por accidente el
    estado de una corrida vieja con el cierre del mes actual."""
    ruta = _ruta()
    estado = pd.read_pickle(ruta)
    if estado["mes"] != mes or estado["anio"] != anio:
        raise ValueError(
            f"El estado intermedio guardado es de {estado['mes']:02d}/{estado['anio']} "
            f"pero config.yaml (cierre.mes/cierre.anio) dice {mes:02d}/{anio}. "
            "Corre de nuevo run_cierre_backup_manual.py para este mes antes de "
            "correr escribir_asientos.py."
        )
    return (
        estado["generacion"],
        estado["redenciones"],
        estado["redenciones_subs"],
        estado["redenciones_otros"],
    )
