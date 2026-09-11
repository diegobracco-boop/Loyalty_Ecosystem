"""
escribir_asientos.py
=====================
Completa y escribe Asientos Cierre Loyalty.xlsx - ver Bitacora Automatizacion
Cierre.md secciones 31, 33 y 36 para el diseno completo, e INSTRUCCIONES.md (en
esta carpeta) para el flujo de trabajo completo paso a paso.

Precondiciones (en este orden):
1. Breakage Esperado calculado a mano y pegado en el archivo de cierre.
2. `run_cierre_backup_manual.py` ya corrio y pego el archivo de cierre.
3. El archivo de cierre se abrio en Excel de verdad y se refresco (Ctrl+Alt+F9) y
   guardo - para que Breakage Esperado se propague por SSP Facturacion ->
   Cobrand/Partners -> Control de Pasivo ML. Sin este paso las columnas de Etapa 2
   tendrian valores VIEJOS cacheados (openpyxl no recalcula formulas), no los del
   mes actual.

Este script:
- Recupera de pipeline_backup.estado_intermedio los DataFrames de Etapa 1
  (Generacion, Redenciones, Redenciones SUBS, Redenciones Otros) que guardo
  `run_cierre_backup_manual.py` - no vuelve a bajar ni filtrar nada, evita
  cualquier riesgo de desalineacion de filas.
- Lee del archivo de cierre, ya recalculado, las columnas que antes quedaban
  "pendientes de Etapa 2": Puntos Valuados / DRO / DRO - up fronts /
  DRO -Fee + Descuentos (Generacion) y Reconocimiento de Ingresos Diferidos ML
  (Redenciones / Redenciones SUBS).
- Lee Breakage por pais/Entidad Legal (columnas K:R de 'Breakage' en el archivo de
  cierre, bloque 100% formula - ver Bitacora seccion 44) y la solapa Accounting
  (tambien ya recalculada).
- Pega todo en Asientos Cierre Loyalty.xlsx (Breakage columnas A:H y Accounting a
  valor, este ultimo reemplazando el vinculo externo vivo que tenia antes).

Correr con:
    py escribir_asientos.py
    py escribir_asientos.py --sin-reconciliacion   (salta el chequeo [1b] - ver mas abajo)
"""

import argparse
import os
import sys

# 2026-07-28 (ver Bitacora seccion 36): pipeline/ y pipeline_backup/ viven adentro
# de esta misma carpeta (Automatizacion Cierre).
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.config import cargar_config
from pipeline import escritura_asientos
from pipeline_backup import estado_intermedio
from pipeline_backup import lectura_etapa2
from pipeline_backup import reconciliacion_cierre


def parse_args():
    parser = argparse.ArgumentParser(description="Completa y escribe Asientos Cierre Loyalty.xlsx")
    parser.add_argument(
        "--sin-reconciliacion", action="store_true",
        help="Salta el chequeo [1b] (Acumulacion Non Tender / Redenciones / SUBS / Otros vs. "
             "lo guardado de la corrida) - el chequeo pide confirmacion por consola (input()), "
             "que no funciona si no se corre en una terminal interactiva de verdad. Usar cuando "
             "ya se reviso a mano que el archivo de cierre esta OK.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = cargar_config()
    mes = cfg["cierre"]["mes"]
    anio = cfg["cierre"]["anio"]

    print("=" * 60)
    print(f"CIERRE LOYALTY - completar y escribir Asientos - mes {mes:02d}/{anio}")
    print("=" * 60)

    print("\n[1] Cargando estado de Etapa 1 (Generacion / Redenciones / SUBS / Otros)...")
    df_generacion, df_redenciones, df_redenciones_subs, df_redenciones_otros = estado_intermedio.cargar(mes, anio)

    if args.sin_reconciliacion:
        print("\n[1b] SALTEADO (--sin-reconciliacion) - no se comparo contra lo que hay ahora")
        print("     en Acumulacion Non Tender / Redenciones / SUBS / Otros.")
    else:
        print("\n[1b] Chequeando que Acumulacion Non Tender / Redenciones / Redenciones SUBS / ")
        print("     Redenciones Otros no se hayan editado a mano desde la corrida guardada...")
        df_generacion = reconciliacion_cierre.reconciliar("Acumulacion Non Tender", df_generacion)
        df_redenciones = reconciliacion_cierre.reconciliar("Redenciones", df_redenciones)
        df_redenciones_subs = reconciliacion_cierre.reconciliar("Redenciones SUBS", df_redenciones_subs)
        df_redenciones_otros = reconciliacion_cierre.reconciliar("Redenciones Otros", df_redenciones_otros)
        reconciliacion_cierre.cerrar()

    print("\n[2] Leyendo columnas de Etapa 2 ya recalculadas del archivo de cierre...")
    df_cols_generacion = lectura_etapa2.leer_columnas_generacion()
    if len(df_cols_generacion) != len(df_generacion):
        raise ValueError(
            f"Generacion tiene {len(df_generacion)} filas pero 'Acumulacion Non Tender' "
            f"del archivo de cierre tiene {len(df_cols_generacion)} - no coinciden. "
            "Revisar antes de seguir (¿se corrio run_cierre_backup_manual.py de nuevo "
            "sin volver a correr este script, o el archivo de cierre no se refresco?)."
        )
    for columna in lectura_etapa2.COLUMNAS_ACUMULACION_NON_TENDER:
        df_generacion[columna] = df_cols_generacion[columna].values
        print(f"  Generacion.{columna}: completada ({df_cols_generacion[columna].notna().sum()} valores no vacios)")

    for nombre_hoja, df in [("Redenciones", df_redenciones), ("Redenciones SUBS", df_redenciones_subs)]:
        ml = lectura_etapa2.leer_reconocimiento_ml(nombre_hoja)
        if len(ml) != len(df):
            raise ValueError(
                f"{nombre_hoja} tiene {len(df)} filas pero la hoja homonima del archivo "
                f"de cierre tiene {len(ml)} - no coinciden. Revisar antes de seguir."
            )
        df[lectura_etapa2.COLUMNA_RECONOCIMIENTO_ML] = ml.values
        print(f"  {nombre_hoja}.{lectura_etapa2.COLUMNA_RECONOCIMIENTO_ML}: completada ({ml.notna().sum()} valores no vacios)")

    print("\n[3] Leyendo Accounting (ya recalculado)...")
    valores_accounting = lectura_etapa2.leer_accounting()
    print(f"  {len(valores_accounting)} filas leidas.")

    print("\n[3b] Leyendo Breakage por pais/Entidad Legal (columnas K:R, ya recalculado)...")
    df_breakage = lectura_etapa2.leer_breakage_pais_el()
    print(f"  {len(df_breakage)} filas leidas.")

    print("\n[4] Pegando en Asientos Cierre Loyalty.xlsx (incluye Breakage y Accounting a valor)...")
    resultado_pegado = escritura_asientos.pegar_todo(
        df_generacion, df_redenciones, df_redenciones_subs, df_redenciones_otros,
        valores_accounting=valores_accounting, df_breakage=df_breakage,
    )

    print("\nFilas pegadas en Asientos Cierre Loyalty.xlsx:")
    for hoja, n in resultado_pegado.items():
        print(f"  {hoja}: {n}")

    print("\nListo. El cierre queda completo (ya no hace falta una Etapa 2 aparte).")


if __name__ == "__main__":
    main()
