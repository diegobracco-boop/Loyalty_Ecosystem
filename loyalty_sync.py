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

warnings.filterwarnings("ignore")

# ==============================================================================
# 1) CONFIGURACIÓN
# ==============================================================================

RUTA_ENV = r"C:\Users\diego.bracco\Proyectos IA\envs\.env"
DSN_NAME = "DataLake Treasure ODBC"

DRIVE_FOLDER_ID = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"
BREAKAGE_FILE   = "loyalty_breakage.json"
DICT_FILE       = "loyalty_dict.json"
SSP_FILE        = "loyalty_ssp.json"
DICT_XLSX       = r"C:\Users\diego.bracco\Proyectos IA\Loyalty_Ecosystem\Diccionario.xlsx"
# Input manual (lo mantiene Control de Gestión): country_code, month (YYYY-MM), breakage_esperado (0..1).
# País/mes sin fila → breakage esperado = 0 → factor reconocido = 1 (como UY/CL en el cierre).
BREAKAGE_ESP_CSV = r"C:\Users\diego.bracco\Proyectos IA\Loyalty_Ecosystem\breakage_esperado.csv"

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


def conectar():
    import pyodbc
    return pyodbc.connect(
        f"DSN={DSN_NAME};UID={DB_USER};PWD={DB_PASSWORD};",
        autocommit=True
    )


def fetch(query: str, label: str) -> pd.DataFrame:
    print(f"  > {label} ...")
    con = conectar()
    df  = pd.read_sql(query, con)
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
     , SUM(CASE WHEN rn_gb = 1 THEN gb_basebi   ELSE 0 END) AS gb_basebi
     , SUM(CASE WHEN rn_gb = 1 THEN gb_basebi_2 ELSE 0 END) AS gb_basebi_2
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
    """Lee Diccionario.xlsx y genera loyalty_dict.json para el dashboard."""
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
SELECT Expiration_Date, country, tier, points_type_id,
       SUM(points) * -1 AS Points
FROM points a
LEFT JOIN categoria b ON a.account_id = b.account_id
GROUP BY Expiration_Date, Country, tier, points_type_id
ORDER BY 1,2,3,4
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
    "KIDDLEBR": "Brasil", "ENTREGOBR": "Brasil",
    "BONDAAR": "Argentina", "ICBCAR": "Argentina", "FOCOAR": "Argentina",
    "INVEXMX": "Mexico", "BBVAMX": "Mexico",
    "SUBS": "Argentina",
}
PARTNER_COUNTRY_CODE = {
    "IFOODBR": "BR", "C6BANKBR": "BR", "BRBBR": "BR", "KIDDLEBR": "BR", "ENTREGOBR": "BR",
    "BONDAAR": "AR", "ICBCAR": "AR", "FOCOAR": "AR",
    "INVEXMX": "MX", "BBVAMX": "MX",
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
PASAPORTE_D_REDEN = {"general"}   # point_type que el dashboard mapea a "Pasaporte D!"


def load_breakage_esperado() -> dict:
    """{(country_code, 'YYYY-MM'): factor_reconocido}  con factor = 1 − breakage_esperado."""
    path = Path(BREAKAGE_ESP_CSV)
    if not path.exists():
        print(f"  [SSP] {path.name} no existe → breakage esperado = 0 (factor 1) para todo")
        return {}
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    out = {}
    for _, r in df.iterrows():
        cc = str(r.get("country_code", "")).strip().upper()
        ym = str(r.get("month", "")).strip()[:7]
        be = pd.to_numeric(r.get("breakage_esperado"), errors="coerce")
        if not cc or len(ym) != 7 or pd.isna(be):
            continue
        out[(cc, ym)] = 1.0 - float(be)
    print(f"  [SSP] breakage esperado: {len(out)} celdas país×mes desde {path.name}")
    return out


def build_ssp_json(*reden_clean_dfs) -> bytes:
    frames = [d for d in reden_clean_dfs if d is not None and len(d)]
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
    for _, r in g.iterrows():
        dk = CC_TO_DATAKEY.get(str(r["country_code"]).strip().upper())
        if not dk:
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
    # El dashboard tomaba abs() por fila y luego sumaba — se preserva ese criterio
    # acá (sumar |valor| por fila) para que los totales no cambien al agregar.
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).abs()
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


def _get_drive_service():
    import json as _json
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    base       = Path(__file__).resolve().parent
    creds_file = base / "credentials_drive.json"
    token_file = base / "token_drive.json"

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


def upload_to_drive(json_bytes: bytes, filename: str):
    from googleapiclient.http import MediaInMemoryUpload
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

print("\n--- Acumulaciones CY ---")
df_acum_cy = aggregate_acum(clean_acum(fetch(build_acum_query(ACTUALS_DESDE, ACTUALS_HASTA), f"Acumulaciones {CY_YEAR}")))

print("\n--- Acumulaciones LY ---")
df_acum_ly = aggregate_acum(clean_acum(fetch(build_acum_query(LY_DESDE, LY_HASTA), f"Acumulaciones {LY_YEAR}")))

print("\n--- Redenciones CY ---")
_reden_cy_clean = clean_reden(fetch(build_reden_query(ACTUALS_DESDE, ACTUALS_HASTA), f"Redenciones {CY_YEAR}"))
df_reden_cy = aggregate_reden(_reden_cy_clean)

print("\n--- Redenciones LY ---")
_reden_ly_clean = clean_reden(fetch(build_reden_query(LY_DESDE, LY_HASTA), f"Redenciones {LY_YEAR}"))
df_reden_ly = aggregate_reden(_reden_ly_clean)

print("\n--- Breakage ---")
df_breakage = clean_breakage(fetch(build_breakage_query(LY_DESDE), "Breakage"))

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

print(f"  Acum {CY_YEAR}:  {len(acum_cy_bytes)//1024:.0f} KB  ({len(df_acum_cy):,} filas)")
print(f"  Acum {LY_YEAR}:  {len(acum_ly_bytes)//1024:.0f} KB  ({len(df_acum_ly):,} filas)")
print(f"  Reden {CY_YEAR}: {len(reden_cy_bytes)//1024:.0f} KB  ({len(df_reden_cy):,} filas)")
print(f"  Reden {LY_YEAR}: {len(reden_ly_bytes)//1024:.0f} KB  ({len(df_reden_ly):,} filas)")
print(f"  Breakage:       {len(breakage_bytes)//1024:.0f} KB  ({len(df_breakage):,} filas)")

print("\n--- Subiendo a Google Drive ---")
upload_to_drive(acum_cy_bytes,  ACUM_CY_FILE)
upload_to_drive(acum_ly_bytes,  ACUM_LY_FILE)
upload_to_drive(reden_cy_bytes, REDEN_CY_FILE)
upload_to_drive(reden_ly_bytes, REDEN_LY_FILE)
upload_to_drive(breakage_bytes, BREAKAGE_FILE)
upload_to_drive(dict_bytes,    DICT_FILE)
upload_to_drive(ssp_bytes,     SSP_FILE)

print(f"\nOK Completado: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
