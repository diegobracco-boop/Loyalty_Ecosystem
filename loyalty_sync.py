# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import json
import warnings
from datetime import date, timedelta, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Solo el ruido conocido de terceros (openpyxl "no default style", pd.read_sql con
# conexión DBAPI2). FutureWarning / DeprecationWarning quedan visibles a propósito:
# así un cambio de API de pandas se ve en el log antes de romper la corrida.
warnings.filterwarnings("ignore", category=UserWarning)

# ==============================================================================
# 1) CONFIGURACIÓN
# ==============================================================================

DSN_NAME = "DataLake Treasure ODBC"

# Credenciales del datalake por usuario de Windows (envs\.env.<usuario>), con
# fallback al genérico envs\.env. Ver SETUP.md A.1.
_ENVS_DIR  = Path(__file__).resolve().parent.parent / "envs"
_WIN_USER  = os.environ.get("USERNAME", "").lower()
RUTA_ENV   = _ENVS_DIR / f".env.{_WIN_USER}"
if not RUTA_ENV.exists():
    RUTA_ENV = _ENVS_DIR / ".env"

DRIVE_FOLDER_ID = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"
BREAKAGE_FILE   = "loyalty_breakage.json"
DICT_FILE       = "loyalty_dict.json"
SSP_FILE        = "loyalty_ssp.json"
MIEMBROS_FILE       = "loyalty_miembros.json"
CLUB_DESPEGAR_FILE  = "loyalty_club_despegar.json"
IFOOD_ENROLL_FILE   = "loyalty_ifood_enroll.json"
RATIO_ACUM_FILE     = "loyalty_ratio_acumulacion.json"
# Fallbacks locales de la planilla de config: viven al lado de este script en todo
# clon (ambos trackeados en git), asi que se resuelven relativos a el — antes eran la
# ruta absoluta de una maquina y rompian el --dry-run del resto (no lee la planilla).
_SCRIPT_DIR      = Path(__file__).resolve().parent
DICT_XLSX        = str(_SCRIPT_DIR / "Diccionario.xlsx")
BREAKAGE_ESP_CSV = str(_SCRIPT_DIR / "breakage_esperado.csv")
REGLA_PRODUCTO_CSV = str(_SCRIPT_DIR / "regla_producto.csv")

# Precios de facturación de Cobrand/Partners + FX mensual por moneda.
# Fuente: Input_Precios.xlsx (lo mantiene Control de Gestión en OneDrive). Solapas:
# `Cobrand` / `Partners` (fecha_inicio, fecha_fin, pais, cobrand|partner, point_type,
# moneda, precio_facturacion) y `FX_Currency` (Pais, Moneda, Fecha, FX_Cuerrency).
# Se prueba: env PRECIOS_XLSX → ruta OneDrive → copia local en el repo (fallback).
# Si no se encuentra ninguno, `acum_usd_precio` sale 0 (sin romper la corrida).
PRECIOS_XLSX_CANDIDATES = [
    os.environ.get("PRECIOS_XLSX", ""),
    str(Path.home() / "OneDrive - despegar365" / "Control de Gestión - Loyalty"
        / "Loyalty_Ecosystem" / "Input_Precios.xlsx"),
    str(_SCRIPT_DIR / "Input_Precios.xlsx"),
]

# Planilla "Loyalty Ecosystem - Config" (folder Drive de loyalty). Pestañas que
# editan los analistas sin tocar el repo: `breakage_esperado`, `diccionario`,
# `regla producto` (agregado 09-sep: mapeo produto_agrupado/product → grupo P&L,
# mismo criterio que usa Control de Gestión — insumo del ratio de acumulación).
# Si no se puede leer, el sync cae a los archivos locales (breakage_esperado.csv /
# Diccionario.xlsx / regla_producto.csv). Ver SETUP.md sección B.
CONFIG_SHEET_ID = "1M48FXIAFvyKpP9RSLLSuWh9DgetFPovYfWAM3lQNASI"

# --dry-run / --no-upload: corre queries y arma los JSON en ./_out/ SIN subir a
# Drive ni leer la planilla de config (usa breakage_esperado.csv / Diccionario.xlsx /
# regla_producto.csv). Para validar cambios de query sin credenciales de Drive.
DRY_RUN = ("--dry-run" in sys.argv) or ("--no-upload" in sys.argv)

TODAY        = date.today()
YESTERDAY    = TODAY - timedelta(days=1)
CY_YEAR      = TODAY.year
LY_YEAR      = TODAY.year - 1
ACTUALS_FROM = date(CY_YEAR, 1, 1)
LY_FROM      = date(LY_YEAR, 1, 1)
# Anio fiscal Abr->Mar: para poder armar el fiscal year anterior completo
# (Abr LY_YEAR -> Mar CY_YEAR) el dashboard necesita el calendario LY_YEAR
# completo (Ene-Dic), no solo hasta la fecha equivalente a "ayer".
LY_TO        = date(LY_YEAR, 12, 31)

# Las queries usan < {{Hasta}} (exclusivo) — HASTA = hoy para incluir hasta ayer
ACTUALS_DESDE = str(ACTUALS_FROM)
ACTUALS_HASTA = str(TODAY)
LY_DESDE      = str(LY_FROM)
LY_HASTA      = str(LY_TO + timedelta(days=1))

ACUM_CY_FILE   = f"loyalty_acumulaciones_{CY_YEAR}.json"
ACUM_LY_FILE   = f"loyalty_acumulaciones_{LY_YEAR}.json"
REDEN_CY_FILE  = f"loyalty_redenciones_{CY_YEAR}.json"
REDEN_LY_FILE  = f"loyalty_redenciones_{LY_YEAR}.json"

print(f"[{TODAY}]  Actuals: {ACTUALS_FROM} -> {YESTERDAY}  |  LY: {LY_FROM} -> {LY_TO}")

# ==============================================================================
# 2) CONEXIÓN
# ==============================================================================

load_dotenv(RUTA_ENV)
DB_USER     = os.getenv("USER")
DB_PASSWORD = os.getenv("PASSWORD")


import time as _time

# El handshake del driver ODBC de Treasure Data falla de forma intermitente
# (errorCode member not found / SSL), sobre todo con la VPN inestable. Como fetch()
# abre una conexion nueva por query (~10 por corrida), cualquiera puede caer al azar.
# Se reintenta la CONEXION con backoff; los errores de la query en si no se reintentan.
_CONN_RETRIES = 4
_CONN_BACKOFF = 8  # segundos: 8, 16, 24...


def conectar():
    import pyodbc
    last = None
    for intento in range(1, _CONN_RETRIES + 1):
        try:
            return pyodbc.connect(
                f"DSN={DSN_NAME};UID={DB_USER};PWD={DB_PASSWORD};",
                autocommit=True,
            )
        except pyodbc.Error as e:
            last = e
            if intento < _CONN_RETRIES:
                espera = _CONN_BACKOFF * intento
                print(f"  ! conexion falló (intento {intento}/{_CONN_RETRIES}): "
                      f"{str(e)[:90]} — reintento en {espera}s")
                _time.sleep(espera)
    raise last


def fetch(query: str, label: str) -> pd.DataFrame:
    print(f"  > {label} ...")
    con = conectar()
    try:
        df = pd.read_sql(query, con)
    except Exception as e:
        # Nombrar la query que falló: si no, el traceback de pyodbc/pandas no dice cuál.
        raise RuntimeError(f"fetch('{label}') falló: {str(e)[:200]}") from e
    finally:
        con.close()
    print(f"  OK {len(df):,} filas")
    return df


# ==============================================================================
# 3) QUERIES (placeholders: {{Desde}}, {{Hasta}}, {{Pais}}, {{Partner}})
# ==============================================================================

def _sub(sql: str, desde: str, hasta: str) -> str:
    """Reemplaza placeholders de Metabase por valores SQL concretos."""
    return (sql
        .replace("{{Desde}}",    f"DATE('{desde}')")
        .replace("{{Hasta}}",    f"DATE('{hasta}')")
        .replace("{{Pais}}",     "'TODOS'")
        .replace("{{Partner}}", "'TODOS'")
    )


_ACUM_SQL = """

-- ╔══════════════════════════════════════════════════════╗
-- ║  FILTROS DISPONIBLES                                 ║
-- ║                                                      ║
-- ║  {{Desde}}    → Fecha inicio  ej: 2026-06-01         ║
-- ║  {{Hasta}}    → Primer día del mes siguiente         ║
-- ║                 ej: 2026-07-01 → trae hasta 2026-06-30 ║
-- ║                                                      ║
-- ║  {{Pais}}     → TODOS | AR | BR | MX | CO |         ║
-- ║                  CL | PE | EC | UY                   ║
-- ║                                                      ║
-- ║  {{Partner}}  → TODOS | DP | SUBS | IFOODBR |       ║
-- ║                  R&B | BBVAMX | INVEX | ICBCAR       ║
-- ╚══════════════════════════════════════════════════════╝
--
-- FIX: el gb_basebi/gb_basebi_2/comision/fee/descuentos venian repetidos
-- una vez por cada fila de accumulation/cancellation con distinto
-- processing_date para la misma transaccion+producto+business (el reporte
-- de Comarch a veces reemite el mismo accrual en mas de una fecha). Se
-- agrega rn_gb (ROW_NUMBER particionado por dsp_transaction_id, product,
-- business) y se blindan esas columnas para que solo se cuenten en la
-- primera fila. "points" queda sin blindar: eso si debe sumarse por cada
-- fecha de procesamiento.

WITH tipopunto AS (

    -- Rama 1: GR activos + GA REFUND reembolsados
    SELECT CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id
         , pt.code                                AS point_code
         , SUM(-tp.points)                        AS puntosv2
    FROM data.lake.clm_transactions t
    JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
    JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
    WHERE t.processing_date >= {{Desde}}
      AND t.processing_date <  {{Hasta}}          -- ← CAMBIADO: <= a <
      AND t.status = 'B'
      AND (   t.transaction_type = 'GR'
           OR (t.transaction_type = 'GA' AND t.ext_despegar_trn_type = 'REFUND'))
    GROUP BY t.ext_despegar_trn_id, pt.code

    UNION ALL

    -- Rama 2: cancelaciones de tipos no reembolsables
    SELECT tp_orig.transaction_id
         , tp_orig.point_code
         , -SUM(tp_orig.puntosv2)               AS puntosv2
    FROM (
        SELECT CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id
             , pt.code                                AS point_code
             , SUM(-tp.points)                        AS puntosv2
        FROM data.lake.clm_transactions t
        JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
        JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
        WHERE t.processing_date >= {{Desde}}
          AND t.processing_date <  {{Hasta}}          -- ← CAMBIADO: <= a <
          AND t.status = 'B'
          AND t.transaction_type = 'GR'
          AND pt.code IN (
              'FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO',
              'IFOOD_WEL','IFOOD_2W','IFOOD_RWB','IF_MISSION',
              'IF_CAMPAI','PONTOSBR','MISSIONS','IFO_WE_CLU'
          )
        GROUP BY t.ext_despegar_trn_id, pt.code
    ) tp_orig
    INNER JOIN (
        SELECT DISTINCT CAST(dsp_transaction_id AS VARCHAR) AS dsp_transaction_id
        FROM data.lake.comarch_accumulation_report
        WHERE processing_date >= {{Desde}}
          AND processing_date <  {{Hasta}}            -- ← CAMBIADO: <= a <
          AND COALESCE(dsp_transaction_type, 'Nulo') = 'REFUND'
          AND COALESCE(points, 0) = 0
    ) ar_ref ON tp_orig.transaction_id = ar_ref.dsp_transaction_id
    GROUP BY tp_orig.transaction_id, tp_orig.point_code

)

-- Accrual
SELECT processing_date
     , country_code
     , partner
     , sum(points)                     points
     , point_type
     , business
     , product
     , COALESCE(
          country,
          CASE country_code
              WHEN 'AR' THEN 'Argentina'
              WHEN 'BR' THEN 'Brasil'
              WHEN 'CO' THEN 'Colombia'
              WHEN 'EC' THEN 'Ecuador'
              WHEN 'MX' THEN 'Mexico'
              WHEN 'PE' THEN 'Peru'
              WHEN 'UY' THEN 'Uruguay'
          END
      ) AS country
     , payment_type
     , CASE
           WHEN channel IN ('viajes-falabella-presencial','viajes-falabella-corporate','vf-presencial-markup','bestday-islas','bestday-islas-markup','tiendas-b2c') THEN 'Sucursales'
           WHEN channel IN ('beneficios-despegar','site','site-smartphone','site-tablet','bestday-site','viajes-falabella-wl','viajes-falabella-viajaya','viajanet-passagens','viajanet-site', 'agencia-exoticca', 'phanton-brand','puntosbonus-pe') THEN 'Site'
           WHEN channel IN ('call-sales-b2c','call-sales-outbound','bestday-call','viajes-falabella-call','viajanet-televentas', 'videollamada-b2c','whatsapp-b2c') THEN 'Call Center'
           WHEN channel IN ('android-app','iphone-app','bestday-app','viajes-falabella-app','viajanet-app') THEN 'App'
           ELSE 'Site'
         END AS channel_condition
     , trip_type
     , produto_original
     , produto
     , SUM(CASE WHEN rn_gb = 1 THEN comision   ELSE 0 END) AS comision
     , SUM(CASE WHEN rn_gb = 1 THEN fee         ELSE 0 END) AS fee
     , SUM(CASE WHEN rn_gb = 1 THEN descuentos  ELSE 0 END) AS descuentos
     -- FIX GB (2026-09-09): solo se cuenta el GB si el combo (dsp_transaction_id,
     -- product, business) tiene puntos NETOS > 0. Evita contar GB de reservas cuyos
     -- puntos general fueron cancelados (accrual + cancelacion neteaban <= 0), que
     -- inflaban el GB por encima del GB completo del producto. net_pts_combo se
     -- calcula abajo, junto a rn_gb. SOLO afecta gb_basebi/gb_basebi_2 - el resto
     -- de las columnas queda igual que antes.
     , SUM(CASE WHEN rn_gb = 1 AND net_pts_combo > 0 THEN gb_basebi   ELSE 0 END) AS gb_basebi
     , SUM(CASE WHEN rn_gb = 1 AND net_pts_combo > 0 THEN gb_basebi_2 ELSE 0 END) AS gb_basebi_2
     , COALESCE(
           CAST(SUM(CASE WHEN rn_gb = 1 THEN descuento_consumo_puntos_usd ELSE 0 END) AS DOUBLE)
           / NULLIF(SUM(CASE WHEN rn_gb = 1 THEN gb_basebi_2 ELSE 0 END) + ABS(SUM(CASE WHEN rn_gb = 1 THEN descuentos ELSE 0 END)), 0)
         , 0)                              AS pct_pagado_con_puntos
     , COALESCE(
          country,
          CASE country_code
              WHEN 'AR' THEN 'Argentina'
              WHEN 'BR' THEN 'Brasil'
              WHEN 'CO' THEN 'Colombia'
              WHEN 'EC' THEN 'Ecuador'
              WHEN 'MX' THEN 'Mexico'
              WHEN 'PE' THEN 'Peru'
              WHEN 'UY' THEN 'Uruguay'
          END
      )||' '||product||' '||business concatenado
     , CASE
           WHEN business = 'DOMESTIC'
                THEN UPPER(COALESCE(country, CASE country_code
              WHEN 'AR' THEN 'Argentina'
              WHEN 'BR' THEN 'Brasil'
              WHEN 'CO' THEN 'Colombia'
              WHEN 'EC' THEN 'Ecuador'
              WHEN 'MX' THEN 'Mexico'
              WHEN 'PE' THEN 'Peru'
              WHEN 'UY' THEN 'Uruguay'
          END))
           WHEN business = 'INTERNATIONAL' AND product = 'FLIGHT' OR product = 'INSURANCE'
                THEN UPPER(COALESCE(country, CASE country_code
              WHEN 'AR' THEN 'Argentina'
              WHEN 'BR' THEN 'Brasil'
              WHEN 'CO' THEN 'Colombia'
              WHEN 'EC' THEN 'Ecuador'
              WHEN 'MX' THEN 'Mexico'
              WHEN 'PE' THEN 'Peru'
              WHEN 'UY' THEN 'Uruguay'
          END))
           ELSE 'TRAVEL'
         END AS legal_entity
     , SUM(CASE WHEN rn_gb = 1 THEN descuento_consumo_puntos_usd ELSE 0 END) * -1  AS descuento_consumo_puntos_usd


FROM (
  SELECT *
       , ROW_NUMBER() OVER (
             PARTITION BY dsp_transaction_id, product, business
             ORDER BY processing_date
         ) AS rn_gb
       -- FIX GB (2026-09-09): neto de puntos por combo. "points" ya viene con signo
       -- (accrual +, cancelacion * -1), asi que esta suma es accrual - cancelacion.
       , SUM(points) OVER (
             PARTITION BY dsp_transaction_id, product, business
         ) AS net_pts_combo
  FROM (

    -- ACCUMULATION branch
    SELECT 'Accumulation'         file
         , ar.dsp_transaction_id
         , ar.country             AS country_code
         , ar.partner
         , ar.points
         , ar.point_type
         , ar.business
         , ar.product
         , ar.processing_date
         , qr1.transaction_code
         , qr1.transaction_code_padre
         , qr1.country
         , qr1.payment_type
         , qr1.channel
         , qr1.trip_type
         , qr1.produto_original
         , qr1.produto
         , qr1.comision
         , qr1.fee
         , qr1.descuentos
         , qr1.gb_basebi
         , qr1.gb_basebi_2
         , CAST(
               CASE WHEN ar.country = 'MX'
                    THEN COALESCE(tp_agg.total_puntosv2, 0) * COALESCE(ratio_map.ratio_prd, 0) / 1.16
                    ELSE COALESCE(tp_agg.total_puntosv2, 0) * COALESCE(ratio_map.ratio_prd, 0)
               END AS DECIMAL(18,2)
           ) AS descuento_consumo_puntos_usd
    FROM (
        SELECT ar1.dsp_transaction_id
             , ar1.country
             , ar1.partner
             , SUM(ar1.points)                   AS points
             , ar1.point_type
             , ar1.business
             , ar1.product
             , CAST(ar1.processing_date AS DATE) AS processing_date
        FROM data.lake.comarch_accumulation_report ar1
        WHERE ar1.processing_date >= {{Desde}}
          AND ar1.processing_date <  {{Hasta}}    -- ya estaba correcto ✅
          AND COALESCE(ar1.dsp_transaction_type,'Nulo') <> 'REFUND'
          AND ({{Pais}}    = 'TODOS' OR ar1.country = {{Pais}})
          AND ({{Partner}} = 'TODOS' OR ar1.partner = {{Partner}})
        GROUP BY ar1.dsp_transaction_id
               , ar1.country
               , ar1.partner
               , ar1.point_type
               , ar1.business
               , ar1.product
               , CAST(ar1.processing_date AS DATE)
    ) ar
    LEFT JOIN (
        SELECT /*+ PARALLEL(80) */
               a.transaction_code
             , NULL                                         AS transaction_code_padre
             , CAST(a.transaction_code AS VARCHAR)         AS transaction_code_2
             , b.country
             , a.payment_type
             , b.channel
             , a.trip_type
             , b.purchase_type                             AS produto_original
             , array_agg(a.product_type)                   AS produto
             , CASE
                 WHEN a.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN a.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN a.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN a.product_type = 'Universal'             THEN 'TICKET'
                 WHEN a.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN a.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN a.product_type = 'Disney'                THEN 'TICKET'
                 WHEN a.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN a.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN a.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN a.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN a.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN a.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN a.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN a.product_type = 'Valijas'               THEN 'ONA'
                 WHEN a.product_type = 'Autos'                 THEN 'CAR'
                 WHEN a.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN a.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END                                         AS product_type_qr1
             , SUM(CAST((commission+flight_over+flight_markup) AS DECIMAL(18,2))) AS comision
             , SUM(CAST((fee+flight_du) AS DECIMAL(18,2)))                        AS fee
             , SUM(CAST(discount AS DECIMAL(18,2))) * -1                          AS descuentos
             , SUM(CAST(total AS DECIMAL(18,2)))                                  AS gb_basebi
             , SUM(CAST(gross_booking AS DECIMAL(18,2)))                          AS gb_basebi_2
        FROM data.analytics.bi_transactional_fact_products a
        LEFT JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_transactions
            WHERE reservation_year_month >= CAST('2023-01-01' AS DATE)
        ) b ON a.transaction_code = b.transaction_code
        LEFT JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_charges
            WHERE reservation_year_month >= CAST('2023-01-01' AS DATE)
        ) c ON CAST(a.transaction_code AS VARCHAR)||a.product_id
             = CAST(c.transaction_code AS VARCHAR)||c.product_id
        WHERE a.reservation_year_month >= CAST('2023-01-01' AS DATE)
        GROUP BY a.transaction_code
               , CAST(a.transaction_code AS VARCHAR)
               , b.country
               , a.payment_type
               , b.channel
               , a.trip_type
               , b.purchase_type
               , CASE
                 WHEN a.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN a.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN a.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN a.product_type = 'Universal'             THEN 'TICKET'
                 WHEN a.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN a.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN a.product_type = 'Disney'                THEN 'TICKET'
                 WHEN a.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN a.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN a.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN a.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN a.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN a.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN a.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN a.product_type = 'Valijas'               THEN 'ONA'
                 WHEN a.product_type = 'Autos'                 THEN 'CAR'
                 WHEN a.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN a.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
    ) qr1 ON CAST(ar.dsp_transaction_id AS VARCHAR)||ar.product
           = CAST(qr1.transaction_code AS VARCHAR)||qr1.product_type_qr1
    LEFT JOIN (
        SELECT transaction_id, SUM(puntosv2) AS total_puntosv2
        FROM tipopunto
        GROUP BY transaction_id
    ) tp_agg ON CAST(ar.dsp_transaction_id AS VARCHAR) = tp_agg.transaction_id
    LEFT JOIN (
        SELECT CAST(t.ext_despegar_trn_id AS VARCHAR)     AS transaction_code
             , CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END                                        AS product_type_qr1
             , MAX(CAST(t_prd.ext_ratio AS DECIMAL(18,4))) AS ratio_prd
        FROM data.lake.clm_transactions t
        JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_products
            WHERE reservation_year_month >= CAST('2024-01-01' AS DATE)
        ) prod ON CAST(t.ext_despegar_trn_id AS VARCHAR) = CAST(prod.transaction_code AS VARCHAR)
        JOIN data.lake.clm_transaction_products t_prd
          ON t.id = t_prd.transaction_id
         AND t_prd.original_product_code = CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
        WHERE t.transaction_type = 'GR'
          AND t.status = 'B'
        GROUP BY CAST(t.ext_despegar_trn_id AS VARCHAR), CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
    ) ratio_map ON CAST(ar.dsp_transaction_id AS VARCHAR)||ar.product
               = ratio_map.transaction_code||ratio_map.product_type_qr1

    UNION ALL

    -- CANCELLATION branch
    SELECT 'Cancellation'         file
         , cr.dsp_transaction_id
         , cr.country             AS country_code
         , cr.partner
         , (cr.points * -1)       points
         , cr.point_type
         , cr.business
         , cr.product
         , cr.processing_date
         , qr1.transaction_code
         , qr1.transaction_code_padre
         , qr1.country
         , qr1.payment_type
         , qr1.channel
         , qr1.trip_type
         , qr1.produto_original
         , qr1.produto
         , qr1.comision
         , qr1.fee
         , qr1.descuentos
         , qr1.gb_basebi
         , qr1.gb_basebi_2
         , CAST(
               CASE WHEN cr.country = 'MX'
                    THEN COALESCE(tp_agg.total_puntosv2, 0) * COALESCE(ratio_map.ratio_prd, 0) / 1.16
                    ELSE COALESCE(tp_agg.total_puntosv2, 0) * COALESCE(ratio_map.ratio_prd, 0)
               END AS DECIMAL(18,2)
           ) AS descuento_consumo_puntos_usd
    FROM (
        SELECT cr1.dsp_transaction_id
             , cr1.country
             , cr1.partner
             , SUM(cr1.points)                      AS points
             , cr1.point_type
             , cr1.business
             , cr1.product
             , CAST(cr1.generation_date AS DATE)    AS processing_date
        FROM data.lake.comarch_cancellation_report cr1
        WHERE cr1.generation_date >= {{Desde}}
          AND cr1.generation_date <  {{Hasta}}      -- ya estaba correcto ✅
          AND ({{Pais}}    = 'TODOS' OR cr1.country = {{Pais}})
          AND ({{Partner}} = 'TODOS' OR cr1.partner = {{Partner}})
        GROUP BY cr1.dsp_transaction_id
               , cr1.country
               , cr1.partner
               , cr1.point_type
               , cr1.business
               , cr1.product
               , CAST(cr1.generation_date AS DATE)
    ) cr
    LEFT JOIN (
        SELECT /*+ PARALLEL(80) */
               a.transaction_code
             , NULL                                         AS transaction_code_padre
             , CAST(a.transaction_code AS VARCHAR)         AS transaction_code_2
             , b.country
             , a.payment_type
             , b.channel
             , a.trip_type
             , b.purchase_type                             AS produto_original
             , array_agg(a.product_type)                   AS produto
             , CASE
                 WHEN a.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN a.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN a.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN a.product_type = 'Universal'             THEN 'TICKET'
                 WHEN a.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN a.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN a.product_type = 'Disney'                THEN 'TICKET'
                 WHEN a.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN a.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN a.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN a.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN a.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN a.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN a.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN a.product_type = 'Valijas'               THEN 'ONA'
                 WHEN a.product_type = 'Autos'                 THEN 'CAR'
                 WHEN a.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN a.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END                                         AS product_type_qr1
             , SUM(CAST((commission+flight_over+flight_markup) AS DECIMAL(18,2))) AS comision
             , SUM(CAST((fee+flight_du) AS DECIMAL(18,2)))                        AS fee
             , SUM(CAST(discount AS DECIMAL(18,2))) * -1                          AS descuentos
             , SUM(CAST(total AS DECIMAL(18,2)))                                  AS gb_basebi
             , SUM(CAST(gross_booking AS DECIMAL(18,2)))                          AS gb_basebi_2
        FROM data.analytics.bi_transactional_fact_products a
        LEFT JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_transactions
            WHERE reservation_year_month >= CAST('2023-01-01' AS DATE)
        ) b ON a.transaction_code = b.transaction_code
        LEFT JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_charges
            WHERE reservation_year_month >= CAST('2023-01-01' AS DATE)
        ) c ON CAST(a.transaction_code AS VARCHAR)||a.product_id
             = CAST(c.transaction_code AS VARCHAR)||c.product_id
        WHERE a.reservation_year_month >= CAST('2023-01-01' AS DATE)
        GROUP BY a.transaction_code
               , CAST(a.transaction_code AS VARCHAR)
               , b.country
               , a.payment_type
               , b.channel
               , a.trip_type
               , b.purchase_type
               , CASE
                 WHEN a.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN a.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN a.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN a.product_type = 'Universal'             THEN 'TICKET'
                 WHEN a.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN a.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN a.product_type = 'Disney'                THEN 'TICKET'
                 WHEN a.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN a.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN a.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN a.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN a.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN a.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN a.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN a.product_type = 'Valijas'               THEN 'ONA'
                 WHEN a.product_type = 'Autos'                 THEN 'CAR'
                 WHEN a.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN a.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
    ) qr1 ON CAST(cr.dsp_transaction_id AS VARCHAR)||cr.product
           = CAST(qr1.transaction_code AS VARCHAR)||qr1.product_type_qr1
    LEFT JOIN (
        SELECT transaction_id, SUM(puntosv2) AS total_puntosv2
        FROM tipopunto
        GROUP BY transaction_id
    ) tp_agg ON CAST(cr.dsp_transaction_id AS VARCHAR) = tp_agg.transaction_id
    LEFT JOIN (
        SELECT CAST(t.ext_despegar_trn_id AS VARCHAR)     AS transaction_code
             , CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END                                        AS product_type_qr1
             , MAX(CAST(t_prd.ext_ratio AS DECIMAL(18,4))) AS ratio_prd
        FROM data.lake.clm_transactions t
        JOIN (
            SELECT * FROM data.analytics.bi_transactional_fact_products
            WHERE reservation_year_month >= CAST('2024-01-01' AS DATE)
        ) prod ON CAST(t.ext_despegar_trn_id AS VARCHAR) = CAST(prod.transaction_code AS VARCHAR)
        JOIN data.lake.clm_transaction_products t_prd
          ON t.id = t_prd.transaction_id
         AND t_prd.original_product_code = CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
        WHERE t.transaction_type = 'GR'
          AND t.status = 'B'
        GROUP BY CAST(t.ext_despegar_trn_id AS VARCHAR), CASE
                 WHEN prod.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                 WHEN prod.product_type = 'Excursiones'           THEN 'TOUR'
                 WHEN prod.product_type = 'Cruceros'              THEN 'ONA'
                 WHEN prod.product_type = 'Universal'             THEN 'TICKET'
                 WHEN prod.product_type = 'Alquileres'            THEN 'HOTEL'
                 WHEN prod.product_type = 'SeaWorld'              THEN 'TICKET'
                 WHEN prod.product_type = 'Disney'                THEN 'TICKET'
                 WHEN prod.product_type = 'Circuito'              THEN 'TOUR'
                 WHEN prod.product_type = 'Tickets'               THEN 'TICKET'
                 WHEN prod.product_type = 'Vuelos'                THEN 'FLIGHT'
                 WHEN prod.product_type = 'Busch Gardens'         THEN 'TICKET'
                 WHEN prod.product_type = 'Hoteles'               THEN 'HOTEL'
                 WHEN prod.product_type = 'EspectÃ¡culos'         THEN 'TOUR'
                 WHEN prod.product_type = 'Traslados'             THEN 'TRANSFER'
                 WHEN prod.product_type = 'Valijas'               THEN 'ONA'
                 WHEN prod.product_type = 'Autos'                 THEN 'CAR'
                 WHEN prod.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                 WHEN prod.product_type = 'Buses'                 THEN 'ONA'
                 ELSE 'N/D'
               END
    ) ratio_map ON CAST(cr.dsp_transaction_id AS VARCHAR)||cr.product
               = ratio_map.transaction_code||ratio_map.product_type_qr1

  ) union_base
)
GROUP BY processing_date
       , country_code
       , partner
       , point_type
       , business
       , product
       , COALESCE(
          country,
          CASE country_code
              WHEN 'AR' THEN 'Argentina'
              WHEN 'BR' THEN 'Brasil'
              WHEN 'CO' THEN 'Colombia'
              WHEN 'EC' THEN 'Ecuador'
              WHEN 'MX' THEN 'Mexico'
              WHEN 'PE' THEN 'Peru'
              WHEN 'UY' THEN 'Uruguay'
          END
      )
       , payment_type
       , CASE
           WHEN channel IN ('viajes-falabella-presencial','viajes-falabella-corporate','vf-presencial-markup','bestday-islas','bestday-islas-markup','tiendas-b2c') THEN 'Sucursales'
           WHEN channel IN ('beneficios-despegar','site','site-smartphone','site-tablet','bestday-site','viajes-falabella-wl','viajes-falabella-viajaya','viajanet-passagens','viajanet-site', 'agencia-exoticca', 'phanton-brand','puntosbonus-pe') THEN 'Site'
           WHEN channel IN ('call-sales-b2c','call-sales-outbound','bestday-call','viajes-falabella-call','viajanet-televentas', 'videollamada-b2c','whatsapp-b2c') THEN 'Call Center'
           WHEN channel IN ('android-app','iphone-app','bestday-app','viajes-falabella-app','viajanet-app') THEN 'App'
           ELSE 'Site'
         END
       , trip_type
       , produto_original
       , produto
"""


_REDEN_SQL = """
WITH Redemption AS (
SELECT
    dsp_transaction_id, product, country_code, partner,
    SUM(points) points, point_type, business, transaction_code, country,
    produto_original,
    CASE
         WHEN channel IN ('viajes-falabella-presencial','viajes-falabella-corporate','vf-presencial-markup','bestday-islas','bestday-islas-markup','tiendas-b2c') THEN 'Sucursales'
         WHEN channel IN ('beneficios-despegar','site','site-smartphone','site-tablet','bestday-site','viajes-falabella-wl','viajes-falabella-viajaya','viajanet-passagens','viajanet-site','agencia-exoticca','phanton-brand','puntosbonus-pe') THEN 'Site'
         WHEN channel IN ('call-sales-b2c','call-sales-outbound','bestday-call','viajes-falabella-call','viajanet-televentas','videollamada-b2c','whatsapp-b2c') THEN 'Call Center'
         WHEN channel IN ('android-app','iphone-app','bestday-app','viajes-falabella-app','viajanet-app') THEN 'App'
         ELSE 'Site'
       END AS channel_condition,
    payment_type, produto_agrupado, transaction_type, ratio_prd,
    CASE
        WHEN business = 'DOMESTIC' THEN UPPER(country)
        WHEN business = 'INTERNATIONAL' AND product = 'FLIGHT' OR product = 'INSURANCE' THEN UPPER(country)
        ELSE 'TRAVEL'
    END AS legal_entity
FROM (
    SELECT 'Accumulation' file,
             ar.dsp_transaction_id, ar.product, ar.country_code, ar.partner,
             (ar.points * -1) points, ar.point_type, ar.business,
             qr1.transaction_code, qr1.country, qr1.produto_original,
             qr1.channel, qr1.payment_type, qr1.produto_agrupado,
             qr1.transaction_type, qr1.ratio_prd
    FROM (
        SELECT ar1.dsp_transaction_id, ar1.country AS country_code, ar1.partner,
               SUM(ar1.points) points, ar1.point_type, ar1.business, ar1.product
        FROM data.lake.comarch_accumulation_report ar1
        WHERE ar1.processing_date >= {{Desde}}
          AND ar1.processing_date < {{Hasta}}
          AND COALESCE(ar1.dsp_transaction_type,'Nulo') = 'REFUND'
        GROUP BY ar1.dsp_transaction_id, ar1.country, ar1.partner,
                 ar1.point_type, ar1.business, ar1.product
    ) ar
    JOIN (
        SELECT base.transaction_code, t_trn.ext_country AS country_code,
               base.product_type AS produto_agrupado,
               t_trn.transaction_type, b.country, b.purchase_type AS produto_original,
               b.channel, base.payment_type,
               CAST(t_prd.ext_ratio AS DECIMAL(18,4)) AS ratio_prd,
               CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END AS product_type_qr1
        FROM data.lake.clm_transactions t_trn
        JOIN data.lake.clm_customers t_cstm ON t_trn.account_id = t_cstm.account_id
        LEFT JOIN (
            SELECT transaction_code, product_type, payment_type, trip_type
            FROM data.analytics.bi_transactional_fact_products
            WHERE reservation_year_month > CAST('2024-01-01' AS DATE)
        ) base ON CAST(t_trn.ext_despegar_trn_id AS VARCHAR) = base.transaction_code
        LEFT JOIN (
            SELECT transaction_code, country, channel, purchase_type
            FROM data.analytics.bi_transactional_fact_transactions
            WHERE reservation_year_month > CAST('2024-01-01' AS DATE)
        ) b ON base.transaction_code = b.transaction_code
        JOIN data.lake.clm_transaction_products t_prd
            ON t_trn.id = t_prd.transaction_id
           AND original_product_code = CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END
        WHERE t_trn.transaction_type = 'GR' AND t_trn.status = 'B'
        GROUP BY base.transaction_code, t_trn.ext_country, base.product_type,
                 t_trn.transaction_type, b.country, b.channel, base.payment_type,
                 b.purchase_type, t_prd.ext_ratio,
                 CASE
                     WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                     WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                     WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                     WHEN base.product_type = 'Universal'             THEN 'TICKET'
                     WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                     WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                     WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                     WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                     WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                     WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                     WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                     WHEN base.product_type = 'Valijas'               THEN 'ONA'
                     WHEN base.product_type = 'Autos'                 THEN 'CAR'
                     WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                     WHEN base.product_type = 'Buses'                 THEN 'ONA'
                     ELSE 'N/D'
                 END
    ) qr1 ON CAST(ar.dsp_transaction_id AS VARCHAR)||ar.product
           = CAST(qr1.transaction_code AS VARCHAR)||qr1.product_type_qr1

    UNION ALL

    SELECT 'Redemption' file,
            rd.dsp_transaction_id, rd.product, rd.country_code, rd.partner,
            (rd.points) points, rd.point_type, rd.business,
            qr1.transaction_code, qr1.country, qr1.produto_original,
            qr1.channel, qr1.payment_type, qr1.produto_agrupado,
            qr1.transaction_type, qr1.ratio_prd
    FROM (
        SELECT rd1.dsp_transaction_id, rd1.clm_transaction_id, rd1.product,
               rd1.country AS country_code, rd1.partner,
               SUM(rd1.points) points, rd1.point_type, rd1.business
        FROM data.lake.comarch_redemption_report rd1
        WHERE rd1.processing_date >= {{Desde}}
          AND rd1.processing_date < {{Hasta}}
        GROUP BY rd1.dsp_transaction_id, rd1.clm_transaction_id,
                 rd1.product, rd1.country, rd1.partner, rd1.point_type, rd1.business
    ) rd
    JOIN (
        SELECT base.transaction_code, t_trn.id,
               t_trn.ext_country AS country_code, base.product_type AS produto_agrupado,
               t_trn.transaction_type, b.country, b.purchase_type AS produto_original,
               b.channel, base.payment_type,
               CAST(t_prd.ext_ratio AS DECIMAL(18,4)) AS ratio_prd,
               CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END AS product_type_qr1
        FROM data.lake.clm_transactions t_trn
        JOIN data.lake.clm_customers t_cstm ON t_trn.account_id = t_cstm.account_id
        LEFT JOIN (
            SELECT transaction_code, product_type, payment_type, trip_type
            FROM data.analytics.bi_transactional_fact_products
            WHERE reservation_year_month > CAST('2024-01-01' AS DATE)
        ) base ON CAST(t_trn.ext_despegar_trn_id AS VARCHAR) = base.transaction_code
        LEFT JOIN (
            SELECT transaction_code, country, channel, purchase_type
            FROM data.analytics.bi_transactional_fact_transactions
            WHERE reservation_year_month > CAST('2024-01-01' AS DATE)
        ) b ON base.transaction_code = b.transaction_code
        JOIN data.lake.clm_transaction_products t_prd
            ON t_trn.id = t_prd.transaction_id
           AND original_product_code = CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END
        WHERE t_trn.transaction_type = 'GR' AND t_trn.status = 'B'
        GROUP BY base.transaction_code, t_trn.id, t_trn.ext_country, base.product_type,
                 t_trn.transaction_type, b.country, b.channel, base.payment_type,
                 b.purchase_type, t_prd.ext_ratio,
                 CASE
                     WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                     WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                     WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                     WHEN base.product_type = 'Universal'             THEN 'TICKET'
                     WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                     WHEN base.product_type IN ('SeaWorld','Disney','Busch Gardens','Tickets') THEN 'TICKET'
                     WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                     WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                     WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                     WHEN base.product_type = 'Espectaculos'          THEN 'TOUR'
                     WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                     WHEN base.product_type = 'Valijas'               THEN 'ONA'
                     WHEN base.product_type = 'Autos'                 THEN 'CAR'
                     WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                     WHEN base.product_type = 'Buses'                 THEN 'ONA'
                     ELSE 'N/D'
                 END
    ) qr1 ON CAST(rd.dsp_transaction_id AS VARCHAR)||rd.product
           = CAST(qr1.transaction_code AS VARCHAR)||qr1.product_type_qr1
           AND qr1.id = rd.clm_transaction_id
)
GROUP BY dsp_transaction_id, product, country_code, partner, point_type, business,
    transaction_code, country, produto_original, channel, payment_type,
    produto_agrupado, transaction_type, ratio_prd
),

tipopunto_raw AS (
    SELECT CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id,
           pt.code AS point_code, CAST(t.processing_date AS DATE) AS processing_date,
           SUM(-tp.points) AS puntosv2
    FROM data.lake.clm_transactions t
    JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
    JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
    WHERE t.processing_date >= {{Desde}}
      AND t.processing_date < {{Hasta}}
      AND t.status = 'B'
      AND (t.transaction_type = 'GR' OR (t.transaction_type = 'GA' AND t.ext_despegar_trn_type = 'REFUND'))
    GROUP BY t.ext_despegar_trn_id, pt.code, CAST(t.processing_date AS DATE)

    UNION ALL

    SELECT tp_orig.transaction_id, tp_orig.point_code, tp_orig.processing_date,
           -SUM(tp_orig.puntosv2) AS puntosv2
    FROM (
        SELECT CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id,
               pt.code AS point_code, CAST(t.processing_date AS DATE) AS processing_date,
               SUM(-tp.points) AS puntosv2
        FROM data.lake.clm_transactions t
        JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
        JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
        WHERE t.processing_date >= {{Desde}}
          AND t.processing_date < {{Hasta}}
          AND t.status = 'B' AND t.transaction_type = 'GR'
          AND pt.code IN ('FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO','IFOOD_WEL',
              'IFOOD_2W','IFOOD_RWB','IF_MISSION','IF_CAMPAI','PONTOSBR','MISSIONS','IFO_WE_CLU')
        GROUP BY t.ext_despegar_trn_id, pt.code, CAST(t.processing_date AS DATE)
    ) tp_orig
    INNER JOIN (
        SELECT DISTINCT CAST(ar.dsp_transaction_id AS VARCHAR) AS dsp_transaction_id
        FROM data.lake.comarch_accumulation_report ar
        WHERE ar.processing_date >= {{Desde}} AND ar.processing_date < {{Hasta}}
          AND COALESCE(ar.dsp_transaction_type, 'Nulo') = 'REFUND'
          AND NOT EXISTS (
              SELECT 1 FROM data.lake.comarch_accumulation_report ar2
              WHERE ar2.dsp_transaction_id = ar.dsp_transaction_id
                AND ar2.processing_date >= {{Desde}} AND ar2.processing_date < {{Hasta}}
                AND COALESCE(ar2.dsp_transaction_type, 'Nulo') = 'REFUND'
                AND COALESCE(ar2.point_type, '') IN ('FORTUNE','IFOOD_BR','IFOOD_WELCOME',
                    'IFOOD_PROMO','IFOOD_WEL','IFOOD_2W','IFOOD_RWB','IF_MISSION',
                    'IF_CAMPAI','PONTOSBR','MISSIONS','IFO_WE_CLU')
                AND COALESCE(ar2.points, 0) > 0
          )
          AND NOT EXISTS (
              SELECT 1 FROM data.lake.clm_transactions t_ga
              JOIN data.lake.clm_transaction_points tp_ga ON t_ga.id = tp_ga.source_transaction_id
              JOIN data.lake.clm_point_types pt_ga ON tp_ga.points_type_id = pt_ga.id
              WHERE CAST(t_ga.ext_despegar_trn_id AS VARCHAR) = CAST(ar.dsp_transaction_id AS VARCHAR)
                AND t_ga.transaction_type = 'GA' AND t_ga.ext_despegar_trn_type = 'REFUND'
                AND t_ga.status = 'B'
                AND t_ga.processing_date >= {{Desde}} AND t_ga.processing_date < {{Hasta}}
                AND pt_ga.code IN ('FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO','IFOOD_WEL',
                    'IFOOD_2W','IFOOD_RWB','IF_MISSION','IF_CAMPAI','PONTOSBR','MISSIONS','IFO_WE_CLU')
          )
    ) ar_ref ON tp_orig.transaction_id = ar_ref.dsp_transaction_id
    GROUP BY tp_orig.transaction_id, tp_orig.point_code, tp_orig.processing_date
),

tipopunto AS (
    SELECT transaction_id, point_code, MAX(processing_date) AS processing_date, SUM(puntosv2) AS puntosv2
    FROM tipopunto_raw GROUP BY transaction_id, point_code
),

final_base AS (
    SELECT cc.processing_date, a.dsp_transaction_id, a.product, a.country_code, a.partner,
           cc.puntosv2 AS points, cc.point_code,
           CASE
               WHEN cc.point_code = 'FORTUNE'    THEN 'FORTUNE'
               WHEN cc.point_code IN ('GAMI','R&B') THEN 'Puntos R&B'
               WHEN cc.point_code = 'SUBS'       THEN 'SUBSCRIPTION'
               WHEN cc.point_code = 'SUBS_INT'   THEN 'SUBSCRIPTION_INT'
               WHEN cc.point_code = 'IFOOD_BR'   THEN 'IFOOD_BR'
               WHEN cc.point_code = 'IFOOD_WEL'  THEN 'IFOOD_WEL'
               WHEN cc.point_code = 'IFOOD_2W'   THEN 'IFOOD_2W'
               WHEN cc.point_code = 'IFOOD_PR'   THEN 'IFOOD_PR'
               WHEN cc.point_code = 'IFOOD_1M'   THEN 'IFOOD_1M'
               WHEN cc.point_code = 'PONTOSBR'   THEN 'PONTOSBR'
               WHEN cc.point_code = 'IFO_WE_CLU' THEN 'IFO_WE_CLU'
               WHEN cc.point_code = 'IFOOD_RWB'  THEN 'IFOOD_RWB'
               WHEN cc.point_code = 'IF_MISSION' THEN 'IF_MISSION'
               WHEN cc.point_code = 'IF_CAMPAI'  THEN 'IF_CAMPAI'
               WHEN cc.point_code = 'IFOOD_WELCOME' THEN 'IFOOD_WELCOME'
               WHEN cc.point_code = 'IFOOD_PROMO'   THEN 'IFOOD_PROMO'
               WHEN cc.point_code = 'MISSIONS'      THEN 'MISSIONS'
               WHEN cc.point_code = 'KIDD_FLASH'    THEN 'KIDD_FLASH'
               -- Cobrand y Partners caian en 'general' (-> Pasaporte D! en el dashboard),
               -- inflandolo ~24.5%. Se separan aca. Cobrand: prefijo C_ (ICBCAR/INVEXMX/
               -- BDBCO; Santander/BR cae aca pero no se muestra, BR no tiene solapa Cobrand).
               -- Partners: SALE_POINT/BONDA_WE (se abre por pais, no por partner: la col
               -- partner de redencion es siempre 'DP'). Clasificados via dict reden.
               -- NOTA: el SSP (build_ssp_json) reincorpora COBRAND+PARTNERS a la base
               -- 'general' para no alterar el factor $/punto historico.
               WHEN cc.point_code LIKE 'C\\_%' ESCAPE '\\' THEN 'COBRAND'
               WHEN cc.point_code IN ('SALE_POINT','BONDA_WE') THEN 'PARTNERS'
               ELSE 'general'
           END AS point_type,
           a.business, a.transaction_code, a.country, a.produto_original,
           a.channel_condition, a.payment_type, a.produto_agrupado,
           a.transaction_type, a.ratio_prd, a.legal_entity,
           CAST(CASE WHEN a.country_code = 'MX'
                THEN cc.puntosv2 * a.ratio_prd / 1.16
                ELSE cc.puntosv2 * a.ratio_prd
           END AS DECIMAL(18,2)) * -1 AS descuento_consumo_puntos_usd
    FROM redemption a
    LEFT JOIN tipopunto cc ON CAST(a.dsp_transaction_id AS VARCHAR) = cc.transaction_id
)

SELECT processing_date, product, country_code, partner,
       SUM(points) AS points, point_type,
       business, country, produto_original, channel_condition, payment_type, produto_agrupado,
       SUM(descuento_consumo_puntos_usd) AS descuento_consumo_puntos_usd,
       legal_entity
FROM final_base
GROUP BY processing_date, product, country_code, partner, point_type, business, country,
         produto_original, channel_condition, payment_type, produto_agrupado, legal_entity
ORDER BY point_type, produto_agrupado
"""


def build_dict_json() -> bytes:
    """Genera loyalty_dict.json (mapeo programa) desde la pestaña `diccionario` de la
    planilla de config; si no está, cae a Diccionario.xlsx."""
    df = config_sheet_tab("diccionario")
    if df is None:
        df = pd.read_excel(DICT_XLSX)
    acum, reden = {}, {}
    for _, row in df.iterrows():
        concat  = str(row["concatenado"]) if not pd.isna(row["concatenado"]) else ""
        pt      = str(row["point_type"])  if not pd.isna(row["point_type"])  else ""
        sec     = str(row["seccion"])     if not pd.isna(row["seccion"])     else "Otros"
        partner = row.get("partner")
        if concat:
            acum[concat] = sec
        if pd.isna(partner) and pt:   # filas sin partner → lookup para redenciones
            reden[pt] = sec
    # Tokens sinteticos que emite el CASE de _REDEN_SQL para separar Cobrand y
    # Partners (antes caian en 'general' → Pasaporte D!, inflandolo ~24.5%). No son
    # point_types reales de Comarch, por eso se mapean aca y no en Diccionario.xlsx.
    # setdefault: si algun dia se agregan al Excel, gana el Excel.
    reden.setdefault("COBRAND", "Cobrand")
    reden.setdefault("PARTNERS", "Partners")
    result = {"acum": acum, "reden": reden}
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def build_acum_query(desde: str, hasta: str) -> str:
    return _sub(_ACUM_SQL, desde, hasta)


def build_reden_query(desde: str, hasta: str) -> str:
    return _sub(_REDEN_SQL, desde, hasta)


def build_breakage_query(ly_from: str) -> str:
    return f"""
WITH points AS (
    SELECT cm.ext_country_program AS Country,
           trxp.account_id,
           date_format(trx.transaction_date, '%m-%Y') AS Expiration_Date,
           trxp.source_transaction_id, trxp.points_type_id, pt.code,
           trxp.points
    FROM data.lake.clm_transactions trx
    INNER JOIN data.lake.clm_transaction_points trxp ON trx.id = trxp.source_transaction_id
    INNER JOIN data.lake.clm_customers cm            ON trx.account_id = cm.account_id
    INNER JOIN data.lake.clm_point_types pt          ON trxp.points_type_id = pt.id
    WHERE trx.transaction_type = 'PE'
      AND trx.transaction_date >= DATE('{ly_from}')
      -- points_type_id excluidos: tipos de punto que NO cuentan para breakage
      -- (bonos / ajustes / promos — no son acumulación orgánica). Lista espejo de
      -- la query de cierre de Loyalty en Metabase; si allá cambia, actualizar acá.
      AND trxp.points_type_id NOT IN (2751,2801,2901,2953,2954,3001,3002,3003,3004,3051,3101,3102,3103,3151)
    GROUP BY 1,2,3,4,5,6,7
),
categoria AS (
    SELECT c.account_id, a.customer_id, a.start_date,
           CASE WHEN a.recognition_tier_id = 2352 THEN 'Viajero'
                WHEN a.recognition_tier_id = 2353 THEN 'Explorador'
                WHEN a.recognition_tier_id = 2354 THEN 'Global'
           END AS tier
    FROM (
        SELECT customer_id, MAX(recognition_tier_id) AS recognition_tier_id, start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > date(now()))
        GROUP BY customer_id, start_date
    ) a
    INNER JOIN data.lake.clm_customers c ON a.customer_id = c.id
    INNER JOIN (
        SELECT customer_id, MAX(start_date) AS start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > date(now()))
        GROUP BY customer_id
    ) b ON a.customer_id = b.customer_id AND a.start_date = b.start_date
)
SELECT Expiration_Date, country, tier, points_type_id, code,
       SUM(points) * -1 AS Points
FROM points a
LEFT JOIN categoria b ON a.account_id = b.account_id
GROUP BY Expiration_Date, Country, tier, points_type_id, code
ORDER BY 1,2,3,4
"""
# `code` sale para poder clasificar el breakage por programa en el dashboard
# (loyalty_dict.reden[code] -> sección) — ej. excluir IFOOD / Acciones Marketing
# del roll-forward de pasivo. points_type_id -> code es 1:1, no cambia el grain.


# Miembros del programa — snapshot de la base activa (status = 'A') abierta por
# mes de alta (enrolment_date), pais y tier de reconocimiento. NO tiene ventana de
# fecha: es una foto del padron actual (los meses de alta viejos solo incluyen a
# los que HOY siguen activos). El tier sale de clm_account_recognition_levels con
# el mismo criterio que la query de breakage (ultimo nivel vigente por customer);
# sin nivel vigente -> 'Sin tier'.
_MIEMBROS_SQL = """
WITH categoria AS (
    SELECT a.customer_id,
           CASE WHEN a.recognition_tier_id = 2352 THEN 'Viajero'
                WHEN a.recognition_tier_id = 2353 THEN 'Explorador'
                WHEN a.recognition_tier_id = 2354 THEN 'Global'
                ELSE 'Sin tier'
           END AS tier
    FROM (
        SELECT customer_id, MAX(recognition_tier_id) AS recognition_tier_id, start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > date(now()))
        GROUP BY customer_id, start_date
    ) a
    INNER JOIN (
        SELECT customer_id, MAX(start_date) AS start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > date(now()))
        GROUP BY customer_id
    ) b ON a.customer_id = b.customer_id AND a.start_date = b.start_date
)
SELECT DATE_FORMAT(cm.enrolment_date, '%Y-%m')         AS fecha,
       CASE cm.ext_country_program
            WHEN 'BR' THEN 'BRASIL'   WHEN 'AR' THEN 'ARGENTINA'
            WHEN 'MX' THEN 'MEXICO'   WHEN 'EC' THEN 'ECUADOR'
            WHEN 'CO' THEN 'COLOMBIA' WHEN 'PE' THEN 'PERU'
            WHEN 'UY' THEN 'URUGUAY'  ELSE 'OTRO'
       END                                             AS pais,
       COALESCE(cat.tier, 'Sin tier')                  AS tier,
       COUNT(*)                                        AS clientes
FROM data.lake.clm_customers cm
LEFT JOIN categoria cat ON cat.customer_id = cm.id
WHERE cm.status = 'A'
  AND cm.ext_country_program IN ('AR', 'BR', 'MX', 'EC', 'CO', 'PE', 'UY')
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
"""


# Club Despegar (programa de suscripcion, Argentina). Query simplificada de la que
# pasó Diego: se saca was_client (Nuevo/Recomprador/Churn) — no se usa en el dashboard
# y evita el JOIN pesado contra analytics.mkt_users_fact_transactions.
#  - rn = 1: una suscripcion por social_id (ACTIVE gana; si no, la mas reciente)
# OJO: en data.raw.membertrip_subscription el `updated_at` está bulk-touched (todos los
# ACTIVE actualizados ago-2026; cero bajas registradas dic25-may26 y pico de 4k en jun26).
# NO sirve para el stock historico real ni el timing exacto de bajas. Unico timestamp
# confiable = created_at. Por eso:
#  - 'stock' : base activa ACUMULADA — suscripciones que HOY siguen ACTIVE, contadas por
#              su mes de alta (created_at). Monotona creciente, survivorship (= criterio
#              de loyalty_miembros). A mes actual == status ACTIVE.
#  - 'alta'  : suscripciones creadas ese mes (created_at) — confiable
#  - 'baja'  : USER_CANCELLED + PENDING_USER_CANCELLATION por updated_at — timing APROXIMADO
_CLUB_DESPEGAR_SQL = """
WITH ranked AS (
    SELECT
        mm.social_id,
        CASE ms.plan_id
            WHEN '90370891-0a09-4ade-bf5c-0ebfeb1b68bf' THEN 'Plan 1'
            WHEN '0d1e7af4-1558-4080-91c9-86d40a000e4b' THEN 'Plan 2'
            WHEN '0bcbacb4-4e6b-4539-928b-8f0aff08551e' THEN 'Plan 3'
            WHEN 'c09a89d0-ac09-4cdd-a2fc-142bbd3b0080' THEN 'Plan 4'
            ELSE 'Otro'
        END                        AS plan_type,
        ms.status                  AS membership_status,
        DATE(ms.created_at)        AS created_date,
        DATE(ms.updated_at)        AS updated_date,
        ROW_NUMBER() OVER (
            PARTITION BY mm.social_id
            ORDER BY CASE WHEN ms.status = 'ACTIVE' THEN 1 ELSE 2 END, ms.created_at DESC
        )                          AS rn
    FROM data.raw.membertrip_subscription ms
    JOIN data.raw.mike_members mm   ON ms.account_id = mm.provider_id
    JOIN data.raw.membertrip_plan p ON ms.plan_id = p.id
    WHERE ms.status IN (
        'ACTIVE', 'USER_CANCELLED', 'PENDING_USER_CANCELLATION', 'EXPIRED_PAYMENT', 'PAYMENT_PENDING'
    )
),
base AS (SELECT plan_type, membership_status, created_date, updated_date FROM ranked WHERE rn = 1),
meses AS (
    SELECT date_add('month', s, DATE('2025-01-01')) AS m0
    FROM UNNEST(sequence(0, date_diff('month', DATE('2025-01-01'), current_date))) AS t(s)
)
SELECT DATE_FORMAT(m.m0, '%Y-%m') AS ym, b.plan_type, 'stock' AS serie, COUNT(*) AS n
FROM meses m
JOIN (SELECT plan_type, created_date FROM base WHERE membership_status = 'ACTIVE') b
  ON b.created_date < date_add('month', 1, m.m0)
GROUP BY 1, 2

UNION ALL
SELECT DATE_FORMAT(created_date, '%Y-%m') AS ym, plan_type, 'alta' AS serie, COUNT(*) AS n
FROM base
WHERE created_date >= DATE('2025-01-01')
GROUP BY 1, 2

UNION ALL
SELECT DATE_FORMAT(updated_date, '%Y-%m') AS ym, plan_type, 'baja' AS serie, COUNT(*) AS n
FROM base
WHERE membership_status IN ('USER_CANCELLED', 'PENDING_USER_CANCELLATION')
  AND updated_date >= DATE('2025-01-01')
GROUP BY 1, 2

ORDER BY 3, 1, 2
"""


# iFood — usuarios enrolados, separado en 'iFood enrol' (initiative cross_cashback)
# y 'Club iFood' (initiative closed_loop_discount). De la pregunta Metabase 150076.
# Cambio vs la query original: se agrega MIN(closed_loop_discount) como fecha de alta
# de Club iFood, y el piso de fecha se baja a 2025-01 (era 2026-01) para poder comparar
# CY vs LY en el dashboard — si la iniciativa no existía antes, esos meses quedan vacíos.
_IFOOD_ENROLL_SQL = """
WITH u AS (
    SELECT despegar_session_id                                                       AS userid,
           MIN(CASE WHEN initiative = 'cross_cashback'       THEN DATE(event_date) END) AS ifood_date,
           MIN(CASE WHEN initiative = 'closed_loop_discount' THEN DATE(event_date) END) AS clube_date
    FROM analytics.ifood_dim_users
    WHERE initiative IN ('cross_cashback', 'closed_loop_discount')
      AND DATE(event_date) >= DATE('2025-01-01')
    GROUP BY 1
)
SELECT DATE_FORMAT(ifood_date, '%Y-%m') AS ym, 'iFood enrol' AS tipo, COUNT(*) AS n
FROM u WHERE ifood_date IS NOT NULL GROUP BY 1
UNION ALL
SELECT DATE_FORMAT(clube_date, '%Y-%m') AS ym, 'Club iFood' AS tipo, COUNT(*) AS n
FROM u WHERE clube_date IS NOT NULL GROUP BY 1
ORDER BY 1, 2
"""


# ==============================================================================
# 4) CLEAN & TRANSFORM
# ==============================================================================

def _fix_date(val) -> str:
    """Maneja fechas que vienen como datetime, string o serial Excel (float)."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return (pd.Timestamp("1899-12-30") + timedelta(days=float(val))).strftime("%Y-%m-%d")
    return pd.to_datetime(val).strftime("%Y-%m-%d")


# Welcome bonuses / subscripciones de partner no traen country/country_code de la
# query (no hay transaccion de viaje asociada para el JOIN) pero el partner ya
# identifica el pais — ej. INVEXMX -> Mexico, ICBCAR/BONDAAR/FOCOAR -> Argentina.
# SUBS (Club Despegar) es exclusivo de Argentina.
PARTNER_COUNTRY = {
    "IFOODBR": "Brasil", "C6BANKBR": "Brasil", "BRBBR": "Brasil",
    "KIDDLEBR": "Brasil", "ENTREGOBR": "Brasil", "NOMADBR": "Brasil", "GETNET": "Brasil",
    "BONDAAR": "Argentina", "ICBCAR": "Argentina", "FOCOAR": "Argentina", "MASLOWAR": "Argentina",
    "INVEXMX": "Mexico", "BBVAMX": "Mexico",
    "BDBCO": "Colombia",
    "SUBS": "Argentina",
}
PARTNER_COUNTRY_CODE = {
    "IFOODBR": "BR", "C6BANKBR": "BR", "BRBBR": "BR", "KIDDLEBR": "BR", "ENTREGOBR": "BR",
    "NOMADBR": "BR", "GETNET": "BR",
    "BONDAAR": "AR", "ICBCAR": "AR", "FOCOAR": "AR", "MASLOWAR": "AR",
    "INVEXMX": "MX", "BBVAMX": "MX",
    "BDBCO": "CO",
    "SUBS": "AR",
}


def _backfill_country_from_partner(df: pd.DataFrame) -> pd.DataFrame:
    if "partner" not in df.columns:
        return df
    if "country" in df.columns:
        missing = df["country"] == "N/D"
        df.loc[missing, "country"] = df.loc[missing, "partner"].map(PARTNER_COUNTRY).fillna("N/D")
    if "country_code" in df.columns:
        missing = df["country_code"] == "N/D"
        df.loc[missing, "country_code"] = df.loc[missing, "partner"].map(PARTNER_COUNTRY_CODE).fillna("N/D")
    return df


def clean_acum(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["processing_date"] = df["processing_date"].apply(_fix_date)
    df = df.dropna(subset=["processing_date"])
    for col in ["points", "descuento_consumo_puntos_usd",
                "comision", "fee", "descuentos", "gb_basebi", "gb_basebi_2"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round(2)
    # Ratio (0-1 aprox) — mas precision que los montos en USD.
    if "pct_pagado_con_puntos" in df.columns:
        df["pct_pagado_con_puntos"] = pd.to_numeric(df["pct_pagado_con_puntos"], errors="coerce").fillna(0).round(6)
    str_cols = ["country_code", "partner", "point_type", "business", "product",
                "country", "payment_type", "channel_condition", "trip_type",
                "produto_original", "legal_entity", "concatenado"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].fillna("N/D").astype(str)
    # "produto" viene como ARRAY(varchar) de Presto (array_agg) — lo normalizamos
    # a string para que sea un valor simple y predecible en el JSON de salida.
    if "produto" in df.columns:
        df["produto"] = df["produto"].apply(
            lambda v: ", ".join(v) if isinstance(v, (list, tuple))
            else ("" if pd.isna(v) else str(v))
        )
    df = _backfill_country_from_partner(df)
    return df


def clean_reden(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["processing_date"] = df["processing_date"].apply(_fix_date)
    df = df.dropna(subset=["processing_date"])
    for col in ["points", "descuento_consumo_puntos_usd"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round(2)
    str_cols = ["product", "country_code", "partner", "point_type", "business",
                "country", "produto_original", "channel_condition", "payment_type",
                "produto_agrupado", "legal_entity"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].fillna("N/D").astype(str)
    df = _backfill_country_from_partner(df)
    return df


def clean_breakage(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    if "points" in df.columns:
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).round(0).astype(int)
    for col in ["expiration_date", "country", "tier"]:
        if col in df.columns:
            df[col] = df[col].fillna("N/D").astype(str)
    if "points_type_id" in df.columns:
        df["points_type_id"] = pd.to_numeric(df["points_type_id"], errors="coerce").fillna(0).astype(int)
    return df


# Nombre de pais que emite _MIEMBROS_SQL -> dataKey del dashboard (mismo criterio
# que CC_TO_DATAKEY pero desde el nombre en mayusculas).
MIEMBROS_PAIS_TO_DATAKEY = {
    "BRASIL": "brasil", "ARGENTINA": "argentina", "MEXICO": "mexico",
    "ECUADOR": "ecuador", "COLOMBIA": "colombia", "PERU": "peru", "URUGUAY": "uruguay",
}
TIER_ORDER = {"Viajero": 0, "Explorador": 1, "Global": 2, "Sin tier": 3}


def clean_miembros(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el snapshot de miembros a cols [ym, country, tier, clientes],
    con country en dataKey del dashboard ('brasil', ...) y agregado por las 3."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["fecha"])
    df["ym"]      = df["fecha"].astype(str).str.slice(0, 7)
    df["country"] = (df["pais"].astype(str).str.strip().str.upper()
                       .map(MIEMBROS_PAIS_TO_DATAKEY).fillna("otro"))
    df["tier"]    = df["tier"].fillna("Sin tier").astype(str).str.strip()
    df.loc[~df["tier"].isin(TIER_ORDER), "tier"] = "Sin tier"
    df["clientes"] = pd.to_numeric(df["clientes"], errors="coerce").fillna(0).round(0).astype(int)
    _sin_map = df.loc[df["country"] == "otro", "pais"].astype(str).str.strip().str.upper()
    if not _sin_map.empty:
        _det = _sin_map.value_counts().to_dict()
        print(f"  [WARN] miembros: {int(_sin_map.shape[0]):,} filas con pais sin mapear, descartadas: {_det}")
    df = df[(df["country"] != "otro") & (df["ym"].str.len() == 7)]
    out = (df.groupby(["ym", "country", "tier"], as_index=False)
             .agg(clientes=("clientes", "sum")))
    out = out.sort_values(
        ["ym", "country", "tier"],
        key=lambda s: s.map(TIER_ORDER) if s.name == "tier" else s,
    ).reset_index(drop=True)
    return out[["ym", "country", "tier", "clientes"]]


CDD_PLANS = ["Plan 1", "Plan 2", "Plan 3", "Plan 4"]
CDD_SERIE_ORDER = {"stock": 0, "alta": 1, "baja": 2}


def clean_club_despegar(df: pd.DataFrame) -> pd.DataFrame:
    """Club Despegar a [ym, country, plan_type, serie, n]. serie: stock | alta | baja.
    country fijo 'argentina' (Club Despegar solo aplica a AR)."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["ym"])
    df["ym"] = df["ym"].astype(str).str.slice(0, 7)
    df = df[df["ym"].str.len() == 7]
    df["plan_type"] = df["plan_type"].fillna("Otro").astype(str).str.strip()
    df.loc[~df["plan_type"].isin(CDD_PLANS), "plan_type"] = "Otro"
    df["serie"]   = df["serie"].astype(str).str.strip().str.lower()
    _bad_serie = df.loc[~df["serie"].isin(CDD_SERIE_ORDER), "serie"]
    if not _bad_serie.empty:
        print(f"  [WARN] club despegar: {int(_bad_serie.shape[0]):,} filas con serie inesperada, "
              f"descartadas: {_bad_serie.value_counts().to_dict()}")
    df = df[df["serie"].isin(CDD_SERIE_ORDER)]
    df["country"] = "argentina"
    df["n"] = pd.to_numeric(df["n"], errors="coerce").fillna(0).round(0).astype(int)
    out = (df.groupby(["ym", "country", "plan_type", "serie"], as_index=False)
             .agg(n=("n", "sum")))
    out = out.sort_values(
        ["serie", "ym", "plan_type"],
        key=lambda s: s.map(CDD_SERIE_ORDER) if s.name == "serie" else s,
    ).reset_index(drop=True)
    return out[["ym", "country", "plan_type", "serie", "n"]]


def clean_ifood_enroll(df: pd.DataFrame) -> pd.DataFrame:
    """Altas de enrolamiento iFood agregadas a [ym, tipo, n]. tipo: iFood enrol | Club iFood."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["ym"])
    df["ym"]   = df["ym"].astype(str).str.slice(0, 7)
    df = df[df["ym"].str.len() == 7]
    df["tipo"] = df["tipo"].astype(str).str.strip()
    df["n"]    = pd.to_numeric(df["n"], errors="coerce").fillna(0).round(0).astype(int)
    out = (df.groupby(["ym", "tipo"], as_index=False).agg(n=("n", "sum")))
    return out.sort_values(["ym", "tipo"]).reset_index(drop=True)[["ym", "tipo", "n"]]


def to_compact(df: pd.DataFrame) -> dict:
    """Formato cols+rows: reduce ~75% el tamaño del JSON vs records."""
    return {"cols": list(df.columns), "rows": df.values.tolist()}


# ------------------------------------------------------------------------------
# SSP / precio del punto — factor (SSP − breakage esperado) por país y mes.
# Reemplaza la constante SSP_BREAKAGE hardcodeada en el dashboard.
#   SSP_Calculado[país][mes] = Σ descuento_consumo_puntos_usd / Σ points
#       sobre redenciones "Pasaporte D!" (point_type = 'general'), por país.
#   SSP_Facturación = SSP_Calculado · (1 − breakage_esperado[país][mes])
# (mismo criterio que la hoja "SSP Facturación" del cierre mensual de Loyalty).
# ------------------------------------------------------------------------------
CC_TO_DATAKEY = {"AR": "argentina", "BR": "brasil", "CO": "colombia", "EC": "ecuador",
                 "MX": "mexico", "PE": "peru", "UY": "uruguay", "CL": "chile"}
# Base del SSP ($/punto): las redenciones que HISTORICAMENTE eran 'general' antes de
# separar Cobrand/Partners en el CASE de _REDEN_SQL. Se reincorporan 'cobrand'/'partners'
# (el CASE emite COBRAND/PARTNERS; aca se comparan en minuscula por el .str.lower() de
# build_ssp_json) para que el factor SSP y la valuacion USD de acumulaciones NO cambien
# por el split de programas del dashboard. El dashboard igual muestra Cobrand/Partners
# como programas propios (via dict.reden), pero el SSP sigue sobre el pool completo.
PASAPORTE_D_REDEN = {"general", "cobrand", "partners"}


_CONFIG_CACHE = {}
# Se pone True si NO se pudo leer la planilla de config y se cayó a los archivos
# locales (breakage_esperado.csv / Diccionario.xlsx). Esos archivos son un fallback
# desactualizado a propósito — si el sync real termina con esto en True, los números
# de breakage / mapeo de programas pueden estar mal. Se chequea al final del script.
USO_FALLBACK_CONFIG = False


def config_sheet_tab(tab: str):
    """DataFrame de una pestaña de la planilla de config, o None si no se puede leer."""
    if DRY_RUN:
        return None
    global USO_FALLBACK_CONFIG
    if "tabs" not in _CONFIG_CACHE:
        tabs = {}
        try:
            svc = _get_drive_service()
            data = svc.files().export_media(
                fileId=CONFIG_SHEET_ID,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ).execute()
            tabs = pd.read_excel(io.BytesIO(data), sheet_name=None)
            print(f"  [config] planilla OK — pestañas: {list(tabs)}")
        except Exception as e:
            print(f"  [config] planilla no disponible ({str(e)[:120]}) → archivos locales")
            USO_FALLBACK_CONFIG = True
        _CONFIG_CACHE["tabs"] = tabs
    return _CONFIG_CACHE["tabs"].get(tab)


def load_breakage_esperado() -> dict:
    """{(country_code, 'YYYY-MM'): factor_reconocido}  con factor = 1 − breakage_esperado."""
    df = config_sheet_tab("breakage_esperado")
    src = "planilla"
    if df is None:
        path = Path(BREAKAGE_ESP_CSV)
        if not path.exists():
            print(f"  [SSP] sin breakage esperado (ni planilla ni {path.name}) → factor 1")
            return {}
        df = pd.read_csv(path, dtype=str)
        src = path.name
    df.columns = [str(c).strip().lower() for c in df.columns]
    out = {}
    for _, r in df.iterrows():
        cc = str(r.get("country_code", "")).strip().upper()
        ym = str(r.get("month", "")).strip()[:7]
        be = pd.to_numeric(r.get("breakage_esperado"), errors="coerce")
        if not cc or len(ym) != 7 or pd.isna(be):
            continue
        out[(cc, ym)] = 1.0 - float(be)
    print(f"  [SSP] breakage esperado: {len(out)} celdas país×mes desde {src}")
    return out


def build_ssp_json(*reden_clean_dfs) -> bytes:
    frames = [d for d in reden_clean_dfs if d is not None and len(d)]
    if not frames:
        raise RuntimeError(
            "build_ssp_json: 0 filas de redención — el SSP no se puede calcular. "
            "Probablemente una query de redenciones falló o devolvió vacío.")
    df = pd.concat(frames, ignore_index=True)
    df = df[df["point_type"].astype(str).str.lower().isin(PASAPORTE_D_REDEN)].copy()
    df["ym"]     = df["processing_date"].str.slice(0, 7)
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).abs()
    df["usd"]    = pd.to_numeric(df["descuento_consumo_puntos_usd"], errors="coerce").fillna(0).abs()
    g = (df.groupby(["country_code", "ym"], as_index=False)
           .agg(points=("points", "sum"), usd=("usd", "sum")))
    g = g[g["points"] > 0]

    brk = load_breakage_esperado()
    out = {}
    _dropped = set()
    for _, r in g.iterrows():
        dk = CC_TO_DATAKEY.get(str(r["country_code"]).strip().upper())
        if not dk:
            _dropped.add(str(r["country_code"]).strip().upper())
            continue
        ym       = r["ym"]
        ssp_calc = -abs(r["usd"] / r["points"])            # negativo, como en el cierre
        factor   = brk.get((str(r["country_code"]).strip().upper(), ym), 1.0)
        out.setdefault(dk, {})[ym] = {
            "ssp_calculado":     round(ssp_calc, 6),
            "breakage_esperado": round(1.0 - factor, 4),
            "ssp_facturacion":   round(ssp_calc * factor, 6),
            "puntos":            round(float(r["points"]), 0),
        }
    payload = {
        "meta": {"generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                 "fuente": "redenciones Pasaporte D! (point_type=general) / breakage_esperado.csv"},
        "data": out,
    }
    for dk in sorted(out):
        meses = sorted(out[dk])
        print(f"  [SSP] {dk:10s} {meses[0]}..{meses[-1]}  ({len(meses)} meses)")
    if _dropped:
        print(f"  [WARN] SSP: country_code sin mapear, filas descartadas: {sorted(_dropped)} "
              f"(agregar a CC_TO_DATAKEY si es un país nuevo)")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


# ------------------------------------------------------------------------------
# Agregación mensual — el dashboard sólo consume nivel
# mes + país + partner + point_type (programa = partner+point_type). Colapsar
# acá baja el JSON de ~50 MB a ~1-2 MB y evita el límite de blob de 50 MB de
# Apps Script (que dejaba la serie LY en cero al no poder leer el archivo).
# ------------------------------------------------------------------------------
_AGG_KEYS = ["processing_date", "country", "country_code", "partner", "point_type"]


def aggregate_acum(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["processing_date"] = df["processing_date"].str.slice(0, 7) + "-01"
    # Puntos CON signo (sin abs()). _ACUM_SQL trae dos ramas — Accumulation
    # (positivo) y Cancellation (ya negado con *-1 en la query) — para que al
    # sumar por mes/país/partner/point_type la cancelación reste del accrual.
    # El abs() que había acá anulaba esa resta: cualquier partner/point_type
    # con cancelaciones quedaba sumado en vez de neteado (accrual + |cancel|
    # en vez de accrual − cancel). Confirmado contra el bajada real del cierre
    # de 06-2026 (Pasaporte D!/DP+general: el cierre neta a 234,6M vía SUMA
    # simple de la columna con signo; con abs() salían 259,2M, +24,6M de más
    # solo en ese mes — para el año completo la sobreestimación es ~+157%).
    # Impacto medido (2026, todos los partner/point_type): +5.814M puntos de
    # más sobre un total correcto de 18.026M (+32%), concentrado casi 100% en
    # DP/general (Pasaporte D!) y FORTUNE/FORTUNE — el resto de los programas
    # no tiene cancelaciones registradas y no cambia.
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
    for c in ("comision", "fee", "descuentos", "pct_pagado_con_puntos"):
        if c not in df.columns:
            df[c] = 0.0
    # Valor USD base de acumulaciones, pre-calculado por fila (el factor
    # SSP-breakage por país lo aplica el dashboard sobre este total).
    df["acum_usd_base"] = (
        (df["comision"].astype(float) + df["fee"].astype(float) + df["descuentos"].astype(float))
        * (1.0 - df["pct_pagado_con_puntos"].astype(float))
    ).abs()
    out = (df.groupby(_AGG_KEYS, as_index=False, dropna=False)
             .agg(points=("points", "sum"),
                  acum_usd_base=("acum_usd_base", "sum")))
    out["points"] = out["points"].round(2)
    out["acum_usd_base"] = out["acum_usd_base"].round(4)
    return out


# ------------------------------------------------------------------------------
# Ratio de acumulación (puntos otorgados / GB) — Pasaporte D! genuino (09-sep)
# ------------------------------------------------------------------------------
# Definición confirmada por Rosario: SUM(points) / SUM(GB), por producto, SOLO
# sobre point_type='general' (partner=DP, "Pasaporte D! genuino" — no Cobrand/
# Partners/IFOOD/etc.). GB = gb_basebi_2 (gross_booking), ya neteado por el fix
# de net_pts_combo>0 del 2026-09-09 (commit 83dd0bf) — antes se inflaba con GB
# de reservas cuyos puntos general fueron cancelados.
#
# Se corre ANTES de aggregate_acum(), que descarta 'produto' (nombre de
# producto) y 'gb_basebi_2' al agregar por partner+point_type — acá sí hacen
# falta, así que este agregado toma como input el DataFrame ya limpio
# (clean_acum + apply_wclube + apply_acum_er_country) pero SIN pasar por
# aggregate_acum().
#
# "Producto" en el output = grupo del P&L (mismo criterio que usa Control de
# Gestión para armar el P&L), NO el código crudo de Comarch — viene de la
# pestaña 'regla producto' del Sheet Config (ver load_regla_producto()).
# Orden de match en _grupo() (fix 11-sep): primero 'produto_original'
# (b.purchase_type, a nivel de RESERVA completa — la única señal real de
# "esto es un paquete/combo", ej. 'Carrito'/'Bundles'/'Escapadas'); si no
# matchea, 'produto' (array_agg(product_type) de _ACUM_SQL, normalizado a
# string en clean_acum, a nivel de LINEA de producto — NO una columna
# 'produto_agrupado', esa solo existe en _REDEN_SQL); por último el código
# Comarch. Antes de este fix solo se miraba produto→código, y como "paquete"
# nunca es un product_type de línea, todo el volumen de Carrito/Bundles/
# Escapadas se colaba silenciosamente bajo el código del componente ancla
# (typ. FLIGHT), inflando esa categoría y dejando Packages General/Vacation
# Rentals en cero.
_PASAPORTE_GENERAL_POINT_TYPE = "general"


def load_regla_producto() -> tuple[dict, dict]:
    """(by_name, by_code): mapeo producto → grupo P&L, desde la pestaña
    'regla producto' del Sheet Config (fallback: regla_producto.csv).

    La tabla mezcla en la misma columna llave nombres de produto_agrupado
    (ej. 'Vuelos', 'Hoteles') y códigos de product (ej. 'FLIGHT', 'HOTEL') —
    regla de Rosario (09-sep): buscar primero por produto_agrupado (nombre);
    si no matchea (viene vacío o no está en la tabla), caer a product (código).
    by_name usa la key tal cual (nombres, case-sensitive); by_code la uppercasea
    (los códigos reales de comarch_accumulation_report.product son siempre
    mayúsculas, pero el Sheet no siempre respeta el casing — ej. 'Transfer').
    """
    df = config_sheet_tab("regla producto")
    src = "planilla"
    if df is None:
        path = Path(REGLA_PRODUCTO_CSV)
        if not path.exists():
            print(f"  [WARN] ratio acum: sin 'regla producto' (ni planilla ni {path.name}) "
                  f"→ todo cae a 'Sin clasificar'")
            return {}, {}
        df = pd.read_csv(path, header=None)
        src = path.name
    else:
        df = df.copy()
    df = df.iloc[:, :2]
    df.columns = ["key", "grupo_pnl"]
    df = df.dropna(subset=["key", "grupo_pnl"])
    by_name, by_code = {}, {}
    for _, r in df.iterrows():
        key = str(r["key"]).strip()
        grupo = str(r["grupo_pnl"]).strip()
        if not key or not grupo:
            continue
        by_name[key] = grupo
        by_code[key.upper()] = grupo
    print(f"  [ratio acum] regla producto: {len(by_name)} filas desde {src}")
    return by_name, by_code


def aggregate_ratio_acum(df: pd.DataFrame, by_name: dict, by_code: dict) -> pd.DataFrame:
    cols = ["processing_date", "country", "country_code", "grupo_pnl", "points", "gb"]
    d = df[df["point_type"].astype(str).str.lower() == _PASAPORTE_GENERAL_POINT_TYPE].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["processing_date"] = d["processing_date"].str.slice(0, 7) + "-01"
    d["points"] = pd.to_numeric(d["points"], errors="coerce").fillna(0)
    d["gb_basebi_2"] = pd.to_numeric(d.get("gb_basebi_2", 0), errors="coerce").fillna(0)

    def _grupo(row):
        # FIX 11-sep: 'produto_original' (= b.purchase_type, a nivel de RESERVA
        # completa) se chequea primero. Es la unica senial que distingue un
        # combo/paquete (ej. "Carrito", "Bundles", "Escapadas") — estos valores
        # NUNCA aparecen en 'produto' (array_agg de product_type, a nivel de
        # LINEA de producto), porque "paquete" no es un product_type de linea,
        # es una propiedad de la reserva completa. Sin este chequeo, un combo
        # vuelo+hotel+seguro se clasificaba con el codigo Comarch del componente
        # ancla (casi siempre FLIGHT), inflando Flights con puntos de paquetes
        # completos sin su GB correspondiente (GB solo cuenta el JOIN del
        # componente que matchea ese codigo) y dejando Packages General/Vacation
        # Rentals siempre en cero pese a tener volumen real (confirmado con
        # Rosario contra el datalake real, 11-sep).
        original = str(row.get("produto_original", "")).strip()
        if original in by_name:
            return by_name[original]
        # 'produto' viene de array_agg(product_type) en Presto SIN ORDER BY interno
        # -> el orden de los elementos no esta garantizado entre corridas cuando una
        # fila agrupa varios product_type distintos. sorted() hace que "el primero
        # que matchea" sea determinístico (aunque arbitrario) en vez de depender del
        # orden que devuelva Presto esa corrida.
        nombres = sorted(n.strip() for n in str(row.get("produto", "")).split(",") if n.strip())
        for n in nombres:
            if n in by_name:
                return by_name[n]
        codigo = str(row.get("product", "")).strip().upper()
        return by_code.get(codigo)

    d["grupo_pnl"] = d.apply(_grupo, axis=1)
    sin_map = d[d["grupo_pnl"].isna()]
    if len(sin_map):
        combos = sorted(set(zip(sin_map["produto_original"], sin_map["produto"], sin_map["product"])))
        pts = sin_map["points"].sum()
        print(f"  [WARN] ratio acum: {len(combos)} combinaciones producto/código sin grupo P&L "
              f"en 'regla producto' ({pts:,.0f} pts → 'Sin clasificar'): {combos}")
    d["grupo_pnl"] = d["grupo_pnl"].fillna("Sin clasificar")

    out = (d.groupby(["processing_date", "country", "country_code", "grupo_pnl"],
                      as_index=False, dropna=False)
             .agg(points=("points", "sum"), gb=("gb_basebi_2", "sum")))
    out["points"] = out["points"].round(2)
    out["gb"] = out["gb"].round(2)
    return out[cols]


# ------------------------------------------------------------------------------
# Valuación USD de Cobrand / Partners por PRECIO DE FACTURACIÓN (Input_Precios.xlsx)
# ------------------------------------------------------------------------------
# Cobrand y Partners no generan `acum_usd_base` (no hay comisión/GB de viaje detrás),
# así que el dashboard los mostraba en $0. Acá se calcula `acum_usd_precio` = puntos ×
# precio_facturacion, con el precio por país + point_type (Cobrand) o país + partner
# (Partners) y ventana [fecha_inicio, fecha_fin]. Si el precio está en moneda local
# (BRL / MXN) se pasa a USD con el FX del mes (solapa FX_Currency). El dashboard usa
# esta columna para esos dos programas y sigue con acum_usd_base×SSP para el resto.
_COBRAND_PARTNERS  = {"ICBCAR", "INVEXMX", "BDBCO"}
_PARTNERS_PARTNERS = {"FOCOAR", "BONDAAR", "MASLOWAR", "NOMADBR", "GETNET",
                      "C6BANKBR", "BRBBR", "ENTREGOBR", "KIDDLEBR", "BBVAMX"}
_PAIS_A_CC = {"mexico": "MX", "méxico": "MX", "argentina": "AR", "colombia": "CO",
              "brasil": "BR", "brazil": "BR", "chile": "CL", "peru": "PE", "perú": "PE",
              "uruguay": "UY", "ecuador": "EC"}
_PRECIOS_CACHE = {}


def _load_precios():
    """(cobrand_df, partners_df, fx) desde Input_Precios.xlsx.
    fx = {(MONEDA, 'YYYY-MM'): rate}. Devuelve (None, None, {}) si no hay archivo."""
    if "v" in _PRECIOS_CACHE:
        return _PRECIOS_CACHE["v"]
    path = next((p for p in PRECIOS_XLSX_CANDIDATES if p and Path(p).exists()), None)
    if not path:
        print("  [precios] Input_Precios.xlsx no encontrado (ni env PRECIOS_XLSX, ni "
              "OneDrive, ni copia local) → acum_usd_precio = 0 para Cobrand/Partners")
        _PRECIOS_CACHE["v"] = (None, None, {})
        return _PRECIOS_CACHE["v"]

    sheets = pd.read_excel(path, sheet_name=None)

    def _norm_precio(df):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        df["cc"] = df["pais"].astype(str).str.strip().str.lower().map(_PAIS_A_CC)
        df["fi"] = pd.to_datetime(df["fecha_inicio"], errors="coerce")
        df["ff"] = pd.to_datetime(df["fecha_fin"], errors="coerce")
        df["moneda"] = df["moneda"].astype(str).str.strip().str.upper()
        df["precio_facturacion"] = pd.to_numeric(df["precio_facturacion"], errors="coerce")
        if "point_type" in df.columns:
            df["point_type"] = df["point_type"].astype(str).str.strip()
        if "partner" in df.columns:
            df["partner"] = df["partner"].astype(str).str.strip()
        return df.dropna(subset=["cc", "fi", "ff", "precio_facturacion"])

    cob = _norm_precio(sheets["Cobrand"])
    par = _norm_precio(sheets["Partners"])

    fxdf = sheets["FX_Currency"].copy()
    fxdf.columns = [str(c).strip().lower() for c in fxdf.columns]
    fxcol = "fx_cuerrency" if "fx_cuerrency" in fxdf.columns else "fx_currency"
    fxdf["moneda"] = fxdf["moneda"].astype(str).str.strip().str.upper()
    fxdf["ym"] = pd.to_datetime(fxdf["fecha"], errors="coerce").dt.strftime("%Y-%m")
    fxdf[fxcol] = pd.to_numeric(fxdf[fxcol], errors="coerce")
    fxdf = fxdf.dropna(subset=["moneda", "ym", fxcol])
    fx = {(r["moneda"], r["ym"]): float(r[fxcol]) for _, r in fxdf.iterrows()}

    print(f"  [precios] {Path(path).name} OK — cobrand {len(cob)} filas · "
          f"partners {len(par)} filas · fx {len(fx)} puntos")
    _PRECIOS_CACHE["v"] = (cob, par, fx)
    return _PRECIOS_CACHE["v"]


def _fx_rate(fx: dict, moneda: str, ym: str):
    """Rate del mes; si falta, el último mes disponible <= ym; si no, el más viejo."""
    if (moneda, ym) in fx:
        return fx[(moneda, ym)]
    yms = sorted(k[1] for k in fx if k[0] == moneda)
    if not yms:
        return None
    prev = [y for y in yms if y <= ym]
    return fx[(moneda, prev[-1])] if prev else fx[(moneda, yms[0])]


def apply_precios_facturacion(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna `acum_usd_precio` al df de acumulaciones agregado."""
    cob, par, fx = _load_precios()
    if cob is None:
        df = df.copy()
        df["acum_usd_precio"] = 0.0
        return df

    sin_precio, sin_fx = {}, {}

    def _valor(row):
        cc = str(row.country_code or "").strip().upper()
        partner = str(row.partner or "").strip()
        if cc in ("", "N/D"):
            cc = PARTNER_COUNTRY_CODE.get(partner, "N/D")
        es_cob = partner in _COBRAND_PARTNERS
        es_par = partner in _PARTNERS_PARTNERS
        if not (es_cob or es_par):
            return 0.0
        ym = str(row.processing_date)[:7]
        ts = pd.Timestamp(ym + "-01")
        if es_cob:
            m = cob[(cob["cc"] == cc) & (cob["point_type"] == str(row.point_type).strip())
                    & (cob["fi"] <= ts) & (cob["ff"] >= ts)]
        else:
            m = par[(par["cc"] == cc) & (par["partner"] == partner)
                    & (par["fi"] <= ts) & (par["ff"] >= ts)]
        if len(m) == 0:
            sin_precio[(cc, partner, str(row.point_type))] = \
                sin_precio.get((cc, partner, str(row.point_type)), 0) + (row.points or 0)
            return 0.0
        r = m.iloc[-1]  # si hay solapamiento de ventanas, gana la última fila
        local = (row.points or 0) * float(r["precio_facturacion"])
        if r["moneda"] == "USD":
            return round(local, 2)
        rate = _fx_rate(fx, r["moneda"], ym)
        if not rate:
            sin_fx[(r["moneda"], ym)] = sin_fx.get((r["moneda"], ym), 0) + (row.points or 0)
            return 0.0
        return round(local / rate, 2)

    df = df.copy()
    df["acum_usd_precio"] = [_valor(r) for r in df.itertuples(index=False)]

    if sin_precio:
        tot = sum(sin_precio.values())
        print(f"  [WARN] precios: {len(sin_precio)} combinaciones Cobrand/Partners sin "
              f"precio en Input_Precios.xlsx ({tot:,.0f} puntos → $0): "
              f"{ {k: round(v) for k, v in sin_precio.items()} }")
    if sin_fx:
        print(f"  [WARN] precios: sin FX para {sorted(sin_fx)} → esas filas quedan en $0")
    return df


# ------------------------------------------------------------------------------
# IFOOD Welcome Clube — accruals via transaction_type 'CA'
# ------------------------------------------------------------------------------
# Los accruals reales de IFOOD Welcome Clube entran como transaction_type='CA'
# (point code IFO_WE_CLU) en clm_transactions y NO estan en comarch_accumulation_report,
# por eso faltaban en acumulaciones. En comarch si estan los REVERSOS bajo el name largo
# IFOOD_WELCOME_CLUBE (puntos negativos), que se contaban mal como acumulacion (el
# pipeline hacia abs() por fila — aggregate_acum ya no, ver gotcha del abs() en CLAUDE.md,
# pero esta exclusion sigue siendo la decision correcta igual, ver mas abajo). Los
# reversos caen casi todos en un mes (jul-2026) y no se
# alinean con los accruals (may-jul), asi que netear mensualmente daria barras negativas.
# Decision (Rosario, 2026-08-31): mostrar los accruals BRUTOS (~10.04B YTD) e ignorar los
# reversos. Por eso: (1) se excluye IFOOD_WELCOME_CLUBE del accrual de comarch, y (2) se
# suman los CA/IFO_WE_CLU como fuente nueva. Pais = Brasil (IFOOD es solo BR; el CA viene
# sin pais ni codigo de transaccion). Ver BITACORA 2026-08-31.
WCLUBE_ACCRUAL_CODE = "IFO_WE_CLU"           # code corto en clm_transactions (accruals +)
WCLUBE_REVERSO_PT   = "IFOOD_WELCOME_CLUBE"  # name largo en comarch (reversos -)

_WCLUBE_CA_SQL = """
SELECT CAST(t.processing_date AS DATE) AS processing_date,
       SUM(tp.points)                  AS points
FROM data.lake.clm_transactions t
JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
WHERE t.processing_date >= {{Desde}}
  AND t.processing_date <  {{Hasta}}
  AND t.status = 'B'
  AND t.transaction_type = 'CA'
  AND pt.code = 'IFO_WE_CLU'
GROUP BY CAST(t.processing_date AS DATE)
"""


def fetch_wclube_ca(desde: str, hasta: str) -> pd.DataFrame:
    """Accruals de IFOOD Welcome Clube (transaction_type='CA', code IFO_WE_CLU) por dia,
    con las columnas que espera aggregate_acum. Pais fijo Brasil (el CA viene sin pais)."""
    df = fetch(_sub(_WCLUBE_CA_SQL, desde, hasta), "WClube CA (IFOOD accruals)")
    if df.empty:
        return df
    df["processing_date"] = df["processing_date"].apply(_fix_date)
    df = df.dropna(subset=["processing_date"])
    df["points"]       = pd.to_numeric(df["points"], errors="coerce").fillna(0)
    df["country"]      = "Brasil"
    df["country_code"] = "BR"
    df["partner"]      = "N/D"
    df["point_type"]   = WCLUBE_ACCRUAL_CODE
    # Welcome Clube no tiene valor USD de acumulacion (no joinea BI); 0 para que
    # acum_usd_base no salga NaN al concatenar con el df de acumulaciones.
    for c in ("comision", "fee", "descuentos", "pct_pagado_con_puntos"):
        df[c] = 0.0
    return df


def apply_wclube(df_acum: pd.DataFrame, desde: str, hasta: str) -> pd.DataFrame:
    """Saca los reversos IFOOD_WELCOME_CLUBE del accrual de comarch y agrega los accruals
    reales (CA/IFO_WE_CLU). Se aplica sobre el df ya limpiado, antes de aggregate_acum."""
    if "point_type" in df_acum.columns:
        df_acum = df_acum[df_acum["point_type"] != WCLUBE_REVERSO_PT].copy()
    ca = fetch_wclube_ca(desde, hasta)
    if ca is not None and len(ca):
        df_acum = pd.concat([df_acum, ca], ignore_index=True)
    return df_acum


# ------------------------------------------------------------------------------
# Fallback de país para accruals 'ER' sin reserva de viaje asociada (FORTUNE/
# MISSIONS: campañas/misiones que no traen ar1.country ni dsp_transaction_id en
# comarch_accumulation_report, así que el JOIN contra la reserva de _ACUM_SQL
# nunca les resuelve país — quedaban 100% en 'N/D', invisibles en el dashboard
# en todos los países y hasta en TOTAL). Va en query APARTE a propósito: sumar
# este JOIN adentro de _ACUM_SQL tira en Presto "Number of stages (61) exceeds
# the allowed maximum (60)" — esa query ya está en el límite. Resuelve vía
# clm_transaction_id -> clm_transactions.account_id -> clm_customers.ext_country_program
# (mismo campo que ya usan Breakage/Miembros). Validado con query diagnóstica
# contra el datalake (2026): 100% de los puntos resuelven, 0 perdidos.
# Incluye tambien la cancelacion (comarch_cancellation_report, negada) para
# netear igual que _ACUM_SQL — sin esto quedaría el mismo bug de abs() que
# aggregate_acum (ver mas abajo) para estos dos point_type puntualmente.
# ------------------------------------------------------------------------------
_ACUM_ER_COUNTRY_SQL = """
SELECT processing_date, country_code, partner, point_type, SUM(points) AS points
FROM (
    SELECT CAST(ar1.processing_date AS DATE) AS processing_date
         , cm.ext_country_program              AS country_code
         , ar1.partner
         , ar1.point_type
         , ar1.points                          AS points
    FROM data.lake.comarch_accumulation_report ar1
    JOIN data.lake.clm_transactions t ON t.id = ar1.clm_transaction_id
    JOIN data.lake.clm_customers cm  ON cm.account_id = t.account_id
    WHERE ar1.processing_date >= {{Desde}}
      AND ar1.processing_date <  {{Hasta}}
      AND COALESCE(ar1.dsp_transaction_type,'Nulo') <> 'REFUND'
      AND ar1.point_type IN ('FORTUNE','MISSIONS')

    UNION ALL

    -- Cancelaciones (negadas) de esos mismos accruals — sin esto se repite el
    -- mismo bug de aggregate_acum (abs() neutraliza la resta) para estos dos
    -- point_type especificamente. Mismo mecanismo de pais (clm_transaction_id).
    SELECT CAST(cr1.generation_date AS DATE) AS processing_date
         , cm.ext_country_program              AS country_code
         , cr1.partner
         , cr1.point_type
         , (cr1.points * -1)                    AS points
    FROM data.lake.comarch_cancellation_report cr1
    JOIN data.lake.clm_transactions t ON t.id = cr1.clm_transaction_id
    JOIN data.lake.clm_customers cm  ON cm.account_id = t.account_id
    WHERE cr1.generation_date >= {{Desde}}
      AND cr1.generation_date <  {{Hasta}}
      AND cr1.point_type IN ('FORTUNE','MISSIONS')
) u
GROUP BY processing_date, country_code, partner, point_type
"""

_CC_TO_NAME = {
    "AR": "Argentina", "BR": "Brasil", "CO": "Colombia", "EC": "Ecuador",
    "MX": "Mexico", "PE": "Peru", "UY": "Uruguay", "CL": "Chile",
}


def fetch_acum_er_country(desde: str, hasta: str) -> pd.DataFrame:
    df = fetch(_sub(_ACUM_ER_COUNTRY_SQL, desde, hasta), "Acumulaciones (país FORTUNE/MISSIONS)")
    if df.empty:
        return df
    df["processing_date"] = df["processing_date"].apply(_fix_date)
    df = df.dropna(subset=["processing_date"])
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
    df["country_code"] = df["country_code"].fillna("N/D").astype(str)
    df["country"] = df["country_code"].map(_CC_TO_NAME).fillna("N/D")
    for c in ("comision", "fee", "descuentos", "pct_pagado_con_puntos"):
        df[c] = 0.0
    return df


def apply_acum_er_country(df_acum: pd.DataFrame, desde: str, hasta: str) -> pd.DataFrame:
    """Reemplaza las filas FORTUNE/MISSIONS sin país (quedan 'N/D' en _ACUM_SQL)
    por la versión con país resuelto de fetch_acum_er_country(). Solo toca esas
    filas puntuales — si por lo que sea el fallback no resuelve nada, no cambia
    nada (se preserva el 'N/D' de siempre, no se pierden puntos)."""
    if "point_type" not in df_acum.columns or "country" not in df_acum.columns:
        return df_acum
    resolved = fetch_acum_er_country(desde, hasta)
    if resolved is None or not len(resolved):
        return df_acum
    mask_er = df_acum["point_type"].isin(["FORTUNE", "MISSIONS"]) & (df_acum["country"] == "N/D")
    removed_pts = pd.to_numeric(df_acum.loc[mask_er, "points"], errors="coerce").fillna(0).sum()
    resolved_pts = pd.to_numeric(resolved["points"], errors="coerce").fillna(0).sum()
    # Guarda de integridad: sale de _ACUM_SQL el 100% de FORTUNE/MISSIONS con
    # country='N/D' (accrual y cancelación, verificado contra el datalake) — si
    # algún día eso deja de ser así, esta resta no da ~0 y hay que revisar antes
    # de confiar en el reemplazo (podría estar duplicando o perdiendo puntos).
    if abs(removed_pts - resolved_pts) > max(1.0, abs(removed_pts) * 0.001):
        print(f"  [WARN] FORTUNE/MISSIONS: se sacaron {removed_pts:,.0f} puntos (N/D) y "
              f"se agregaron {resolved_pts:,.0f} resueltos — no coinciden, revisar "
              f"antes de confiar en apply_acum_er_country")
    df_acum = pd.concat([df_acum[~mask_er], resolved], ignore_index=True)
    return df_acum


def aggregate_reden(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["processing_date"] = df["processing_date"].str.slice(0, 7) + "-01"
    if "descuento_consumo_puntos_usd" not in df.columns:
        df["descuento_consumo_puntos_usd"] = 0.0
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).abs()
    df["descuento_consumo_puntos_usd"] = pd.to_numeric(
        df["descuento_consumo_puntos_usd"], errors="coerce").fillna(0).abs()
    out = (df.groupby(_AGG_KEYS, as_index=False, dropna=False)
             .agg(points=("points", "sum"),
                  descuento_consumo_puntos_usd=("descuento_consumo_puntos_usd", "sum")))
    out["points"] = out["points"].round(2)
    out["descuento_consumo_puntos_usd"] = out["descuento_consumo_puntos_usd"].round(2)
    return out


# ==============================================================================
# 5) GOOGLE DRIVE
# ==============================================================================

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


_DRIVE_SERVICE = None


def _get_drive_service():
    # Cacheado: upload_to_drive() se llama ~11×/corrida y reconstruir el cliente
    # (leer token, refrescar credenciales, build()) cada vez es puro overhead.
    global _DRIVE_SERVICE
    if _DRIVE_SERVICE is not None:
        return _DRIVE_SERVICE
    _DRIVE_SERVICE = _build_drive_service()
    return _DRIVE_SERVICE


def _build_drive_service():
    import json as _json
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    base       = Path(__file__).resolve().parent
    creds_file = base / "credentials_drive.json"
    token_file = base / "token_drive.json"

    # Auth de Drive = OAuth de usuario, mismo patrón que B2B_Ecosystem: el client
    # compartido credentials_drive.json + token_drive.json personal (lo genera
    # auth_drive.py con la cuenta @despegar.com). El refresh token no expira
    # mientras la consent screen del proyecto GCP esté en modo "Internal".
    if creds_file.exists():
        from google_auth_oauthlib.flow import InstalledAppFlow
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), DRIVE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(creds_file), DRIVE_SCOPES)
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json())
        return build("drive", "v3", credentials=creds)

    clasprc = Path.home() / ".clasprc.json"
    tok     = _json.loads(clasprc.read_text())["tokens"]["default"]
    expiry  = datetime.utcfromtimestamp(tok["expiry_date"] / 1000)
    creds   = Credentials(
        token=tok["access_token"], refresh_token=tok["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tok["client_id"], client_secret=tok["client_secret"],
        expiry=expiry,
    )
    if not creds.valid:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


# Apps Script no puede leer blobs > 50 MB (getDataAsString() tira). Si un JSON se
# acerca, la serie LY de los charts se cae a cero sin aviso (fyYears() -> NaN).
_APPS_SCRIPT_BLOB_LIMIT = 50 * 1024 * 1024
_SIZE_WARN_THRESHOLD    = 45 * 1024 * 1024


def upload_to_drive(json_bytes: bytes, filename: str):
    from googleapiclient.http import MediaInMemoryUpload
    if len(json_bytes) > _SIZE_WARN_THRESHOLD:
        mb = len(json_bytes) / 1024 / 1024
        print(f"  [WARN] {filename} = {mb:.1f} MB — cerca del límite de 50 MB de "
              f"Apps Script. Si lo pasa, el dashboard muestra ceros. Volver a "
              f"agregar más (por mes ya se hace; agregar por trimestre o quitar dims).")
    service = _get_drive_service()
    media   = MediaInMemoryUpload(json_bytes, mimetype="application/json", resumable=False)
    results  = service.files().list(
        q=f"name='{filename}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false",
        fields="files(id,name)"
    ).execute()
    existing = results.get("files", [])
    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        print(f"  OK Drive: actualizado ({filename})")
    else:
        service.files().create(
            body={"name": filename, "parents": [DRIVE_FOLDER_ID]},
            media_body=media, fields="id"
        ).execute()
        print(f"  OK Drive: creado ({filename})")


# ==============================================================================
# 6) MAIN
# ==============================================================================
# Todo lo de abajo corre a nivel de módulo (no hay def main()). Guard mínimo para
# que un `import loyalty_sync` accidental (un test, otro script) NO dispare las
# ~10 queries ni suba a Drive. Refactor a def main() pendiente.
if __name__ != "__main__":
    raise SystemExit(
        "loyalty_sync.py se corre como script, no se importa "
        "(un import dispararía las queries y, sin --dry-run, subiría a Drive). "
        "Usá: python loyalty_sync.py [--dry-run]")

print("\n--- Acumulaciones CY ---")
# _acum_cy_pre queda ANTES de aggregate_acum() (que descarta 'produto'/'gb_basebi_2')
# para que el ratio de acumulación (ver aggregate_ratio_acum) pueda usarlos.
_acum_cy_pre = apply_acum_er_country(apply_wclube(clean_acum(fetch(build_acum_query(ACTUALS_DESDE, ACTUALS_HASTA), f"Acumulaciones {CY_YEAR}")), ACTUALS_DESDE, ACTUALS_HASTA), ACTUALS_DESDE, ACTUALS_HASTA)
df_acum_cy = apply_precios_facturacion(aggregate_acum(_acum_cy_pre))

print("\n--- Acumulaciones LY ---")
_acum_ly_pre = apply_acum_er_country(apply_wclube(clean_acum(fetch(build_acum_query(LY_DESDE, LY_HASTA), f"Acumulaciones {LY_YEAR}")), LY_DESDE, LY_HASTA), LY_DESDE, LY_HASTA)
df_acum_ly = apply_precios_facturacion(aggregate_acum(_acum_ly_pre))

print("\n--- Redenciones CY ---")
_reden_cy_clean = clean_reden(fetch(build_reden_query(ACTUALS_DESDE, ACTUALS_HASTA), f"Redenciones {CY_YEAR}"))
df_reden_cy = aggregate_reden(_reden_cy_clean)

print("\n--- Redenciones LY ---")
_reden_ly_clean = clean_reden(fetch(build_reden_query(LY_DESDE, LY_HASTA), f"Redenciones {LY_YEAR}"))
df_reden_ly = aggregate_reden(_reden_ly_clean)

print("\n--- Breakage ---")
df_breakage = clean_breakage(fetch(build_breakage_query(LY_DESDE), "Breakage"))

print("\n--- Miembros del programa ---")
df_miembros = clean_miembros(fetch(_MIEMBROS_SQL, "Miembros (snapshot base activa)"))

print("\n--- Club Despegar (suscripción AR) ---")
df_club = clean_club_despegar(fetch(_CLUB_DESPEGAR_SQL, "Club Despegar (stock/altas/bajas x plan x mes)"))

print("\n--- iFood enrolados ---")
df_ifood = clean_ifood_enroll(fetch(_IFOOD_ENROLL_SQL, "iFood enrol + Club iFood"))

print("\n--- Ratio de acumulación Pasaporte D! (puntos/GB por producto) ---")
_regla_by_name, _regla_by_code = load_regla_producto()
df_ratio = pd.concat([
    aggregate_ratio_acum(_acum_cy_pre, _regla_by_name, _regla_by_code),
    aggregate_ratio_acum(_acum_ly_pre, _regla_by_name, _regla_by_code),
], ignore_index=True)

print("\n--- Construyendo diccionario de puntos ---")
dict_bytes = build_dict_json()
print(f"  Dict: {len(dict_bytes)} bytes")

print("\n--- Construyendo SSP (precio del punto) ---")
ssp_bytes = build_ssp_json(_reden_cy_clean, _reden_ly_clean)
print(f"  SSP: {len(ssp_bytes)} bytes")

print("\n--- Construyendo JSON ---")

META_CY = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "last_date":    str(YESTERDAY),
    "year":         CY_YEAR,
    "from":         str(ACTUALS_FROM),
    "to":           str(YESTERDAY),
}
META_LY = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "last_date":    str(YESTERDAY),
    "year":         LY_YEAR,
    "from":         str(LY_FROM),
    "to":           str(LY_TO),
}

acum_cy_bytes   = json.dumps({"meta": META_CY, "data": to_compact(df_acum_cy)},  ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
acum_ly_bytes   = json.dumps({"meta": META_LY, "data": to_compact(df_acum_ly)},  ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
reden_cy_bytes  = json.dumps({"meta": META_CY, "data": to_compact(df_reden_cy)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
reden_ly_bytes  = json.dumps({"meta": META_LY, "data": to_compact(df_reden_ly)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
breakage_bytes  = json.dumps({"meta": META_LY, "data": df_breakage.to_dict(orient="records")}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

META_MIEMBROS = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "snapshot_date": str(TODAY),
    "fuente": "clm_customers (status='A') x mes de enrolment x tier; foto del padron actual",
}
miembros_bytes  = json.dumps({"meta": META_MIEMBROS, "data": to_compact(df_miembros)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

META_CLUB = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "snapshot_date": str(TODAY),
    "fuente": "data.raw.membertrip_subscription (una suscripcion por social_id, ACTIVE gana). series: stock (suscripciones vivas a fin de mes) / alta (created_at) / baja (USER_CANCELLED+PENDING por updated_at)",
}
club_bytes  = json.dumps({"meta": META_CLUB, "data": to_compact(df_club)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

META_IFOOD = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "fuente": "analytics.ifood_dim_users; cross_cashback='iFood enrol', closed_loop_discount='Club iFood'; alta = 1er evento de la iniciativa, desde 2025-01",
}
ifood_bytes = json.dumps({"meta": META_IFOOD, "data": to_compact(df_ifood)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

META_RATIO = {
    "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "fuente": "comarch_accumulation_report point_type='general' (Pasaporte D! genuino, partner=DP); "
              "gb = gb_basebi_2 (gross_booking, neteado por combo con net_pts_combo>0 desde 09-sep); "
              "grupo_pnl = pestaña 'regla producto' del Sheet Config, match en orden: purchase_type "
              "de la reserva (detecta paquetes/combos, ej. Carrito/Bundles) -> product_type de linea -> "
              "codigo Comarch (fix 11-sep); "
              "ratio de acumulación = points / gb",
}
ratio_bytes = json.dumps({"meta": META_RATIO, "data": to_compact(df_ratio)}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

_stk = df_club[df_club["serie"] == "stock"]
_club_act = int(_stk[_stk["ym"] == _stk["ym"].max()]["n"].sum()) if len(_stk) else 0
print(f"  Acum {CY_YEAR}:  {len(acum_cy_bytes)//1024:.0f} KB  ({len(df_acum_cy):,} filas)")
print(f"  Acum {LY_YEAR}:  {len(acum_ly_bytes)//1024:.0f} KB  ({len(df_acum_ly):,} filas)")
print(f"  Reden {CY_YEAR}: {len(reden_cy_bytes)//1024:.0f} KB  ({len(df_reden_cy):,} filas)")
print(f"  Reden {LY_YEAR}: {len(reden_ly_bytes)//1024:.0f} KB  ({len(df_reden_ly):,} filas)")
print(f"  Breakage:       {len(breakage_bytes)//1024:.0f} KB  ({len(df_breakage):,} filas)")
print(f"  Miembros:       {len(miembros_bytes)//1024:.0f} KB  ({len(df_miembros):,} filas · {df_miembros['clientes'].sum():,} miembros)")
print(f"  Club Despegar:  {len(club_bytes)//1024:.0f} KB  ({len(df_club):,} filas · {_club_act:,} activos)")
print(f"  iFood enrol:    {len(ifood_bytes)//1024:.0f} KB  ({len(df_ifood):,} filas · {int(df_ifood['n'].sum()):,} altas)")
print(f"  Ratio acum.:    {len(ratio_bytes)//1024:.0f} KB  ({len(df_ratio):,} filas)")

_OUT = [
    (acum_cy_bytes,  ACUM_CY_FILE), (acum_ly_bytes,  ACUM_LY_FILE),
    (reden_cy_bytes, REDEN_CY_FILE), (reden_ly_bytes, REDEN_LY_FILE),
    (breakage_bytes, BREAKAGE_FILE), (dict_bytes, DICT_FILE), (ssp_bytes, SSP_FILE),
    (miembros_bytes, MIEMBROS_FILE),
    (club_bytes, CLUB_DESPEGAR_FILE), (ifood_bytes, IFOOD_ENROLL_FILE),
    (ratio_bytes, RATIO_ACUM_FILE),
]

if DRY_RUN:
    out_dir = Path(__file__).resolve().parent / "_out"
    out_dir.mkdir(exist_ok=True)
    print(f"\n--- DRY RUN: escribiendo en {out_dir} (sin subir a Drive) ---")
    for data, name in _OUT:
        (out_dir / name).write_bytes(data)
        print(f"  OK {name}")
    # Peeks útiles para validar cambios de query
    _pt = _reden_cy_clean.groupby("point_type")["points"].apply(lambda s: s.abs().sum())
    print("\n  Redenciones CY por point_type (puntos):")
    for pt, v in _pt.sort_values(ascending=False).items():
        print(f"    {pt:20s} {v:15,.0f}")
    _ssp = json.loads(ssp_bytes)["data"]
    print("\n  SSP por país (último mes):")
    for k in sorted(_ssp):
        last = sorted(_ssp[k])[-1]
        print(f"    {k:10s} {last}  ssp_facturacion={_ssp[k][last]['ssp_facturacion']}")
    print("\n  Miembros activos por país × tier:")
    _piv = df_miembros.pivot_table(index="country", columns="tier", values="clientes",
                                   aggfunc="sum", fill_value=0)
    for c in _piv.index:
        detalle = "  ".join(f"{t}={int(_piv.loc[c, t]):,}" for t in _piv.columns)
        print(f"    {c:10s} total={int(_piv.loc[c].sum()):>10,}   {detalle}")

    _stk2 = df_club[df_club["serie"] == "stock"]
    if len(_stk2):
        _lm = _stk2["ym"].max()
        _cact = _stk2[_stk2["ym"] == _lm].groupby("plan_type")["n"].sum().sort_index()
        print(f"\n  Club Despegar — stock de suscriptos a {_lm}:")
        for p, v in _cact.items():
            print(f"    {p:8s} {int(v):>9,}")
        print(f"    {'TOTAL':8s} {int(_cact.sum()):>9,}")
        _s6 = sorted(_stk2["ym"].unique())[-6:]
        _tot = _stk2[_stk2["ym"].isin(_s6)].groupby("ym")["n"].sum()
        print("    últimos 6 meses:", "  ".join(f"{m}={int(_tot[m]):,}" for m in _s6))
    _ab = df_club[df_club["serie"].isin(["alta", "baja"])].groupby("serie")["n"].sum()
    print(f"    altas total={int(_ab.get('alta', 0)):,}  ·  bajas total={int(_ab.get('baja', 0)):,}")
    print("\n  iFood enrolados — total por tipo:")
    for t, v in df_ifood.groupby("tipo")["n"].sum().items():
        print(f"    {t:14s} {int(v):>9,}")

    if len(df_ratio):
        print("\n  Ratio de acumulación Pasaporte D! por grupo P&L (total periodo, puntos/GB):")
        _rg = df_ratio.groupby("grupo_pnl", as_index=False).agg(points=("points", "sum"), gb=("gb", "sum"))
        _rg["ratio"] = _rg["points"] / _rg["gb"].replace(0, pd.NA)
        for _, r in _rg.sort_values("points", ascending=False).iterrows():
            print(f"    {r['grupo_pnl']:18s} pts={r['points']:>15,.0f}  gb={r['gb']:>15,.0f}  ratio={r['ratio']}")
    else:
        print("\n  Ratio de acumulación: sin filas (revisar point_type='general' / regla producto)")
else:
    print("\n--- Subiendo a Google Drive ---")
    for data, name in _OUT:
        upload_to_drive(data, name)

print(f"\nOK Completado: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

if USO_FALLBACK_CONFIG and not DRY_RUN:
    print(
        "\n  [WARN] La planilla 'Loyalty Ecosystem - Config' no estuvo accesible.\n"
        "         Se usó el fallback local (breakage_esperado.csv / Diccionario.xlsx),\n"
        "         que está desactualizado a propósito y NO cubre CL/UY. Los números de\n"
        "         breakage y el mapeo de programas de esta corrida pueden estar mal.\n"
        "         Revisar el acceso a la planilla y volver a correr."
    )
    sys.exit(2)
