"""
Conexion al Datalake (Treasure Data) via ODBC.
Confirmado funcionando 2026-07-17 con DSN "Datalake Treasure ODBC" y usuario
en formato nombre.apellido@ar.infra.d (ver test_conexion_datalake.py en la carpeta de trabajo).

TODO: mover aca la logica de conectar() + fetch() de daily_sync_grego.py, adaptada
para las 3 queries de Loyalty en vez de las de B2B2C.
"""

import os
import time
from pathlib import Path

import pyodbc
import pandas as pd
from dotenv import load_dotenv

DSN_NAME = "Datalake Treasure ODBC"

# Mismo criterio que loyalty_sync.py::conectar() (reintento con backoff ante fallas
# transitorias de VPN/red) - replicado aca en vez de importado porque esta carpeta
# es autocontenida a proposito (ver INSTRUCCIONES.md, se comparte por SharePoint sin
# el resto del repo).
_CONN_RETRIES = 4
_CONN_BACKOFF = 8  # segundos: 8, 16, 24...

# 2026-07-28 (ver Bitacora seccion 36): el .env con las credenciales PERSONALES del
# Datalake vive FUERA de esta carpeta a proposito. Esta carpeta (Automatizacion Cierre)
# esta pensada para subirse a SharePoint y compartirse - si el .env viviera adentro,
# se sincronizaria junto con todo lo demas y expondria la contraseña de quien lo haya
# creado a cualquiera con acceso a la carpeta compartida. Cada persona crea su propio
# .env en esta ruta fija de SU USUARIO de Windows (nunca sincronizada con OneDrive/
# SharePoint) - ver INSTRUCCIONES.md.
RUTA_ENV = Path.home() / ".automatizacion_cierre" / ".env"


def conectar():
    load_dotenv(dotenv_path=RUTA_ENV)
    usuario = os.getenv("DATALAKE_USER")
    contrasena = os.getenv("DATALAKE_PASSWORD")
    if not usuario or not contrasena:
        raise RuntimeError(
            f"Faltan DATALAKE_USER / DATALAKE_PASSWORD. Crea el archivo {RUTA_ENV} "
            "con tu usuario y contraseña del Datalake (ver INSTRUCCIONES.md) - NO lo "
            "pongas dentro de esta carpeta ni de ninguna carpeta sincronizada con "
            "OneDrive/SharePoint."
        )
    cadena = f"DSN={DSN_NAME};UID={usuario};PWD={contrasena};"
    last = None
    for intento in range(1, _CONN_RETRIES + 1):
        try:
            return pyodbc.connect(cadena, autocommit=True)
        except pyodbc.Error as e:
            last = e
            if intento < _CONN_RETRIES:
                espera = _CONN_BACKOFF * intento
                print(f"  ! conexion fallo (intento {intento}/{_CONN_RETRIES}): "
                      f"{str(e)[:90]} - reintento en {espera}s")
                time.sleep(espera)
    raise last


def fetch(query: str, label: str) -> pd.DataFrame:
    print(f"  > Bajando {label} ...")
    con = conectar()
    try:
        df = pd.read_sql(query, con)
    except Exception as e:
        raise RuntimeError(f"fetch('{label}') fallo: {str(e)[:200]}") from e
    finally:
        con.close()
    print(f"  OK {len(df):,} filas")
    return df
