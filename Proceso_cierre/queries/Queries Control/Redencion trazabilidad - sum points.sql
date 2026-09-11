WITH Redemption AS (
SELECT
    dsp_transaction_id,
    product,
    country_code,
    partner,
    SUM(points) points,
    point_type,
    business,
    transaction_code,
    country,
    produto_original,
    CASE
         WHEN channel IN ('viajes-falabella-presencial','viajes-falabella-corporate','vf-presencial-markup','bestday-islas','bestday-islas-markup','tiendas-b2c') THEN 'Sucursales'
         WHEN channel IN ('beneficios-despegar','site','site-smartphone','site-tablet','bestday-site','viajes-falabella-wl','viajes-falabella-viajaya','viajanet-passagens','viajanet-site', 'agencia-exoticca', 'phanton-brand','puntosbonus-pe') THEN 'Site'
         WHEN channel IN ('call-sales-b2c','call-sales-outbound','bestday-call','viajes-falabella-call','viajanet-televentas', 'videollamada-b2c','whatsapp-b2c') THEN 'Call Center'
         WHEN channel IN ('android-app','iphone-app','bestday-app','viajes-falabella-app','viajanet-app') THEN 'App'
         ELSE 'Site'
       END AS channel_condition,
    payment_type,
    produto_agrupado,
    transaction_type,
    ratio_prd,
    comision,
    fee,
    descuentos,
    gb_basebi,
    gb_basebi_2,
    country || ' ' || product || ' ' || business concatenado,
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
             qr1.transaction_type, qr1.ratio_prd, qr1.comision, qr1.fee,
             qr1.descuentos, qr1.gb_basebi, qr1.gb_basebi_2
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
        SELECT base.transaction_code,
               t_trn.ext_country        AS country_code,
               base.product_type        AS produto_agrupado,
               transaction_type, b.country,
               b.purchase_type          AS produto_original,
               b.channel, base.payment_type,
               CAST(t_prd.ext_ratio AS DECIMAL(18,4)) AS ratio_prd,
               CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                   WHEN base.product_type = 'Disney'                THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END AS product_type_qr1,
               SUM(CAST((commission+flight_over+flight_markup) AS DECIMAL(18,2))) AS comision,
               SUM(CAST((fee+flight_du) AS DECIMAL(18,2)))                        AS fee,
               SUM(CAST(discount AS DECIMAL(18,2))) * -1                          AS descuentos,
               SUM(CAST(total AS DECIMAL(18,2)))                                  AS gb_basebi,
               SUM(CAST(gross_booking AS DECIMAL(18,2)))                          AS gb_basebi_2
        FROM data.lake.clm_transactions t_trn
        JOIN data.lake.clm_customers t_cstm ON t_trn.account_id = t_cstm.account_id
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_products
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) base
               ON CAST(t_trn.ext_despegar_trn_id AS VARCHAR) = base.transaction_code
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_transactions
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) b
               ON base.transaction_code = b.transaction_code
        JOIN data.lake.clm_transaction_products t_prd
            ON t_trn.id = t_prd.transaction_id
           AND original_product_code = CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                   WHEN base.product_type = 'Disney'                THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_charges
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) c
               ON CAST(base.transaction_code AS VARCHAR)||base.product_id
                = CAST(c.transaction_code AS VARCHAR)||c.product_id
        WHERE t_trn.transaction_type = 'GR' AND t_trn.status = 'B'
        GROUP BY base.transaction_code, t_trn.ext_country,
                 base.product_type,
                 transaction_type, b.country, b.channel, base.payment_type,
                 b.purchase_type, t_prd.ext_ratio,
                 CASE
                     WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                     WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                     WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                     WHEN base.product_type = 'Universal'             THEN 'TICKET'
                     WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                     WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                     WHEN base.product_type = 'Disney'                THEN 'TICKET'
                     WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                     WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                     WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                     WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                     WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                     WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
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
            qr1.transaction_code, qr1.country AS country_code, qr1.produto_original,
            qr1.channel, qr1.payment_type, qr1.produto_agrupado,
            qr1.transaction_type, qr1.ratio_prd, qr1.comision, qr1.fee,
            qr1.descuentos, qr1.gb_basebi, qr1.gb_basebi_2
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
               t_trn.ext_country               AS country_code,
               base.product_type               AS produto_agrupado,
               transaction_type, b.country,
               b.purchase_type                 AS produto_original,
               b.channel, base.payment_type,
               CAST(t_prd.ext_ratio AS DECIMAL(18,4)) AS ratio_prd,
               CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                   WHEN base.product_type = 'Disney'                THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END AS product_type_qr1,
               SUM(CAST((commission+flight_over+flight_markup) AS DECIMAL(18,2))) AS comision,
               SUM(CAST((fee+flight_du) AS DECIMAL(18,2)))                        AS fee,
               SUM(CAST(discount AS DECIMAL(18,2))) * -1                          AS descuentos,
               SUM(CAST(total AS DECIMAL(18,2)))                                  AS gb_basebi,
               SUM(CAST(gross_booking AS DECIMAL(18,2)))                          AS gb_basebi_2
        FROM data.lake.clm_transactions t_trn
        JOIN data.lake.clm_customers t_cstm ON t_trn.account_id = t_cstm.account_id
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_products
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) base
               ON CAST(t_trn.ext_despegar_trn_id AS VARCHAR) = base.transaction_code
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_transactions
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) b
               ON base.transaction_code = b.transaction_code
        JOIN data.lake.clm_transaction_products t_prd
            ON t_trn.id = t_prd.transaction_id
           AND original_product_code = CASE
                   WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                   WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                   WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                   WHEN base.product_type = 'Universal'             THEN 'TICKET'
                   WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                   WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                   WHEN base.product_type = 'Disney'                THEN 'TICKET'
                   WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                   WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                   WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                   WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                   WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                   WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
                   WHEN base.product_type = 'Traslados'             THEN 'TRANSFER'
                   WHEN base.product_type = 'Valijas'               THEN 'ONA'
                   WHEN base.product_type = 'Autos'                 THEN 'CAR'
                   WHEN base.product_type = 'Asistencia al viajero' THEN 'INSURANCE'
                   WHEN base.product_type = 'Buses'                 THEN 'ONA'
                   ELSE 'N/D'
               END
        LEFT JOIN (SELECT * FROM data.analytics.bi_transactional_fact_charges
                   WHERE reservation_year_month > CAST('2024-01-01' AS DATE)) c
               ON CAST(base.transaction_code AS VARCHAR)||base.product_id
                = CAST(c.transaction_code AS VARCHAR)||c.product_id
        WHERE t_trn.transaction_type = 'GR' AND t_trn.status = 'B'
        GROUP BY base.transaction_code, t_trn.id, t_trn.ext_country,
                 base.product_type,
                 transaction_type, b.country, b.channel, base.payment_type,
                 b.purchase_type, t_prd.ext_ratio,
                 CASE
                     WHEN base.product_type = 'Seguros de Autos'      THEN 'INSURANCE'
                     WHEN base.product_type = 'Excursiones'           THEN 'TOUR'
                     WHEN base.product_type = 'Cruceros'              THEN 'ONA'
                     WHEN base.product_type = 'Universal'             THEN 'TICKET'
                     WHEN base.product_type = 'Alquileres'            THEN 'HOTEL'
                     WHEN base.product_type = 'SeaWorld'              THEN 'TICKET'
                     WHEN base.product_type = 'Disney'                THEN 'TICKET'
                     WHEN base.product_type = 'Circuito'              THEN 'TOUR'
                     WHEN base.product_type = 'Tickets'               THEN 'TICKET'
                     WHEN base.product_type = 'Vuelos'                THEN 'FLIGHT'
                     WHEN base.product_type = 'Busch Gardens'         THEN 'TICKET'
                     WHEN base.product_type = 'Hoteles'               THEN 'HOTEL'
                     WHEN base.product_type = 'EspectÃ¡culos'          THEN 'TOUR'
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
GROUP BY
    dsp_transaction_id, product, country_code, partner, point_type, business,
    transaction_code, country, produto_original, channel, payment_type,
    produto_agrupado, transaction_type, ratio_prd, comision, fee,
    descuentos, gb_basebi, gb_basebi_2
),

tipopunto_raw AS (

    -- Rama original — FIX 1: CAST a VARCHAR para compatibilidad con UNION ALL
    SELECT
        CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id,
        pt.code                                AS point_code,
        CAST(t.processing_date AS DATE)        AS processing_date,
        SUM(-tp.points)                        AS puntosv2
    FROM data.lake.clm_transactions t
    JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
    JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
    WHERE t.processing_date >= {{Desde}}
      AND t.processing_date < {{Hasta}}
      AND t.status = 'B'
      AND (
            t.transaction_type = 'GR'
         OR (t.transaction_type = 'GA' AND t.ext_despegar_trn_type = 'REFUND')
          )
    GROUP BY t.ext_despegar_trn_id, pt.code, CAST(t.processing_date AS DATE)

    UNION ALL

    -- Nueva rama — contrapartida non-refundable canceladas
    SELECT
        tp_orig.transaction_id,
        tp_orig.point_code,
        tp_orig.processing_date,
        -SUM(tp_orig.puntosv2) AS puntosv2
    FROM (
        SELECT
            CAST(t.ext_despegar_trn_id AS VARCHAR) AS transaction_id,
            pt.code                                AS point_code,
            CAST(t.processing_date AS DATE)        AS processing_date,
            SUM(-tp.points)                        AS puntosv2
        FROM data.lake.clm_transactions t
        JOIN data.lake.clm_transaction_points tp ON t.id = tp.source_transaction_id
        JOIN data.lake.clm_point_types pt        ON tp.points_type_id = pt.id
        WHERE t.processing_date >= {{Desde}}
          AND t.processing_date < {{Hasta}}
          AND t.status = 'B'
          AND t.transaction_type = 'GR'
          AND pt.code IN (
              'FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO',
              'IFOOD_WEL','IFOOD_2W','IFOOD_RWB','IF_MISSION',
              'IF_CAMPAI','PONTOSBR','MISSIONS','IFO_WE_CLU'
          )
        GROUP BY t.ext_despegar_trn_id, pt.code, CAST(t.processing_date AS DATE)
    ) tp_orig
    INNER JOIN (
        -- ✅ FIX v6: detecta canceladas donde NO se reembolsó ningún tipo non-refundable en Comarch
        -- Cubre tanto points=0 como devolución parcial de puntos 'general'
        SELECT DISTINCT CAST(ar.dsp_transaction_id AS VARCHAR) AS dsp_transaction_id
        FROM data.lake.comarch_accumulation_report ar
        WHERE ar.processing_date >= {{Desde}}
          AND ar.processing_date < {{Hasta}}
          AND COALESCE(ar.dsp_transaction_type, 'Nulo') = 'REFUND'
          AND NOT EXISTS (
            SELECT 1
            FROM data.lake.comarch_accumulation_report ar2
            WHERE ar2.dsp_transaction_id = ar.dsp_transaction_id
              AND ar2.processing_date >= {{Desde}}
              AND ar2.processing_date < {{Hasta}}
              AND COALESCE(ar2.dsp_transaction_type, 'Nulo') = 'REFUND'
              AND COALESCE(ar2.point_type, '') IN (
                  'FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO','IFOOD_WEL',
                  'IFOOD_2W','IFOOD_RWB','IF_MISSION','IF_CAMPAI','PONTOSBR',
                  'MISSIONS','IFO_WE_CLU'
              )
              AND COALESCE(ar2.points, 0) > 0
          )
          -- ▼ FIX: excluir si CLM ya emitió GA REFUND para este tipo de punto
          --        (la Rama 1 ya lo cubre → evita doble negativo)
          AND NOT EXISTS (
              SELECT 1
              FROM data.lake.clm_transactions t_ga
              JOIN data.lake.clm_transaction_points tp_ga
                ON t_ga.id = tp_ga.source_transaction_id
              JOIN data.lake.clm_point_types pt_ga
                ON tp_ga.points_type_id = pt_ga.id
              WHERE CAST(t_ga.ext_despegar_trn_id AS VARCHAR) = CAST(ar.dsp_transaction_id AS VARCHAR)
                AND t_ga.transaction_type      = 'GA'
                AND t_ga.ext_despegar_trn_type = 'REFUND'
                AND t_ga.status                = 'B'
                AND t_ga.processing_date >= {{Desde}}
                AND t_ga.processing_date <  {{Hasta}}
                AND pt_ga.code IN (
                    'FORTUNE','IFOOD_BR','IFOOD_WELCOME','IFOOD_PROMO','IFOOD_WEL',
                    'IFOOD_2W','IFOOD_RWB','IF_MISSION','IF_CAMPAI','PONTOSBR',
                    'MISSIONS','IFO_WE_CLU'
                )
          )
          -- ▲ FIN FIX
    ) ar_ref ON tp_orig.transaction_id = ar_ref.dsp_transaction_id
    GROUP BY tp_orig.transaction_id, tp_orig.point_code, tp_orig.processing_date
),

-- FIX: colapsar tipopunto_raw a UNA fila por (transaction_id, point_code).
-- Antes, cuando existian 2+ filas (rama original + contrapartida, o GR + GA REFUND-0)
-- para la misma transaccion+tipo de punto, el LEFT JOIN posterior (solo por transaction_id)
-- multiplicaba cada producto del carrito una vez por cada fila, y el SUM(gb_basebi) OVER(...)
-- sumaba el mismo gb_basebi N veces, diluyendo peso_producto a 1/N.
tipopunto AS (
    SELECT
        transaction_id,
        point_code,
        MAX(processing_date) AS processing_date,
        SUM(puntosv2)        AS puntosv2
    FROM tipopunto_raw
    GROUP BY transaction_id, point_code
),

final_base AS (
    SELECT
        cc.processing_date,
        a.dsp_transaction_id,
        a.product,
        a.country_code,
        a.partner,
        cc.puntosv2          AS points,
        cc.point_code,
        CASE
            WHEN cc.point_code = 'FORTUNE'    THEN 'FORTUNE'
            WHEN cc.point_code = 'GAMI'       THEN 'Puntos R&B'
            WHEN cc.point_code = 'R&B'        THEN 'Puntos R&B'
            WHEN cc.point_code = 'SUBS'       THEN 'SUBSCRIPTION'
            WHEN cc.point_code = 'SUBS_INT'   THEN 'SUBSCRIPTION_INT'
            WHEN cc.point_code = 'IFOOD_BR'   THEN 'IFOOD_BR'
            WHEN cc.point_code = 'IFOOD_WEL'  THEN 'IFOOD_WEL'
            WHEN cc.point_code = 'IFOOD_2W'   THEN 'IFOOD_2W'
            WHEN cc.point_code = 'IFOOD_PR'   THEN 'IFOOD_PR'
            WHEN cc.point_code = 'IFOOD_1M'   THEN 'IFOOD_1M'
            WHEN cc.point_code = 'PONTOSBR'   THEN 'PONTOSBR'
            WHEN cc.point_code = 'IFO_WE_CLU' THEN 'IFO_WE_CLU'
            ELSE 'general'
        END                  AS point_type,
        a.business,
        a.transaction_code,
        a.country,
        a.produto_original,
        a.channel_condition,
        a.payment_type,
        a.produto_agrupado,
        a.transaction_type,
        a.ratio_prd,
        a.comision,
        a.fee,
        a.descuentos,
        a.gb_basebi,
        a.gb_basebi_2,
        a.concatenado,
        a.legal_entity,
        ex.exchange_currency AS moneda_local,
        ex.exchange_rate     AS cotizacion_usd
    FROM redemption a
    LEFT JOIN tipopunto cc ON CAST(a.dsp_transaction_id AS VARCHAR) = cc.transaction_id
    LEFT JOIN data.analytics.bi_common_dim_exchange_rates ex
           ON ex.exchange_date = cc.processing_date
          AND ex.exchange_currency = CASE
                  WHEN a.country_code = 'AR' THEN 'ARS'
                  WHEN a.country_code = 'BR' THEN 'BRL'
                  WHEN a.country_code = 'CL' THEN 'CLP'
                  WHEN a.country_code = 'CO' THEN 'COP'
                  WHEN a.country_code = 'MX' THEN 'MXN'
                  WHEN a.country_code = 'PE' THEN 'PEN'
                  WHEN a.country_code = 'UY' THEN 'UYU'
                  WHEN a.country_code = 'EC' THEN 'USD'
                  WHEN a.country_code = 'US' THEN 'USD'
                  ELSE NULL
              END
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26
),

proration AS (
    SELECT
        *,
        SUM(gb_basebi) OVER (PARTITION BY dsp_transaction_id, point_code)
            AS gb_total_carrito,
        CAST(
            gb_basebi / NULLIF(SUM(gb_basebi) OVER (PARTITION BY dsp_transaction_id, point_code), 0)
            AS DECIMAL(10,6))
            AS peso_producto,
        CAST(
            points * gb_basebi / NULLIF(SUM(gb_basebi) OVER (PARTITION BY dsp_transaction_id, point_code), 0)
            AS DECIMAL(18,2))
            AS points_distribuidos
    FROM final_base
)

-- CONTROL: sumatoria total de puntos
SELECT
    SUM(points)              AS total_points_raw,
    SUM(points_distribuidos) AS total_points_distribuidos
FROM proration