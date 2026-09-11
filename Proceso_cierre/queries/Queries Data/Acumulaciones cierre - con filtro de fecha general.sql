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
     -- de las columnas (points, comision, fee, descuentos, pct_pagado_con_puntos,
     -- descuento_consumo_puntos_usd) queda igual que antes.
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
