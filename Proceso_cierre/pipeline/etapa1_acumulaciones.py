"""
Etapa 1 - "Acumulacion Non Tender": filtra Query Acumulaciones por point_type y partner
(= "DP", ver Bitacora seccion 38) y calcula las columnas derivadas que se pegan en
Asientos!Generacion (rango A-AB del layout real de 'Acumulacion Non Tender' - ver
Bitacora Automatizacion Cierre.md seccion 3.1 y 4).

Formulas verificadas celda a celda en 'Cierre 2026 06.xlsx'!Acumulacion Non Tender (fila 3):

- Revenue (T)
    =SUM(comision:descuentos) * (1 - pct_pagado_con_puntos)

- Producto (AA)
    =IFERROR(
        IF(OR(product="CFAR", product="FLIGHT"), "Vuelos",
           VLOOKUP(produto, 'Regla entidad Legal'!F:G, 2, 0)),   -- tabla "producto"
        VLOOKUP(product, 'Regla entidad Legal'!J:K, 2, FALSE)    -- tabla "producto_fallback"
    )

- Filtro P&L (Y)
    =CONCAT(country_code, product, business)

- Entidad Legal (Z)
    =IFERROR(
        VLOOKUP(Filtro P&L, 'Regla entidad Legal'!A:B, 2, FALSE),         -- tabla "entidad_legal"
        VLOOKUP(country_code & Producto & business, 'Regla entidad Legal'!A:B, 2, FALSE)
    )
    OJO: el fallback usa la columna "Producto" (AA) ya calculada, no el "product" (G) crudo -
    por eso Producto se calcula antes que Entidad Legal.

- Points ABS (AB)
    =ABS(points)

Puntos Valuados / DRO / DRO - up fronts / DRO - Fee + Descuentos (U-X) dependen de
"SSP Facturacion" (Etapa 2, ver Pendientes Etapa 2.md) - quedan fuera de este modulo,
se pegan vacias en Asientos segun config.yaml -> columnas_pendientes_etapa_2.

Producto homologado / Pts > 0 / GB pts > 0 (AC-AE) no se pegan en Asientos (quedan
fuera del rango A-AB) - no se calculan aca.
"""

from pipeline.referencias import cargar_entidad_legal, cargar_producto, cargar_producto_fallback


def filtrar_acumulacion_non_tender(df_query_acumulaciones, point_types):
    """Filtra Query Acumulaciones por los point_types de 'Acumulacion Non Tender'
    (config.yaml -> point_types.acumulacion_non_tender) Y por partner = "DP"
    (2026-07-29, pedido de Rosario - ver Bitacora seccion 38)."""
    filtro = df_query_acumulaciones["point_type"].isin(point_types) & (df_query_acumulaciones["partner"] == "DP")
    return df_query_acumulaciones[filtro].copy()


def calcular_columnas_derivadas(df):
    """Agrega Revenue, Producto, Filtro P&L, Entidad Legal y Points ABS a un DataFrame
    ya filtrado por filtrar_acumulacion_non_tender()."""
    df = df.copy()

    tabla_entidad_legal = cargar_entidad_legal()
    tabla_producto = cargar_producto()
    tabla_producto_fallback = cargar_producto_fallback()

    df["Revenue"] = (df["comision"] + df["fee"] + df["descuentos"]) * (1 - df["pct_pagado_con_puntos"])

    # Producto: "Vuelos" fijo para CFAR/FLIGHT, si no VLOOKUP por produto con fallback por product.
    producto = df["produto"].map(tabla_producto)
    es_vuelos = df["product"].isin(["CFAR", "FLIGHT"])
    producto = producto.where(~es_vuelos, "Vuelos")
    faltantes = producto.isna() & ~es_vuelos
    producto = producto.where(~faltantes, df["product"].map(tabla_producto_fallback))
    df["Producto"] = producto

    df["Filtro P&L"] = df["country_code"] + df["product"] + df["business"]

    # Entidad Legal: VLOOKUP por Filtro P&L, con fallback por country_code+Producto+business.
    entidad_legal = df["Filtro P&L"].map(tabla_entidad_legal)
    clave_fallback = df["country_code"] + df["Producto"].astype(str) + df["business"]
    faltantes = entidad_legal.isna()
    entidad_legal = entidad_legal.where(~faltantes, clave_fallback.map(tabla_entidad_legal))
    df["Entidad Legal"] = entidad_legal

    df["Points ABS"] = df["points"].abs()

    return df


def procesar(df_query_acumulaciones, point_types):
    """Filtra + calcula columnas derivadas - listo para pegar en Asientos!Generacion."""
    df = filtrar_acumulacion_non_tender(df_query_acumulaciones, point_types)
    return calcular_columnas_derivadas(df)
