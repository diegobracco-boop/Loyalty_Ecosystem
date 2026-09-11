"""
run_cierre_backup_manual.py
============================
Baja las 3 queries del Datalake, corre los guardrails, calcula las columnas
derivadas de Etapa 1, y pega el archivo de cierre unificado (datos del mes +
Diccionario) - ver Bitacora Automatizacion Cierre.md secciones 31, 33 y 36 para el
diseno completo. Este script NO escribe Asientos Cierre Loyalty.xlsx - eso lo hace
`escribir_asientos.py`, despues de un refresco manual de Excel (ver mas abajo y
INSTRUCCIONES.md para el flujo completo).

Precondicion: Rosario ya calculo Breakage Esperado a mano y lo pego en la solapa
"Breakage Esperado" del archivo de cierre.

Al terminar, frena con instrucciones: hay que refrescar el archivo de cierre en
Excel de verdad (openpyxl no recalcula formulas) para que Breakage Esperado se
propague a SSP Facturacion -> Cobrand/Partners -> Control de Pasivo ML, y recien
ahi correr `escribir_asientos.py`, que lee esas columnas ya recalculadas (antes
quedaban "pendientes de Etapa 2") y escribe Asientos.

Correr con:
    py run_cierre_backup_manual.py
    py run_cierre_backup_manual.py --aceptar-puntos-nuevos
    py run_cierre_backup_manual.py --aceptar-cambios-queries

Ver INSTRUCCIONES.md (en esta carpeta) para el flujo completo, paso a paso.
"""

import argparse
import os
import sys

# 2026-07-28 (ver Bitacora seccion 36): pipeline/ y pipeline_backup/ viven ahora
# adentro de esta misma carpeta (Automatizacion Cierre), no en la carpeta padre -
# alcanza con agregar esta carpeta a sys.path.
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.config import cargar_config, fechas_cierre, ruta_cierre
from pipeline import bajadas
from pipeline import diccionario_puntos
from pipeline import validacion_queries
from pipeline import etapa1_acumulaciones
from pipeline import etapa1_redenciones
from pipeline import validaciones
from pipeline_backup import escritura_cierre_manual
from pipeline_backup import estado_intermedio


def parse_args():
    parser = argparse.ArgumentParser(description="Cierre mensual Loyalty - bajar datos y armar el archivo de cierre")
    parser.add_argument("--aceptar-puntos-nuevos", action="store_true")
    parser.add_argument("--aceptar-cambios-queries", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = cargar_config()
    date_from, date_to = fechas_cierre()
    mes = cfg["cierre"]["mes"]
    anio = cfg["cierre"]["anio"]

    print("=" * 60)
    print(f"CIERRE LOYALTY - bajar datos y armar el archivo de cierre - mes {mes:02d}/{anio}")
    print(f"Rango de fechas: {date_from} a {date_to}")
    print("=" * 60)

    print("\n[0a] Verificando diccionario de tipos de punto...")
    try:
        diccionario_puntos.verificar(aceptar_nuevos=args.aceptar_puntos_nuevos)
    except diccionario_puntos.PuntosNuevosError as e:
        print(f"\nFRENADO: {e}")
        print("Volve a correr con: py run_cierre_backup_manual.py --aceptar-puntos-nuevos")
        sys.exit(1)

    print("\n[0b] Bajando Diccionario Puntos Excl (se pega en el paso [5], junto con el resto)...")
    df_diccionario_excl = escritura_cierre_manual.bajar_diccionario_excl()

    print("\n[0c] Verificando columnas y cobertura de las queries...")
    try:
        validacion_queries.verificar(date_from, date_to, aceptar_cambios=args.aceptar_cambios_queries)
    except validacion_queries.CoberturaPointTypeError as e:
        print(f"\nFRENADO: {e}")
        sys.exit(1)
    except validacion_queries.CambiosColumnasError as e:
        print(f"\nFRENADO: {e}")
        print("Volve a correr con: py run_cierre_backup_manual.py --aceptar-cambios-queries")
        sys.exit(1)

    print("\n[1] Bajando queries del Datalake...")
    df_acumulaciones = bajadas.bajar_acumulaciones(date_from, date_to)
    df_redenciones_raw = bajadas.bajar_redenciones(date_from, date_to)
    df_puntos_expirados = bajadas.bajar_puntos_expirados(date_from, date_to)

    carpeta_bajadas = ruta_cierre(cfg["rutas"]["carpeta_bajadas_auditoria"])
    sufijo_mes = f"{anio}_{mes:02d}"
    bajadas.guardar_bajada_auditoria(df_acumulaciones, f"acumulaciones_{sufijo_mes}.xlsx", carpeta_bajadas)
    bajadas.guardar_bajada_auditoria(df_redenciones_raw, f"redenciones_{sufijo_mes}.xlsx", carpeta_bajadas)
    bajadas.guardar_bajada_auditoria(df_puntos_expirados, f"puntos_expirados_{sufijo_mes}.xlsx", carpeta_bajadas)

    # Recorte defensivo del borde del mes (ver pipeline/bajadas.py::recortar_borde_mes) -
    # va DESPUES de guardar la bajada cruda en Auditoria (esa queda tal cual vino).
    df_acumulaciones = bajadas.recortar_borde_mes(
        df_acumulaciones, "processing_date", date_from, date_to, "Acumulaciones", ["points"]
    )
    df_redenciones_raw = bajadas.recortar_borde_mes(
        df_redenciones_raw, "processing_date", date_from, date_to, "Redenciones",
        ["points", "points_distribuidos"],
    )

    print("\n[2] Chequeando totales de puntos contra los controles...")
    resultados_chequeos = [
        validaciones.chequear_sum_points_acumulaciones(df_acumulaciones, date_from, date_to),
        validaciones.chequear_sum_points_redenciones(df_redenciones_raw, date_from, date_to),
        validaciones.chequear_sum_points_puntos_expirados(df_puntos_expirados),
        validaciones.chequear_vigencia_tc(date_to),
    ]

    print("\n[3] Calculando columnas derivadas - Generacion...")
    df_generacion = etapa1_acumulaciones.procesar(
        df_acumulaciones, cfg["point_types"]["acumulacion_non_tender"]
    )
    resultados_chequeos.append(
        validaciones.chequear_filas_vacias(df_generacion, ["Entidad Legal", "Producto"])
    )

    print("\n[4] Calculando columnas derivadas - Redenciones / SUBS / Otros...")
    df_redenciones = etapa1_redenciones.procesar_redenciones(
        df_redenciones_raw, cfg["point_types"]["redenciones_general"]
    )
    df_redenciones_subs = etapa1_redenciones.procesar_redenciones_subs(
        df_redenciones_raw, cfg["point_types"]["redenciones_subs"]
    )
    df_redenciones_otros = etapa1_redenciones.procesar_redenciones_otros(
        df_redenciones_raw,
        cfg["point_types"]["redenciones_general"],
        cfg["point_types"]["redenciones_subs"],
    )
    for nombre, df in [
        ("Redenciones", df_redenciones),
        ("Redenciones Subs", df_redenciones_subs),
        ("Redenciones Otros", df_redenciones_otros),
    ]:
        chequeo = validaciones.chequear_filas_vacias(df, ["Entidad Legal", "Producto"])
        chequeo["nombre"] = f"{chequeo['nombre']} ({nombre})"
        resultados_chequeos.append(chequeo)

    print("\n[gate] Evaluando controles antes de tocar el archivo de cierre...")
    todo_ok = validaciones.resumen_final(resultados_chequeos)
    if not todo_ok:
        print("\nHay controles marcados REVISAR - no continuar sin revisar antes.")
        print("(No se modifico el archivo de cierre ni el estado intermedio - nada quedo pegado.)")
        sys.exit(1)

    print("\n[5] Pegando bajadas + filtros crudos + Diccionario en el archivo de cierre...")
    resultado_pegado_manual = escritura_cierre_manual.pegar_todo_manual(
        df_acumulaciones, df_redenciones_raw, df_puntos_expirados,
        cfg["point_types"]["acumulacion_non_tender"],
        cfg["point_types"]["redenciones_general"],
        cfg["point_types"]["redenciones_subs"],
        df_diccionario_excl=df_diccionario_excl,
    )

    print("\n[6] Guardando estado intermedio de Etapa 1 (lo usa escribir_asientos.py despues)...")
    ruta_estado = estado_intermedio.guardar(
        df_generacion, df_redenciones, df_redenciones_subs, df_redenciones_otros, mes, anio
    )
    print(f"  Guardado OK: {ruta_estado}")

    print("\nFilas pegadas en el archivo de cierre:")
    for hoja, n in resultado_pegado_manual.items():
        print(f"  {hoja}: {n}")

    print("\n" + "=" * 60)
    print("PROXIMO PASO (manual):")
    print("1. Si todavia no lo hiciste, pega Breakage Esperado (calculado a mano)")
    print("   en la solapa 'Breakage Esperado' del archivo de cierre.")
    print("2. Abri el archivo de cierre en Excel, refresca con Ctrl+Alt+F9, y guardalo.")
    print("3. Corre: py escribir_asientos.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
