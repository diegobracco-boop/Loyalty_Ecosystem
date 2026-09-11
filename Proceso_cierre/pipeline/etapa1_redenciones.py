"""
Etapa 1 - "Redenciones" / "Redenciones SUBS" / "Redenciones Otros": filtra Query
Redenciones por point_type y calcula las columnas derivadas que se pegan en
Asientos!Redenciones / Redenciones Subs / Redenciones Otros.

CAMBIO DE QUERY (2026-07-22, confirmado por Rosario): la query de Redenciones se
reescribio para traer menos filas (se agrego un GROUP BY final que agrega a un grano
mas grueso, sin dsp_transaction_id/transaction_code como clave) y menos columnas. Se
eliminaron del todo estos campos crudos (ya no existen en la query): `dsp_transaction_id`,
`gb_total_carrito`, `peso_producto`, `transaction_code`, `transaction_type`, `ratio_prd`.

El bloque raw ahora es de 18 campos (antes 24), mismo orden que la query real:
processing_date, product, country_code, partner, points, point_type,
points_distribuidos, business, country, produto_original, channel_condition,
payment_type, produto_agrupado, comision, fee, descuentos, gb_basebi, gb_basebi_2.

Ademas, la query ahora trae `legal_entity` (pegado a valor, columna nueva) INMEDIATAMENTE
despues de `descuento_consumo_puntos_usd` en su propio orden de columnas - Rosario ya
aplico este mismo reordenamiento en las 3 hojas de 'Cierre 2026 06.xlsx' (el archivo de
formulas/referencia que duplica cada mes). `legal_entity` REEMPLAZA el calculo de
"Entidad Legal" que antes se hacia con VLOOKUP en Python (ver seccion de abajo) - ahora
es un pass-through directo, igual que ya pasaba con "Descuento por Consumo de Puntos".

NOTA IMPORTANTE (pendiente de resolver con Rosario, ver Bitacora): `Asientos Cierre
Loyalty.xlsx` (el archivo DESTINO real, no la referencia) todavia NO fue restructurado -
sigue con el header viejo, con columnas para los 6 campos eliminados (dsp_transaction_id,
gb_total_carrito, peso_producto, transaction_code, transaction_type, ratio_prd) y con
"Entidad Legal" en su posicion vieja (despues de "Reconocimiento de Ingresos Diferidos
ML"/"Concat Entidad Legal", no al lado del descuento). Este modulo (etapa1_redenciones.py)
ya calcula todo con la logica NUEVA (Entidad Legal = pass-through desde `legal_entity`);
el mapeo hacia el header VIEJO de Asientos se resuelve en escritura_asientos.py (que
sigue mapeando por nombre de columna, no por posicion - las 6 columnas sin dato quedan
vacias en Asientos hasta que se decida si se restructura ese archivo tambien).

- Descuento por Consumo de Puntos: pass-through de `descuento_consumo_puntos_usd`
  (decision de Rosario 2026-07-16, ver Bitacora seccion 4 decision 6) - NO se recalcula.

- Entidad Legal: pass-through de `legal_entity` (decision de Rosario 2026-07-22) - YA NO
  se calcula con VLOOKUP en Python. Reemplaza la logica vieja unificada (2026-07-16, ver
  Bitacora seccion 4 decision 2) que hacia VLOOKUP(country_code & product & business,
  'Regla entidad Legal') en las 3 hojas por igual.

- Concat Entidad Legal: igual que antes, country_code & Entidad Legal (ahora con el
  Entidad Legal ya pass-through, pero la formula de concatenacion no cambia).

- Producto: SIN CAMBIOS, sigue siendo VLOOKUP(produto_agrupado, 'Regla entidad Legal'!
  producto, 2) - la query no toco esta columna.

- Reconocimiento de Ingresos Diferidos ML:
    - Redenciones y Redenciones SUBS: depende del "Precio Redencion" de
      'Control de Pasivo ML' (Etapa 2, ver Pendientes Etapa 2.md) - queda vacio en
      Etapa 1 (config.yaml -> columnas_pendientes_etapa_2).
    - Redenciones Otros: NO depende de Etapa 2, se calcula completo en Etapa 1:
        = Descuento por Consumo de Puntos * VLOOKUP(Concat Entidad Legal, TC_mensual, 2)

- Reconocimiento de Ingresos Diferidos USD (solo Redenciones Otros):
    = Descuento por Consumo de Puntos (mismo valor, sin transformar)

"Reduccion del pasivo" / "DRI" (solo Redenciones y Redenciones SUBS) NO se pegan en
Asientos y ademas dependen de Reconocimiento ML (Etapa 2) - no se calculan en este modulo.

CLASIFICACION EN 3 HOJAS (2026-07-21, logica confirmada por Rosario): se hace 100% a
partir del `point_type` que ya sale MAPEADO de la query de Redenciones (su CASE traduce
cada `code` crudo al point_type). No se usa mas el viejo diccionario_point_types.xlsx.
    - general                        -> Redenciones
    - SUBSCRIPTION / SUBSCRIPTION_INT -> Redenciones SUBS
    - todo el resto (complemento)     -> Redenciones Otros
El guardrail de pipeline/diccionario_puntos.py frena el cierre si aparece un `code`
nuevo que el CASE todavia no contemple, para que se revise antes de seguir.
"""

from pipeline.referencias import cargar_producto, cargar_tc_mensual

CAMPOS_RAW = [
    "processing_date", "product", "country_code", "partner", "points", "point_type",
    "points_distribuidos", "business", "country", "produto_original",
    "channel_condition", "payment_type", "produto_agrupado", "comision", "fee",
    "descuentos", "gb_basebi", "gb_basebi_2",
]

# No forman parte del bloque de campos raw de arriba, pero se usan directo (sin
# recalcular) - ambos son pass-through de la query, no se tocan en Python.
CAMPO_DESCUENTO_CONSUMO_PUNTOS = "descuento_consumo_puntos_usd"
CAMPO_ENTIDAD_LEGAL = "legal_entity"


def filtrar_redenciones_general(df_query_redenciones, point_types):
    return df_query_redenciones[df_query_redenciones["point_type"].isin(point_types)].copy()


def filtrar_redenciones_subs(df_query_redenciones, point_types):
    return df_query_redenciones[df_query_redenciones["point_type"].isin(point_types)].copy()


def filtrar_redenciones_otros(df_query_redenciones, point_types_general, point_types_subs):
    """Complemento: todo point_type que NO sea general ni subs."""
    excluidos = set(point_types_general) | set(point_types_subs)
    return df_query_redenciones[~df_query_redenciones["point_type"].isin(excluidos)].copy()


def _concat_entidad_legal(df):
    # Concatenacion elemento a elemento vía pandas: si Entidad Legal es NaN, el
    # resultado tambien queda NaN (no se convierte a texto "nan").
    return df["country_code"] + df["Entidad Legal"]


def _producto(df, tabla_producto):
    return df["produto_agrupado"].map(tabla_producto)


def calcular_columnas_comunes(df):
    """Descuento, Entidad Legal, Concat Entidad Legal y Producto - igual en las 3 hojas."""
    df = df.copy()
    tabla_producto = cargar_producto()

    df["Descuento por Consumo de Puntos"] = df[CAMPO_DESCUENTO_CONSUMO_PUNTOS]
    df["Entidad Legal"] = df[CAMPO_ENTIDAD_LEGAL]
    df["Concat Entidad Legal"] = _concat_entidad_legal(df)
    df["Producto"] = _producto(df, tabla_producto)
    return df


def calcular_columnas_derivadas_redenciones(df):
    """Redenciones / Redenciones SUBS: Reconocimiento ML queda vacio (Etapa 2)."""
    df = calcular_columnas_comunes(df)
    df["Reconocimiento de Ingresos Diferidos ML"] = None
    return df


def calcular_columnas_derivadas_otros(df):
    """Redenciones Otros: Reconocimiento ML se calcula completo en Etapa 1."""
    df = calcular_columnas_comunes(df)
    tabla_tc = cargar_tc_mensual()
    tc = df["Concat Entidad Legal"].map(tabla_tc)
    df["Reconocimiento de Ingresos Diferidos ML"] = df["Descuento por Consumo de Puntos"] * tc
    df["Reconocimiento de Ingresos Diferidos USD"] = df["Descuento por Consumo de Puntos"]
    return df


def procesar_redenciones(df_query_redenciones, point_types):
    df = filtrar_redenciones_general(df_query_redenciones, point_types)
    return calcular_columnas_derivadas_redenciones(df)


def procesar_redenciones_subs(df_query_redenciones, point_types):
    df = filtrar_redenciones_subs(df_query_redenciones, point_types)
    return calcular_columnas_derivadas_redenciones(df)


def procesar_redenciones_otros(df_query_redenciones, point_types_general, point_types_subs):
    df = filtrar_redenciones_otros(df_query_redenciones, point_types_general, point_types_subs)
    return calcular_columnas_derivadas_otros(df)
